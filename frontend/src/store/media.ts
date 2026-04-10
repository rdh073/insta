import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MediaSummary } from '../types/instagram/media';

type DrawerTab = 'detail' | 'comments';

interface MediaState {
  // Persisted preferences
  userId: string;

  // In-memory data (lost on page refresh)
  media: MediaSummary[];
  selected: MediaSummary | null;
  drawerTab: DrawerTab;

  // Actions
  setUserId: (v: string) => void;
  setMedia: (items: MediaSummary[]) => void;
  prependMedia: (item: MediaSummary) => void;
  setSelected: (item: MediaSummary | null) => void;
  setDrawerTab: (tab: DrawerTab) => void;
  clearMedia: () => void;
}

export const useMediaStore = create<MediaState>()(
  persist(
    (set, get) => ({
      userId: '',
      media: [],
      selected: null,
      drawerTab: 'detail',

      setUserId: (userId) => set({ userId }),

      setMedia: (media) => set({ media, selected: null }),

      prependMedia: (item) =>
        set((s) => ({
          media: s.media.find((x) => x.pk === item.pk) ? s.media : [item, ...s.media],
          selected: item,
        })),

      setSelected: (selected) => set({ selected }),

      setDrawerTab: (drawerTab) => set({ drawerTab }),

      clearMedia: () => {
        const { selected } = get();
        set({ media: [], selected: selected ? null : null });
      },
    }),
    {
      name: 'insta-media',
      partialize: (s) => ({ userId: s.userId }),
    },
  ),
);
