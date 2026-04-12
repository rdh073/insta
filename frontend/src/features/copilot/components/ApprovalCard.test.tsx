import { describe, expect, it } from 'vitest';
import { buildEditableDraft } from './ApprovalCard';

describe('buildEditableDraft', () => {
  it('prefills from interrupt draft_content before nested draft fields', () => {
    const payload = {
      draft_content: 'Top-level draft content',
      draft_action: { content: 'Action content' },
      draft_payload: { content: 'Payload content' },
    };

    expect(buildEditableDraft(payload)).toEqual([{ content: 'Top-level draft content' }]);
  });

  it('falls back to draft_payload.content when other draft fields are missing', () => {
    const payload = {
      draft_payload: { content: 'Payload fallback content' },
    };

    expect(buildEditableDraft(payload)).toEqual([{ content: 'Payload fallback content' }]);
  });
});
