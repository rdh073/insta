import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  Globe,
  ImagePlus,
  LogIn,
  LogOut,
  RefreshCw,
  ScrollText,
  Search,
  ShieldOff,
  Timer,
  X,
  Zap,
} from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { PageHeader } from '../components/ui/PageHeader';
import { logsApi } from '../api/logs';
import type { ActivityLogEntry } from '../types';
import { useActivityStore } from '../store/activity';
import { cn } from '../lib/cn';

// ─── Event registry ──────────────────────────────────────────────────────────

type Level = 'success' | 'error' | 'warn' | 'info' | 'muted';

const EVENT_META: Record<
  string,
  { label: string; level: Level; Icon: React.FC<{ className?: string }> }
> = {
  login_success:          { label: 'LOGIN_OK',       level: 'success', Icon: LogIn },
  login_failed:           { label: 'LOGIN_FAIL',      level: 'error',   Icon: LogIn },
  relogin_success:        { label: 'RELOGIN_OK',      level: 'success', Icon: RefreshCw },
  relogin_failed:         { label: 'RELOGIN_FAIL',    level: 'error',   Icon: RefreshCw },
  logout:                 { label: 'LOGOUT',          level: 'muted',   Icon: LogOut },
  proxy_changed:          { label: 'PROXY_CHANGED',   level: 'info',    Icon: Globe },
  post_success:           { label: 'POST_OK',         level: 'success', Icon: ImagePlus },
  post_failed:            { label: 'POST_FAIL',       level: 'error',   Icon: ImagePlus },
  session_expired:        { label: 'SESSION_EXPIRED', level: 'warn',    Icon: AlertTriangle },
  challenge:              { label: 'CHALLENGE',       level: 'warn',    Icon: ShieldOff },
  upload_timeout:         { label: 'UPLOAD_TIMEOUT',  level: 'error',   Icon: Timer },
  circuit_open:           { label: 'CIRCUIT_OPEN',    level: 'error',   Icon: Zap },
  rate_limited:           { label: 'RATE_LIMITED',    level: 'warn',    Icon: Clock },
  connectivity_verified:  { label: 'HEALTH_OK',       level: 'success', Icon: CheckCircle },
  connectivity_failed:    { label: 'HEALTH_FAIL',     level: 'error',   Icon: AlertTriangle },
};

const LEVEL_STYLES: Record<Level, { badge: string; dot: string; icon: string }> = {
  success: {
    badge: 'text-[#9ece6a] bg-[rgba(158,206,106,0.10)] border border-[#9ece6a]/20',
    dot:   'bg-[#9ece6a]',
    icon:  'text-[#9ece6a]',
  },
  error: {
    badge: 'text-[#f7768e] bg-[rgba(247,118,142,0.10)] border border-[#f7768e]/20',
    dot:   'bg-[#f7768e]',
    icon:  'text-[#f7768e]',
  },
  warn: {
    badge: 'text-[#e0af68] bg-[rgba(224,175,104,0.10)] border border-[#e0af68]/20',
    dot:   'bg-[#e0af68]',
    icon:  'text-[#e0af68]',
  },
  info: {
    badge: 'text-[#7dcfff] bg-[rgba(125,207,255,0.10)] border border-[#7dcfff]/20',
    dot:   'bg-[#7dcfff]',
    icon:  'text-[#7dcfff]',
  },
  muted: {
    badge: 'text-[#8f9bc4] bg-[rgba(162,179,229,0.07)] border border-[rgba(162,179,229,0.15)]',
    dot:   'bg-[#59658c]',
    icon:  'text-[#59658c]',
  },
};

