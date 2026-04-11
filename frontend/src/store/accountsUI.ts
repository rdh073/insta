import { create } from 'zustand';

interface AccountsUIStore {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
}

/**
 * Ephemeral UI state for the accounts page.
 *
 * NOT persisted — search queries are transient and should not survive
 * page reloads or browser restarts.
 */
export const useAccountsUIStore = create<AccountsUIStore>()((set) => ({
  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),
}));