import { useRef, useState, useMemo, useEffect } from 'react';
import {
  AlertCircle,
  CheckCircle,
  CheckSquare,
  Clock,
  Copy,
  Download,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Loader,
  Lock,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Square,
  Trash2,
  Upload,
  UserPlus,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { accountsApi } from '../api/accounts';
import type { RateLimitEntry } from '../api/accounts';
import { ApiError } from '../api/client';
import { logsApi } from '../api/logs';
import type { ActivityLogEntry } from '../types';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { useAccountStore } from '../store/accounts';
import { useSettingsStore } from '../store/settings';
import { useAccountsUIStore } from '../store/accountsUI';
import { buildProxyImageUrl } from '../lib/api-base';
import type { Account } from '../types';

/** Format remaining cooldown seconds into a compact human string. */
function formatCooldown(sec: number): string {
  if (sec < 60) return `${Math.ceil(sec)}s`;
  if (sec < 3600) return `~${Math.ceil(sec / 60)}min`;
  return `~${(sec / 3600).toFixed(1)}h`;
}

/** Format relative time like "2m ago", "1h ago", "3d ago" */
function formatRelativeTime(isoString: string | undefined): string | null {
  if (!isoString) return null;
  const date = new Date(isoString);
  const now = Date.now();
  const diffMs = now - date.getTime();
  if (diffMs < 0) return null;

  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  return date.toLocaleDateString();
}

const statusBadge = (account: Account, compact = false) => {
  const { status, lastVerifiedAt } = account;
  const verifiedAgo = formatRelativeTime(lastVerifiedAt);

  switch (status) {
    case 'active':
      return (
        <Badge variant="green" title={lastVerifiedAt ? `Last verified: ${new Date(lastVerifiedAt).toLocaleString()}` : 'Not verified yet'}>
          <CheckCircle className="h-3 w-3" />
          {compact ? (verifiedAgo ?? 'Active') : (verifiedAgo ? `Verified ${verifiedAgo}` : 'Active')}
        </Badge>
      );
    case 'logging_in':
      return <Badge variant="blue"><Loader className="h-3 w-3 animate-spin" />{compact ? 'Login...' : 'Logging in'}</Badge>;
    case 'error':
      return <Badge variant="red"><AlertCircle className="h-3 w-3" />Error</Badge>;
    case 'challenge':
      return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />Challenge</Badge>;
    case '2fa_required':
      return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />2FA</Badge>;
    default:
      return (
        <Badge variant="gray" title={verifiedAgo ? `Last verified: ${verifiedAgo}` : 'Never verified'}>
          {verifiedAgo ? `Idle (${verifiedAgo})` : 'Idle'}
        </Badge>
      );
  }
};

function AccountAvatar({ username, avatar, size = 'md' }: { username: string; avatar?: string; size?: 'sm' | 'md' }) {
  const [imgFailed, setImgFailed] = useState(false);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
  const dim = size === 'sm' ? 'h-8 w-8' : 'h-12 w-12';
  const radius = size === 'sm' ? 'rounded-[0.8rem]' : 'rounded-[1.2rem]';
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

  if (avatar && !imgFailed) {
    const src = buildProxyImageUrl(avatar, backendUrl, backendApiKey);
    return (
      <img
        src={src}
        alt={username}
        className={`${dim} shrink-0 ${radius} border border-[rgba(125,207,255,0.16)] object-cover`}
        onError={() => setImgFailed(true)}
      />
    );
  }
  return (
    <div className={`flex ${dim} shrink-0 items-center justify-center ${radius} border border-[rgba(125,207,255,0.16)] bg-[linear-gradient(135deg,rgba(122,162,247,0.22),rgba(125,207,255,0.12)_60%,rgba(187,154,247,0.18))] ${textSize} font-semibold uppercase text-[#eef4ff]`}>
      {username[0]}
    </div>
  );
}

/* ── Compact account row for left column ─────────────────────────────────── */

const NON_ACTIVE_STATUSES = new Set(['idle', 'error', 'challenge', '2fa_required']);

function AccountRow({
  account,
  isActive,
  selectMode,
  selected,
  onToggle,
  onClick,
  onRelogin,
  relogging,
  rateLimitInfo,
}: {
  account: Account;
  isActive: boolean;
  selectMode: boolean;
  selected: boolean;
  onToggle: () => void;
  onClick: () => void;
  onRelogin: () => void;
  relogging: boolean;
  rateLimitInfo?: RateLimitEntry;
}) {
  const handleClick = () => {
    if (selectMode) onToggle();
    else onClick();
  };

  const showReauth = NON_ACTIVE_STATUSES.has(account.status) && !selectMode;

  return (
    <div
      onClick={handleClick}
      className={`flex cursor-pointer items-center gap-3 rounded-[1rem] px-3 py-2.5 transition-all duration-150 ${
        selectMode && selected
          ? 'bg-[rgba(125,207,255,0.10)] ring-1 ring-[rgba(125,207,255,0.24)]'
          : isActive
            ? 'bg-[rgba(187,154,247,0.10)] ring-1 ring-[rgba(187,154,247,0.22)]'
            : 'hover:bg-[rgba(255,255,255,0.04)]'
      }`}
    >
      {selectMode && (
        <div className="shrink-0" onClick={(e) => { e.stopPropagation(); onToggle(); }}>
          {selected
            ? <CheckSquare className="h-4 w-4 text-[#7dcfff]" />
            : <Square className="h-4 w-4 text-[#5a6a90]" />}
        </div>
      )}

      <AccountAvatar username={account.username} avatar={account.avatar} size="sm" />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[#eef4ff]">@{account.username}</p>
        {account.fullName && (
          <p className="truncate text-xs text-[#7f8bb3]">{account.fullName}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <div className="flex flex-col items-end gap-1">
          {statusBadge(account, true)}
          {rateLimitInfo && (
            <span className="flex items-center gap-1 rounded-full border border-[rgba(255,158,100,0.24)] bg-[rgba(255,158,100,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[#ffb07a]">
              <Clock className="h-2.5 w-2.5" />
              {formatCooldown(rateLimitInfo.retry_after)}
            </span>
          )}
        </div>

        {showReauth && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onRelogin(); }}
            disabled={relogging}
            title="Re-authenticate"
            className="cursor-pointer rounded-lg p-1.5 text-[#5a6a90] transition-colors duration-150 hover:bg-[rgba(122,162,247,0.12)] hover:text-[#7aa2f7] disabled:opacity-40"
          >
            {relogging
              ? <Loader className="h-3.5 w-3.5 animate-spin" />
              : <RotateCcw className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Audit trail helpers ─────────────────────────────────────────────────── */

const AUDIT_META: Record<string, { label: string; color: string }> = {
  login_success:         { label: 'Login OK',         color: '#9ece6a' },
  login_failed:          { label: 'Login failed',      color: '#f7768e' },
  relogin_success:       { label: 'Relogin OK',        color: '#9ece6a' },
  relogin_failed:        { label: 'Relogin failed',    color: '#f7768e' },
  logout:                { label: 'Logout',            color: '#7f8bb3' },
  proxy_changed:         { label: 'Proxy changed',     color: '#7dcfff' },
  post_success:          { label: 'Post OK',           color: '#9ece6a' },
  post_failed:           { label: 'Post failed',       color: '#f7768e' },
  session_expired:       { label: 'Session expired',   color: '#e0af68' },
  challenge:             { label: 'Challenge',         color: '#e0af68' },
  upload_timeout:        { label: 'Upload timeout',    color: '#f7768e' },
  circuit_open:          { label: 'Circuit open',      color: '#f7768e' },
  rate_limited:          { label: 'Rate limited',      color: '#ff9e64' },
  connectivity_verified: { label: 'Health OK',         color: '#9ece6a' },
  connectivity_failed:   { label: 'Health failed',     color: '#f7768e' },
};

function auditMeta(event: string) {
  return AUDIT_META[event] ?? { label: event.replace(/_/g, ' '), color: '#7f8bb3' };
}

/* ── Credentials modal ───────────────────────────────────────────────────── */

function CredentialField({ label, value }: { label: string; value: string }) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const display = visible ? value : '•'.repeat(Math.min(value.length || 8, 24));

  async function handleCopy() {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5a6a90]">{label}</p>
      <div className="flex items-center gap-2 rounded-[0.9rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-3 py-2.5">
        <span className="flex-1 break-all font-mono text-sm text-[#c0caf5]">
          {value ? display : <span className="text-[#4a5578]">—</span>}
        </span>
        {value && (
          <>
            <button
              type="button"
              onClick={() => setVisible((v) => !v)}
              className="cursor-pointer shrink-0 text-[#5a6a90] transition-colors hover:text-[#c0caf5]"
              title={visible ? 'Hide' : 'Show'}
            >
              {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="cursor-pointer shrink-0 text-[#5a6a90] transition-colors hover:text-[#7aa2f7]"
              title="Copy"
            >
              {copied ? <CheckCircle className="h-3.5 w-3.5 text-[#9ece6a]" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function CredentialsModal({
  open,
  onClose,
  accountId,
  username,
}: {
  open: boolean;
  onClose: () => void;
  accountId: string;
  username: string;
}) {
  const [loading, setLoading] = useState(false);
  const [creds, setCreds] = useState<{ username: string; password: string; totpSecret: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    accountsApi.getCredentials(accountId)
      .then(setCreds)
      .catch(() => setCreds(null))
      .finally(() => setLoading(false));
  }, [open, accountId]);

  function handleClose() {
    setCreds(null);
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose} title={`Credentials — @${username}`}>
      {loading ? (
        <div className="flex h-24 items-center justify-center">
          <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
        </div>
      ) : creds ? (
        <div className="space-y-4">
          <CredentialField label="Username" value={creds.username} />
          <CredentialField label="Password" value={creds.password} />
          {creds.totpSecret && (
            <CredentialField label="TOTP Secret" value={creds.totpSecret} />
          )}
          <p className="rounded-[0.9rem] bg-[rgba(247,118,142,0.08)] px-3 py-2 text-[11px] text-[#f7768e]">
            Keep these credentials private. Do not share or expose them.
          </p>
        </div>
      ) : (
        <p className="text-sm text-[#f7768e]">Failed to load credentials.</p>
      )}
    </Modal>
  );
}

/* ── Detail panel (right column) ─────────────────────────────────────────── */

function AccountDetail({
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
  const upsertAccount = useAccountStore((s) => s.upsertAccount);
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
        upsertAccount(updated);
        toast.success(`@${account.username} relogged in`);
        setRelogging(false);
        return;
      } catch (err) {
        lastError = err as ApiError;
        if (!TRANSIENT_CODES.has(lastError.code ?? '')) break;
      }
    }

    const code = lastError?.code ?? '';
    let msg = lastError?.message || 'Relogin failed';
    let status: 'error' | 'challenge' | '2fa_required' = 'error';

    if (code === 'bad_password' || code === 'bad_credentials') {
      msg = 'Wrong password — update credentials and try again';
    } else if (code === 'two_factor_required') {
      msg = '2FA required — add TOTP secret to enable auto-auth';
      status = '2fa_required';
    } else if (code.startsWith('challenge')) {
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
        {account.error && (
          <p className="rounded-[0.75rem] bg-[rgba(247,118,142,0.08)] px-3 py-2 text-xs text-[#ffbfd0]">{account.error}</p>
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
                  {/* Timeline connector */}
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

/* ── Modals (unchanged logic) ────────────────────────────────────────────── */

function AddAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [proxy, setProxy] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'credentials' | '2fa'>('credentials');
  const [pendingAccountId, setPendingAccountId] = useState<string | null>(null);
  const [twoFACode, setTwoFACode] = useState('');
  const upsertAccount = useAccountStore((s) => s.upsertAccount);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('Username and password are required');
      return;
    }

    setLoading(true);
    try {
      const cleanTotpSecret = totpSecret.trim().replace(/\s+/g, '') || undefined;
      const account = await accountsApi.login(username.trim(), password.trim(), proxy.trim() || undefined, cleanTotpSecret);
      if (account.status === '2fa_required') {
        setPendingAccountId(account.id);
        setStep('2fa');
        setLoading(false);
        return;
      }
      upsertAccount(account);
      toast.success(`@${account.username} logged in`);
      setUsername('');
      setPassword('');
      setProxy('');
      setTotpSecret('');
      setLoading(false);
      onClose();
    } catch (error) {
      setError((error as Error).message);
      setLoading(false);
    }
  };

  const handle2FASubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!twoFACode.trim()) {
      setError('2FA code is required');
      return;
    }

    setLoading(true);
    try {
      const account = await accountsApi.verify2fa(pendingAccountId!, twoFACode.trim(), false);
      upsertAccount(account);
      toast.success(`@${account.username} logged in`);
      setUsername('');
      setPassword('');
      setProxy('');
      setStep('credentials');
      setPendingAccountId(null);
      setTwoFACode('');
      onClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleModalClose = () => {
    setStep('credentials');
    setPendingAccountId(null);
    setTwoFACode('');
    setError('');
    setTotpSecret('');
    setLoading(false);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleModalClose} title={step === 'credentials' ? 'Add Account' : 'Enter 2FA Code'}>
      {step === 'credentials' ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input label="Username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="your_instagram" autoFocus />
          <Input label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" />
          <Input
            label="2FA Secret / TOTP"
            value={totpSecret}
            onChange={(event) => setTotpSecret(event.target.value)}
            placeholder="2OWR 5YTV ZHAN 66UJ YOCT RZC2 7DCS WTDQ"
            hint="Optional base32 TOTP secret. Spaces are removed automatically."
          />
          <Input label="Proxy" value={proxy} onChange={(event) => setProxy(event.target.value)} placeholder="http://user:pass@host:port" hint="Optional. Leave empty to use direct connection." />
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          {loading && <p className="text-xs text-[#8e9ac0]">Connecting to Instagram — this can take up to 30 seconds…</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleModalClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" loading={loading}>
              {loading ? 'Logging in…' : 'Login'}
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={handle2FASubmit} className="space-y-4">
          <p className="text-sm text-[#8e9ac0]">Enter the 6-digit code from your authenticator app or SMS.</p>
          <Input
            label="2FA Code"
            value={twoFACode}
            onChange={(event) => setTwoFACode(event.target.value)}
            placeholder="000000"
            autoFocus
            maxLength={6}
          />
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleModalClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" loading={loading}>
              {loading ? 'Verifying…' : 'Verify'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const upsertAccount = useAccountStore((s) => s.upsertAccount);

  const loadFileText = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setText(content);
      setFileName(file.name);
      setError('');
    };
    reader.readAsText(file);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) loadFileText(file);
    event.target.value = '';
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files[0];
    if (file) loadFileText(file);
  };

  const handleImport = async () => {
    setError('');
    const lines = text.trim().split('\n').filter((line) => line.includes(':'));
    if (!lines.length) {
      setError('No valid lines found. Format: username:password');
      return;
    }

    setLoading(true);
    try {
      const importedAccounts = await accountsApi.importFile(text.trim());
      importedAccounts.forEach((account) => upsertAccount(account));
      toast.success(`Imported ${importedAccounts.length} account(s)`);
      setText('');
      setFileName('');
      onClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setText('');
    setFileName('');
    setError('');
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Import Accounts">
      <div className="space-y-4">
        <p className="text-sm text-[#8e9ac0]">
          One account per line: <code className="rounded bg-[rgba(125,207,255,0.12)] px-1.5 py-0.5 text-[#d2f3ff]">username:password[:proxy][|totp_secret]</code>
        </p>

        {/* File drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center gap-2 rounded-[1.25rem] border px-4 py-5 text-center transition-all duration-200 ${
            dragOver
              ? 'border-[rgba(125,207,255,0.4)] bg-[rgba(125,207,255,0.12)]'
              : 'border-dashed border-[rgba(162,179,229,0.2)] bg-[rgba(255,255,255,0.03)] hover:border-[rgba(125,207,255,0.3)] hover:bg-[rgba(255,255,255,0.05)]'
          }`}
        >
          <Upload className={`h-5 w-5 ${dragOver ? 'text-[#7dcfff]' : 'text-[#5a6a90]'}`} />
          {fileName ? (
            <p className="text-sm font-medium text-[#9ece6a]">{fileName}</p>
          ) : (
            <p className="text-sm text-[#7f8bb3]">Drop a .txt / .csv file here, or click to browse</p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.csv,text/plain,text/csv"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-[rgba(162,179,229,0.12)]" />
          <span className="text-[11px] text-[#4a5578]">or paste below</span>
          <div className="h-px flex-1 bg-[rgba(162,179,229,0.12)]" />
        </div>

        <textarea
          value={text}
          onChange={(event) => { setText(event.target.value); setFileName(''); }}
          placeholder={"user1:pass1\nuser2:pass2:http://proxy:3128\nuser3:pass3|BASE32TOTPSECRET"}
          rows={6}
          className="glass-textarea font-mono text-sm"
          aria-label="Accounts list"
        />

        {error && <p className="text-sm text-[#ff9db0]">{error}</p>}

        <div className="flex gap-3">
          <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
            Cancel
          </Button>
          <Button className="flex-1" loading={loading} onClick={handleImport} disabled={!text.trim()}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function BulkProxyModal({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (proxy: string) => void;
}) {
  const [proxy, setProxy] = useState('');

  return (
    <Modal open={open} onClose={onClose} title="Set Proxy for Selected">
      <div className="space-y-4">
        <Input
          label="Proxy URL"
          value={proxy}
          onChange={(event) => setProxy(event.target.value)}
          placeholder="http://user:pass@host:port or socks5://host:port"
          autoFocus
        />
        <div className="flex gap-3">
          <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={() => { onConfirm(proxy); onClose(); }} disabled={!proxy.trim()}>
            Apply
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function TOTPSetupModal({
  open,
  onClose,
  accountId,
}: {
  open: boolean;
  onClose: () => void;
  accountId?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState('');
  const [secret, setSecret] = useState('');
  const [qrUri, setQrUri] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [step, setStep] = useState<'setup' | 'verify'>('setup');
  const patchAccount = useAccountStore((s) => s.patchAccount);

  const handleGenerateSecret = async () => {
    if (!accountId) return;
    setLoading(true);
    setError('');
    try {
      const result = await accountsApi.setupTotp(accountId);
      setSecret(result.secret);
      setQrUri(result.provisioning_uri);
      setStep('verify');
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyTotp = async () => {
    if (!accountId || !verificationCode.trim()) {
      setError('Verification code is required');
      return;
    }

    setVerifying(true);
    setError('');
    try {
      await accountsApi.verifyTotp(accountId, secret, verificationCode.trim());
      patchAccount(accountId, { totpEnabled: true });
      toast.success('TOTP enabled successfully');
      handleClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setVerifying(false);
    }
  };

  const handleClose = () => {
    setSecret('');
    setQrUri('');
    setVerificationCode('');
    setError('');
    setStep('setup');
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Setup 2FA with TOTP">
      {step === 'setup' ? (
        <div className="space-y-4">
          <p className="text-sm text-[#8e9ac0]">
            Generate a TOTP secret, scan the QR code in your authenticator, then verify the first code to enable 2FA.
          </p>
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
              Cancel
            </Button>
            <Button className="flex-1" loading={loading} onClick={handleGenerateSecret}>
              Generate TOTP Secret
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col items-center rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-4 py-5">
            <p className="text-sm text-[#8e9ac0]">Scan with an authenticator app</p>
            {qrUri && (
              <div className="mt-4 rounded-[1.2rem] bg-white p-3">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUri)}`}
                  alt="QR code for TOTP setup"
                  className="h-40 w-40"
                />
              </div>
            )}
            <p className="mt-4 text-xs text-[#8e9ac0]">Manual secret</p>
            <p className="mt-2 rounded-[1rem] bg-[rgba(125,207,255,0.12)] px-3 py-2 font-mono text-sm text-[#d2f3ff]">{secret}</p>
          </div>

          <Input
            label="Verification Code"
            value={verificationCode}
            onChange={(event) => setVerificationCode(event.target.value)}
            placeholder="000000"
            maxLength={6}
          />

          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
              Cancel
            </Button>
            <Button className="flex-1" loading={verifying} onClick={handleVerifyTotp}>
              Verify & Enable
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export function AccountsPage() {
  const accounts = useAccountStore((s) => s.accounts);
  const setAccounts = useAccountStore((s) => s.setAccounts);
  const removeAccount = useAccountStore((s) => s.removeAccount);
  const upsertPageAccount = useAccountStore((s) => s.upsertAccount);
  const patchAccount = useAccountStore((s) => s.patchAccount);
  const updatePageStatus = useAccountStore((s) => s.updateStatus);
  const activeId = useAccountStore((s) => s.activeId);
  const setActive = useAccountStore((s) => s.setActive);

  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [reloggingIds, setReloggingIds] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkProgress, setBulkProgress] = useState('');
  const [, setBusyAccountIds] = useState<Set<string>>(new Set());
  const [showBulkProxy, setShowBulkProxy] = useState(false);
  const [showTOTPSetup, setShowTOTPSetup] = useState(false);
  const [totpAccountId, setTOTPAccountId] = useState<string | undefined>();
  const searchQuery = useAccountsUIStore((s) => s.searchQuery);
  const setSearchQuery = useAccountsUIStore((s) => s.setSearchQuery);
  const [rateLimitMap, setRateLimitMap] = useState<Map<string, RateLimitEntry>>(new Map());
  const sessionInputRef = useRef<HTMLInputElement>(null);

  // Poll rate-limited accounts every 15 s
  useEffect(() => {
    const fetchLimited = () => {
      accountsApi.rateLimited().then((entries) => {
        setRateLimitMap(new Map(entries.map((e) => [e.account_id, e])));
      }).catch(() => {});
    };
    fetchLimited();
    const id = setInterval(fetchLimited, 15_000);
    return () => clearInterval(id);
  }, []);

  const handleClearRateLimit = (accountId: string) => {
    setRateLimitMap((prev) => {
      const next = new Map(prev);
      next.delete(accountId);
      return next;
    });
  };

  const handleQuickRelogin = async (account: Account) => {
    if (reloggingIds.has(account.id)) return;
    setReloggingIds((prev) => new Set(prev).add(account.id));
    updatePageStatus(account.id, 'logging_in');
    try {
      const updated = await accountsApi.relogin(account.id);
      upsertPageAccount(updated);
      toast.success(`@${account.username} re-authenticated`);
    } catch (err) {
      const e = err as ApiError;
      const code = e.code ?? '';
      let msg = e.message || 'Relogin failed';
      let status: Account['status'] = 'error';
      if (code === 'two_factor_required') { msg = '2FA required'; status = '2fa_required'; }
      else if (code.startsWith('challenge')) { msg = 'Security challenge'; status = 'challenge'; }
      updatePageStatus(account.id, status, msg);
      toast.error(`@${account.username}: ${msg}`, { duration: 5000 });
    } finally {
      setReloggingIds((prev) => { const s = new Set(prev); s.delete(account.id); return s; });
    }
  };

  const errorAccounts = accounts.filter((a) => a.status === 'error' || a.status === 'challenge');
  const activeAccounts = accounts.filter((a) => a.status === 'active').length;
  const focusedAccount = accounts.find((a) => a.id === activeId) ?? null;

  const filteredAccounts = useMemo(() => {
    if (!searchQuery.trim()) return accounts;
    const q = searchQuery.toLowerCase();
    return accounts.filter(
      (a) =>
        a.username.toLowerCase().includes(q) ||
        (a.fullName?.toLowerCase().includes(q) ?? false) ||
        a.status.includes(q)
    );
  }, [accounts, searchQuery]);

  const toggleSelect = (id: string) =>
    setSelectedIds((cur) => (cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id]));

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds([]);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const list = await accountsApi.list();
      setAccounts(list);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleExportSessions = async () => {
    try {
      const blob = await accountsApi.exportSessions();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `insta-sessions-${Date.now()}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  const handleImportSessions = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = await accountsApi.importSessions(file);
      imported.forEach((account) => useAccountStore.getState().upsertAccount(account));
      toast.success(`Restored ${imported.length} session(s)`);
    } catch (error) {
      toast.error((error as Error).message);
    }
    event.target.value = '';
  };

  const handleBulkRelogin = async () => {
    const total = selectedIds.length;
    if (!total) return;
    setBulkLoading(true);
    setBulkProgress(`0/${total}`);
    setBusyAccountIds(new Set(selectedIds));
    selectedIds.forEach((id) => updatePageStatus(id, 'logging_in'));

    let done = 0;
    let ok = 0;
    let fail = 0;
    const CONCURRENCY = 3;
    const queue = [...selectedIds];

    const worker = async () => {
      while (queue.length > 0) {
        const id = queue.shift();
        if (!id) break;
        try {
          const updated = await accountsApi.relogin(id);
          upsertPageAccount(updated);
          ok++;
        } catch {
          updatePageStatus(id, 'error');
          fail++;
        }
        done++;
        setBulkProgress(`${done}/${total}`);
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));

    if (ok > 0) toast.success(`${ok}/${total} relogged in`);
    if (fail > 0) toast.error(`${fail} failed`);
    setBulkLoading(false);
    setBulkProgress('');
    setBusyAccountIds(new Set());
    exitSelectMode();
  };

  const handleBulkLogout = async () => {
    if (!selectedIds.length) return;
    setBulkLoading(true);
    try {
      await accountsApi.bulkLogout(selectedIds);
      selectedIds.forEach((id) => removeAccount(id));
      toast.success(`${selectedIds.length} account${selectedIds.length !== 1 ? 's' : ''} removed`);
      exitSelectMode();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkProxy = async (proxy: string) => {
    if (!selectedIds.length || !proxy.trim()) return;
    setBulkLoading(true);
    try {
      const results = await accountsApi.bulkSetProxy(selectedIds, proxy.trim());
      results.forEach((r) => patchAccount(r.id, { proxy: r.proxy, status: r.status as Account['status'] }));
      toast.success(`Proxy updated for ${selectedIds.length} account${selectedIds.length !== 1 ? 's' : ''}`);
      exitSelectMode();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBulkLoading(false);
    }
  };

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Identity Operations"
        title="Account Workspace"
        description="Track live login state, recover sessions, import credential batches, and coordinate bulk actions."
        icon={<ShieldCheck className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          selectMode ? (
            <Button variant="ghost" size="sm" onClick={exitSelectMode}>
              <X className="h-4 w-4" />
              Exit select mode
            </Button>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={handleRefresh} loading={refreshing}>
                <RefreshCw className="h-4 w-4" />
                Sync
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setSelectMode(true)}>
                <CheckSquare className="h-4 w-4" />
                Select
              </Button>
              <Button variant="secondary" size="sm" onClick={() => sessionInputRef.current?.click()}>
                <Download className="h-4 w-4" />
                Import Session
              </Button>
              <Button variant="secondary" size="sm" onClick={handleExportSessions}>
                <Download className="h-4 w-4 rotate-180" />
                Export Session
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setShowImport(true)}>
                <Upload className="h-4 w-4" />
                Import File
              </Button>
              <Button size="sm" onClick={() => setShowAdd(true)}>
                <UserPlus className="h-4 w-4" />
                Add Account
              </Button>
            </>
          )
        }
      >
        <div className="metric-grid">
          <HeaderStat label="Connected" value={accounts.length} tone="cyan" />
          <HeaderStat label="Active" value={activeAccounts} tone="green" />
          <HeaderStat label="Needs Attention" value={errorAccounts.length} tone="rose" />
          <HeaderStat label="Rate Limited" value={rateLimitMap.size} tone={rateLimitMap.size > 0 ? 'rose' : 'cyan'} />
        </div>
      </PageHeader>

      {accounts.length === 0 ? (
        <Card className="py-18 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
            <UserPlus className="h-7 w-7 text-[#7dcfff]" />
          </div>
          <p className="mt-5 text-lg font-semibold text-[#eef4ff]">No accounts connected</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8e9ac0]">
            Add a single account, restore a saved session bundle, or import a credential file to start managing the fleet.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              Import File
            </Button>
            <Button onClick={() => setShowAdd(true)}>
              Add Account
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_22rem] pb-24">
          {/* ── Left column: search + account list ──────────────── */}
          <div className="space-y-3">
            {/* Search bar */}
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#5a6a90]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search accounts..."
                className="glass-field w-full py-2.5 pl-10 pr-3 text-sm"
                aria-label="Search accounts"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-[#5a6a90] transition-colors hover:text-[#8e9ac0]"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Select mode toolbar */}
            {selectMode && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedIds(filteredAccounts.map((a) => a.id))}
                  className="glass-chip cursor-pointer text-xs"
                >
                  Select all ({filteredAccounts.length})
                </button>
                {errorAccounts.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelectedIds(errorAccounts.map((a) => a.id))}
                    className="glass-chip cursor-pointer text-xs !border-[rgba(247,118,142,0.18)] !bg-[rgba(247,118,142,0.12)] !text-[#ffc4d0]"
                  >
                    Errors ({errorAccounts.length})
                  </button>
                )}
                <button type="button" onClick={() => setSelectedIds([])} className="glass-chip cursor-pointer text-xs">
                  Clear
                </button>
              </div>
            )}

            {/* Account list */}
            <Card className="overflow-hidden p-1.5">
              <div className="max-h-[calc(100vh-22rem)] space-y-0.5 overflow-y-auto pr-0.5">
                {filteredAccounts.length === 0 ? (
                  <div className="py-8 text-center">
                    <p className="text-sm text-[#5a6a90]">
                      {searchQuery ? `No accounts matching "${searchQuery}"` : 'No accounts'}
                    </p>
                  </div>
                ) : (
                  filteredAccounts.map((account) => (
                    <AccountRow
                      key={account.id}
                      account={account}
                      isActive={activeId === account.id}
                      selectMode={selectMode}
                      selected={selectedIds.includes(account.id)}
                      onToggle={() => toggleSelect(account.id)}
                      onClick={() => {
                        const next = activeId === account.id ? null : account.id;
                        setActive(next);
                        // Only refresh counts if not verified within the last 10 minutes —
                        // avoids hammering user_info() on every account click.
                        if (next) {
                          const acc = filteredAccounts.find((a) => a.id === next);
                          const verifiedMs = acc?.lastVerifiedAt ? new Date(acc.lastVerifiedAt).getTime() : 0;
                          const staleSec = (Date.now() - verifiedMs) / 1000;
                          if (staleSec > 600) {
                            accountsApi.refreshCounts(next).catch(() => {});
                          }
                        }
                      }}
                      onRelogin={() => void handleQuickRelogin(account)}
                      relogging={reloggingIds.has(account.id)}
                      rateLimitInfo={rateLimitMap.get(account.id)}
                    />
                  ))
                )}
              </div>
              {searchQuery && filteredAccounts.length > 0 && (
                <p className="border-t border-[rgba(162,179,229,0.08)] px-3 py-2 text-[11px] text-[#5a6a90]">
                  {filteredAccounts.length} of {accounts.length} accounts
                </p>
              )}
            </Card>
          </div>

          {/* ── Right column: detail panel ──────────────── */}
          <div className="hidden lg:block">
            {focusedAccount ? (
              <AccountDetail
                key={focusedAccount.id}
                account={focusedAccount}
                onSetupTOTP={(id) => {
                  setTOTPAccountId(id);
                  setShowTOTPSetup(true);
                }}
                rateLimitInfo={rateLimitMap.get(focusedAccount.id)}
                onClearRateLimit={handleClearRateLimit}
              />
            ) : (
              <Card className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
                  <ShieldCheck className="h-5 w-5 text-[#5a6a90]" />
                </div>
                <p className="mt-4 text-sm text-[#5a6a90]">Click an account to view details</p>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Mobile detail: show below list when active */}
      {focusedAccount && (
        <div className="lg:hidden pb-24">
          <AccountDetail
            key={focusedAccount.id}
            account={focusedAccount}
            onSetupTOTP={(id) => {
              setTOTPAccountId(id);
              setShowTOTPSetup(true);
            }}
            rateLimitInfo={rateLimitMap.get(focusedAccount.id)}
            onClearRateLimit={handleClearRateLimit}
          />
        </div>
      )}

      {selectMode && selectedIds.length > 0 && (
        <div className="fixed bottom-4 left-4 right-4 z-30 rounded-[1.6rem] border border-[rgba(162,179,229,0.16)] bg-[rgba(9,12,22,0.86)] p-4 shadow-[0_24px_54px_rgba(4,8,18,0.42)] backdrop-blur-2xl lg:left-[23rem] lg:right-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <span className="text-sm text-[#d6e0ff]">{selectedIds.length} selected</span>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" loading={bulkLoading} onClick={handleBulkRelogin}>
                <RotateCcw className="h-3.5 w-3.5" />
                {bulkProgress ? `Relogin ${bulkProgress}` : 'Relogin All'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowBulkProxy(true)}>
                <Globe className="h-3.5 w-3.5" />
                Set Proxy
              </Button>
              <Button size="sm" variant="danger" loading={bulkLoading} onClick={handleBulkLogout}>
                <Trash2 className="h-3.5 w-3.5" />
                Logout All
              </Button>
            </div>
          </div>
        </div>
      )}

      <input ref={sessionInputRef} type="file" accept=".json" className="hidden" onChange={handleImportSessions} aria-hidden="true" />

      <AddAccountModal open={showAdd} onClose={() => setShowAdd(false)} />
      <ImportModal open={showImport} onClose={() => setShowImport(false)} />
      <BulkProxyModal open={showBulkProxy} onClose={() => setShowBulkProxy(false)} onConfirm={handleBulkProxy} />
      <TOTPSetupModal open={showTOTPSetup} onClose={() => setShowTOTPSetup(false)} accountId={totpAccountId} />
    </div>
  );
}
