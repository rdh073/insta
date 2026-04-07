import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import type { AIProvider } from '../store/settings';

type OAuthProvider = Extract<AIProvider, 'openai_codex' | 'claude_code'>;

export interface DashboardLoginResponse {
  token: string;
  token_type: string;
  expires_in_hours: number;
}

export interface OAuthAuthorizeResponse {
  provider: OAuthProvider;
  authorization_url: string;
}

async function readErrorMessage(resp: Response, fallback: string): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: unknown };
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object') {
      const message = (detail as { message?: unknown }).message;
      const code = (detail as { code?: unknown }).code;
      if (typeof message === 'string' && typeof code === 'string') return `${code}: ${message}`;
      if (typeof message === 'string') return message;
      if (typeof code === 'string') return code;
    }
  } catch {
    // Fall back to text below
  }
  const text = await resp.text().catch(() => fallback);
  return text || fallback;
}

function buildDashboardHeaders(dashboardToken?: string): HeadersInit {
  const token = dashboardToken?.trim();
  const apiKey = useSettingsStore.getState().backendApiKey?.trim();
  const headers: Record<string, string> = {};
  if (apiKey) headers['X-API-Key'] = apiKey;
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function authStatus(backendUrl?: string): Promise<{ enabled: boolean }> {
  const url = buildApiUrl('/dashboard/auth/status', backendUrl);
  const resp = await fetch(url);
  if (!resp.ok) return { enabled: false };
  return resp.json();
}

export async function dashboardLogin(
  password: string,
  backendUrl?: string
): Promise<DashboardLoginResponse> {
  const url = buildApiUrl('/dashboard/auth/login', backendUrl);
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!resp.ok) {
    const txt = await readErrorMessage(resp, 'Login failed');
    throw new Error(`Dashboard login failed: ${txt}`);
  }
  return resp.json();
}

export async function createOAuthAuthorize(
  provider: OAuthProvider,
  redirectUri: string,
  dashboardToken?: string,
  backendUrl?: string
): Promise<OAuthAuthorizeResponse> {
  const url = buildApiUrl(`/dashboard/llm-providers/${provider}/oauth/authorize`, backendUrl);
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildDashboardHeaders(dashboardToken),
    },
    body: JSON.stringify({ redirectUri }),
  });
  if (!resp.ok) {
    const txt = await readErrorMessage(resp, 'Authorize failed');
    throw new Error(`OAuth authorize failed: ${txt}`);
  }
  return resp.json();
}

export interface OAuthExchangeResponse {
  message?: string;
  [key: string]: unknown;
}

export interface OAuthStatusResponse {
  provider: string;
  connected: boolean;
  expires_at_ms: number | null;
  account_id: string | null;
}

export async function getOAuthStatus(
  provider: OAuthProvider,
  backendUrl?: string,
  dashboardToken?: string,
): Promise<OAuthStatusResponse> {
  const url = buildApiUrl(`/dashboard/llm-providers/${provider}/oauth/status`, backendUrl);
  const resp = await fetch(url, { headers: buildDashboardHeaders(dashboardToken) });
  if (!resp.ok) return { provider, connected: false, expires_at_ms: null, account_id: null };
  return resp.json();
}

export async function revokeOAuth(
  provider: OAuthProvider,
  backendUrl?: string,
  dashboardToken?: string,
): Promise<void> {
  const url = buildApiUrl(`/dashboard/llm-providers/${provider}/oauth/revoke`, backendUrl);
  await fetch(url, { method: 'DELETE', headers: buildDashboardHeaders(dashboardToken) });
}

export async function createOAuthExchange(
  provider: OAuthProvider,
  code: string,
  state: string,
  backendUrl?: string,
  dashboardToken?: string,
): Promise<OAuthExchangeResponse> {
  const url = buildApiUrl(`/dashboard/llm-providers/${provider}/oauth/exchange`, backendUrl);
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...buildDashboardHeaders(dashboardToken) },
    body: JSON.stringify({ code, state }),
  });
  if (!resp.ok) {
    const txt = await readErrorMessage(resp, 'Failed to exchange code');
    throw new Error(txt);
  }
  try {
    return (await resp.json()) as OAuthExchangeResponse;
  } catch {
    return {};
  }
}
