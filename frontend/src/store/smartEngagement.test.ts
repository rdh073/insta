import { beforeEach, describe, expect, it } from 'vitest';
import { getValidSelectedIds, useSmartEngagementStore } from './smartEngagement';

describe('smart engagement selection reconciliation', () => {
  beforeEach(() => {
    useSmartEngagementStore.setState({
      goal: '',
      mode: 'recommendation',
      maxTargets: 5,
      selectedIds: [],
      results: [],
      loading: false,
      progress: '',
      resumeLoading: false,
    });
  });

  it('computes valid selected ids as intersection with active accounts', () => {
    const valid = getValidSelectedIds(['acct-1', 'acct-2', 'acct-1', 'stale'], ['acct-2', 'acct-1']);
    expect(valid).toEqual(['acct-1', 'acct-2']);
  });

  it('deduplicates ids in setSelectedIds', () => {
    useSmartEngagementStore.getState().setSelectedIds(['acct-1', 'acct-1', 'acct-2']);
    expect(useSmartEngagementStore.getState().selectedIds).toEqual(['acct-1', 'acct-2']);
  });

  it('prunes stale persisted ids against active account ids', () => {
    useSmartEngagementStore.setState({ selectedIds: ['acct-1', 'stale', 'acct-2'] });
    useSmartEngagementStore.getState().pruneSelectedIds(['acct-2', 'acct-3']);
    expect(useSmartEngagementStore.getState().selectedIds).toEqual(['acct-2']);
  });
});
