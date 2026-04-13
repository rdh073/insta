import { describe, expect, it } from 'vitest';
import { getPollBackoffDelay, SingleFlightRequestRunner } from './single-flight';

describe('SingleFlightRequestRunner', () => {
  it('skips overlapping requests when skipIfInFlight is enabled', async () => {
    const runner = new SingleFlightRequestRunner();
    const ref: { release: (() => void) | null } = { release: null };

    const first = runner.run(
      () =>
        new Promise<string>((resolve) => {
          ref.release = () => resolve('first');
        }),
    );

    const second = await runner.run(async () => 'second', { skipIfInFlight: true });
    expect(second).toEqual({ kind: 'skipped' });
    expect(runner.isInFlight()).toBe(true);

    ref.release?.();
    await expect(first).resolves.toEqual({ kind: 'success', value: 'first' });
    expect(runner.isInFlight()).toBe(false);
  });

  it('aborts stale request and keeps only latest result when cancelPrevious is enabled', async () => {
    const runner = new SingleFlightRequestRunner();
    const ref: {
      resolve: ((value: string) => void) | null;
      signal: AbortSignal | null;
    } = { resolve: null, signal: null };

    const first = runner.run(
      (signal) =>
        new Promise<string>((resolve) => {
          ref.signal = signal;
          ref.resolve = resolve;
        }),
    );

    const second = runner.run(async () => 'second', { cancelPrevious: true });
    ref.resolve?.('first');

    await expect(first).resolves.toEqual({ kind: 'aborted' });
    await expect(second).resolves.toEqual({ kind: 'success', value: 'second' });
    expect(ref.signal?.aborted).toBe(true);
  });
});

describe('getPollBackoffDelay', () => {
  it('returns exponential delay and caps at max', () => {
    expect(getPollBackoffDelay(5_000, 0)).toBe(5_000);
    expect(getPollBackoffDelay(5_000, 1)).toBe(10_000);
    expect(getPollBackoffDelay(5_000, 2)).toBe(20_000);
    expect(getPollBackoffDelay(5_000, 5)).toBe(60_000);
    expect(getPollBackoffDelay(5_000, 6)).toBe(60_000);
    expect(getPollBackoffDelay(2_000, 6, 10_000)).toBe(10_000);
  });
});
