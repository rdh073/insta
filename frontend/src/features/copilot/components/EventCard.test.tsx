import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import type { CopilotEvent } from '../../../api/operator-copilot';
import { EventCard, normalizePolicyResultEvent } from './EventCard';

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
