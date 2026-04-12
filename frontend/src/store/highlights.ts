import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { HighlightSummary } from '../types/instagram/highlight';

interface HighlightsState {
  // Persisted preferences
  userId: string;

  // In-memory data (lost on page refresh, preserved across navigation)
  scopeAccountId: string;
  highlights: HighlightSummary[];
  loading: boolean;

  // Actions
  setScopeAccountId: (accountId: string) => void;
  setUserId: (v: string) => void;
  setHighlights: (items: HighlightSummary[]) => void;
  setLoading: (v: boolean) => void;
  removeHighlight: (pk: string) => void;
  clearHighlights: () => void;
}

export const useHighlightsStore = create<HighlightsState>()(
  persist(
    (set) => ({
      userId: '',
      scopeAccountId: '',
      highlights: [],
      loading: false,

      setScopeAccountId: (scopeAccountId) =>
        set((state) => {
          if (state.scopeAccountId === scopeAccountId) {
            return { scopeAccountId };
          }
          return { scopeAccountId, highlights: [], loading: false };
        }),

      setUserId: (userId) => set({ userId }),
      setHighlights: (highlights) => set({ highlights }),
      setLoading: (loading) => set({ loading }),

      removeHighlight: (pk) =>
        set((s) => ({ highlights: s.highlights.filter((h) => h.pk !== pk) })),

      clearHighlights: () => set({ highlights: [] }),
    }),
    {
      name: 'insta-highlights',
      partialize: (s) => ({ userId: s.userId }),
    },
  ),
);
