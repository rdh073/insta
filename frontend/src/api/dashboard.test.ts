import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AxiosResponse } from 'axios';
import { api, API_TIMEOUT_MS } from './client';
import { dashboardApi, DashboardContractError } from './dashboard';

describe('dashboardApi contract normalization', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns canonical snake_case dashboard payloads unchanged', async () => {
    const payload = {
      contract_version: 1,
      accounts: { total: 3, active: 2, idle: 0, error: 1 },
      error_accounts: [{ id: 'acct-1', username: 'alpha', proxy: 'http://proxy:8080' }],
      jobs_today: { total: 5, completed: 3, partial: 1, failed: 1 },
      recent_jobs: [
        {
          id: 'job-1',
          caption: 'Launch day',
          status: 'completed',
          targets: [{ accountId: 'acct-1' }],
        },
      ],
      top_accounts: [{ id: 'acct-1', username: 'alpha', followers: 1200, status: 'active' }],
    };

    const getSpy = vi.spyOn(api, 'get').mockResolvedValue({
      data: payload,
    } as AxiosResponse<unknown>);

    const result = await dashboardApi.get();

    expect(getSpy).toHaveBeenCalledWith('/dashboard');
    expect(result).toEqual(payload);
  });

  it('maps legacy mixed keys into canonical snake_case shape', async () => {
    const legacyPayload = {
      accounts: {
        total: 2,
        active: 1,
        idle: 0,
        error: 1,
        errorAccounts: [{ id: 'acct-2', username: 'beta', proxy: null }],
      },
      jobsToday: { total: 4, completed: 2, partial: 1, failed: 1 },
      recentJobs: [
        {
          id: 'job-2',
          caption: 'Legacy contract',
          status: 'partial',
          targets: [{ accountId: 'acct-2', scheduledAt: '2026-04-13T08:00:00Z' }],
        },
      ],
      topAccounts: [{ id: 'acct-2', username: 'beta', followers: 800, status: 'error' }],
    };

    vi.spyOn(api, 'get').mockResolvedValue({
      data: legacyPayload,
    } as AxiosResponse<unknown>);

    const result = await dashboardApi.get();

    expect(result).toEqual({
      contract_version: 1,
      accounts: { total: 2, active: 1, idle: 0, error: 1 },
      error_accounts: [{ id: 'acct-2', username: 'beta', proxy: undefined }],
      jobs_today: { total: 4, completed: 2, partial: 1, failed: 1 },
      recent_jobs: [
        {
          id: 'job-2',
          caption: 'Legacy contract',
          status: 'partial',
          targets: [{ accountId: 'acct-2', scheduledAt: '2026-04-13T08:00:00Z' }],
        },
      ],
      top_accounts: [{ id: 'acct-2', username: 'beta', followers: 800, status: 'error' }],
    });
  });

  it('throws DashboardContractError when required keys are missing', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        accounts: { total: 1, active: 1, idle: 0, error: 0 },
        jobsToday: { total: 1 },
        recentJobs: [],
        topAccounts: [],
      },
    } as AxiosResponse<unknown>);

    await expect(dashboardApi.get()).rejects.toBeInstanceOf(DashboardContractError);
  });

  it('uses long timeout override for relogin', async () => {
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: { id: 'acct-1', username: 'alpha' },
    } as AxiosResponse<unknown>);

    await dashboardApi.relogin('acct-1');

    expect(postSpy).toHaveBeenCalledWith(
      '/accounts/acct-1/relogin',
      undefined,
      { timeout: API_TIMEOUT_MS.relogin },
    );
  });
});
