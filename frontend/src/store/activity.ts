import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ActivityStore {
  // Persisted filters
  username: string;
  event: string;
  search: string;
  autoRefresh: boolean;

  // Actions
  setUsername: (v: string) => void;
  setEvent: (v: string) => void;
  setSearch: (v: string) => void;
  setAutoRefresh: (v: boolean) => void;
}

export const useActivityStore = create<ActivityStore>()(
  persist(
    (set) => ({
      username: '',
      event: '',
      search: '',
      autoRefresh: false,

      setUsername: (username) => set({ username }),
      setEvent: (event) => set({ event }),
      setSearch: (search) => set({ search }),
      setAutoRefresh: (autoRefresh) => set({ autoRefresh }),
    }),
    {
      name: 'insta-activity',
    },
  ),
);