const ALL_EVENTS = Object.keys(EVENT_META);
const LIMIT = 100;
const AUTO_REFRESH_MS = 5000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtTs(ts: string): string {
  const d = new Date(ts);
  const pad = (n: number, w = 2) => String(n).padStart(w, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

function matchesSearch(entry: ActivityLogEntry, q: string): boolean {
  if (!q) return true;
  const lower = q.toLowerCase();
  return (
    entry.username?.toLowerCase().includes(lower) ||
    entry.event?.toLowerCase().includes(lower) ||
    entry.detail?.toLowerCase().includes(lower) ||
    false
  );
}

function downloadJson(entries: ActivityLogEntry[]) {
  const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `activity-log-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ActivityPage() {
  const didInitialLoad = useRef(false);
  const autoRefreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const username = useActivityStore((s) => s.username);
  const setUsername = useActivityStore((s) => s.setUsername);
  const event = useActivityStore((s) => s.event);
  const setEvent = useActivityStore((s) => s.setEvent);
  const search = useActivityStore((s) => s.search);
  const setSearch = useActivityStore((s) => s.setSearch);
  const autoRefresh = useActivityStore((s) => s.autoRefresh);
  const setAutoRefresh = useActivityStore((s) => s.setAutoRefresh);
  const [offset, setOffset] = useState(0);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const load = useCallback(
    async (nextOffset = 0) => {
      setLoading(true);
      try {
        const data = await logsApi.get({
          limit: LIMIT,
          offset: nextOffset,
          username: username.trim() || undefined,
          event: event || undefined,
        });
        setEntries(data.entries);
        setTotal(data.total);
        setOffset(nextOffset);
        setLastRefreshed(new Date());
      } catch {
        // keep previous data on error
      } finally {
        setLoading(false);
      }
    },
    [event, username],
  );

  // Initial load
  useEffect(() => {
    if (didInitialLoad.current) return;
    didInitialLoad.current = true;
    void load(0);
  }, [load]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshTimer.current = setInterval(() => void load(0), AUTO_REFRESH_MS);
    } else {
      if (autoRefreshTimer.current) clearInterval(autoRefreshTimer.current);
    }
    return () => {
      if (autoRefreshTimer.current) clearInterval(autoRefreshTimer.current);
    };
  }, [autoRefresh, load]);

  const visible = entries.filter((e) => matchesSearch(e, search));

  const levelCounts = visible.reduce<Record<Level, number>>(
    (acc, e) => {
      const lvl = (EVENT_META[e.event]?.level ?? 'muted') as Level;
      acc[lvl] = (acc[lvl] ?? 0) + 1;
      return acc;
    },
    { success: 0, error: 0, warn: 0, info: 0, muted: 0 },
  );

  return (
    <div className="page-shell max-w-6xl space-y-5">
      <PageHeader
        eyebrow="Audit Feed"
        title="Activity Log"
        description="Structured event stream — logins, relogins, uploads, circuit breakers, proxy changes."
        icon={<ScrollText className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          <div className="flex items-center gap-2">
            {/* Live indicator */}
            {autoRefresh && (
              <span className="flex items-center gap-1.5 text-xs text-[#9ece6a]">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#9ece6a] opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-[#9ece6a]" />
                </span>
                LIVE
              </span>
            )}
            <Button
              variant={autoRefresh ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setAutoRefresh((v) => !v)}
            >
              <Activity className="h-4 w-4" />
              {autoRefresh ? 'Live On' : 'Live Off'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(offset)}
              loading={loading}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => downloadJson(visible)}
              disabled={visible.length === 0}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      {/* Filters bar */}
      <div className="glass-panel flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-1">
          <label className="field-label" htmlFor="log-username">Username</label>
          <input
            id="log-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void load(0)}
            placeholder="@filter_by_user"
            className="glass-field text-sm"
          />
        </div>
        <div className="w-full sm:w-52 space-y-1">
          <label className="field-label" htmlFor="log-event">Event</label>
          <select
            id="log-event"
            value={event}
            onChange={(e) => setEvent(e.target.value)}
            className="glass-select text-sm"
          >
            <option value="">All events</option>
            {ALL_EVENTS.map((k) => (
              <option key={k} value={k}>{EVENT_META[k]?.label ?? k}</option>
            ))}
          </select>
        </div>
        <Button variant="secondary" size="sm" onClick={() => void load(0)}>
          Apply
        </Button>

        <div className="flex-1 space-y-1 sm:border-l sm:border-[rgba(162,179,229,0.1)] sm:pl-4">
          <label className="field-label" htmlFor="log-search">Search results</label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#59658c]" />
            <input
              id="log-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="filter loaded rows…"
              className="glass-field pl-8 text-sm"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#59658c] hover:text-[#8f9bc4] cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Level summary pills */}
      {visible.length > 0 && (
        <div className="flex flex-wrap gap-2 px-0.5">
          {(Object.entries(levelCounts) as [Level, number][])
            .filter(([, count]) => count > 0)
            .map(([level, count]) => (
              <span
                key={level}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-wider',
                  LEVEL_STYLES[level].badge,
                )}
              >
                <span className={cn('h-1.5 w-1.5 rounded-full', LEVEL_STYLES[level].dot)} />
                {level} · {count}
              </span>
            ))}
          {search && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(162,179,229,0.12)] px-2.5 py-0.5 text-[10px] font-mono text-[#8f9bc4]">
              {visible.length} / {entries.length} rows
            </span>
          )}
          {lastRefreshed && !loading && (
            <span className="ml-auto text-[10px] font-mono text-[#59658c]">
              updated {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
        </div>
      )}

      {/* Log table */}
      {visible.length === 0 && !loading ? (
        <div className="glass-panel flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.04)]">
            <ScrollText className="h-6 w-6 text-[#7dcfff]" />
          </div>
          <p className="mt-4 text-sm font-semibold text-[#eef4ff]">No events found</p>
          <p className="mt-1 text-xs text-[#59658c]">
            {search ? 'No rows match your search filter.' : 'Events appear here as operator actions reach the backend.'}
          </p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden p-0">
          {/* Table head */}
          <div className="grid grid-cols-[140px_140px_1fr] gap-0 border-b border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] px-4 py-2 text-[10px] font-semibold uppercase tracking-widest text-[#59658c] hidden sm:grid">
            <span>Timestamp</span>
            <span>Event</span>
            <span>Account · Detail</span>
          </div>

          {/* Rows */}
          <div className="divide-y divide-[rgba(162,179,229,0.05)]">
            {loading && entries.length === 0
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
              : visible.map((entry, idx) => (
                  <LogRow key={`${entry.ts}-${idx}`} entry={entry} />
                ))}
          </div>
        </div>
      )}

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#59658c]">
            {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={offset === 0}
              onClick={() => void load(Math.max(0, offset - LIMIT))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={offset + LIMIT >= total}
              onClick={() => void load(offset + LIMIT)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Row ──────────────────────────────────────────────────────────────────────

function LogRow({ entry }: { entry: ActivityLogEntry }) {
  const meta = EVENT_META[entry.event] ?? { label: entry.event.toUpperCase(), level: 'muted' as Level, Icon: Activity };
  const { label, level, Icon } = meta;
  const styles = LEVEL_STYLES[level];

  return (
    <div className="group grid grid-cols-1 gap-1 px-4 py-2.5 transition-colors hover:bg-[rgba(255,255,255,0.025)] sm:grid-cols-[140px_140px_1fr] sm:items-center sm:gap-0">
      {/* Timestamp */}
      <time className="font-mono text-[11px] text-[#59658c] group-hover:text-[#7b8abf]">
        {fmtTs(entry.ts)}
      </time>

      {/* Event badge */}
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide',
            styles.badge,
          )}
        >
          <Icon className={cn('h-2.5 w-2.5', styles.icon)} />
          {label}
        </span>
      </div>

      {/* Account + detail */}
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-mono text-[12px] font-semibold text-[#c0caf5]">
          @{entry.username || 'system'}
        </span>
        {entry.detail && (
          <span className="truncate text-[11px] text-[#59658c] group-hover:text-[#8e9ac0]">
            {entry.detail}
          </span>
        )}
        {/* Mobile: show event badge inline */}
        <Badge
          variant={level === 'success' ? 'green' : level === 'error' ? 'red' : level === 'warn' ? 'yellow' : level === 'info' ? 'blue' : 'gray'}
          className="!min-h-0 !py-0.5 !text-[9px] sm:hidden"
        >
          {label}
        </Badge>
      </div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="grid grid-cols-1 gap-1 px-4 py-2.5 sm:grid-cols-[140px_140px_1fr] sm:items-center sm:gap-0">
      <div className="h-3 w-28 animate-pulse rounded bg-[rgba(162,179,229,0.08)]" />
      <div className="h-4 w-24 animate-pulse rounded bg-[rgba(162,179,229,0.06)]" />
      <div className="h-3 w-48 animate-pulse rounded bg-[rgba(162,179,229,0.06)]" />
    </div>
  );
}
