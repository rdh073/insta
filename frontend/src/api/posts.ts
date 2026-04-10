import { api } from './client';
import { resolveApiBaseUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import { buildSseUrl } from './sse-token';
import type { PostJob } from '../types';

export const postsApi = {
  list: () => api.get<PostJob[]>('/posts').then((r) => r.data),

  /**
   * Connect to the SSE stream for real-time post job updates.
   * Returns a cleanup function to close the connection.
   */
  streamJobs: async (
    onUpdate: (jobs: PostJob[]) => void,
    onError?: (err: Event) => void,
  ): Promise<() => void> => {
    const { backendUrl } = useSettingsStore.getState();
    const baseUrl = resolveApiBaseUrl(backendUrl);
    const url = await buildSseUrl('/posts/stream', baseUrl);
    const source = new EventSource(url);

    source.onmessage = (event) => {
      try {
        const jobs: PostJob[] = JSON.parse(event.data);
        onUpdate(jobs);
      } catch {
        // skip malformed data
      }
    };

    source.onerror = (event) => {
      onError?.(event);
    };

    return () => source.close();
  },

  create: (data: {
    caption: string;
    mediaFiles: File[];
    accountIds: string[];
    scheduledAt?: string;
    mediaType?: string;
    thumbnail?: File;
    igtvTitle?: string;
    usertags?: Array<{ user_id: string; username?: string; x?: number; y?: number }>;
    location?: { name: string; lat?: number | null; lng?: number | null };
    extraData?: Record<string, unknown>;
  }) => {
    const form = new FormData();
    form.append('caption', data.caption);
    data.mediaFiles.forEach((f) => form.append('media', f));
    form.append('account_ids', JSON.stringify(data.accountIds));
    if (data.scheduledAt) form.append('scheduled_at', data.scheduledAt);
    if (data.mediaType) form.append('media_type', data.mediaType);
    if (data.thumbnail) form.append('thumbnail', data.thumbnail);
    if (data.igtvTitle) form.append('igtv_title', data.igtvTitle);
    if (data.usertags?.length) form.append('usertags', JSON.stringify(data.usertags));
    if (data.location?.name) form.append('location', JSON.stringify(data.location));
    if (data.extraData && Object.keys(data.extraData).length > 0)
      form.append('extra_data', JSON.stringify(data.extraData));
    return api.post<PostJob>('/posts', form).then((r) => r.data);
  },

  stop:   (id: string) => api.post(`/posts/${id}/stop`).then((r) => r.data),
  pause:  (id: string) => api.post(`/posts/${id}/pause`).then((r) => r.data),
  resume: (id: string) => api.post(`/posts/${id}/resume`).then((r) => r.data),
  delete: (id: string) => api.delete(`/posts/${id}`).then((r) => r.data),
};
