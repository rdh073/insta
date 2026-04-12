import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { commandJsonRunner } from './command-json-runner';
import { graphRunner } from './graph-runner';
import type { CopilotEvent } from './operator-copilot';
import { useSettingsStore } from '../store/settings';

async function collectEvents(stream: ReadableStream<CopilotEvent>): Promise<CopilotEvent[]> {
  const reader = stream.getReader();
  const events: CopilotEvent[] = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      events.push(value);
    }
    return events;
  } finally {
    reader.releaseLock();
  }
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('command transport contracts', () => {
  beforeEach(() => {
    useSettingsStore.setState({ backendApiKey: '' });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('maps /engage run JSON interrupt into approval flow events', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      mode: 'execute',
      status: 'interrupted',
      thread_id: 'thread-engage-run',
      interrupted: true,
      outcome_reason: 'Awaiting operator decision',
      recommendation: {
        target: 'target_user',
        action_type: 'comment',
      },
      risk: {
        level: 'medium',
      },
      interrupt_payload: {
        approval_id: 'apr_123',
        draft_content: 'Looks great!',
      },
      brief_audit: [],
      audit_trail: [],
    })));

    const events = await collectEvents(
      commandJsonRunner.run('/ai/smart-engagement/recommend', {
        execution_mode: 'execute',
        goal: 'comment on niche posts',
        account_id: 'acct_1',
      }),
    );

    expect(events.map((event) => event.type)).toEqual([
      'run_start',
      'final_response',
      'approval_required',
    ]);
    expect(events[0].thread_id).toBe('thread-engage-run');
    expect(events[1].type).toBe('final_response');
    expect(String(events[1].text)).toContain('paused for approval');
    expect(events[2].type).toBe('approval_required');
    expect((events[2].payload as Record<string, unknown>).thread_id).toBe('thread-engage-run');
  });

  it('maps /engage resume JSON completion into final response and finish events', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      mode: 'execute',
      status: 'completed',
      thread_id: 'thread-engage-resume',
      interrupted: false,
      outcome_reason: 'Action executed successfully',
      recommendation: {
        target: 'target_user',
        action_type: 'comment',
      },
      risk: {
        level: 'low',
      },
      decision: {
        decision: 'approved',
      },
      execution: {
        status: 'success',
      },
      brief_audit: [],
      audit_trail: [],
    })));

    const events = await collectEvents(
      commandJsonRunner.resume('/ai/smart-engagement/resume', {
        thread_id: 'thread-engage-resume',
        decision: 'approved',
      }),
    );

    expect(events.map((event) => event.type)).toEqual([
      'run_start',
      'final_response',
      'run_finish',
    ]);
    expect(events[0].thread_id).toBe('thread-engage-resume');
    expect(String(events[1].text)).toContain('completed');
    expect(events[2].stop_reason).toBe('completed');
  });

  it('maps /engage resume JSON error status into run_error + run_finish', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      mode: 'execute',
      status: 'error',
      thread_id: 'thread-engage-error',
      interrupted: false,
      outcome_reason: 'Resume failed because approval token expired',
      brief_audit: [],
      audit_trail: [],
    })));

    const events = await collectEvents(
      commandJsonRunner.resume('/ai/smart-engagement/resume', {
        thread_id: 'thread-engage-error',
        decision: 'approved',
      }),
    );

    expect(events.map((event) => event.type)).toEqual([
      'run_start',
      'run_error',
      'run_finish',
    ]);
    expect(events[1].message).toBe('Resume failed because approval token expired');
    expect(events[2].stop_reason).toBe('error');
  });

  it('fails fast when SSE transport receives JSON instead of event-stream', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      status: 'recommendation_only',
      interrupted: false,
    })));

    await expect(
      collectEvents(graphRunner.run('/ai/campaign-monitor/run', { threadId: 't-1' })),
    ).rejects.toThrow(/text\/event-stream/i);
  });
});
