import { api } from './client';
import type { ActivityLogEntry } from '../types';

export const logsApi = {
  get: (params?: { limit?: number; offset?: number; username?: string; event?: string }) =>
    api
      .get<{ entries: ActivityLogEntry[]; total: number }>('/logs', { params })
      .then((r) => r.data),
};
