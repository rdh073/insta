import { describe, expect, it } from 'vitest';
import { reconcileAccountSelection } from './AccountPicker';

describe('reconcileAccountSelection', () => {
  it('keeps current selection when it is still active', () => {
    const next = reconcileAccountSelection('acct-2', ['acct-1', 'acct-2'], 'acct-1');
    expect(next).toBe('acct-2');
  });

  it('falls back to persisted selection when current id is invalid', () => {
    const next = reconcileAccountSelection('missing', ['acct-1', 'acct-2'], 'acct-1');
    expect(next).toBe('acct-1');
  });

  it('falls back to first active account when persisted id is stale', () => {
    const next = reconcileAccountSelection('', ['acct-1', 'acct-2'], 'stale-id');
    expect(next).toBe('acct-1');
  });

  it('returns empty selection when there are no active accounts', () => {
    const next = reconcileAccountSelection('', [], 'stale-id');
    expect(next).toBe('');
  });
});
