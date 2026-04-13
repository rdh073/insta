import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { postsApi } from './posts';
import { useSettingsStore } from '../store/settings';
import type { PostJob } from '../types';

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly listeners = new Map<string, Set<EventListener>>();
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener): void {
    const existing = this.listeners.get(type) ?? new Set<EventListener>();
    existing.add(listener);
    this.listeners.set(type, existing);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  emitMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }

  emitNamed(type: string, payload: unknown): void {
    const event = { data: JSON.stringify(payload) } as MessageEvent<string>;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

function buildPostJob(jobId: string): PostJob {
  return {
    id: jobId,
    caption: 'hello',
    mediaUrls: [],
    mediaType: 'photo',
    targets: [],
    status: 'pending',
    results: [],
    createdAt: '2026-04-13T00:00:00Z',
  };
}

describe('postsApi.streamJobs named run_error handling', () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    useSettingsStore.setState({
      backendUrl: 'http://127.0.0.1:8000',
      backendApiKey: '',
    });
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('handles named run_error SSE events with structured payloads', async () => {
    const onUpdate = vi.fn();
    const onRunError = vi.fn();

    const cleanup = await postsApi.streamJobs(onUpdate, undefined, onRunError);
    const source = FakeEventSource.instances[0];

    source.emitMessage([buildPostJob('job-1')]);
    source.emitNamed('run_error', {
      type: 'run_error',
      code: 'stream_error',
      message: 'Stream transport failed',
    });

    expect(onUpdate).toHaveBeenCalledTimes(1);
    expect(onRunError).toHaveBeenCalledWith({
      type: 'run_error',
      code: 'stream_error',
      message: 'Stream transport failed',
    });

    cleanup();
    expect(source.closed).toBe(true);
  });

  it('also handles run_error payloads on the default data channel', async () => {
    const onUpdate = vi.fn();
    const onRunError = vi.fn();

    await postsApi.streamJobs(onUpdate, undefined, onRunError);
    const source = FakeEventSource.instances[0];

    source.emitMessage({
      type: 'run_error',
      code: 'stream_error',
      message: 'Fallback data channel error',
    });

    expect(onUpdate).not.toHaveBeenCalled();
    expect(onRunError).toHaveBeenCalledWith({
      type: 'run_error',
      code: 'stream_error',
      message: 'Fallback data channel error',
    });
  });
});
