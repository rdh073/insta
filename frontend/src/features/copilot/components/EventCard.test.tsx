import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { CopilotEvent } from '../../../api/operator-copilot';
import { EventCard, normalizeFinalResponseEvent, normalizePolicyResultEvent } from './EventCard';

function renderEvent(event: CopilotEvent): string {
  return renderToStaticMarkup(<EventCard event={event} />);
}

describe('EventCard policy_result', () => {
  it('normalizes modern policy payload fields', () => {
    const normalized = normalizePolicyResultEvent({
      type: 'policy_result',
      flags: {
        follow_user: 'write_sensitive',
        list_accounts: 'read_only',
      },
      risk_level: 'high',
      risk_reasons: ['tool writes account relationships'],
      needs_approval: true,
    });

    expect(normalized.flags).toEqual({
      follow_user: 'write_sensitive',
      list_accounts: 'read_only',
    });
    expect(normalized.riskLevel).toBe('high');
    expect(normalized.riskReasons).toEqual(['tool writes account relationships']);
    expect(normalized.needsApproval).toBe(true);
    expect(normalized.hasModernPayload).toBe(true);
    expect(normalized.hasLegacyPayload).toBe(false);
  });

  it('keeps legacy policy payload fields available for fallback rendering', () => {
    const normalized = normalizePolicyResultEvent({
      type: 'policy_result',
      proposed_calls: [{ id: 'c1' }, { id: 'c2' }],
      approved_calls: [{ id: 'c1' }],
    });

    expect(normalized.proposedCalls).toEqual([{ id: 'c1' }, { id: 'c2' }]);
    expect(normalized.approvedCalls).toEqual([{ id: 'c1' }]);
    expect(normalized.flags).toEqual({});
    expect(normalized.riskLevel).toBeNull();
    expect(normalized.riskReasons).toEqual([]);
    expect(normalized.needsApproval).toBeNull();
    expect(normalized.hasModernPayload).toBe(false);
    expect(normalized.hasLegacyPayload).toBe(true);
  });

  it('renders modern policy risk and approval context in the card', () => {
    const html = renderEvent({
      type: 'policy_result',
      flags: { follow_user: 'write_sensitive' },
      risk_level: 'high',
      risk_reasons: ['follow_user modifies relationship state'],
      needs_approval: true,
    });

    expect(html).toContain('policy_check');
    expect(html).toContain('risk high');
    expect(html).toContain('approval required');
    expect(html).toContain('follow_user: write_sensitive');
    expect(html).toContain('follow_user modifies relationship state');
  });

  it('renders legacy proposed/approved counters without runtime errors', () => {
    const html = renderEvent({
      type: 'policy_result',
      proposed_calls: [{ id: 'c1' }, { id: 'c2' }],
      approved_calls: [{ id: 'c1' }],
    });

    expect(html).toContain('2 proposed');
    expect(html).toContain('1 approved');
  });
});

describe('EventCard final_response', () => {
  it('renders content pipeline artifacts including job id and caption', () => {
    const html = renderEvent({
      type: 'final_response',
      text: 'Content pipeline complete.',
      stop_reason: 'scheduled',
      job_id: 'job-content-001',
      caption: 'Launch post caption #brand',
    });

    expect(html).toContain('status scheduled');
    expect(html).toContain('job job-content-001');
    expect(html).toContain('caption');
    expect(html).toContain('Launch post caption #brand');
  });

  it('renders risk control policy and recheck metadata', () => {
    const html = renderEvent({
      type: 'final_response',
      text: 'Risk control run complete.',
      stop_reason: 'completed',
      final_policy: 'cooldown',
      recheck_risk_level: 'medium',
    });

    expect(html).toContain('policy cooldown');
    expect(html).toContain('recheck risk medium');
  });

  it('renders campaign monitor follow-up references and summary metadata', () => {
    const event: CopilotEvent = {
      type: 'final_response',
      text: 'Campaign monitor run complete.',
      stop_reason: 'followup_created',
      recommended_action: 'boost',
      followup_job_id: 'followup-001',
      campaign_summary: { completion_rate: 0.8, failed_jobs: 1 },
    };
    const html = renderEvent(event);
    const normalized = normalizeFinalResponseEvent(event);

    expect(html).toContain('follow-up followup-001');
    expect(html).toContain('recommended_action');
    expect(html).toContain('boost');
    expect(html).toContain('campaign_summary');
    expect(normalized.campaignSummary).toEqual({ completion_rate: 0.8, failed_jobs: 1 });
  });

  it('renders account recovery result metadata', () => {
    const event: CopilotEvent = {
      type: 'final_response',
      text: 'Account recovery complete.',
      stop_reason: 'recovered',
      recovery_successful: true,
      result: { method: 'two_fa', attempts: 1 },
    };
    const html = renderEvent(event);
    const normalized = normalizeFinalResponseEvent(event);

    expect(html).toContain('recovery ok');
    expect(html).toContain('result_metadata');
    expect(normalized.resultMetadata).toEqual({ method: 'two_fa', attempts: 1 });
  });

  it('normalizes payload fallback fields for final_response metadata', () => {
    const normalized = normalizeFinalResponseEvent({
      type: 'final_response',
      text: 'Smart engagement run completed.',
      payload: {
        status: 'completed',
        result: { execution: { success: true } },
      },
    });

    expect(normalized.stopReason).toBe('completed');
    expect(normalized.resultMetadata).toEqual({ execution: { success: true } });
  });
});
