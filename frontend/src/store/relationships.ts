import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RelationshipTab } from '../features/relationships/types';

interface RelationshipsStore {
  tab: RelationshipTab;
  setTab: (v: RelationshipTab) => void;
}

export const useRelationshipsStore = create<RelationshipsStore>()(
  persist(
    (set) => ({
      tab: 'follow',
      setTab: (tab) => set({ tab }),
    }),
    {
      name: 'insta-relationships',
    },
  ),
);
