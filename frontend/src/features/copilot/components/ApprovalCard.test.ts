import { describe, expect, it } from 'vitest';
import { buildEditableDraft, normalizeEditedCalls } from './ApprovalCard';

describe('ApprovalCard helpers', () => {
  describe('normalizeEditedCalls', () => {
    it('normalizes array values and filters non-objects', () => {
      const result = normalizeEditedCalls([
        { id: 'c1', name: 'follow_user', arguments: { user_id: 'u1' } },
        'skip-me',
        null,
      ]);
      expect(result).toEqual([{ id: 'c1', name: 'follow_user', arguments: { user_id: 'u1' } }]);
    });

    it('wraps a single object into an array', () => {
      const result = normalizeEditedCalls({ id: 'c1', name: 'follow_user' });
      expect(result).toEqual([{ id: 'c1', name: 'follow_user' }]);
    });

    it('returns empty for invalid values', () => {
      expect(normalizeEditedCalls('invalid')).toEqual([]);
      expect(normalizeEditedCalls(null)).toEqual([]);
      expect(normalizeEditedCalls(undefined)).toEqual([]);
    });
  });

  describe('buildEditableDraft', () => {
    it('prefers proposed_tool_calls over aliases', () => {
      const draft = buildEditableDraft({
        proposed_tool_calls: [{ id: 'c1', name: 'follow_user' }],
        proposed_calls: [{ id: 'legacy', name: 'list_accounts' }],
      });
      expect(draft).toEqual([{ id: 'c1', name: 'follow_user' }]);
    });

    it('uses alias when canonical key is empty', () => {
      const draft = buildEditableDraft({
        proposed_tool_calls: [],
        proposed_calls: [{ id: 'legacy', name: 'list_accounts' }],
      });
      expect(draft).toEqual([{ id: 'legacy', name: 'list_accounts' }]);
    });

    it('does not let empty proposed_calls mask non-empty proposed_tool_calls', () => {
      const draft = buildEditableDraft({
        proposed_calls: [],
        proposed_tool_calls: [{ id: 'c1', name: 'follow_user' }],
      });
      expect(draft).toEqual([{ id: 'c1', name: 'follow_user' }]);
    });

    it('falls back to caption draft when no tool calls exist', () => {
      const draft = buildEditableDraft({ caption: '  revised caption  ' });
      expect(draft).toEqual([{ edited_caption: 'revised caption' }]);
    });
  });
});
