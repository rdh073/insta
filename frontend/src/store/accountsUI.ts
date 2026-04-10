import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AccountsUIStore {
  // Persisted
  searchQuery: string;

  // Actions
  setSearchQuery: (v: string) => void;
}

export const useAccountsUIStore = create<AccountsUIStore>()(
  persist(
    (set) => ({
      searchQuery: '',
      setSearchQuery: (searchQuery) => set({ searchQuery }),
    }),
    {
      name: 'insta-accounts-ui',
    },
  ),
);
