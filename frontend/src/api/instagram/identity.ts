import { api } from '../client';
import { resolveApiBaseUrl } from '../../lib/api-base';
import { useSettingsStore } from '../../store/settings';
import type { AuthenticatedAccountProfile, PublicUserProfile } from '../../types/instagram/user';

export const identityApi = {
  getMe: (accountId: string) =>
    api
      .get<AuthenticatedAccountProfile>(`/instagram/identity/${accountId}/me`)
      .then((r) => r.data),

  getUserByUsername: (accountId: string, username: string) =>
    api
      .get<PublicUserProfile>(`/instagram/identity/${accountId}/user/${encodeURIComponent(username.replace(/^@/, ''))}`)
      .then((r) => r.data),

  getFollowers: (accountId: string, username: string, amount = 50) =>
    api
      .get<PublicUserProfile[]>(`/instagram/relationships/${accountId}/followers`, {
        params: { username, amount },
      })
      .then((r) => r.data),

  getFollowing: (accountId: string, username: string, amount = 50) =>
    api
      .get<PublicUserProfile[]>(`/instagram/relationships/${accountId}/following`, {
        params: { username, amount },
      })
      .then((r) => r.data),

  followUser: (accountId: string, targetUsername: string) =>
    api
      .post<{ success: boolean; action: string; target: string }>(
        `/instagram/relationships/${accountId}/follow`,
        null,
        { params: { target_username: targetUsername.replace(/^@/, '') } },
      )
      .then((r) => r.data),

  unfollowUser: (accountId: string, targetUsername: string) =>
    api
      .post<{ success: boolean; action: string; target: string }>(
        `/instagram/relationships/${accountId}/unfollow`,
        null,
        { params: { target_username: targetUsername.replace(/^@/, '') } },
      )
      .then((r) => r.data),

  /**
   * Batch follow/unfollow via SSE stream.
   * Calls onResult for each completed action, onDone when finished.
   * Returns an abort function.
   */
  batchRelationship: (
    action: 'follow' | 'unfollow',
    payload: { account_ids: string[]; targets: string[]; concurrency?: number; delay_between?: number },
    onResult: (result: {
      account_id: string;
      account: string;
      target: string;
      action: string;
      success: boolean;
      error?: string;
      completed: number;
      total: number;
    }) => void,
    onDone: () => void,
    onError: (err: Error) => void,
  ): (() => void) => {
    const controller = new AbortController();
    const baseUrl = resolveApiBaseUrl(useSettingsStore.getState().backendUrl);
    const url = `${baseUrl}/instagram/relationships/batch/${action}`;

    const apiKey = useSettingsStore.getState().backendApiKey?.trim();
    const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
    if (apiKey) fetchHeaders['X-API-Key'] = apiKey;

    fetch(url, {
      method: 'POST',
      headers: fetchHeaders,
      body: JSON.stringify({
        account_ids: payload.account_ids,
        targets: payload.targets,
        concurrency: payload.concurrency ?? 3,
        delay_between: payload.delay_between ?? 1.0,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text().catch(() => 'Unknown error');
          throw new Error(`Batch ${action} failed: ${text}`);
        }
        const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
        if (!contentType.includes('text/event-stream')) {
          const text = await response.text().catch(() => 'Unknown error');
          throw new Error(
            `Batch ${action} expected text/event-stream but received '${contentType || 'unknown'}': ${text}`,
          );
        }
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';
        let sawEvent = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            sawEvent = true;
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              onDone();
              return;
            }
            let event: Record<string, unknown>;
            try {
              event = JSON.parse(data) as Record<string, unknown>;
            } catch {
              // skip malformed SSE lines
              continue;
            }
            if (event.type === 'run_error') {
              const message = typeof event.message === 'string'
                ? event.message
                : `Batch ${action} failed`;
              throw new Error(message);
            }
            onResult(event as {
              account_id: string;
              account: string;
              target: string;
              action: string;
              success: boolean;
              error?: string;
              completed: number;
              total: number;
            });
          }
        }
        if (!sawEvent) {
          throw new Error(`Batch ${action} stream ended without events`);
        }
        onDone();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') onError(err);
      });

    return () => controller.abort();
  },
};
