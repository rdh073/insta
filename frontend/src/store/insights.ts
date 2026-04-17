import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { InsightPostType, InsightOrdering, InsightTimeFrame } from '../api/instagram/insights';
import type { AccountInsightSummary, MediaInsightListResult } from '../types/instagram/insight';

interface AccountInsightCacheEntry {
  data: AccountInsightSummary;
  fetchedAt: number;
}

interface InsightsState {
  // Persisted filter preferences
  postType: InsightPostType;
  timeFrame: InsightTimeFrame;
  ordering: InsightOrdering;

  // In-memory result
  scopeAccountId: string;
  result: MediaInsightListResult | null;

  // Account insight cache (per account_id, short-lived)
  accountInsightCache: Record<string, AccountInsightCacheEntry>;

  // Actions
  setScopeAccountId: (accountId: string) => void;
  setPostType: (v: InsightPostType) => void;
  setTimeFrame: (v: InsightTimeFrame) => void;
  setOrdering: (v: InsightOrdering) => void;
  setResult: (r: MediaInsightListResult | null) => void;
  setAccountInsight: (accountId: string, data: AccountInsightSummary) => void;
  clearAccountInsight: (accountId: string) => void;
}

export const ACCOUNT_INSIGHT_TTL_MS = 60_000;

export const useInsightsStore = create<InsightsState>()(
  persist(
    (set) => ({
      postType: 'ALL',
      timeFrame: 'TWO_YEARS',
      ordering: 'REACH_COUNT',
      scopeAccountId: '',
      result: null,
      accountInsightCache: {},

      setScopeAccountId: (scopeAccountId) =>
        set((state) => {
          if (state.scopeAccountId === scopeAccountId) {
            return { scopeAccountId };
          }
          return { scopeAccountId, result: null };
        }),

      setPostType: (postType) => set({ postType }),
      setTimeFrame: (timeFrame) => set({ timeFrame }),
      setOrdering: (ordering) => set({ ordering }),
      setResult: (result) => set({ result }),
      setAccountInsight: (accountId, data) =>
        set((state) => ({
          accountInsightCache: {
            ...state.accountInsightCache,
            [accountId]: { data, fetchedAt: Date.now() },
          },
        })),
      clearAccountInsight: (accountId) =>
        set((state) => {
          if (!(accountId in state.accountInsightCache)) return state;
          const next = { ...state.accountInsightCache };
          delete next[accountId];
          return { accountInsightCache: next };
        }),
    }),
    {
      name: 'insta-insights',
      partialize: (s) => ({
        postType: s.postType,
        timeFrame: s.timeFrame,
        ordering: s.ordering,
      }),
    },
  ),
);
