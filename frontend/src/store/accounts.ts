import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Account } from '../types';

interface AccountStore {
  accounts: Account[];
  activeId: string | null;
  setAccounts: (accounts: Account[]) => void;
  upsertAccount: (account: Account) => void;
  patchAccount: (id: string, patch: Partial<Account>) => void;
  removeAccount: (id: string) => void;
  setActive: (id: string | null) => void;
  updateStatus: (id: string, status: Account['status'], error?: string) => void;
}

export const useAccountStore = create<AccountStore>()(
  persist(
    (set) => ({
      accounts: [],
      activeId: null,

      setAccounts: (accounts) => set({ accounts }),

      upsertAccount: (account) =>
        set((s) => {
          const idx = s.accounts.findIndex((a) => a.id === account.id);
          if (idx >= 0) {
            const next = [...s.accounts];
            next[idx] = account;
            return { accounts: next };
          }
          return { accounts: [...s.accounts, account] };
        }),

      patchAccount: (id, patch) =>
        set((s) => ({
          accounts: s.accounts.map((a) =>
            a.id === id ? { ...a, ...patch } : a
          ),
        })),

      removeAccount: (id) =>
        set((s) => ({
          accounts: s.accounts.filter((a) => a.id !== id),
          activeId: s.activeId === id ? null : s.activeId,
        })),

      setActive: (id) => set({ activeId: id }),

      updateStatus: (id, status, error) =>
        set((s) => ({
          accounts: s.accounts.map((a) =>
            a.id === id ? { ...a, status, error } : a
          ),
        })),
    }),
    { name: 'insta-accounts', partialize: (s) => ({ accounts: s.accounts, activeId: s.activeId }) }
  )
);
