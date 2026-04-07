import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';

type CallbackView = 'loading' | 'success' | 'error';

function normalizeProviderLabel(provider: string | null): string {
  if (!provider) return 'provider';
  if (provider === 'openai_codex') return 'OpenAI Codex';
  if (provider === 'claude_code') return 'Claude Code';
  return provider;
}

/**
 * Detects the provider from the OAuth state token (base64url-encoded JSON).
 * Returns null if the state cannot be decoded.
 */
function detectProviderFromState(state: string): string | null {
  try {
    const payloadSegment = state.split('.')[0];
    const padding = '='.repeat((4 - (payloadSegment.length % 4)) % 4);
    const raw = atob(payloadSegment.replace(/-/g, '+').replace(/_/g, '/') + padding);
    const payload = JSON.parse(raw);
    return typeof payload?.provider === 'string' ? payload.provider : null;
  } catch {
    return null;
  }
}

export function OAuthCallbackPage() {
  const [params] = useSearchParams();
  const backendUrl = useSettingsStore((s) => s.backendUrl);

  // Two modes:
  // 1. Raw OAuth redirect: has `code` + `state` query params → exchange with backend
  // 2. Processed result: has `status` + `provider` params → display result
  const code = params.get('code');
  const state = params.get('state');
  const statusParam = params.get('status');
  const providerParam = params.get('provider');
  const message = params.get('message');

  const isRawCallback = Boolean(code && state);

  const [view, setView] = useState<CallbackView>(
    isRawCallback ? 'loading' : statusParam === 'connected' ? 'success' : statusParam === 'error' ? 'error' : 'loading',
  );
  const [resultMessage, setResultMessage] = useState(message || '');
  const [resolvedProvider, setResolvedProvider] = useState(providerParam || '');

  useEffect(() => {
    if (!isRawCallback) return;

    const provider = detectProviderFromState(state!) || 'claude_code';
    setResolvedProvider(provider);

    const exchangeUrl = buildApiUrl(
      `/dashboard/llm-providers/${provider}/oauth/exchange`,
      backendUrl,
    );

    const apiKey = useSettingsStore.getState().backendApiKey?.trim();
    const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
    if (apiKey) fetchHeaders['X-API-Key'] = apiKey;

    fetch(exchangeUrl, {
      method: 'POST',
      headers: fetchHeaders,
      body: JSON.stringify({ code, state }),
    })
      .then(async (resp) => {
        const data = await resp.json().catch(() => ({}));
        if (resp.ok) {
          setView('success');
          setResultMessage(data.message || `${provider} OAuth connected successfully.`);
        } else {
          setView('error');
          const detail = data.detail;
          setResultMessage(
            typeof detail === 'string'
              ? detail
              : typeof detail?.message === 'string'
                ? detail.message
                : 'Failed to exchange OAuth authorization code.',
          );
        }
      })
      .catch(() => {
        setView('error');
        setResultMessage('Network error while exchanging OAuth code.');
      });
  }, [isRawCallback, code, state, backendUrl]);

  const providerLabel = normalizeProviderLabel(resolvedProvider);
  const displayMessage =
    resultMessage ||
    (view === 'success'
      ? `${providerLabel} OAuth connected successfully.`
      : view === 'error'
        ? `OAuth callback failed for ${providerLabel}.`
        : 'Exchanging authorization code with backend…');

  const icon =
    view === 'loading' ? (
      <Loader2 className="h-7 w-7 animate-spin text-[#7dcfff]" />
    ) : view === 'success' ? (
      <CheckCircle2 className="h-7 w-7 text-[#9ece6a]" />
    ) : (
      <AlertTriangle className="h-7 w-7 text-[#f7768e]" />
    );

  return (
    <div className="page-shell flex min-h-screen max-w-3xl items-center justify-center">
      <Card className="w-full max-w-xl overflow-hidden p-0">
        <div className="page-header-shell rounded-none border-0 border-b border-[rgba(162,179,229,0.12)] px-6 py-6">
          <div className="relative z-10 flex items-start gap-4">
            <div className="glass-panel glass-panel-soft flex h-14 w-14 shrink-0 items-center justify-center rounded-[1.4rem] border-[rgba(125,207,255,0.22)]">
              <ShieldCheck className="h-6 w-6 text-[#7dcfff]" />
            </div>
            <div>
              <p className="text-kicker">OAuth Handoff</p>
              <h1 className="mt-2 text-2xl font-semibold text-[#eef4ff]">Authorization Result</h1>
              <p className="mt-2 text-sm text-[#95a4cc]">
                {isRawCallback
                  ? 'Exchanging authorization code with the backend…'
                  : 'The dashboard completed the provider callback and redirected back with the connection status.'}
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-5 px-6 py-6">
          <div className="flex items-start gap-4 rounded-[1.4rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-4">
            <div className="mt-0.5 flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.05)]">
              {icon}
            </div>
            <div>
              <p className="text-sm font-semibold text-[#eef4ff]">
                {view === 'loading' ? 'Connecting…' : view === 'success' ? 'Connected' : 'Connection failed'}
              </p>
              <p className={view === 'error' ? 'mt-2 text-sm text-[#ffbfd0]' : 'mt-2 text-sm text-[#95a4cc]'}>
                {displayMessage}
              </p>
            </div>
          </div>

          <Link
            to="/settings"
            className="inline-flex min-h-11 w-full items-center justify-center rounded-[1.1rem] border border-[rgba(162,179,229,0.16)] bg-[rgba(255,255,255,0.05)] px-4 py-2.5 text-sm font-semibold text-[#eef4ff] transition-all duration-200 hover:border-[rgba(125,207,255,0.28)] hover:bg-[rgba(125,207,255,0.12)]"
          >
            Return to Settings
          </Link>
        </div>
      </Card>
    </div>
  );
}
