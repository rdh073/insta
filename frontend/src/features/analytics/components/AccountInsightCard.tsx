import { Loader, RefreshCw } from 'lucide-react';
import { cn } from '../../../lib/cn';
import { useAccountInsight } from '../hooks/useAccountInsight';

function fmt(n: number | null): string {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtDelta(n: number | null): string {
  if (n == null) return '—';
  const body = fmt(Math.abs(n));
  if (n > 0) return `+${body}`;
  if (n < 0) return `-${body}`;
  return body;
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="metric-tile">
      <p className="text-kicker">{label}</p>
      <p className={cn('mt-2 text-2xl font-semibold leading-none', tone ?? 'text-[#7aa2f7]')}>
        {value}
      </p>
    </div>
  );
}

interface Props {
  accountId: string;
}

export function AccountInsightCard({ accountId }: Props) {
  const { data, loading, error, stale, refetch } = useAccountInsight(accountId);

  if (!accountId) {
    return null;
  }

  if (!data && loading) {
    return (
      <div className="glass-panel flex h-40 items-center justify-center">
        <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
      </div>
    );
  }

  if (!data && error) {
    return (
      <div className="glass-panel flex flex-col gap-3 p-4">
        <p className="text-sm text-[#f7768e]">{error}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="glass-chip self-start text-xs"
        >
          <RefreshCw className="mr-1 inline h-3 w-3" /> Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const deltaTone =
    data.followerChangeLast7Days == null
      ? 'text-[#7aa2f7]'
      : data.followerChangeLast7Days >= 0
      ? 'text-[#9ece6a]'
      : 'text-[#f7768e]';

  return (
    <div className="glass-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-kicker">ACCOUNT INSIGHTS · LAST 7 DAYS</p>
          {stale && !loading && (
            <p className="mt-1 text-[10px] text-[#4a5578]">Cached — refresh for latest</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={loading}
          className="glass-chip text-xs disabled:opacity-50"
          aria-label="Refresh account insight"
        >
          {loading ? (
            <Loader className="mr-1 inline h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="mr-1 inline h-3 w-3" />
          )}
          Refresh
        </button>
      </div>

      <div className="metric-grid">
        <Tile label="FOLLOWERS" value={fmt(data.followersCount)} tone="text-[#7dcfff]" />
        <Tile label="FOLLOWER Δ 7D" value={fmtDelta(data.followerChangeLast7Days)} tone={deltaTone} />
        <Tile label="REACH 7D" value={fmt(data.reachLast7Days)} tone="text-[#7dcfff]" />
        <Tile label="IMPRESSIONS 7D" value={fmt(data.impressionsLast7Days)} tone="text-[#7aa2f7]" />
        <Tile label="PROFILE VIEWS 7D" value={fmt(data.profileViewsLast7Days)} tone="text-[#bb9af7]" />
        <Tile label="WEBSITE CLICKS 7D" value={fmt(data.websiteClicksLast7Days)} tone="text-[#9ece6a]" />
        <Tile label="FOLLOWING" value={fmt(data.followingCount)} tone="text-[#e0af68]" />
        <Tile label="POSTS" value={fmt(data.mediaCount)} tone="text-[#f7768e]" />
      </div>

      {error && (
        <p className="mt-3 text-[11px] text-[#f7768e]">
          Could not refresh: {error}
        </p>
      )}
    </div>
  );
}
