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

  it('normalizes alias decisions before resume requests', async () => {
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

    await smartEngagementApi.resume({
      thread_id: 'thread-2',
      decision: 'approve',
    });

    expect(postSpy).toHaveBeenCalledWith('/ai/smart-engagement/resume', {
      thread_id: 'thread-2',
      decision: 'approved',
    });
  });

  it('hydrates recommendation and risk from interrupt_payload when top-level fields are missing', async () => {
    const response: SmartEngagementResponse = {
      mode: 'execute',
      status: 'interrupted',
      thread_id: 'thread-3',
      interrupted: true,
      interrupt_payload: {
        target: 'target_user',
        draft_action: {
          action_type: 'comment',
          target_id: 'target_user',
          content: 'Nice post!',
        },
        relevance_reason: 'Strong audience match',
        risk_level: 'medium',
        risk_reason: 'Write action needs operator approval',
        rule_hits: ['write_action_requires_approval'],
      },
      brief_audit: [],
      audit_trail: [],
    };

    vi.spyOn(api, 'post').mockResolvedValue({
      data: response,
    } as AxiosResponse<SmartEngagementResponse>);

    const result = await smartEngagementApi.recommend({
      execution_mode: 'execute',
      goal: 'test goal',
      account_id: 'acct-1',
      max_targets: 3,
      max_actions_per_target: 1,
    });

    expect(result.recommendation).toEqual({
      target: 'target_user',
      action_type: 'comment',
      draft_content: 'Nice post!',
      reasoning: 'Strong audience match',
      expected_outcome: undefined,
    });
    expect(result.risk).toEqual({
      level: 'medium',
      rule_hits: ['write_action_requires_approval'],
      reasoning: 'Write action needs operator approval',
      requires_approval: true,
    });
  });
});
