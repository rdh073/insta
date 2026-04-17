import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RelationshipTab } from '../features/relationships/types';
import type { NotificationKind } from '../api/instagram/relationships';

export type UserControlState = {
  mutedPosts: boolean;
  mutedStories: boolean;
  notifications: Record<NotificationKind, boolean>;
};

export const emptyControlState = (): UserControlState => ({
  mutedPosts: false,
  mutedStories: false,
  notifications: { posts: false, videos: false, reels: false, stories: false },
});

function controlKey(accountId: string, targetUsername: string): string {
  return `${accountId}::${targetUsername.trim().replace(/^@/, '').toLowerCase()}`;
}

interface RelationshipsStore {
  tab: RelationshipTab;
  setTab: (v: RelationshipTab) => void;

  controlState: Record<string, UserControlState>;
  getControl: (accountId: string, targetUsername: string) => UserControlState;
  setMuted: (
    accountId: string,
    targetUsername: string,
    scope: 'posts' | 'stories',
    muted: boolean,
  ) => void;
  setNotification: (
    accountId: string,
    targetUsername: string,
    kind: NotificationKind,
    enabled: boolean,
  ) => void;
}

export const useRelationshipsStore = create<RelationshipsStore>()(
  persist(
    (set, get) => ({
      tab: 'follow',
      setTab: (tab) => set({ tab }),

      controlState: {},
      getControl: (accountId, targetUsername) => {
        const key = controlKey(accountId, targetUsername);
        return get().controlState[key] ?? emptyControlState();
      },
      setMuted: (accountId, targetUsername, scope, muted) => {
        const key = controlKey(accountId, targetUsername);
        set((state) => {
          const current = state.controlState[key] ?? emptyControlState();
          const next: UserControlState = {
            ...current,
            mutedPosts: scope === 'posts' ? muted : current.mutedPosts,
            mutedStories: scope === 'stories' ? muted : current.mutedStories,
          };
          return { controlState: { ...state.controlState, [key]: next } };
        });
      },
      setNotification: (accountId, targetUsername, kind, enabled) => {
        const key = controlKey(accountId, targetUsername);
        set((state) => {
          const current = state.controlState[key] ?? emptyControlState();
          const next: UserControlState = {
            ...current,
            notifications: { ...current.notifications, [kind]: enabled },
          };
          return { controlState: { ...state.controlState, [key]: next } };
        });
      },
    }),
    {
      name: 'insta-relationships',
    },
  ),
);
