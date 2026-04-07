import { useCallback } from 'react';
import { useRelationshipStore } from '../store';

/**
 * Thin hook that reads batch job state from the Zustand store.
 * The SSE connection and results survive tab switches and re-mounts.
 */
export function useFollowAction(action: 'follow' | 'unfollow') {
  const { running, results, progress } = useRelationshipStore((s) => s[action]);
  const storeExecute = useRelationshipStore((s) => s.execute);
  const storeCancel = useRelationshipStore((s) => s.cancel);
  const storeClear = useRelationshipStore((s) => s.clearResults);

  const execute = useCallback(
    (selectedAccountIds: Set<string>, targets: string[]) => {
      storeExecute(action, Array.from(selectedAccountIds), targets);
    },
    [action, storeExecute],
  );

  const cancel = useCallback(() => storeCancel(action), [action, storeCancel]);
  const clearResults = useCallback(() => storeClear(action), [action, storeClear]);

  return { running, results, progress, execute, cancel, clearResults };
}
