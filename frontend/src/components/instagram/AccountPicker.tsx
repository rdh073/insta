/* eslint-disable react-refresh/only-export-components */

import { useEffect, useState } from 'react';
import { useAccountStore } from '../../store/accounts';
import { cn } from '../../lib/cn';

const SESSION_KEY = 'ig-account-id';

interface AccountPickerProps {
  value: string;
  onChange: (id: string) => void;
  className?: string;
}

export function AccountPicker({ value, onChange, className }: AccountPickerProps) {
  const accounts = useAccountStore((s) => s.accounts);
  const active = accounts.filter((a) => a.status === 'active');

  // Restore persisted selection or auto-select first active account
  useEffect(() => {
    if (value) return;
    const persisted = sessionStorage.getItem(SESSION_KEY);
    const target = persisted && active.find((a) => a.id === persisted) ? persisted : active[0]?.id;
    if (target) onChange(target);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const id = e.target.value;
    sessionStorage.setItem(SESSION_KEY, id);
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
  const active = accounts.filter((a) => a.status === 'active');
  const [accountId, setAccountId] = useState<string>(() => {
    const persisted = sessionStorage.getItem(SESSION_KEY);
    return (persisted && active.find((a) => a.id === persisted)) ? persisted : (active[0]?.id ?? '');
  });

  function handleChange(id: string) {
    sessionStorage.setItem(SESSION_KEY, id);
    setAccountId(id);
  }

  return { accountId, setAccountId: handleChange, active };
}
