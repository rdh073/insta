import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Account } from '../types';

type AccountWithLegacyError = Account & { error?: string };
type AccountPatchWithLegacyError = Partial<Account> & { error?: string };

interface AccountStore {
  accounts: Account[];
  activeId: string | null;
  setAccounts: (accounts: Account[]) => void;
  upsertAccount: (account: Account) => void;
  patchAccount: (id: string, patch: Partial<Account>) => void;
  removeAccount: (id: string) => void;
  setActive: (id: string | null) => void;
  updateStatus: (
    id: string,
    status: Account['status'],
    lastError?: string,
    lastErrorCode?: string,
  ) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isAccountStatus(value: unknown): value is Account['status'] {
  return (
    value === 'idle' ||
    value === 'logging_in' ||
    value === 'active' ||
    value === 'error' ||
    value === 'challenge' ||
    value === '2fa_required'
  );
}

export function normalizeAccount(account: AccountWithLegacyError): Account {
  const { error: legacyError, ...rest } = account;
  return {
    ...rest,
    lastError: account.lastError ?? legacyError ?? undefined,
    lastErrorCode: account.lastErrorCode ?? undefined,
  };
}

export function normalizeAccountPatch(patch: AccountPatchWithLegacyError): Partial<Account> {
  const { error: legacyError, ...rest } = patch;
  if (legacyError !== undefined && rest.lastError === undefined) {
    return { ...rest, lastError: legacyError };
  }
  return rest;
}

function toAccountOrNull(raw: unknown): Account | null {
  if (!isRecord(raw)) {
    return null;
  }
  if (typeof raw.id !== 'string' || typeof raw.username !== 'string' || !isAccountStatus(raw.status)) {
    return null;
  }

  const hydrated: AccountWithLegacyError = {
    id: raw.id,
    username: raw.username,
    status: raw.status,
    proxy: typeof raw.proxy === 'string' ? raw.proxy : undefined,
    avatar: typeof raw.avatar === 'string' ? raw.avatar : undefined,
    followers: typeof raw.followers === 'number' ? raw.followers : undefined,
    following: typeof raw.following === 'number' ? raw.following : undefined,
    fullName: typeof raw.fullName === 'string' ? raw.fullName : undefined,
    totpEnabled: typeof raw.totpEnabled === 'boolean' ? raw.totpEnabled : undefined,
    lastVerifiedAt: typeof raw.lastVerifiedAt === 'string' ? raw.lastVerifiedAt : undefined,
    lastError: typeof raw.lastError === 'string' ? raw.lastError : undefined,
    lastErrorCode: typeof raw.lastErrorCode === 'string' ? raw.lastErrorCode : undefined,
    error: typeof raw.error === 'string' ? raw.error : undefined,
  };
  return normalizeAccount(hydrated);
}

export function migratePersistedAccountsState(persistedState: unknown): {
  accounts: Account[];
  activeId: string | null;
} {
  if (!isRecord(persistedState)) {
    return { accounts: [], activeId: null };
  }

  const rawAccounts = Array.isArray(persistedState.accounts) ? persistedState.accounts : [];
  const accounts = rawAccounts.map(toAccountOrNull).filter((account): account is Account => account !== null);
  const rawActiveId = persistedState.activeId;
  const activeId = typeof rawActiveId === 'string' ? rawActiveId : null;
  const validActiveId = activeId && accounts.some((account) => account.id === activeId) ? activeId : null;

  return { accounts, activeId: validActiveId };
}

export const useAccountStore = create<AccountStore>()(
  persist(
    (set) => ({
      accounts: [],
      activeId: null,

      setAccounts: (accounts) => set({ accounts: accounts.map((account) => normalizeAccount(account)) }),

      upsertAccount: (account) =>
        set((s) => {
          const normalized = normalizeAccount(account);
          const idx = s.accounts.findIndex((a) => a.id === account.id);
          if (idx >= 0) {
            const next = [...s.accounts];
            next[idx] = normalized;
            return { accounts: next };
          }
          return { accounts: [...s.accounts, normalized] };
        }),

      patchAccount: (id, patch) =>
        set((s) => ({
          accounts: s.accounts.map((a) =>
            a.id === id ? { ...a, ...normalizeAccountPatch(patch) } : a
          ),
        })),

      removeAccount: (id) =>
        set((s) => ({
          accounts: s.accounts.filter((a) => a.id !== id),
          activeId: s.activeId === id ? null : s.activeId,
        })),

      setActive: (id) => set({ activeId: id }),

      updateStatus: (id, status, lastError, lastErrorCode) =>
        set((s) => ({
          accounts: s.accounts.map((a) =>
            a.id === id ? { ...a, status, lastError, lastErrorCode } : a
          ),
        })),
    }),
    {
      name: 'insta-accounts',
      version: 2,
      partialize: (s) => ({ accounts: s.accounts, activeId: s.activeId }),
      migrate: (persistedState) => migratePersistedAccountsState(persistedState),
    }
  )
);
