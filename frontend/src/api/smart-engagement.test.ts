import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AxiosResponse } from 'axios';
import { smartEngagementApi, type SmartEngagementResponse } from './smart-engagement';
import { api } from './client';

describe('smartEngagementApi', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uses the shared api client for recommend requests', async () => {
    const response: SmartEngagementResponse = {
      mode: 'recommendation',
      status: 'done',
      interrupted: false,
      brief_audit: [],
      audit_trail: [],
    };

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: response,
    } as AxiosResponse<SmartEngagementResponse>);

    const result = await smartEngagementApi.recommend({
      execution_mode: 'recommendation',
      goal: 'test goal',
      account_id: 'acct-1',
      max_targets: 3,
      max_actions_per_target: 1,
    });

    expect(result).toEqual(response);
    expect(postSpy).toHaveBeenCalledWith('/ai/smart-engagement/recommend', expect.any(Object));
  });

  it('uses the shared api client for resume requests', async () => {
    const response: SmartEngagementResponse = {
      mode: 'execute',
      status: 'done',
      interrupted: false,
      brief_audit: [],
      audit_trail: [],
    };

    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      data: response,
    } as AxiosResponse<SmartEngagementResponse>);

    const result = await smartEngagementApi.resume({
      thread_id: 'thread-1',
      decision: 'approved',
    });

    expect(result).toEqual(response);
    expect(postSpy).toHaveBeenCalledWith('/ai/smart-engagement/resume', {
      thread_id: 'thread-1',
      decision: 'approved',
    });
  });
});
