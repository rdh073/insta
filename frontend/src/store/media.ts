import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MediaSummary } from '../types/instagram/media';
import type { PublicUserProfile } from '../types/instagram/user';
import type { MediaAction } from '../features/media/types';

type DrawerTab = 'detail' | 'comments' | 'likers';
type FeedTab = 'posts' | 'clips' | 'tagged';

interface UserMediaCache {
  posts: MediaSummary[];
  clips: MediaSummary[];
  tagged: MediaSummary[];
}

const EMPTY_USER_CACHE: UserMediaCache = { posts: [], clips: [], tagged: [] };

interface MediaState {
  // Persisted preferences
  userId: string;

  // In-memory data (lost on page refresh)
  scopeAccountId: string;
  media: MediaSummary[];
  selected: MediaSummary | null;
  drawerTab: DrawerTab;
  feedTab: FeedTab;

  // Per-media in-flight mutation actions (for disabling buttons + spinners).
  mutating: Record<string, MediaAction[]>;

  // Caches for new reads, keyed by id.
  // likers: keyed by media_id (string)
  // clips/tagged: keyed by user_id (number stringified)
  likersByMediaId: Record<string, PublicUserProfile[]>;
  clipsByUserId: Record<string, MediaSummary[]>;
  taggedByUserId: Record<string, MediaSummary[]>;

  // Actions
  setScopeAccountId: (accountId: string) => void;
  setUserId: (v: string) => void;
  setMedia: (items: MediaSummary[]) => void;
  prependMedia: (item: MediaSummary) => void;
  setSelected: (item: MediaSummary | null) => void;
  setDrawerTab: (tab: DrawerTab) => void;
  setFeedTab: (tab: FeedTab) => void;
  clearMedia: () => void;

  // Cache writers
  setLikers: (mediaId: string, users: PublicUserProfile[]) => void;
  setClips: (userId: number | string, items: MediaSummary[]) => void;
  setTagged: (userId: number | string, items: MediaSummary[]) => void;
  getUserCache: (userId: number | string) => UserMediaCache;

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
    (set, get) => ({
      userId: '',
      scopeAccountId: '',
      media: [],
      selected: null,
      drawerTab: 'detail',
      feedTab: 'posts',
      mutating: {},
      likersByMediaId: {},
      clipsByUserId: {},
      taggedByUserId: {},

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
            feedTab: 'posts',
            mutating: {},
            likersByMediaId: {},
            clipsByUserId: {},
            taggedByUserId: {},
          };
        }),

      setUserId: (userId) => set({ userId }),

      setMedia: (media) => set({ media, selected: null, mutating: {} }),

      prependMedia: (item) =>
        set((s) => ({
          media: s.media.find((x) => x.pk === item.pk) ? s.media : [item, ...s.media],
          selected: item,
        })),

      setSelected: (selected) => set({ selected }),

      setDrawerTab: (drawerTab) => set({ drawerTab }),

      setFeedTab: (feedTab) => set({ feedTab }),

      clearMedia: () =>
        set({
          media: [],
          selected: null,
          drawerTab: 'detail',
          feedTab: 'posts',
          mutating: {},
          likersByMediaId: {},
          clipsByUserId: {},
          taggedByUserId: {},
        }),

      setLikers: (mediaId, users) =>
        set((state) => ({
          likersByMediaId: { ...state.likersByMediaId, [mediaId]: users },
        })),

      setClips: (userId, items) =>
        set((state) => ({
          clipsByUserId: { ...state.clipsByUserId, [String(userId)]: items },
        })),

      setTagged: (userId, items) =>
        set((state) => ({
          taggedByUserId: { ...state.taggedByUserId, [String(userId)]: items },
        })),

      getUserCache: (userId) => {
        const key = String(userId);
        const state = get();
        return {
          posts: state.media,
          clips: state.clipsByUserId[key] ?? EMPTY_USER_CACHE.clips,
          tagged: state.taggedByUserId[key] ?? EMPTY_USER_CACHE.tagged,
        };
      },

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
