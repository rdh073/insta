import { beforeEach, describe, expect, it } from 'vitest';
import type { Account } from '../types';
import {
  migratePersistedAccountsState,
  normalizeAccount,
  normalizeAccountPatch,
  selectTrackedAccountCount,
  useAccountStore,
} from './accounts';

const BASE_ACCOUNT: Account = {
  id: 'acct-1',
  username: 'alpha',
  status: 'active',
};

describe('accounts store migration and normalization', () => {
  beforeEach(() => {
    useAccountStore.setState({ accounts: [], activeId: null });
  });

  it('maps legacy error field into lastError', () => {
    const normalized = normalizeAccount({
      ...BASE_ACCOUNT,
      status: 'error',
      error: 'legacy failure',
    });
    expect(normalized.lastError).toBe('legacy failure');
  });

  it('normalizes legacy error in patch payloads', () => {
    const patch = normalizeAccountPatch({
      status: 'error',
      error: 'legacy failure',
    });
    expect(patch).toEqual({
      status: 'error',
      lastError: 'legacy failure',
    });
  });

  it('migrates persisted account payloads and preserves valid activeId', () => {
    const migrated = migratePersistedAccountsState({
      accounts: [
        { id: 'acct-1', username: 'alpha', status: 'error', error: 'legacy failure' },
        { id: 'invalid' },
      ],
      activeId: 'acct-1',
    });

    expect(migrated.accounts).toHaveLength(1);
    expect(migrated.accounts[0].lastError).toBe('legacy failure');
    expect(migrated.activeId).toBe('acct-1');
  });

  it('updateStatus writes canonical lastError fields', () => {
    useAccountStore.setState({ accounts: [BASE_ACCOUNT], activeId: null });
    useAccountStore.getState().updateStatus('acct-1', 'error', 'failed', 'bad_password');

    const updated = useAccountStore.getState().accounts[0];
    expect(updated.status).toBe('error');
    expect(updated.lastError).toBe('failed');
    expect(updated.lastErrorCode).toBe('bad_password');
  });
});

describe('selectTrackedAccountCount', () => {
  beforeEach(() => {
    useAccountStore.setState({ accounts: [], activeId: null });
  });

  it('returns zero when the store has no accounts', () => {
    expect(selectTrackedAccountCount({ accounts: [] })).toBe(0);
  });

  it('counts every managed account regardless of status or proxy assignment', () => {
    const accounts: Account[] = [
      { id: 'a', username: 'alpha', status: 'active', proxy: 'http://proxy:8080' },
      { id: 'b', username: 'bravo', status: 'error' },
      { id: 'c', username: 'charlie', status: 'challenge' },
    ];
    expect(selectTrackedAccountCount({ accounts })).toBe(3);
  });

  it('matches the managed-account count exposed by the Accounts page for the same store data', () => {
    const accounts: Account[] = [
      { ...BASE_ACCOUNT },
      { id: 'acct-2', username: 'bravo', status: 'idle' },
      { id: 'acct-3', username: 'charlie', status: '2fa_required' },
    ];
    useAccountStore.setState({ accounts });

    const storeState = useAccountStore.getState();
    // Accounts page renders `accounts.length` for its "Connected" stat; the
    // Proxy page must use the same denominator via this selector.
    expect(selectTrackedAccountCount(storeState)).toBe(storeState.accounts.length);
    expect(selectTrackedAccountCount(storeState)).toBe(3);
  });

  it('reacts to setAccounts mutations so the Proxy page metric stays in sync', () => {
    expect(selectTrackedAccountCount(useAccountStore.getState())).toBe(0);

    useAccountStore.getState().setAccounts([
      BASE_ACCOUNT,
      { id: 'acct-2', username: 'bravo', status: 'idle' },
      { id: 'acct-3', username: 'charlie', status: 'active' },
    ]);
    expect(selectTrackedAccountCount(useAccountStore.getState())).toBe(3);

    useAccountStore.getState().removeAccount('acct-2');
    expect(selectTrackedAccountCount(useAccountStore.getState())).toBe(2);
  });
});
