export interface DirectSearchJob {
  token: number;
  query: string;
  signal: AbortSignal;
}

export const DIRECT_SEARCH_DEBOUNCE_MS = 250;

export class DirectSearchScheduler {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private controller: AbortController | null = null;
  private latestToken = 0;
  private readonly debounceMs: number;

  constructor(debounceMs: number) {
    this.debounceMs = debounceMs;
  }

  schedule(
    query: string,
    onRun: (job: DirectSearchJob) => void,
    options?: { immediate?: boolean },
  ): DirectSearchJob {
    this.cancelPending();

    const controller = new AbortController();
    const job: DirectSearchJob = {
      token: ++this.latestToken,
      query,
      signal: controller.signal,
    };
    this.controller = controller;

    const run = () => {
      this.timer = null;
      onRun(job);
    };

    if (options?.immediate) {
      run();
    } else {
      this.timer = setTimeout(run, this.debounceMs);
    }

    return job;
  }

  cancelPending(): void {
    if (this.timer != null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.controller != null) {
      this.controller.abort();
      this.controller = null;
    }
  }

  isLatest(token: number): boolean {
    return token === this.latestToken;
  }
}
