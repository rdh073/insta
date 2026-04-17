import { isApiCanceledError } from '../../api/client';
import {
  classifyStartupHydrationFailure,
  getHydrationErrorStatus,
} from '../../lib/startup-hydration';
import type { Account, PostJob } from '../../types';

export interface StartupHydratorDeps {
  signal: AbortSignal;
  listAccounts: (signal: AbortSignal) => Promise<Account[]>;
  listPosts: (signal: AbortSignal) => Promise<PostJob[]>;
  bulkHydrateProfiles: (signal: AbortSignal) => Promise<unknown>;
  waitForBackend: (signal: AbortSignal) => Promise<boolean>;
  setAccounts: (accounts: Account[]) => void;
  setJobs: (jobs: PostJob[]) => void;
  isStoreEmpty: () => boolean;
  /** True when React effect cleanup has already fired (component teardown / deps change). */
  isCleanupFired: () => boolean;
  sessionStore: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
  sessionKey: string;
  /** Optional transform around store mutations (e.g. React startTransition). */
  commit: (update: () => void) => void;
  /** Toggles the "Syncing" header chip. */
  setSyncing: (syncing: boolean) => void;
  /** When true, clear stores before hydrating (first load / backend URL switch). */
  resetStores: boolean;
  backendUrlLabel: string;
  /** Short pause before retrying after a mid-flight abort. Defaults to 50ms. */
  retryDelayMs?: number;
  /** Injectable timer so tests can drive the retry without real delays. */
  scheduleRetry?: (cb: () => void, delayMs: number) => void;
  logger?: Pick<Console, 'warn'>;
}

export interface StartupHydrationOutcome {
  backendReady: boolean;
  accountsLoaded: boolean;
  jobsLoaded: boolean;
  retried: boolean;
  aborted: boolean;
}

const DEFAULT_RETRY_DELAY_MS = 50;

function defaultScheduleRetry(cb: () => void, delayMs: number): void {
  setTimeout(cb, delayMs);
}

/**
 * Orchestrates the one-shot startup hydration of the account + post stores.
 *
 * Threads `signal` through every network call so React effect cleanup can
 * abort in-flight requests cleanly. If a list request is cancelled mid-flight
 * *while the effect is still active* (cleanup has not yet fired), and the
 * store ends up empty, the hydrator fires a single retry against a fresh
 * request batch. This guards against the Proxy page regression where an
 * opaque `net::ERR_ABORTED` on `/api/accounts` left the store empty with no
 * surface-level retry, visible as TRACKED=0 until full reload.
 */
export async function runStartupHydration(deps: StartupHydratorDeps): Promise<StartupHydrationOutcome> {
  const outcome: StartupHydrationOutcome = {
    backendReady: false,
    accountsLoaded: false,
    jobsLoaded: false,
    retried: false,
    aborted: false,
  };
  const logger = deps.logger ?? console;

  const isAborted = () => deps.signal.aborted || deps.isCleanupFired();

  if (deps.resetStores) {
    deps.commit(() => {
      deps.setAccounts([]);
      deps.setJobs([]);
    });
  }
  deps.setSyncing(true);

  try {
    const ready = await deps.waitForBackend(deps.signal);
    if (isAborted()) {
      outcome.aborted = true;
      return outcome;
    }
    outcome.backendReady = ready;
    if (!ready) {
      logger.warn('[startup-hydration]', {
        outcome: 'backend_unavailable',
        backendUrl: deps.backendUrlLabel,
      });
      return outcome;
    }

    const [accountsLoaded, jobsLoaded, retried] = await hydrateLists(deps, outcome);
    outcome.accountsLoaded = accountsLoaded;
    outcome.jobsLoaded = jobsLoaded;
    outcome.retried = retried;
    if (isAborted()) {
      outcome.aborted = true;
      return outcome;
    }

    if (!accountsLoaded && !jobsLoaded) {
      // Both lists failed for non-cancel reasons — caller's earlier logging has it.
      return outcome;
    }

    if (!accountsLoaded) {
      // Already logged in hydrateLists via partial_failure.
      return outcome;
    }

    if (!deps.sessionStore.getItem(deps.sessionKey)) {
      try {
        await deps.bulkHydrateProfiles(deps.signal);
        deps.sessionStore.setItem(deps.sessionKey, Date.now().toString());
      } catch (error) {
        if (isApiCanceledError(error) || isAborted()) {
          outcome.aborted = true;
          return outcome;
        }
        const bulkFailure = classifyStartupHydrationFailure({
          backendReady: true,
          failures: [error],
        });
        if (bulkFailure) {
          logger.warn('[startup-hydration]', {
            outcome: bulkFailure,
            phase: 'bulk_hydrate_profiles',
            backendUrl: deps.backendUrlLabel,
            statusCodes: [getHydrationErrorStatus(error)].filter(
              (code): code is number => code !== null,
            ),
          });
        }
      }
    }

    return outcome;
  } finally {
    if (!isAborted()) {
      deps.setSyncing(false);
    }
  }
}

