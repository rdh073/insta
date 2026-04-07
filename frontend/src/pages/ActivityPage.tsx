import { useCallback, useEffect, useRef, useState } from 'react';
import {
  CheckCircle,
  Globe,
  ImagePlus,
  LogIn,
  LogOut,
  RefreshCw,
  ScrollText,
} from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { logsApi } from '../api/logs';
import type { ActivityLogEntry } from '../types';

const EVENT_META: Record<
  string,
  {
    label: string;
    variant: 'green' | 'red' | 'blue' | 'gray' | 'yellow';
    Icon: React.FC<{ className?: string }>;
  }
> = {
  login_success: { label: 'Login', variant: 'green', Icon: LogIn },
  login_failed: { label: 'Login Failed', variant: 'red', Icon: LogIn },
  relogin_success: { label: 'Relogin', variant: 'green', Icon: RefreshCw },
  relogin_failed: { label: 'Relogin Failed', variant: 'red', Icon: RefreshCw },
  logout: { label: 'Logout', variant: 'gray', Icon: LogOut },
  proxy_changed: { label: 'Proxy Changed', variant: 'blue', Icon: Globe },
  post_success: { label: 'Post', variant: 'green', Icon: ImagePlus },
  post_failed: { label: 'Post Failed', variant: 'red', Icon: ImagePlus },
};

const ALL_EVENTS = Object.keys(EVENT_META);
const LIMIT = 50;

export function ActivityPage() {
  const didInitialLoad = useRef(false);
  const [entries, setEntries] = useState<ActivityLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState('');
  const [event, setEvent] = useState('');
  const [offset, setOffset] = useState(0);

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
      } catch {
        setEntries([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [event, username],
  );

  useEffect(() => {
    if (didInitialLoad.current) return;
    didInitialLoad.current = true;
    void load(0);
  }, [load]);

  return (
    <div className="page-shell max-w-6xl space-y-6">
      <PageHeader
        eyebrow="Audit Feed"
        title="Activity Timeline"
        description="Operator-visible events across login state, relogin attempts, proxy changes, and publishing actions."
        icon={<ScrollText className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load(offset)} loading={loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      >
        <div className="metric-grid">
          <HeaderStat label="Events" value={total} tone="cyan" />
          <HeaderStat label="Filter" value={event ? EVENT_META[event]?.label ?? event : 'All events'} tone="violet" />
        </div>
      </PageHeader>

      <Card className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="flex-1 space-y-2">
            <label className="field-label" htmlFor="activity-username">
              Username
            </label>
            <input
              id="activity-username"
              value={username}
              onChange={(entry) => setUsername(entry.target.value)}
              placeholder="@filter_by_user"
              className="glass-field text-sm"
              aria-label="Filter by username"
            />
          </div>
          <div className="w-full lg:w-64 space-y-2">
            <label className="field-label" htmlFor="activity-event">
              Event type
            </label>
            <select
              id="activity-event"
              value={event}
              onChange={(entry) => setEvent(entry.target.value)}
              className="glass-select text-sm"
              aria-label="Filter by event type"
            >
              <option value="">All events</option>
              {ALL_EVENTS.map((eventKey) => (
                <option key={eventKey} value={eventKey}>
                  {EVENT_META[eventKey]?.label ?? eventKey}
                </option>
              ))}
            </select>
          </div>
          <Button variant="secondary" onClick={() => void load(0)}>
            Apply filters
          </Button>
        </div>
      </Card>

      {entries.length === 0 && !loading ? (
        <Card className="py-18 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
            <ScrollText className="h-7 w-7 text-[#7dcfff]" />
          </div>
          <p className="mt-5 text-lg font-semibold text-[#eef4ff]">No activity recorded</p>
          <p className="mt-2 text-sm text-[#8e9ac0]">Events appear here as operator actions hit the backend log stream.</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {entries.map((entry, index) => (
            <LogEntryRow key={`${entry.ts}-${index}`} entry={entry} />
          ))}
        </div>
      )}

      {total > LIMIT && (
        <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[#8e9ac0]">
            Showing {offset + 1} to {Math.min(offset + LIMIT, total)} of {total}
          </p>
          <div className="flex gap-3">
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
        </Card>
      )}
    </div>
  );
}

function LogEntryRow({ entry }: { entry: ActivityLogEntry }) {
  const meta = EVENT_META[entry.event] ?? { label: entry.event, variant: 'gray' as const, Icon: CheckCircle };
  const { label, variant, Icon } = meta;

  return (
    <Card glow className="flex flex-col gap-2 !py-3 !px-4 sm:flex-row sm:items-center sm:justify-between sm:!px-5">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.7rem] ${
            variant === 'green'
              ? 'border border-[#9ece6a]/18 bg-[rgba(158,206,106,0.12)] text-[#9ece6a]'
              : variant === 'red'
                ? 'border border-[#f7768e]/18 bg-[rgba(247,118,142,0.12)] text-[#f7768e]'
                : variant === 'blue'
                  ? 'border border-[#7dcfff]/18 bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                  : variant === 'yellow'
                    ? 'border border-[#e0af68]/18 bg-[rgba(224,175,104,0.12)] text-[#e0af68]'
                    : 'border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.05)] text-[#8f9bc4]'
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold text-[#eef4ff]">@{entry.username || 'system'}</span>
            <Badge variant={variant} className="!min-h-0 !py-0.5 !text-[10px]">{label}</Badge>
          </div>
          {entry.detail && <p className="mt-0.5 truncate text-xs text-[#8e9ac0]">{entry.detail}</p>}
        </div>
      </div>

      <time className="shrink-0 font-mono text-[11px] text-[#59658c]">
        {new Date(entry.ts).toLocaleString()}
      </time>
    </Card>
  );
}
