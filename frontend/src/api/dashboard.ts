import { api } from './client';
import type { Account } from '../types';

export interface DashboardData {
  accounts: { total: number; active: number; error: number; idle: number };
  error_accounts: Pick<Account, 'id' | 'username' | 'proxy'>[];
  jobs_today: { total: number; completed: number; partial: number; failed: number };
  recent_jobs: unknown[];
  top_accounts: { id: string; username: string; followers: number; status: string }[];
}

export const dashboardApi = {
  get: () => api.get<DashboardData>('/dashboard').then((r) => r.data),
  relogin: (id: string) => api.post<Account>(`/accounts/${id}/relogin`).then((r) => r.data),
};
