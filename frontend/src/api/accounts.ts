import { api } from './client';
import type { Account, BulkAccountResult, ProxyCheckResult } from '../types';

export const accountsApi = {
  list: () => api.get<Account[]>('/accounts').then((r) => r.data),
  bulkHydrateProfiles: () => api.post<{ queued: number }>('/accounts/bulk/hydrate-profiles').then((r) => r.data),
  refreshCounts: (id: string) => api.post<{ status: string }>(`/accounts/${id}/refresh-counts`).then((r) => r.data),

  login: (username: string, password: string, proxy?: string, totp_secret?: string) =>
    api.post<Account>('/accounts/login', { username, password, proxy, totp_secret }).then((r) => r.data),

  verify2fa: (account_id: string, code: string, is_totp?: boolean) =>
    api.post<Account>('/accounts/login/2fa', { account_id, code, is_totp }).then((r) => r.data),

  setupTotp: (account_id: string) =>
    api.post<{ account_id: string; secret: string; provisioning_uri: string; manual_entry_key: string }>(
      `/accounts/${account_id}/totp/setup`
    ).then((r) => r.data),

  verifyTotp: (account_id: string, secret: string, code: string) =>
    api.post<{ status: string; message: string }>(
      `/accounts/${account_id}/totp/verify`,
      { account_id, secret, code }
    ).then((r) => r.data),

  disableTotp: (account_id: string) =>
    api.delete<{ status: string; message: string }>(`/accounts/${account_id}/totp`).then((r) => r.data),

  logout: (id: string) => api.delete(`/accounts/${id}`).then((r) => r.data),

  importFile: (text: string) =>
    api.post<Account[]>('/accounts/import', { text }).then((r) => r.data),

  exportSessions: () =>
    api.get('/accounts/sessions/export', { responseType: 'blob' }).then((r) => r.data),

  importSessions: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post<Account[]>('/accounts/sessions/import', form).then((r) => r.data);
  },

  setProxy: (id: string, proxy: string) =>
    api.patch(`/accounts/${id}/proxy`, { proxy }).then((r) => r.data),

  relogin: (id: string) =>
    api.post<Account>(`/accounts/${id}/relogin`).then((r) => r.data),

  bulkRelogin: (ids: string[]) =>
    api.post<BulkAccountResult[]>('/accounts/bulk/relogin', { account_ids: ids }).then((r) => r.data),

  bulkLogout: (ids: string[]) =>
    api.post<BulkAccountResult[]>('/accounts/bulk/logout', { account_ids: ids }).then((r) => r.data),

  bulkSetProxy: (ids: string[], proxy: string) =>
    api.patch<BulkAccountResult[]>('/accounts/bulk/proxy', { account_ids: ids, proxy }).then((r) => r.data),

  checkProxy: (proxyUrl: string) =>
    api.post<ProxyCheckResult>('/accounts/proxy/check', { proxy: proxyUrl }).then((r) => r.data),

  checkAccountProxy: (id: string) =>
    api.get<ProxyCheckResult>(`/accounts/${id}/proxy/check`).then((r) => r.data),
};
