import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { identityApi } from '../../../api/instagram/identity';
import { selectActiveAccounts, useAccountStore } from '../../../store/accounts';
import type { CrossFollowPair, JobResult } from '../types';

export function useCrossFollow(selectedAccountIds: Set<string>) {
  const accounts = useAccountStore((s) => s.accounts);
  const activeAccounts = useMemo(() => selectActiveAccounts({ accounts }), [accounts]);
  const selectedAccounts = useMemo(
    () => activeAccounts.filter((a) => selectedAccountIds.has(a.id)),
    [activeAccounts, selectedAccountIds],
  );

  const [pairs, setPairs] = useState<CrossFollowPair[]>([]);
  const [checking, setChecking] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [results, setResults] = useState<JobResult[]>([]);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    return () => { cancelledRef.current = true; };
  }, []);

  const checkRelationships = useCallback(async () => {
    if (selectedAccounts.length < 2 || checking) return;
    setChecking(true);
    setPairs([]);
    setResults([]);

    // Build all pairs upfront so the UI can show placeholders
    const allPairs: CrossFollowPair[] = [];
    for (let i = 0; i < selectedAccounts.length; i++) {
      for (let j = i + 1; j < selectedAccounts.length; j++) {
        allPairs.push({
          a: selectedAccounts[i].username,
          b: selectedAccounts[j].username,
          aFollowsB: null,
          bFollowsA: null,
        });
      }
    }
    setPairs([...allPairs]);

    // Check all pairs in parallel (limited by browser connection pool)
    const checkPair = async (pair: CrossFollowPair, idx: number) => {
      if (cancelledRef.current) return;
      const a = selectedAccounts.find((acc) => acc.username === pair.a)!;
      const b = selectedAccounts.find((acc) => acc.username === pair.b)!;

      const [aResult, bResult] = await Promise.allSettled([
        identityApi.getFollowing(a.id, a.username, 200),
        identityApi.getFollowing(b.id, b.username, 200),
      ]);

      if (cancelledRef.current) return;

      allPairs[idx] = {
        ...pair,
        aFollowsB: aResult.status === 'fulfilled'
          ? aResult.value.some((u) => u.username?.toLowerCase() === b.username.toLowerCase())
          : null,
        bFollowsA: bResult.status === 'fulfilled'
          ? bResult.value.some((u) => u.username?.toLowerCase() === a.username.toLowerCase())
          : null,
      };
      setPairs([...allPairs]);
    };

    await Promise.allSettled(allPairs.map((pair, idx) => checkPair(pair, idx)));

    if (!cancelledRef.current) {
      setChecking(false);
      toast.success(`Checked ${allPairs.length} pairs`);
    }
  }, [selectedAccounts, checking]);

  const executeCrossFollow = useCallback(async () => {
    if (executing) return;
    const missing: { accountId: string; accountUsername: string; target: string }[] = [];

    for (const pair of pairs) {
      if (pair.aFollowsB === false) {
        const acc = accounts.find((a) => a.username === pair.a);
        if (acc) missing.push({ accountId: acc.id, accountUsername: pair.a, target: pair.b });
      }
      if (pair.bFollowsA === false) {
        const acc = accounts.find((a) => a.username === pair.b);
        if (acc) missing.push({ accountId: acc.id, accountUsername: pair.b, target: pair.a });
      }
    }

    if (missing.length === 0) {
      toast.success('All accounts already follow each other');
      return;
    }

    setExecuting(true);
    setResults([]);
    const newResults: JobResult[] = [];

    for (const { accountId, accountUsername, target } of missing) {
      if (cancelledRef.current) break;
      try {
        const res = await identityApi.followUser(accountId, target);
        newResults.push({ account: accountUsername, target, action: 'follow', success: res.success });
      } catch (err: any) {
        newResults.push({
          account: accountUsername, target, action: 'follow', success: false,
          error: err?.response?.data?.detail || err.message || 'Unknown error',
        });
      }
      if (!cancelledRef.current) setResults([...newResults]);
    }

    if (!cancelledRef.current) {
      const ok = newResults.filter((r) => r.success).length;
      if (ok > 0) toast.success(`${ok} cross-follows completed`);
      setExecuting(false);
    }
  }, [pairs, accounts, executing]);

  const missingCount = pairs.filter((p) => p.aFollowsB === false || p.bFollowsA === false).length;

  return { pairs, checking, executing, results, missingCount, checkRelationships, executeCrossFollow };
}
