import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { BarChart2, ChevronDown, ChevronRight, Loader } from 'lucide-react';
import { insightsApi } from '../api/instagram/insights';
import type { InsightPostType, InsightTimeFrame, InsightOrdering } from '../api/instagram/insights';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { MediaInsightSummary } from '../types/instagram/insight';
import { Button } from '../components/ui/Button';
import { useInsightsStore } from '../store/insights';
import { cn } from '../lib/cn';
import { AccountInsightCard } from '../features/analytics/components/AccountInsightCard';

const POST_TYPES: InsightPostType[] = ['ALL', 'PHOTO', 'VIDEO', 'CAROUSEL'];
const TIME_FRAMES: InsightTimeFrame[] = ['WEEK', 'MONTH', 'SIX_MONTHS', 'ONE_YEAR', 'TWO_YEARS'];
const ORDERINGS: InsightOrdering[] = [
  'REACH_COUNT', 'IMPRESSIONS', 'ENGAGEMENT', 'LIKE_COUNT',
  'COMMENT_COUNT', 'SHARE_COUNT', 'SAVE_COUNT',
];

function fmt(n: number | null) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function MetricTile({ label, value, tone }: { label: string; value: number | null; tone?: string }) {
  return (
    <div className="metric-tile !p-3">
      <p className="text-kicker !text-[0.6rem] !tracking-[0.16em]">{label}</p>
      <p className={cn('mt-2 text-xl font-semibold leading-none', tone ?? 'text-[#7aa2f7]')}>{fmt(value)}</p>
    </div>
  );
}

function InsightRow({ insight }: { insight: MediaInsightSummary }) {
  const [expanded, setExpanded] = useState(false);
  const extras = Object.entries(insight.extraMetrics);

  return (
    <div className="rounded-2xl border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((c) => !c)}
        className={cn(
          'flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left transition-colors duration-150',
          expanded ? 'border-b border-[rgba(162,179,229,0.08)]' : '',
        )}
      >
        <span className="font-mono text-xs text-[#4a5578]">{insight.mediaPk}</span>
        <div className="flex flex-1 flex-wrap gap-x-6 gap-y-1">
          {[
            { label: 'Reach',       value: insight.reachCount,      tone: 'text-[#7dcfff]' },
            { label: 'Impressions', value: insight.impressionCount, tone: 'text-[#7aa2f7]' },
            { label: 'Likes',       value: insight.likeCount,       tone: 'text-[#f7768e]' },
            { label: 'Comments',    value: insight.commentCount,    tone: 'text-[#bb9af7]' },
            { label: 'Shares',      value: insight.shareCount,      tone: 'text-[#9ece6a]' },
            { label: 'Saves',       value: insight.saveCount,       tone: 'text-[#e0af68]' },
          ].map(({ label, value, tone }) => (
            <span key={label} className="flex items-center gap-1 text-[11px]">
              <span className="text-[#4a5578]">{label}</span>
              <span className={cn('font-medium', tone)}>{fmt(value)}</span>
            </span>
          ))}
        </div>
        {extras.length > 0 && (
          expanded
            ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[#7dcfff]" />
            : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#4a5578]" />
        )}
      </button>

      {expanded && extras.length > 0 && (
        <div className="px-4 py-3">
          <p className="mb-2 text-[10px] text-[#4a5578]">Extra metrics</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
            {extras.map(([k, v]) => (
              <span key={k} className="flex items-center gap-1 text-[11px]">
                <span className="text-[#4a5578]">{k}</span>
                <span className="font-medium text-[#9aa7cf]">{String(v)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function sumMetric(items: MediaInsightSummary[], key: keyof MediaInsightSummary): number | null {
  const vals = items.map((i) => i[key] as number | null).filter((v): v is number => v != null);
  return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) : null;
}

export function InsightsPage() {
  const { accountId, setAccountId } = useAccountPicker();

  const postType  = useInsightsStore((s) => s.postType);
  const timeFrame = useInsightsStore((s) => s.timeFrame);
  const ordering  = useInsightsStore((s) => s.ordering);
  const result    = useInsightsStore((s) => s.result);

  const setPostType  = useInsightsStore((s) => s.setPostType);
  const setTimeFrame = useInsightsStore((s) => s.setTimeFrame);
  const setOrdering  = useInsightsStore((s) => s.setOrdering);
  const setResult    = useInsightsStore((s) => s.setResult);
  const setScopeAccountId = useInsightsStore((s) => s.setScopeAccountId);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setScopeAccountId(accountId);
  }, [accountId, setScopeAccountId]);

  async function handleLoad() {
    if (!accountId) return;
    setLoading(true);
    try {
      const data = await insightsApi.listMediaInsights(accountId, {
        post_type: postType,
        time_frame: timeFrame,
        ordering,
      });
      setResult(data);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const items = result?.items ?? [];

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-5 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <AccountPicker
            value={accountId}
            onChange={(id) => {
              setScopeAccountId(id);
              setAccountId(id);
            }}
            className="w-48"
          />
          <select value={postType} onChange={(e) => setPostType(e.target.value as InsightPostType)} className="glass-select text-sm">
            {POST_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={timeFrame} onChange={(e) => setTimeFrame(e.target.value as InsightTimeFrame)} className="glass-select text-sm">
            {TIME_FRAMES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
          </select>
          <select value={ordering} onChange={(e) => setOrdering(e.target.value as InsightOrdering)} className="glass-select text-sm">
            {ORDERINGS.map((o) => <option key={o} value={o}>{o.replace('_', ' ')}</option>)}
          </select>
          <Button size="sm" loading={loading} onClick={() => void handleLoad()}>
            <BarChart2 className="h-3.5 w-3.5 mr-1" /> Load
          </Button>
        </div>
      </div>

      {/* Account-level dashboard (above media list) */}
      {accountId && (
        <div className="shrink-0 border-b border-[rgba(162,179,229,0.06)] px-5 py-3">
          <AccountInsightCard accountId={accountId} />
        </div>
      )}

      {/* Aggregate totals */}
      {items.length > 0 && (
        <div className="shrink-0 border-b border-[rgba(162,179,229,0.06)] px-5 py-3">
          <div className="metric-grid">
            <MetricTile label="TOTAL REACH" value={sumMetric(items, 'reachCount')} tone="text-[#7dcfff]" />
            <MetricTile label="IMPRESSIONS" value={sumMetric(items, 'impressionCount')} tone="text-[#7aa2f7]" />
            <MetricTile label="LIKES" value={sumMetric(items, 'likeCount')} tone="text-[#f7768e]" />
            <MetricTile label="SHARES" value={sumMetric(items, 'shareCount')} tone="text-[#9ece6a]" />
          </div>
        </div>
      )}

      {/* List */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {!result && !loading && (
          <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
            Select filters and click Load
          </div>
        )}
        {loading && (
          <div className="flex h-40 items-center justify-center">
            <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
          </div>
        )}
        {result && !loading && (
          <div className="mx-auto max-w-3xl space-y-2">
            <p className="text-[11px] text-[#4a5578]">{result.count} posts</p>
            {items.map((item) => (
              <InsightRow key={item.mediaPk} insight={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
