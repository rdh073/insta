import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface StoriesStore {
  // Persisted
  userId: string;

  // Actions
  setUserId: (v: string) => void;
}

export const useStoriesStore = create<StoriesStore>()(
  persist(
    (set) => ({
      userId: '',
      setUserId: (userId) => set({ userId }),
    }),
    {
      name: 'insta-stories',
    },
  ),
);
