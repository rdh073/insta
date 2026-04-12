import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AxiosResponse } from 'axios';
import { api, API_TIMEOUT_MS } from './client';
import { accountsApi } from './accounts';

describe('accountsApi timeout overrides', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses long timeout override for relogin', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: { id: 'acct-1', username: 'alpha' },
    } as AxiosResponse<unknown>);

    await accountsApi.relogin('acct-1');

    expect(postSpy).toHaveBeenCalledWith(
      '/accounts/acct-1/relogin',
      undefined,
      { timeout: API_TIMEOUT_MS.relogin },
    );
  });

  it('uses bulk timeout override for bulk relogin', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: [],
    } as AxiosResponse<unknown>);

    await accountsApi.bulkRelogin(['acct-1', 'acct-2']);

    expect(postSpy).toHaveBeenCalledWith(
      '/accounts/bulk/relogin',
      { account_ids: ['acct-1', 'acct-2'] },
      { timeout: API_TIMEOUT_MS.bulkRelogin },
    );
  });
});
