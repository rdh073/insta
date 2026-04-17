import { create } from 'zustand';
import type { MediaSummary } from '../types/instagram/media';

interface LikedPagingByAccount {
  items: MediaSummary[];
  lastMediaPk: number;
  hasMore: boolean;
}

const EMPTY_PAGE: LikedPagingByAccount = { items: [], lastMediaPk: 0, hasMore: true };

interface CollectionsState {
  likedByAccountId: Record<string, LikedPagingByAccount>;

  getLiked: (accountId: string) => LikedPagingByAccount;
  setLiked: (accountId: string, page: LikedPagingByAccount) => void;
  appendLiked: (accountId: string, page: LikedPagingByAccount) => void;
  clearLiked: (accountId: string) => void;
}

export const useCollectionsStore = create<CollectionsState>()((set, get) => ({
  likedByAccountId: {},

  getLiked: (accountId) => get().likedByAccountId[accountId] ?? EMPTY_PAGE,

  setLiked: (accountId, page) =>
    set((state) => ({
      likedByAccountId: { ...state.likedByAccountId, [accountId]: page },
    })),

  appendLiked: (accountId, page) =>
    set((state) => {
      const prev = state.likedByAccountId[accountId] ?? EMPTY_PAGE;
      const existingPks = new Set(prev.items.map((m) => m.pk));
      const merged = [...prev.items, ...page.items.filter((m) => !existingPks.has(m.pk))];
      return {
        likedByAccountId: {
          ...state.likedByAccountId,
          [accountId]: {
            items: merged,
            lastMediaPk: page.lastMediaPk,
            hasMore: page.hasMore,
          },
        },
      };
    }),

  clearLiked: (accountId) =>
    set((state) => {
      const next = { ...state.likedByAccountId };
      delete next[accountId];
      return { likedByAccountId: next };
    }),
}));
