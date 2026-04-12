import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MediaSummary } from '../types/instagram/media';

type DrawerTab = 'detail' | 'comments';

interface MediaState {
  // Persisted preferences
  userId: string;

  // In-memory data (lost on page refresh)
  scopeAccountId: string;
  media: MediaSummary[];
  selected: MediaSummary | null;
  drawerTab: DrawerTab;

  // Actions
  setScopeAccountId: (accountId: string) => void;
  setUserId: (v: string) => void;
  setMedia: (items: MediaSummary[]) => void;
  prependMedia: (item: MediaSummary) => void;
  setSelected: (item: MediaSummary | null) => void;
  setDrawerTab: (tab: DrawerTab) => void;
  clearMedia: () => void;
}

export const useMediaStore = create<MediaState>()(
  persist(
    (set) => ({
      userId: '',
      scopeAccountId: '',
      media: [],
      selected: null,
      drawerTab: 'detail',

      setScopeAccountId: (scopeAccountId) =>
        set((state) => {
          if (state.scopeAccountId === scopeAccountId) {
            return { scopeAccountId };
          }
          return {
            scopeAccountId,
            media: [],
            selected: null,
            drawerTab: 'detail',
          };
        }),

      setUserId: (userId) => set({ userId }),

      setMedia: (media) => set({ media, selected: null }),

      prependMedia: (item) =>
        set((s) => ({
          media: s.media.find((x) => x.pk === item.pk) ? s.media : [item, ...s.media],
          selected: item,
        })),

      setSelected: (selected) =>
        set((state) => {
          if (!selected) {
            return { selected: null };
          }
          const exists = state.media.some((item) => item.pk === selected.pk);
          return { selected: exists ? selected : null };
        }),

      setDrawerTab: (drawerTab) => set({ drawerTab }),

      clearMedia: () => set({ media: [], selected: null, drawerTab: 'detail' }),
    }),
    {
      name: 'insta-media',
      partialize: (s) => ({ userId: s.userId }),
    },
  ),
);
