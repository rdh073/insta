import { beforeEach, describe, expect, it } from 'vitest';
import type { Account } from '../types';
import {
  migratePersistedAccountsState,
  normalizeAccount,
  normalizeAccountPatch,
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
