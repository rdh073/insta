import { useState, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import { createOAuthAuthorize, createOAuthExchange, getOAuthStatus, revokeOAuth } from '../../../api/dashboard-oauth';
import { PROVIDERS, useSettingsStore, type AIProvider } from '../../../store/settings';

type OAuthProvider = Extract<AIProvider, 'openai_codex' | 'claude_code'>;

export interface OAuthStatus {
  connected: boolean;
  expiresAtMs: number | null;
  accountId: string | null;
}

export interface ProviderOAuth {
  busy: boolean;
  codeEntry: boolean;
  code: string;
  status: OAuthStatus;
  setCode: (v: string) => void;
  handleConnect: () => Promise<void>;
  handleSubmit: () => Promise<void>;
  handleCancel: () => void;
  handleRevoke: () => Promise<void>;
}

export function useProviderOAuth(provider: AIProvider, backendUrl: string): ProviderOAuth {
  const [busy, setBusy] = useState(false);
  const [codeEntry, setCodeEntry] = useState(false);
  const [code, setCode] = useState('');
  const [oauthState, setOauthState] = useState('');
  const [status, setStatus] = useState<OAuthStatus>({ connected: false, expiresAtMs: null, accountId: null });
  const dashboardToken = useSettingsStore((s) => s.dashboardToken);

  const isOAuthProvider = provider === 'openai_codex' || provider === 'claude_code';

  const fetchStatus = useCallback(async () => {
    if (!isOAuthProvider) return;
    try {
      const s = await getOAuthStatus(provider as OAuthProvider, backendUrl, dashboardToken);
      setStatus({ connected: s.connected, expiresAtMs: s.expires_at_ms, accountId: s.account_id });
    } catch {
      // backend unreachable — keep previous state
    }
  }, [provider, isOAuthProvider, backendUrl, dashboardToken]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleConnect = useCallback(async () => {
    if (!isOAuthProvider) return;
    setBusy(true);
    try {
      const redirectUri = `${window.location.origin}/oauth/callback`;
      const auth = await createOAuthAuthorize(
        provider as OAuthProvider,
        redirectUri,
        dashboardToken,
        backendUrl,
      );
      try {
        const stateParam = new URL(auth.authorization_url).searchParams.get('state') ?? '';
        setOauthState(stateParam);
      } catch {
        setOauthState('');
      }
      window.open(auth.authorization_url, '_blank', 'noopener,noreferrer');
      setCodeEntry(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'OAuth authorize failed');
    } finally {
      setBusy(false);
    }
  }, [provider, isOAuthProvider, backendUrl]);

  const handleSubmit = useCallback(async () => {
    if (!code.trim()) return;
    setBusy(true);
    try {
      const result = await createOAuthExchange(
        provider as OAuthProvider,
        code.trim(),
        oauthState,
        backendUrl,
        dashboardToken,
      );
      toast.success(
        typeof result.message === 'string'
          ? result.message
          : `${PROVIDERS[provider].label} connected!`,
      );
      setCodeEntry(false);
      setCode('');
      setOauthState('');
      await fetchStatus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to exchange code');
    } finally {
      setBusy(false);
    }
  }, [code, oauthState, provider, backendUrl, fetchStatus]);

  const handleCancel = useCallback(() => {
    setCodeEntry(false);
    setCode('');
    setOauthState('');
  }, []);

  const handleRevoke = useCallback(async () => {
    setBusy(true);
    try {
      await revokeOAuth(provider as OAuthProvider, backendUrl, dashboardToken);
      setStatus({ connected: false, expiresAtMs: null, accountId: null });
      toast.success(`${PROVIDERS[provider].label} disconnected`);
    } catch {
      toast.error('Failed to disconnect');
    } finally {
      setBusy(false);
    }
  }, [provider, backendUrl, dashboardToken]);

  return { busy, codeEntry, code, status, setCode, handleConnect, handleSubmit, handleCancel, handleRevoke };
}
