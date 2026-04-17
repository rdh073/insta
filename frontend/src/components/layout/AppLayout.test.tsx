import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { Account, PostJob } from '../../types';
import { runStartupHydration, type StartupHydratorDeps } from './startup-hydrate';

function sampleAccount(id: string): Account {
  return { id, username: `user_${id}`, status: 'active' };
}

function sampleJob(id: string): PostJob {
  return {
    id,
    caption: 'x',
    mediaUrls: [],
    mediaType: 'photo',
    targets: [],
    status: 'pending',
    results: [],
    createdAt: new Date().toISOString(),
  };
}

function makeCanceledError(): ApiError {
  return new ApiError('Request was cancelled.', 0, undefined, undefined, 'ERR_CANCELED');
}

function createHarness(overrides: Partial<StartupHydratorDeps> = {}): {
  deps: StartupHydratorDeps;
  controller: AbortController;
  sessionStore: Map<string, string>;
  state: {
    accounts: Account[];
    jobs: PostJob[];
    syncingEvents: boolean[];
  };
  warnings: unknown[][];
} {
  const controller = new AbortController();
  const sessionStore = new Map<string, string>();
  const state = { accounts: [] as Account[], jobs: [] as PostJob[], syncingEvents: [] as boolean[] };
  const warnings: unknown[][] = [];

  const deps: StartupHydratorDeps = {
    signal: controller.signal,
    listAccounts: vi.fn(async () => [sampleAccount('a1'), sampleAccount('a2'), sampleAccount('a3')]),
    listPosts: vi.fn(async () => [sampleJob('j1')]),
    bulkHydrateProfiles: vi.fn(async () => ({ queued: 3 })),
    waitForBackend: vi.fn(async () => true),
    setAccounts: (accounts) => {
      state.accounts = accounts;
    },
    setJobs: (jobs) => {
      state.jobs = jobs;
    },
    isStoreEmpty: () => state.accounts.length === 0 && state.jobs.length === 0,
    isCleanupFired: () => false,
    sessionStore: {
      getItem: (key) => sessionStore.get(key) ?? null,
      setItem: (key, value) => {
        sessionStore.set(key, value);
      },
      removeItem: (key) => {
        sessionStore.delete(key);
      },
    },
    sessionKey: 'insta_bulk_hydrated:test',
    commit: (update) => update(),
    setSyncing: (syncing) => state.syncingEvents.push(syncing),
    resetStores: true,
    backendUrlLabel: '(test)',
    retryDelayMs: 0,
    scheduleRetry: (cb) => cb(),
    logger: {
      warn: (...args: unknown[]) => {
        warnings.push(args);
      },
    },
    ...overrides,
  };

  return { deps, controller, sessionStore, state, warnings };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('runStartupHydration', () => {
  it('populates accounts and jobs stores on successful fetch', async () => {
    const { deps, state, sessionStore } = createHarness();

    const outcome = await runStartupHydration(deps);

    expect(outcome.backendReady).toBe(true);
    expect(outcome.accountsLoaded).toBe(true);
    expect(outcome.jobsLoaded).toBe(true);
    expect(outcome.retried).toBe(false);
    expect(outcome.aborted).toBe(false);
    expect(state.accounts).toHaveLength(3);
    expect(state.jobs).toHaveLength(1);
    expect(sessionStore.get('insta_bulk_hydrated:test')).toBeDefined();
    expect(state.syncingEvents).toEqual([true, false]);
  });

  it('resets stores before hydrating when resetStores is true', async () => {
    const { deps, state } = createHarness({ resetStores: true });
    state.accounts = [sampleAccount('stale')];
    state.jobs = [sampleJob('stale')];

    await runStartupHydration(deps);

    expect(state.accounts.map((a) => a.id)).toEqual(['a1', 'a2', 'a3']);
    expect(state.jobs.map((j) => j.id)).toEqual(['j1']);
  });

  it('retries once and populates the store when the first list request aborts mid-flight', async () => {
    const listAccounts = vi
      .fn<(signal: AbortSignal) => Promise<Account[]>>()
      .mockRejectedValueOnce(makeCanceledError())
      .mockResolvedValueOnce([sampleAccount('a1'), sampleAccount('a2'), sampleAccount('a3')]);
    const listPosts = vi
      .fn<(signal: AbortSignal) => Promise<PostJob[]>>()
      .mockRejectedValueOnce(makeCanceledError())
      .mockResolvedValueOnce([sampleJob('j1')]);

    const { deps, state } = createHarness({ listAccounts, listPosts });

    const outcome = await runStartupHydration(deps);

    expect(listAccounts).toHaveBeenCalledTimes(2);
    expect(listPosts).toHaveBeenCalledTimes(2);
    expect(outcome.retried).toBe(true);
    expect(outcome.accountsLoaded).toBe(true);
    expect(outcome.jobsLoaded).toBe(true);
    expect(outcome.aborted).toBe(false);
    expect(state.accounts).toHaveLength(3);
    expect(state.jobs).toHaveLength(1);
  });

  it('does not retry when cleanup already fired (StrictMode double-invoke hand-off)', async () => {
    let cleanupFired = false;
    const listAccounts = vi.fn(async () => {
      cleanupFired = true;
      throw makeCanceledError();
    });
    const listPosts = vi.fn(async () => {
      throw makeCanceledError();
    });

    const { deps, state } = createHarness({
      listAccounts,
      listPosts,
      isCleanupFired: () => cleanupFired,
    });

    const outcome = await runStartupHydration(deps);

    expect(listAccounts).toHaveBeenCalledTimes(1);
    expect(listPosts).toHaveBeenCalledTimes(1);
    expect(outcome.retried).toBe(false);
    expect(outcome.aborted).toBe(true);
    expect(state.accounts).toHaveLength(0);
    expect(state.jobs).toHaveLength(0);
  });

  it('does not retry when the store was already populated on first attempt', async () => {
    const listAccounts = vi
      .fn<(signal: AbortSignal) => Promise<Account[]>>()
      .mockResolvedValueOnce([sampleAccount('a1')]);
    const listPosts = vi
      .fn<(signal: AbortSignal) => Promise<PostJob[]>>()
      .mockRejectedValueOnce(makeCanceledError());

    const { deps } = createHarness({ listAccounts, listPosts });

    const outcome = await runStartupHydration(deps);

    expect(listAccounts).toHaveBeenCalledTimes(1);
    expect(listPosts).toHaveBeenCalledTimes(1);
    expect(outcome.retried).toBe(false);
  });

  it('skips bulk hydrate if the session key is already set', async () => {
    const bulkHydrate = vi.fn(async () => ({ queued: 0 }));
    const { deps, sessionStore } = createHarness({ bulkHydrateProfiles: bulkHydrate });
    sessionStore.set('insta_bulk_hydrated:test', '1');

    await runStartupHydration(deps);

    expect(bulkHydrate).not.toHaveBeenCalled();
  });

  it('classifies unauthorized failure and clears the bulk hydrate session key', async () => {
    const listAccounts = vi
      .fn<(signal: AbortSignal) => Promise<Account[]>>()
      .mockRejectedValueOnce(new ApiError('Invalid token', 401, 'unauthorized', 'auth'));
    const { deps, sessionStore, warnings } = createHarness({ listAccounts });
    sessionStore.set('insta_bulk_hydrated:test', 'stale');

    const outcome = await runStartupHydration(deps);

    expect(outcome.accountsLoaded).toBe(false);
    expect(sessionStore.has('insta_bulk_hydrated:test')).toBe(false);
    expect(warnings.some((entry) => {
      const payload = entry[1];
      return (
        typeof payload === 'object' &&
        payload !== null &&
        (payload as { outcome?: string }).outcome === 'unauthorized'
      );
    })).toBe(true);
  });

  it('returns aborted and keeps store empty when backend is never ready', async () => {
    const { deps, state } = createHarness({ waitForBackend: vi.fn(async () => false) });

    const outcome = await runStartupHydration(deps);

    expect(outcome.backendReady).toBe(false);
    expect(state.accounts).toHaveLength(0);
    expect(state.jobs).toHaveLength(0);
  });
});
