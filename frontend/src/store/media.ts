import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MediaSummary } from '../types/instagram/media';
import type { MediaAction } from '../features/media/types';

type DrawerTab = 'detail' | 'comments';

interface MediaState {
  // Persisted preferences
  userId: string;

  // In-memory data (lost on page refresh)
  scopeAccountId: string;
  media: MediaSummary[];
  selected: MediaSummary | null;
  drawerTab: DrawerTab;

  // Per-media in-flight mutation actions (for disabling buttons + spinners).
  mutating: Record<string, MediaAction[]>;

  // Actions
  setScopeAccountId: (accountId: string) => void;
  setUserId: (v: string) => void;
  setMedia: (items: MediaSummary[]) => void;
  prependMedia: (item: MediaSummary) => void;
  setSelected: (item: MediaSummary | null) => void;
  setDrawerTab: (tab: DrawerTab) => void;
  clearMedia: () => void;

  // Mutation helpers
  beginMutation: (mediaId: string, action: MediaAction) => void;
  endMutation: (mediaId: string, action: MediaAction) => void;
  applyCaptionEdit: (mediaId: string, caption: string) => void;
  removeMedia: (mediaId: string) => void;
}

function withoutAction(actions: MediaAction[] | undefined, action: MediaAction): MediaAction[] {
  if (!actions || actions.length === 0) return [];
  return actions.filter((entry) => entry !== action);
}

export const useMediaStore = create<MediaState>()(
  persist(
    (set) => ({
      userId: '',
      scopeAccountId: '',
      media: [],
      selected: null,
      drawerTab: 'detail',
      mutating: {},

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
            mutating: {},
          };
        }),

      setUserId: (userId) => set({ userId }),

      setMedia: (media) => set({ media, selected: null, mutating: {} }),

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

      clearMedia: () => set({ media: [], selected: null, drawerTab: 'detail', mutating: {} }),

      beginMutation: (mediaId, action) =>
        set((state) => {
          const current = state.mutating[mediaId] ?? [];
          if (current.includes(action)) return {};
          return {
            mutating: { ...state.mutating, [mediaId]: [...current, action] },
          };
        }),

      endMutation: (mediaId, action) =>
        set((state) => {
          const next = withoutAction(state.mutating[mediaId], action);
          const updated = { ...state.mutating };
          if (next.length === 0) {
            delete updated[mediaId];
          } else {
            updated[mediaId] = next;
          }
          return { mutating: updated };
        }),

      applyCaptionEdit: (mediaId, caption) =>
        set((state) => {
          const update = (m: MediaSummary): MediaSummary =>
            m.mediaId === mediaId ? { ...m, captionText: caption } : m;
          return {
            media: state.media.map(update),
            selected: state.selected ? update(state.selected) : null,
          };
        }),

      removeMedia: (mediaId) =>
        set((state) => ({
          media: state.media.filter((m) => m.mediaId !== mediaId),
          selected: state.selected?.mediaId === mediaId ? null : state.selected,
        })),
    }),
    {
      name: 'insta-media',
      partialize: (s) => ({ userId: s.userId }),
    },
  ),
);
