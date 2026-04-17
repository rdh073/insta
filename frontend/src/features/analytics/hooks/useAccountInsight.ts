import { useCallback, useEffect, useState } from 'react';
import { insightsApi } from '../../../api/instagram/insights';
import { ACCOUNT_INSIGHT_TTL_MS, useInsightsStore } from '../../../store/insights';
import type { AccountInsightSummary } from '../../../types/instagram/insight';
import { getErrorMessage } from '../../../lib/error';

interface UseAccountInsightResult {
  data: AccountInsightSummary | null;
  loading: boolean;
  error: string | null;
  stale: boolean;
  refetch: () => Promise<void>;
}

export function useAccountInsight(accountId: string): UseAccountInsightResult {
  const cache = useInsightsStore((s) => s.accountInsightCache);
  const setAccountInsight = useInsightsStore((s) => s.setAccountInsight);

  const entry = accountId ? cache[accountId] : undefined;
  const stale = entry ? Date.now() - entry.fetchedAt > ACCOUNT_INSIGHT_TTL_MS : true;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOnce = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await insightsApi.getAccountInsight(accountId);
      setAccountInsight(accountId, data);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [accountId, setAccountInsight]);

  useEffect(() => {
    if (!accountId) return;
    if (!entry || stale) {
      void fetchOnce();
    }
  }, [accountId, entry, stale, fetchOnce]);

  return {
    data: entry?.data ?? null,
    loading,
    error,
    stale,
    refetch: fetchOnce,
  };
}
