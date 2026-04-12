import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DIRECT_SEARCH_DEBOUNCE_MS, DirectSearchScheduler } from './directSearchScheduler';

describe('DirectSearchScheduler', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('debounces requests and only executes the newest query', () => {
    const scheduler = new DirectSearchScheduler(DIRECT_SEARCH_DEBOUNCE_MS);
    const runs: string[] = [];

    const first = scheduler.schedule('a', ({ query }) => {
      runs.push(query);
    });
    vi.advanceTimersByTime(DIRECT_SEARCH_DEBOUNCE_MS / 2);

    const second = scheduler.schedule('ab', ({ query }) => {
      runs.push(query);
    });

    expect(first.signal.aborted).toBe(true);
    expect(second.signal.aborted).toBe(false);

    vi.advanceTimersByTime(DIRECT_SEARCH_DEBOUNCE_MS - 1);
    expect(runs).toEqual([]);

    vi.advanceTimersByTime(1);
    expect(runs).toEqual(['ab']);
    expect(scheduler.isLatest(second.token)).toBe(true);
    expect(scheduler.isLatest(first.token)).toBe(false);
  });

  it('supports immediate execution for empty-query inbox restore', () => {
    const scheduler = new DirectSearchScheduler(DIRECT_SEARCH_DEBOUNCE_MS);
    const runs: string[] = [];

    const first = scheduler.schedule('query', ({ query }) => {
      runs.push(query);
    });
    const second = scheduler.schedule(
      '',
      ({ query }) => {
        runs.push(query);
      },
      { immediate: true },
    );

    expect(first.signal.aborted).toBe(true);
    expect(second.signal.aborted).toBe(false);
    expect(runs).toEqual(['']);
  });

  it('cancels scheduled jobs and prevents execution after cancelPending', () => {
    const scheduler = new DirectSearchScheduler(DIRECT_SEARCH_DEBOUNCE_MS);
    const runs: string[] = [];

    const job = scheduler.schedule('will-not-run', ({ query }) => {
      runs.push(query);
    });
    scheduler.cancelPending();

    expect(job.signal.aborted).toBe(true);
    vi.advanceTimersByTime(DIRECT_SEARCH_DEBOUNCE_MS);
    expect(runs).toEqual([]);
  });
});
