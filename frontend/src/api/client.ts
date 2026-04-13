import axios, { type AxiosError } from 'axios';
import { resolveApiBaseUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';

export const API_TIMEOUT_MS = {
  default: 20_000,
  relogin: 90_000,
  bulkRelogin: 120_000,
} as const;

const API_TRANSPORT_CODES = {
  canceled: 'ERR_CANCELED',
  timeout: 'ECONNABORTED',
} as const;

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly family?: string;
  readonly transportCode?: string;

  constructor(message: string, status: number, code?: string, family?: string, transportCode?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.family = family;
    this.transportCode = transportCode;
  }
}

export const api = axios.create({
  timeout: API_TIMEOUT_MS.default,
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
  (err: AxiosError) => {
    const status: number = err.response?.status ?? 0;
    const data = err.response?.data as { detail?: unknown } | undefined;
    const detail: unknown = data?.detail;
    const transportCode = typeof err.code === 'string' ? err.code : undefined;
    const code: string | undefined =
      detail && typeof detail === 'object' ? (detail as { code?: string }).code : undefined;
    const family: string | undefined =
      detail && typeof detail === 'object' ? (detail as { family?: string }).family : undefined;
    const timeoutMs = typeof err.config?.timeout === 'number' ? err.config.timeout : API_TIMEOUT_MS.default;
    const fallbackMessage =
      transportCode === API_TRANSPORT_CODES.timeout
        ? `Request timed out after ${Math.round(timeoutMs / 1000)}s. Please retry.`
        : transportCode === API_TRANSPORT_CODES.canceled
          ? 'Request was cancelled.'
          : null;
    const detailMessage =
      detail && typeof detail === 'object' && 'message' in detail && typeof (detail as { message?: unknown }).message === 'string'
        ? ((detail as { message: string }).message)
        : null;
    const message: string =
      (typeof detail === 'string' ? detail : detailMessage) ??
      fallbackMessage ??
      err.message ??
      'Unknown error';
    return Promise.reject(new ApiError(message, status, code, family, transportCode));
  }
);

export function isApiCanceledError(error: unknown): boolean {
  return error instanceof ApiError && error.transportCode === API_TRANSPORT_CODES.canceled;
}

export function isApiTimeoutError(error: unknown): boolean {
  return error instanceof ApiError && error.transportCode === API_TRANSPORT_CODES.timeout;
}
