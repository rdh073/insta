import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { InsightPostType, InsightOrdering, InsightTimeFrame } from '../api/instagram/insights';
import type { MediaInsightListResult } from '../types/instagram/insight';

interface InsightsState {
  // Persisted filter preferences
  postType: InsightPostType;
  timeFrame: InsightTimeFrame;
  ordering: InsightOrdering;

  // In-memory result
  result: MediaInsightListResult | null;

  // Actions
  setPostType: (v: InsightPostType) => void;
  setTimeFrame: (v: InsightTimeFrame) => void;
  setOrdering: (v: InsightOrdering) => void;
  setResult: (r: MediaInsightListResult | null) => void;
}

export const useInsightsStore = create<InsightsState>()(
  persist(
    (set) => ({
      postType: 'ALL',
      timeFrame: 'TWO_YEARS',
      ordering: 'REACH_COUNT',
      result: null,

      setPostType: (postType) => set({ postType }),
      setTimeFrame: (timeFrame) => set({ timeFrame }),
      setOrdering: (ordering) => set({ ordering }),
      setResult: (result) => set({ result }),
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
