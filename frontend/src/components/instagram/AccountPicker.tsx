/* eslint-disable react-refresh/only-export-components */

import { useEffect, useState } from 'react';
import { selectActiveAccounts, useAccountStore } from '../../store/accounts';
import { cn } from '../../lib/cn';

const SESSION_KEY = 'ig-account-id';

interface AccountPickerProps {
  value: string;
  onChange: (id: string) => void;
  className?: string;
}

function getSessionStorage(): Storage | null {
  return typeof globalThis.sessionStorage !== 'undefined' ? globalThis.sessionStorage : null;
}

function readPersistedAccountId(): string | null {
  return getSessionStorage()?.getItem(SESSION_KEY) ?? null;
}

function writePersistedAccountId(id: string): void {
  getSessionStorage()?.setItem(SESSION_KEY, id);
}

function clearPersistedAccountId(): void {
  getSessionStorage()?.removeItem(SESSION_KEY);
}

export function reconcileAccountSelection(
  currentId: string,
  activeIds: string[],
  persistedId: string | null,
): string {
  if (currentId && activeIds.includes(currentId)) {
    return currentId;
  }
  if (persistedId && activeIds.includes(persistedId)) {
    return persistedId;
  }
  return activeIds[0] ?? '';
}

export function AccountPicker({ value, onChange, className }: AccountPickerProps) {
  const accounts = useAccountStore((s) => s.accounts);
  const active = selectActiveAccounts({ accounts });
  const activeIds = active.map((a) => a.id);
  const activeKey = activeIds.join('|');

  // Reconcile controlled selection whenever the active account set changes.
  useEffect(() => {
    const persisted = readPersistedAccountId();
    const next = reconcileAccountSelection(value, activeIds, persisted);
    if (next !== value) {
      onChange(next);
    }
    if (next) {
      writePersistedAccountId(next);
    } else {
      clearPersistedAccountId();
    }
  }, [value, activeKey]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const id = e.target.value;
    if (id) {
      writePersistedAccountId(id);
    } else {
      clearPersistedAccountId();
    }
    onChange(id);
  }

  if (active.length === 0) {
    return (
      <span className={cn('glass-chip text-[#f7768e]', className)}>
        No active accounts
      </span>
    );
  }

  return (
    <select value={value} onChange={handleChange} className={cn('glass-select', className)}>
      {active.map((a) => (
        <option key={a.id} value={a.id}>
          @{a.username}
          {a.fullName ? ` — ${a.fullName}` : ''}
        </option>
      ))}
    </select>
  );
}

/** Hook version — manages accountId state with sessionStorage persistence */
export function useAccountPicker() {
  const accounts = useAccountStore((s) => s.accounts);
  const active = selectActiveAccounts({ accounts });
  const activeIds = active.map((a) => a.id);
  const activeKey = activeIds.join('|');
  const [accountId, setAccountId] = useState<string>('');

  useEffect(() => {
    const persisted = readPersistedAccountId();
    const next = reconcileAccountSelection(accountId, activeIds, persisted);
    if (next !== accountId) {
      setAccountId(next);
    }
    if (next) {
      writePersistedAccountId(next);
    } else {
      clearPersistedAccountId();
    }
  }, [accountId, activeKey]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleChange(id: string) {
    if (id) {
      writePersistedAccountId(id);
    } else {
      clearPersistedAccountId();
    }
    setAccountId(id);
  }

  return { accountId, setAccountId: handleChange, active };
}
