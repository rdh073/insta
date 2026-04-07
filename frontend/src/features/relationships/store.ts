/**
 * Zustand store for relationship batch jobs.
 *
 * State lives here (not in component) so it survives tab switches
 * and page navigation. The SSE connection keeps running in the background.
 */

import { create } from 'zustand';
import toast from 'react-hot-toast';
import { identityApi } from '../../api/instagram/identity';
import type { JobResult } from './types';

interface BatchJobState {
  running: boolean;
  results: JobResult[];
  progress: { completed: number; total: number };
}

interface RelationshipStore {
  follow: BatchJobState;
  unfollow: BatchJobState;

  execute: (
    action: 'follow' | 'unfollow',
    accountIds: string[],
    targets: string[],
  ) => void;
  cancel: (action: 'follow' | 'unfollow') => void;
  clearResults: (action: 'follow' | 'unfollow') => void;
}

const emptyJob = (): BatchJobState => ({
  running: false,
  results: [],
  progress: { completed: 0, total: 0 },
});

/** Module-scoped abort functions — non-serializable, kept out of Zustand state. */
const abortFns: Record<string, (() => void) | null> = { follow: null, unfollow: null };

export const useRelationshipStore = create<RelationshipStore>()((set, get) => ({
  follow: emptyJob(),
  unfollow: emptyJob(),

  execute: (action, accountIds, targets) => {
    const state = get();
    if (state[action].running) return;
    if (accountIds.length === 0 || targets.length === 0) return;

    // Reset state
    set({
      [action]: {
        running: true,
        results: [],
        progress: { completed: 0, total: accountIds.length * targets.length },
      },
    });

    const collected: JobResult[] = [];

    const abort = identityApi.batchRelationship(
      action,
      { account_ids: accountIds, targets, concurrency: 3, delay_between: 1.0 },
      // onResult
      (result) => {
        collected.push({
          account: result.account,
          target: result.target,
          action: result.action as 'follow' | 'unfollow',
          success: result.success,
          error: result.error,
        });
        set({
          [action]: {
            running: true,
            results: [...collected],
            progress: { completed: result.completed, total: result.total },
          },
        });
      },
      // onDone
      () => {
        const successCount = collected.filter((r) => r.success).length;
        const failCount = collected.filter((r) => !r.success).length;
        if (successCount > 0) toast.success(`${successCount} ${action} succeeded`);
        if (failCount > 0) toast.error(`${failCount} ${action} failed`);
        abortFns[action] = null;
        set((s) => ({ [action]: { ...s[action], running: false } }));
      },
      // onError
      (err) => {
        toast.error(err.message || `Batch ${action} failed`);
        abortFns[action] = null;
        set((s) => ({ [action]: { ...s[action], running: false } }));
      },
    );

    abortFns[action] = abort;
  },

  cancel: (action) => {
    abortFns[action]?.();
    abortFns[action] = null;
    set((s) => ({ [action]: { ...s[action], running: false } }));
  },

  clearResults: (action) => {
    set({ [action]: emptyJob() });
  },
}));
