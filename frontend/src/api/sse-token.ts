import { api } from './client';
import { useSettingsStore } from '../store/settings';

interface SseTokenResponse {
  token: string;
  expires_in: number;
  required: boolean;
}

/**
 * Fetch a short-lived SSE token from the backend.
 *
 * Tokens are reusable within their TTL (5 minutes) so EventSource
 * auto-reconnect keeps working after transient disconnects.
 * Use ?sse_token= instead of ?x_api_key= to keep the raw API key out of
 * server access logs.
 *
 * Returns null when API key auth is not configured (no param needed).
 */
export async function fetchSseToken(): Promise<string | null> {
  const apiKey = useSettingsStore.getState().backendApiKey?.trim();
  if (!apiKey) return null;
  const data = await api.post<SseTokenResponse>('/sse/token').then((r) => r.data);
  return data.required ? data.token : null;
}

/**
 * Build an SSE URL using a reusable token instead of the raw API key.
 * Falls back to no auth param when API key auth is not configured.
 */
export async function buildSseUrl(path: string, baseUrl: string): Promise<string> {
  const token = await fetchSseToken();
  if (!token) return `${baseUrl}${path}`;
  return `${baseUrl}${path}?sse_token=${encodeURIComponent(token)}`;
}
