import axios from 'axios';
import { resolveApiBaseUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly family?: string;

  constructor(message: string, status: number, code?: string, family?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.family = family;
  }
}

export const api = axios.create({
  timeout: 0, // no timeout — relogin and other Instagram operations can take >30s
});

api.interceptors.request.use((config) => {
  const { backendUrl, backendApiKey, dashboardToken } = useSettingsStore.getState();
  config.baseURL = resolveApiBaseUrl(backendUrl);
  config.headers = config.headers ?? {};
  if (backendApiKey) {
    config.headers['X-API-Key'] = backendApiKey;
  }
  if (dashboardToken) {
    config.headers['Authorization'] = `Bearer ${dashboardToken}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status: number = err.response?.status ?? 0;
    const data = err.response?.data;
    const detail = data?.detail;
    const code: string | undefined =
      detail && typeof detail === 'object' ? (detail as { code?: string }).code : undefined;
    const family: string | undefined =
      detail && typeof detail === 'object' ? (detail as { family?: string }).family : undefined;
    const message: string =
      (typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : null) ??
      err.message ??
      'Unknown error';
    return Promise.reject(new ApiError(message, status, code, family));
  }
);
