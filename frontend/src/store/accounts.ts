import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Account } from '../types';
import type { AccountSecurityInfo } from '../api/accounts';

type AccountWithLegacyError = Account & { error?: string };
type AccountPatchWithLegacyError = Partial<Account> & { error?: string };

export type PendingConfirmation = 'email' | 'phone';

interface AccountStore {
  accounts: Account[];
  activeId: string | null;
  securityInfo: Record<string, AccountSecurityInfo>;
  pendingConfirmations: Record<string, Partial<Record<PendingConfirmation, string>>>;
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
  setSecurityInfo: (id: string, info: AccountSecurityInfo) => void;
  clearSecurityInfo: (id: string) => void;
  markPendingConfirmation: (id: string, channel: PendingConfirmation, target: string) => void;
  clearPendingConfirmation: (id: string, channel: PendingConfirmation) => void;
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
  pendingConfirmations: Record<string, Partial<Record<PendingConfirmation, string>>>;
} {
  if (!isRecord(persistedState)) {
    return { accounts: [], activeId: null, pendingConfirmations: {} };
  }

  const rawAccounts = Array.isArray(persistedState.accounts) ? persistedState.accounts : [];
  const accounts = rawAccounts.map(toAccountOrNull).filter((account): account is Account => account !== null);
  const rawActiveId = persistedState.activeId;
  const activeId = typeof rawActiveId === 'string' ? rawActiveId : null;
  const validActiveId = activeId && accounts.some((account) => account.id === activeId) ? activeId : null;

  const pendingConfirmations: Record<string, Partial<Record<PendingConfirmation, string>>> = {};
  if (isRecord(persistedState.pendingConfirmations)) {
    for (const [id, entry] of Object.entries(persistedState.pendingConfirmations)) {
      if (!isRecord(entry)) continue;
      const slot: Partial<Record<PendingConfirmation, string>> = {};
      if (typeof entry.email === 'string') slot.email = entry.email;
      if (typeof entry.phone === 'string') slot.phone = entry.phone;
      if (Object.keys(slot).length > 0) pendingConfirmations[id] = slot;
    }
  }

  return { accounts, activeId: validActiveId, pendingConfirmations };
}

/**
 * Managed-account count selector — used by pages that render a "Tracked"
 * or "Connected" metric so the value always reflects the live account list
 * in the store. Kept as a standalone selector (not `accounts.length` inline)
 * so it can be reused and unit-tested without rendering a component.
 */
export const selectTrackedAccountCount = (state: Pick<AccountStore, 'accounts'>): number =>
  state.accounts.length;

export const useAccountStore = create<AccountStore>()(
  persist(
    (set) => ({
      accounts: [],
      activeId: null,
      securityInfo: {},
      pendingConfirmations: {},

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
        set((s) => {
          const { [id]: _removedSecurity, ...remainingSecurity } = s.securityInfo;
          const { [id]: _removedPending, ...remainingPending } = s.pendingConfirmations;
          return {
            accounts: s.accounts.filter((a) => a.id !== id),
            activeId: s.activeId === id ? null : s.activeId,
            securityInfo: remainingSecurity,
            pendingConfirmations: remainingPending,
          };
        }),

      setActive: (id) => set({ activeId: id }),

      updateStatus: (id, status, lastError, lastErrorCode) =>
        set((s) => ({
          accounts: s.accounts.map((a) =>
            a.id === id ? { ...a, status, lastError, lastErrorCode } : a
          ),
        })),

      setSecurityInfo: (id, info) =>
        set((s) => ({ securityInfo: { ...s.securityInfo, [id]: info } })),

      clearSecurityInfo: (id) =>
        set((s) => {
          const { [id]: _removed, ...rest } = s.securityInfo;
          return { securityInfo: rest };
        }),

      markPendingConfirmation: (id, channel, target) =>
        set((s) => ({
          pendingConfirmations: {
            ...s.pendingConfirmations,
            [id]: { ...(s.pendingConfirmations[id] ?? {}), [channel]: target },
          },
        })),

      clearPendingConfirmation: (id, channel) =>
        set((s) => {
          const current = s.pendingConfirmations[id];
          if (!current || !(channel in current)) return s;
          const { [channel]: _removed, ...rest } = current;
          const nextEntry = Object.keys(rest).length > 0 ? rest : undefined;
          const next = { ...s.pendingConfirmations };
          if (nextEntry === undefined) {
            delete next[id];
          } else {
            next[id] = nextEntry;
          }
          return { pendingConfirmations: next };
        }),
    }),
    {
      name: 'insta-accounts',
      version: 2,
      partialize: (s) => ({
        accounts: s.accounts,
        activeId: s.activeId,
        pendingConfirmations: s.pendingConfirmations,
      }),
      migrate: (persistedState) => migratePersistedAccountsState(persistedState),
    }
  )
);