async function hydrateLists(
  deps: StartupHydratorDeps,
  outcome: StartupHydrationOutcome,
  attempt: number = 0,
): Promise<[boolean, boolean, boolean]> {
  const logger = deps.logger ?? console;
  const retryDelayMs = deps.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS;
  const scheduleRetry = deps.scheduleRetry ?? defaultScheduleRetry;

  const isAborted = () => deps.signal.aborted || deps.isCleanupFired();

  const [accountsResult, jobsResult] = await Promise.allSettled([
    deps.listAccounts(deps.signal),
    deps.listPosts(deps.signal),
  ]);

  if (isAborted()) {
    // Cleanup fired (or outer signal tripped) — let the next effect invocation
    // handle rehydration. No retry here to avoid racing with a fresh mount.
    return [false, false, attempt > 0];
  }

  const allFailures: unknown[] = [];
  if (accountsResult.status === 'rejected') allFailures.push(accountsResult.reason);
  if (jobsResult.status === 'rejected') allFailures.push(jobsResult.reason);

  const canceledFailures = allFailures.filter(isApiCanceledError);
  const nonCanceledFailures = allFailures.filter((f) => !isApiCanceledError(f));

  deps.commit(() => {
    if (accountsResult.status === 'fulfilled') deps.setAccounts(accountsResult.value);
    if (jobsResult.status === 'fulfilled') deps.setJobs(jobsResult.value);
  });

  const accountsLoaded = accountsResult.status === 'fulfilled';
  const jobsLoaded = jobsResult.status === 'fulfilled';

  // Abort-tolerant retry — triggered only when:
  //   1) at least one list was cancelled mid-flight,
  //   2) the effect is still active (no cleanup yet),
  //   3) the store is still empty after this attempt,
  //   4) we haven't retried yet (bounded to one retry).
  // Rationale: see module docstring. This prevents the Proxy page regression
  // where a first-visit `net::ERR_ABORTED` leaves the store silently empty.
  if (
    attempt === 0 &&
    canceledFailures.length > 0 &&
    !isAborted() &&
    deps.isStoreEmpty()
  ) {
    logger.warn('[startup-hydration]', {
      outcome: 'aborted_retry',
      backendUrl: deps.backendUrlLabel,
    });
    await new Promise<void>((resolve) => scheduleRetry(resolve, retryDelayMs));
    if (isAborted()) {
      outcome.aborted = true;
      return [accountsLoaded, jobsLoaded, true];
    }
    const [retriedAccountsLoaded, retriedJobsLoaded] = await hydrateLists(
      deps,
      outcome,
      attempt + 1,
    );
    return [
      accountsLoaded || retriedAccountsLoaded,
      jobsLoaded || retriedJobsLoaded,
      true,
    ];
  }

  // Surface any non-cancel failures for telemetry parity with pre-refactor code.
  const failure = classifyStartupHydrationFailure({
    backendReady: true,
    failures: nonCanceledFailures,
  });
  if (failure) {
    const statusCodes = nonCanceledFailures
      .map(getHydrationErrorStatus)
      .filter((code): code is number => code !== null);
    logger.warn('[startup-hydration]', {
      outcome: failure,
      backendUrl: deps.backendUrlLabel,
      statusCodes,
    });
    if (failure === 'unauthorized') {
      deps.sessionStore.removeItem(deps.sessionKey);
    }
  }

  return [accountsLoaded, jobsLoaded, attempt > 0];
}
