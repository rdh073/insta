import { ExternalLink, Key, ShieldCheck, CheckCircle2, AlertTriangle, X } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { PROVIDERS, type AIProvider } from '../../../store/settings';
import type { ProviderOAuth } from '../hooks/useProviderOAuth';

interface Props {
  provider: AIProvider;
  isOAuthProvider: boolean;
  effectiveBaseUrl: string;
  onBaseUrlChange: (v: string) => void;
  apiKey: string;
  onApiKeyChange: (v: string) => void;
  oauth: ProviderOAuth;
}

/** Returns true if the token expires within 24 hours. */
function isNearExpiry(expiresAtMs: number | null): boolean {
  if (expiresAtMs === null) return false;
  return expiresAtMs - Date.now() < 24 * 60 * 60 * 1000;
}

function formatExpiry(expiresAtMs: number | null): string {
  if (expiresAtMs === null) return 'No expiry info';
  const diff = expiresAtMs - Date.now();
  if (diff <= 0) return 'Expired';
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return 'Expires in <1 h';
  if (hours < 24) return `Expires in ${hours} h`;
  const days = Math.floor(hours / 24);
  return `Expires in ${days}d`;
}

export function ProviderAccessCard({
  provider,
  isOAuthProvider,
  effectiveBaseUrl,
  onBaseUrlChange,
  apiKey,
  onApiKeyChange,
  oauth,
}: Props) {
  const cfg = PROVIDERS[provider];
  const { connected, expiresAtMs, accountId } = oauth.status;
  const nearExpiry = isNearExpiry(expiresAtMs);

  return (
    <div className="space-y-4 rounded-[1.25rem] border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] p-4">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-[rgba(187,154,247,0.14)]">
          {isOAuthProvider ? (
            <ShieldCheck className="h-3.5 w-3.5 text-[#bb9af7]" aria-hidden="true" />
          ) : (
            <Key className="h-3.5 w-3.5 text-[#bb9af7]" aria-hidden="true" />
          )}
        </div>
        <p className="text-sm font-semibold text-[#dbe6ff]">
          {cfg.label} &mdash; {isOAuthProvider ? 'OAuth' : 'API Key'}
        </p>
      </div>

      {/* Base URL override (only for providers that have a defaultBaseUrl) */}
      {cfg.defaultBaseUrl !== undefined && (
        <Input
          id={`settings-base-url-${provider}`}
          label="Base URL"
          value={effectiveBaseUrl}
          onChange={(e) => onBaseUrlChange(e.target.value)}
          placeholder={cfg.defaultBaseUrl}
          hint="Override if the provider gateway runs on a different host or port."
        />
      )}

      {/* API key or OAuth flow */}
      {!isOAuthProvider ? (
        <>
          <Input
            id={`settings-api-key-${provider}`}
            label={`${cfg.label} API Key`}
            type="password"
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            placeholder={cfg.placeholder}
            hint={cfg.hint}
          />
          <p className="text-xs text-[#59658c]">
            API keys stay in browser localStorage and are forwarded only when you call the backend from this client.
          </p>
        </>
      ) : connected ? (
        /* ── Connected state ─────────────────────────────────────────── */
        <div className="space-y-3">
          <div
            className={`flex items-start justify-between gap-3 rounded-[1rem] border p-3 ${
              nearExpiry
                ? 'border-[rgba(224,175,104,0.20)] bg-[rgba(224,175,104,0.06)]'
                : 'border-[rgba(158,206,106,0.16)] bg-[rgba(158,206,106,0.05)]'
            }`}
          >
            <div className="flex items-start gap-2">
              {nearExpiry ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#e0af68]" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#9ece6a]" aria-hidden="true" />
              )}
              <div>
                <p className={`text-sm font-medium ${nearExpiry ? 'text-[#e0af68]' : 'text-[#9ece6a]'}`}>
                  {nearExpiry ? 'Token expiring soon' : 'Connected'}
                </p>
                {accountId && (
                  <p className="mt-0.5 text-xs text-[#8e9ac0]">Account: {accountId}</p>
                )}
                <p className="mt-0.5 text-xs text-[#59658c]">{formatExpiry(expiresAtMs)}</p>
                {nearExpiry && (
                  <p className="mt-1 text-xs text-[#e0af68]">
                    Re-authenticate before the token expires. Auto-refresh is not yet supported.
                  </p>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={oauth.handleRevoke}
              disabled={oauth.busy}
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[#59658c] transition-colors hover:bg-[rgba(247,118,142,0.12)] hover:text-[#f7768e] disabled:opacity-40"
              aria-label={`Disconnect ${cfg.label}`}
              title={`Disconnect ${cfg.label}`}
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>

          {/* Allow re-authentication even when connected */}
          {oauth.codeEntry ? (
            <div className="space-y-3">
              <div className="flex flex-col gap-2">
                <label htmlFor={`settings-oauth-code-${provider}`} className="field-label">
                  Authorization code
                </label>
                <input
                  id={`settings-oauth-code-${provider}`}
                  value={oauth.code}
                  onChange={(e) => oauth.setCode(e.target.value)}
                  placeholder={
                    provider === 'openai_codex'
                      ? 'Paste redirect URL here (http://localhost:1455/auth/callback?code=...)'
                      : 'Paste authorization code here...'
                  }
                  className="glass-field w-full text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={oauth.handleSubmit} loading={oauth.busy} size="sm">
                  Exchange Code
                </Button>
                <Button variant="ghost" size="sm" onClick={oauth.handleCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button onClick={oauth.handleConnect} loading={oauth.busy} variant="ghost" size="sm">
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              Re-authenticate
            </Button>
          )}
        </div>
      ) : (
        /* ── Not connected state ─────────────────────────────────────── */
        <>
          <p className="text-sm text-[#8e9ac0]">
            {provider === 'claude_code'
              ? 'Authorize in a browser window, then copy the code shown on the Anthropic page and paste it below.'
              : 'Authorize in a browser window. After login, the browser will redirect to localhost:1455 (connection refused is normal). Copy the full URL from the address bar and paste it below.'}
          </p>

          {oauth.codeEntry ? (
            <div className="space-y-3">
              <div className="flex flex-col gap-2">
                <label htmlFor={`settings-oauth-code-${provider}`} className="field-label">
                  Authorization code
                </label>
                <input
                  id={`settings-oauth-code-${provider}`}
                  value={oauth.code}
                  onChange={(e) => oauth.setCode(e.target.value)}
                  placeholder={
                    provider === 'openai_codex'
                      ? 'Paste redirect URL here (http://localhost:1455/auth/callback?code=...)'
                      : 'Paste authorization code here...'
                  }
                  className="glass-field w-full text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={oauth.handleSubmit} loading={oauth.busy} size="sm">
                  Exchange Code
                </Button>
                <Button variant="ghost" size="sm" onClick={oauth.handleCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button onClick={oauth.handleConnect} loading={oauth.busy} variant="secondary">
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              {oauth.busy ? 'Connecting...' : `Connect ${cfg.label} OAuth`}
            </Button>
          )}

          <p className="text-xs text-[#59658c]">
            OAuth credentials are exchanged through the dashboard API. Use durable SQL persistence
            and an ENCRYPTION_KEY in production.
          </p>
        </>
      )}
    </div>
  );
}
