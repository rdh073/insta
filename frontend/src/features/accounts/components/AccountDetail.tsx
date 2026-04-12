import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, Clock, Globe, KeyRound, Lock, Loader, RotateCcw, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { accountsApi } from '../../../api/accounts';
import type { RateLimitEntry } from '../../../api/accounts';
import { ApiError } from '../../../api/client';
import { logsApi } from '../../../api/logs';
import type { Account, ActivityLogEntry } from '../../../types';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { useAccountStore } from '../../../store/accounts';
import { AccountAvatar } from './AccountAvatar';
import { CredentialsModal } from './CredentialsModal';
import { statusBadge } from './StatusBadge';
import { auditMeta, formatCooldown, formatRelativeTime, isChallengeFailure } from './account-helpers';

export function AccountDetail({
  account,
  onSetupTOTP,
  rateLimitInfo,
  onClearRateLimit,
}: {
  account: Account;
  onSetupTOTP?: (accountId: string) => void;
  rateLimitInfo?: RateLimitEntry;
  onClearRateLimit?: (accountId: string) => void;
}) {
  const removeAccount = useAccountStore((s) => s.removeAccount);
  const patchAccount = useAccountStore((s) => s.patchAccount);
  const updateStatus = useAccountStore((s) => s.updateStatus);
  const [relogging, setRelogging] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [clearingLimit, setClearingLimit] = useState(false);
  const [showCredentials, setShowCredentials] = useState(false);
  const [auditLog, setAuditLog] = useState<ActivityLogEntry[]>([]);

  useEffect(() => {
    logsApi.get({ username: account.username, limit: 6 }).then((res) => {
      setAuditLog(res.entries);
    }).catch(() => {});
  }, [account.username]);

  const handleClearRateLimit = async () => {
    if (clearingLimit) return;
    setClearingLimit(true);
    try {
      await accountsApi.clearRateLimit(account.id);
      onClearRateLimit?.(account.id);
      toast.success(`Rate limit cleared for @${account.username}`);
    } catch {
      toast.error('Failed to clear rate limit');
    } finally {
      setClearingLimit(false);
    }
  };

  const TRANSIENT_CODES = new Set([
    'connection_error', 'request_error', 'json_decode_error', 'graphql_error',
    'throttled', 'rate_limit', 'wait_required', 'incomplete_read',
    'request_timeout', 'unknown_instagram_error',
  ]);

  const handleRelogin = async () => {
    if (relogging) return;
    setRelogging(true);
    updateStatus(account.id, 'logging_in');

    let lastError: ApiError | null = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      if (attempt > 0) await new Promise((r) => setTimeout(r, 2000));
      try {
        const updated = await accountsApi.relogin(account.id);
        patchAccount(account.id, { status: updated.status, lastError: updated.lastError ?? undefined, lastErrorCode: updated.lastErrorCode ?? undefined });
        toast.success(`@${account.username} relogged in`);
        setRelogging(false);
        return;
      } catch (err) {
        lastError = err as ApiError;
        if (!TRANSIENT_CODES.has(lastError.code ?? '')) break;
      }
    }

    const code = lastError?.code ?? '';
    const family = lastError?.family ?? '';
    let msg = lastError?.message || 'Relogin failed';
    let status: 'error' | 'challenge' | '2fa_required' = 'error';

    if (code === 'bad_password' || code === 'bad_credentials') {
      msg = 'Wrong password — update credentials and try again';
    } else if (code === 'two_factor_required') {
      msg = '2FA required — add TOTP secret to enable auto-auth';
      status = '2fa_required';
    } else if (isChallengeFailure(code, family)) {
      msg = 'Instagram security challenge — manual action required';
      status = 'challenge';
    } else if (code === 'relogin_attempt_exceeded') {
      msg = 'Too many attempts — wait before retrying';
    } else if (code === 'proxy_error' || code === 'proxy_connection_failed' || code === 'proxy_blocked') {
      msg = 'Proxy unreachable — check or change proxy';
    }

    updateStatus(account.id, status, msg);
    toast.error(`@${account.username}: ${msg}`, { duration: 6000 });
    setRelogging(false);
  };

  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await accountsApi.logout(account.id);
      removeAccount(account.id);
      toast.success(`${account.username} logged out`);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <Card glow className="sticky top-6 space-y-5 p-5">
      {/* Header */}
      <div className="flex items-start gap-4">
        <AccountAvatar username={account.username} avatar={account.avatar} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-base font-semibold text-[#eef4ff]">@{account.username}</span>
            {statusBadge(account)}
          </div>
          {account.fullName && <p className="mt-1 truncate text-sm text-[#9aa7cf]">{account.fullName}</p>}
        </div>
      </div>

      {/* Stats */}
      {account.status === 'active' && (
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-[1.15rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-3 py-3 text-center">
            <p className="font-mono text-sm text-[#eef4ff]">{account.followers?.toLocaleString() ?? '—'}</p>
            <p className="mt-1 text-[11px] text-[#7f8bb3]">followers</p>
          </div>
          <div className="rounded-[1.15rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-3 py-3 text-center">
            <p className="font-mono text-sm text-[#eef4ff]">{account.following?.toLocaleString() ?? '—'}</p>
            <p className="mt-1 text-[11px] text-[#7f8bb3]">following</p>
          </div>
        </div>
      )}

      {/* Meta */}
      <div className="space-y-2">
        {account.proxy && (
          <div className="flex items-center gap-2 text-xs text-[#8e9ac0]">
            <Globe className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{account.proxy}</span>
          </div>
        )}
        {account.totpEnabled && (
          <div className="flex items-center gap-2 text-xs text-[#9ece6a]">
            <Lock className="h-3.5 w-3.5 shrink-0" />
            <span>TOTP enabled</span>
          </div>
        )}
        {account.lastVerifiedAt && (
          <div className="flex items-center gap-2 text-xs text-[#8e9ac0]">
            <CheckCircle className="h-3.5 w-3.5 shrink-0" />
            <span>Last verified: {new Date(account.lastVerifiedAt).toLocaleString()}</span>
          </div>
        )}
        {account.lastError && (
          <p className="rounded-[0.75rem] bg-[rgba(247,118,142,0.08)] px-3 py-2 text-xs text-[#ffbfd0]">{account.lastError}</p>
        )}
      </div>

      {/* Rate limit cooldown banner */}
      {rateLimitInfo && (
        <div className="flex items-start gap-3 rounded-[1rem] border border-[rgba(255,158,100,0.22)] bg-[rgba(255,158,100,0.07)] px-3 py-3">
          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-[#ffb07a]" />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-[#ffd0a0]">Rate limited</p>
            <p className="mt-0.5 text-[11px] text-[#b8a090]">
              {rateLimitInfo.reason === 'feedback_required'
                ? 'Action blocked by Instagram'
                : 'Too many requests — Instagram cooldown active'}
            </p>
            <p className="mt-1 font-mono text-xs text-[#ffb07a]">
              Retry in {formatCooldown(rateLimitInfo.retry_after)}
            </p>
          </div>
          <Button size="sm" variant="secondary" loading={clearingLimit} onClick={handleClearRateLimit}>
            Clear
          </Button>
        </div>
      )}

      {/* Challenge instruction banner */}
      {account.status === 'challenge' && (
        <div className="flex items-start gap-3 rounded-[1rem] border border-[rgba(224,175,104,0.28)] bg-[rgba(224,175,104,0.07)] px-3 py-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#e0af68]" />
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-xs font-semibold text-[#f5d08a]">Security challenge required</p>
            <p className="text-[11px] leading-relaxed text-[#b8a060]">
              Instagram is blocking automated login for this account. Open{' '}
              <span className="font-mono text-[#e0af68]">instagram.com</span> in a browser,
              log in as <span className="font-mono text-[#e0af68]">@{account.username}</span>,
              and complete any verification Instagram asks for.
              Then click <strong className="text-[#f5d08a]">Activate</strong> below.
            </p>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-[rgba(162,179,229,0.10)] pt-4">
        {(account.status === 'idle' || account.status === 'error' || account.status === 'challenge' || account.status === '2fa_required') && (
          <Button size="sm" onClick={handleRelogin} loading={relogging}>
            <RotateCcw className="h-3.5 w-3.5" />
            Activate
          </Button>
        )}
        {!account.totpEnabled && account.status === 'active' && (
          <Button size="sm" variant="secondary" onClick={() => onSetupTOTP?.(account.id)}>
            <Lock className="h-3.5 w-3.5" />
            Setup 2FA
          </Button>
        )}
        <Button size="sm" variant="secondary" onClick={() => setShowCredentials(true)}>
          <KeyRound className="h-3.5 w-3.5" />
          Credentials
        </Button>
        <Button size="sm" variant="danger" onClick={handleLogout} loading={loggingOut}>
          <Trash2 className="h-3.5 w-3.5" />
          Remove
        </Button>
      </div>

      {/* Audit trail */}
      {auditLog.length > 0 && (
        <div className="border-t border-[rgba(162,179,229,0.10)] pt-4">
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-[#5a6a90]">Recent Activity</p>
          <div className="space-y-0">
            {auditLog.map((entry, i) => {
              const meta = auditMeta(entry.event);
              const ts = new Date(entry.ts);
              const relTime = formatRelativeTime(entry.ts) ?? ts.toLocaleTimeString();
              return (
                <div key={i} className="flex items-start gap-2.5 py-1.5">
                  <div className="flex flex-col items-center pt-1">
                    <div
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: meta.color }}
                    />
                    {i < auditLog.length - 1 && (
                      <div className="mt-0.5 w-px flex-1 bg-[rgba(162,179,229,0.10)]" style={{ minHeight: '12px' }} />
                    )}
                  </div>
                  <div className="min-w-0 flex-1 pb-0.5">
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs font-medium" style={{ color: meta.color }}>
                        {meta.label}
                      </span>
                      <span className="text-[10px] text-[#4a5578]">{relTime}</span>
                    </div>
                    {entry.detail && (
                      <p className="mt-0.5 truncate text-[11px] text-[#7f8bb3]">{entry.detail}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <CredentialsModal
        open={showCredentials}
        onClose={() => setShowCredentials(false)}
        accountId={account.id}
        username={account.username}
      />
    </Card>
  );
}
