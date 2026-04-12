export interface SingleFlightRunOptions {
  cancelPrevious?: boolean;
  skipIfInFlight?: boolean;
}

export type SingleFlightRunResult<T> =
  | { kind: 'success'; value: T }
  | { kind: 'skipped' }
  | { kind: 'aborted' }
  | { kind: 'error'; error: unknown };

function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true;
  }
  if (!error || typeof error !== 'object') {
    return false;
  }
  const maybeError = error as { name?: unknown; code?: unknown; transportCode?: unknown };
  return (
    maybeError.name === 'AbortError' ||
    maybeError.code === 'ERR_CANCELED' ||
    maybeError.transportCode === 'ERR_CANCELED'
  );
}

export class SingleFlightRequestRunner {
  private activeController: AbortController | null = null;
  private activeRequestId = 0;
  private inFlight = false;

  isInFlight(): boolean {
    return this.inFlight;
  }

  abortCurrent(): void {
    this.activeController?.abort();
  }

  async run<T>(
    task: (signal: AbortSignal) => Promise<T>,
    options: SingleFlightRunOptions = {}
  ): Promise<SingleFlightRunResult<T>> {
    const { cancelPrevious = false, skipIfInFlight = false } = options;

    if (this.inFlight) {
      if (cancelPrevious) {
        this.abortCurrent();
      } else if (skipIfInFlight) {
        return { kind: 'skipped' };
      }
    }

    const controller = new AbortController();
    const requestId = this.activeRequestId + 1;
    this.activeRequestId = requestId;
    this.activeController = controller;
    this.inFlight = true;

    try {
      const value = await task(controller.signal);
      if (controller.signal.aborted || requestId !== this.activeRequestId) {
        return { kind: 'aborted' };
      }
      return { kind: 'success', value };
    } catch (error) {
      if (controller.signal.aborted || requestId !== this.activeRequestId || isAbortLikeError(error)) {
        return { kind: 'aborted' };
      }
      return { kind: 'error', error };
    } finally {
      if (requestId === this.activeRequestId) {
        this.inFlight = false;
        if (this.activeController === controller) {
          this.activeController = null;
        }
      }
    }
  }
}

export function getPollBackoffDelay(baseMs: number, consecutiveFailures: number, maxMs = 60_000): number {
  if (consecutiveFailures <= 0) {
    return baseMs;
  }
  const cappedFailures = Math.min(consecutiveFailures, 6);
  const delay = baseMs * 2 ** cappedFailures;
  return Math.min(maxMs, delay);
}
