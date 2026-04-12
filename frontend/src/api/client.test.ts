import { describe, expect, it } from 'vitest';
import type { InternalAxiosRequestConfig } from 'axios';
import { api } from './client';
import { useSettingsStore } from '../store/settings';

function getRequestInterceptor(): (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig {
  const handlers = (api.interceptors.request as unknown as {
    handlers?: Array<{ fulfilled?: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }>;
  }).handlers;
  const fulfilled = handlers?.find((handler) => typeof handler.fulfilled === 'function')?.fulfilled;
  if (!fulfilled) {
    throw new Error('Missing axios request interceptor');
  }
  return fulfilled;
}

describe('api client interceptor', () => {
  it('injects X-API-Key and Authorization from settings store', () => {
    useSettingsStore.setState({
      backendUrl: 'http://127.0.0.1:8000',
      backendApiKey: 'secure-key',
      dashboardToken: 'dash-token',
    });

    const interceptor = getRequestInterceptor();
    const next = interceptor({ headers: {} } as InternalAxiosRequestConfig);

    expect(next.headers['X-API-Key']).toBe('secure-key');
    expect(next.headers['Authorization']).toBe('Bearer dash-token');
  });
});
