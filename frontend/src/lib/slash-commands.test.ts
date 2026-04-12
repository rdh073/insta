import { describe, expect, it } from 'vitest';
import { SLASH_COMMANDS } from './slash-commands';

function command(name: string) {
  const found = SLASH_COMMANDS.find((item) => item.name === name);
  if (!found) throw new Error(`Slash command not found: ${name}`);
  return found;
}

describe('slash command resume payload mapping', () => {
  it('/monitor edited maps endpoint-specific parameters', () => {
    const monitor = command('monitor');
    const payload = monitor.buildResumePayload(
      't-monitor',
      'edited',
      [
        { caption: 'Launch recap post' },
        {
          scheduledAt: '2026-05-01T10:00:00Z',
          mediaRefs: ['media/a.jpg', 'media/b.jpg'],
          targetUsernames: ['acct_a', 'acct_b'],
        },
      ],
    );

    expect(payload).toEqual(expect.objectContaining({
      threadId: 't-monitor',
      decision: 'modify',
      parameters: expect.objectContaining({
        caption: 'Launch recap post',
        scheduled_at: '2026-05-01T10:00:00Z',
        media_paths: ['media/a.jpg', 'media/b.jpg'],
        usernames: ['acct_a', 'acct_b'],
      }),
    }));
  });

  it('/risk edited maps overridePolicy and notes', () => {
    const risk = command('risk');
    const payload = risk.buildResumePayload(
      't-risk',
      'edited',
      [{ policy_decision: 'cooldown', reason: 'Manual override from ops' }],
    );

    expect(payload).toEqual({
      threadId: 't-risk',
      decision: 'override_policy',
      overridePolicy: 'cooldown',
      notes: 'Manual override from ops',
    });
  });

  it('/recover edited prefers explicit decision and forwards twoFaCode/proxy', () => {
    const recover = command('recover');
    const payload = recover.buildResumePayload(
      't-recover',
      'edited',
      [{ decision: 'approve_proxy_swap', twoFaCode: '123456', proxy: 'http://proxy.local:8080' }],
      { options: ['provide_2fa', 'abort'] },
    );

    expect(payload).toEqual({
      threadId: 't-recover',
      decision: 'approve_proxy_swap',
      twoFaCode: '123456',
      proxy: 'http://proxy.local:8080',
    });
  });

  it('/pipeline edited maps editedCaption and reason', () => {
    const pipeline = command('pipeline');
    const payload = pipeline.buildResumePayload(
      't-pipeline',
      'edited',
      [{ caption: 'Edited caption copy', notes: 'Use stronger CTA' }],
    );

    expect(payload).toEqual({
      threadId: 't-pipeline',
      decision: 'edited',
      editedCaption: 'Edited caption copy',
      reason: 'Use stronger CTA',
    });
  });

  it('keeps approved/rejected resume behavior unchanged', () => {
    const monitor = command('monitor');
    const risk = command('risk');
    const recover = command('recover');
    const pipeline = command('pipeline');

    expect(monitor.buildResumePayload('t1', 'approved')).toEqual({ threadId: 't1', decision: 'approve' });
    expect(monitor.buildResumePayload('t2', 'rejected')).toEqual({ threadId: 't2', decision: 'skip' });

    expect(risk.buildResumePayload('t3', 'approved')).toEqual({ threadId: 't3', decision: 'approve_policy' });
    expect(risk.buildResumePayload('t4', 'rejected')).toEqual({ threadId: 't4', decision: 'abort' });

    expect(recover.buildResumePayload('t5', 'approved')).toEqual({ threadId: 't5', decision: 'approve_proxy_swap' });
    expect(recover.buildResumePayload('t6', 'rejected')).toEqual({ threadId: 't6', decision: 'abort' });

    expect(pipeline.buildResumePayload('t7', 'approved')).toEqual({ threadId: 't7', decision: 'approved' });
    expect(pipeline.buildResumePayload('t8', 'rejected')).toEqual({ threadId: 't8', decision: 'rejected' });
  });

  it('validates edited payload shape before send for each command', () => {
    const monitor = command('monitor');
    const risk = command('risk');
    const recover = command('recover');
    const pipeline = command('pipeline');

    expect(() => monitor.buildResumePayload('tm', 'edited', [{}]))
      .toThrow('/monitor edited resume requires non-empty parameters.');
    expect(() => risk.buildResumePayload('tr', 'edited', [{}]))
      .toThrow('/risk edited resume requires overridePolicy.');
    expect(() => recover.buildResumePayload('trec', 'edited', [{}]))
      .toThrow('/recover edited resume requires twoFaCode or proxy.');
    expect(() => pipeline.buildResumePayload('tp', 'edited', [{ reason: 'looks good' }]))
      .toThrow('/pipeline edited resume requires editedCaption.');
  });
});
