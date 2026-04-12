import { api } from './client';
import type { ActivityLogEntry } from '../types';

export const logsApi = {
  get: (
    params?: { limit?: number; offset?: number; username?: string; event?: string },
    options?: { signal?: AbortSignal }
  ) =>
    api
      .get<{ entries: ActivityLogEntry[]; total: number }>(
        '/logs',
        options?.signal ? { params, signal: options.signal } : { params },
      )
      .then((r) => r.data),
};
