/** Format remaining cooldown seconds into a compact human string. */
export function formatCooldown(sec: number): string {
  if (sec < 60) return `${Math.ceil(sec)}s`;
  if (sec < 3600) return `~${Math.ceil(sec / 60)}min`;
  return `~${(sec / 3600).toFixed(1)}h`;
}

/** Format relative time like "2m ago", "1h ago", "3d ago" */
export function formatRelativeTime(isoString: string | undefined): string | null {
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

export const AUDIT_META: Record<string, { label: string; color: string }> = {
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

export function auditMeta(event: string) {
  return AUDIT_META[event] ?? { label: event.replace(/_/g, ' '), color: '#7f8bb3' };
}

export const NON_ACTIVE_STATUSES = new Set(['idle', 'error', 'challenge', '2fa_required']);

const CHALLENGE_ERROR_CODES = new Set([
  'challenge_error',
  'challenge_redirection',
  'challenge_required',
  'challenge_selfie',
  'challenge_unknown_step',
  'challenge_select_contact',
  'challenge_recaptcha',
  'challenge_phone_required',
  'challenge_password_change',
  'captcha_challenge_required',
  'checkpoint_required',
  'consent_required',
  'geo_blocked',
]);

export function isChallengeFailure(code?: string, family?: string): boolean {
  if (family === 'challenge') return true;
  if (!code) return false;
  return CHALLENGE_ERROR_CODES.has(code);
}
