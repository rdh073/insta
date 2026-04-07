import { api } from './client';
import type { PoolProxy, ProxyCheckResult, ProxyImportSummary, ProxyRecheckSummary } from '../types';

export const proxiesApi = {
  import: (text: string) =>
    api.post<ProxyImportSummary>('/proxies/import', { text }).then((r) => r.data),

  list: () =>
    api.get<PoolProxy[]>('/proxies').then((r) => r.data),

  delete: (host: string, port: number) =>
    api.delete(`/proxies/${host}/${port}`).then((r) => r.data),

  check: (url: string) =>
    api.post<ProxyCheckResult>('/proxies/check', { url }).then((r) => r.data),

  recheck: () =>
    api.post<ProxyRecheckSummary>('/proxies/recheck').then((r) => r.data),
};
