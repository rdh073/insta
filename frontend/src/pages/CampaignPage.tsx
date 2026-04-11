import { useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  Loader,
  Pause,
  Play,
  RotateCcw,
  Send,
  Square,
  Trash2,
} from 'lucide-react';
import { postsApi } from '../api/posts';
import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { usePostJobStream } from '../features/posts/hooks/usePostJobStream';
import { usePostStore } from '../store/posts';
import type { PostJob } from '../types';

// ── Status filter ─────────────────────────────────────────────────────────────

type StatusFilter = 'all' | PostJob['status'];

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'running', label: 'Running' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
  { value: 'partial', label: 'Partial' },
  { value: 'failed', label: 'Failed' },
  { value: 'stopped', label: 'Stopped' },
  { value: 'needs_media', label: 'Needs Media' },
];

const MEDIA_TYPE_LABEL: Record<string, string> = {
  photo: 'Photo',
  reels: 'Reels',
  video: 'Feed Video',
  album: 'Album',
  igtv: 'IGTV',
};

// ── Status badge helper ───────────────────────────────────────────────────────

function StatusBadge({ status }: { status: PostJob['status'] }) {
  switch (status) {
    case 'running':     return <Badge variant="blue"><Loader className="h-3 w-3 animate-spin" />Running</Badge>;
    case 'paused':      return <Badge variant="yellow"><Pause className="h-3 w-3" />Paused</Badge>;
    case 'completed':   return <Badge variant="green"><CheckCircle className="h-3 w-3" />Completed</Badge>;
    case 'partial':     return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />Partial</Badge>;
    case 'failed':      return <Badge variant="red"><AlertCircle className="h-3 w-3" />Failed</Badge>;
    case 'stopped':     return <Badge variant="red"><Square className="h-3 w-3" />Stopped</Badge>;
    case 'scheduled':   return <Badge variant="blue"><Clock className="h-3 w-3" />Scheduled</Badge>;
    case 'pending':     return <Badge variant="gray"><Clock className="h-3 w-3" />Pending</Badge>;
    case 'needs_media': return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />Needs Media</Badge>;
    default:            return <Badge variant="gray">{status}</Badge>;
  }
}

// ── Job card ──────────────────────────────────────────────────────────────────

function JobCard({ job, onDelete }: { job: PostJob; onDelete: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState<'stop' | 'pause' | 'resume' | 'retry' | 'delete' | null>(null);

  const successCount  = job.results.filter((r) => r.status === 'success').length;
  const failCount     = job.results.filter((r) => r.status === 'failed').length;
  const pendingCount  = job.results.filter((r) => r.status === 'pending').length;
  const uploadingCount = job.results.filter((r) => r.status === 'uploading').length;
  const skippedCount  = job.results.filter((r) => r.status === 'skipped').length;

  const canPause  = job.status === 'running';
  const canResume = job.status === 'paused';
  const canStop   = job.status === 'running' || job.status === 'paused' || job.status === 'pending' || job.status === 'scheduled';
  const canRetry  = job.status === 'failed' || job.status === 'stopped' || job.status === 'partial';
  const canDelete = ['completed', 'failed', 'stopped', 'partial', 'needs_media'].includes(job.status);

  async function handleAction(action: 'stop' | 'pause' | 'resume') {
    setActionLoading(action);
    try {
      await postsApi[action](job.id);
    } catch {
      // SSE stream will sync next state
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRetry() {
    setActionLoading('retry');
    try {
      await postsApi.retry(job.id);
    } catch {
      // SSE stream will reflect real state
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDelete() {
    setActionLoading('delete');
    try {
      await postsApi.delete(job.id);
      onDelete(job.id);
    } catch {
      // ignore — SSE will reflect real state
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <Card glow className="overflow-hidden">
      {/* Header: top row = info (clickable to expand) + action buttons (not inside button) */}
      <div className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          {/* Left — clickable info area */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => setExpanded((v) => !v)}
            onKeyDown={(e) => e.key === 'Enter' && setExpanded((v) => !v)}
            className="min-w-0 flex-1 cursor-pointer"
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={job.status} />
              {job.mediaType && (
                <span className="glass-chip !text-[11px]">
                  {MEDIA_TYPE_LABEL[job.mediaType] ?? job.mediaType}
                </span>
              )}
              <span className="glass-chip !text-[11px]">
                {job.targets.length} account{job.targets.length !== 1 ? 's' : ''}
              </span>
            </div>
            <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[#dbe5ff]">
              {job.caption || <span className="italic text-[#647196]">no caption</span>}
            </p>
          </div>

          {/* Right — action buttons + chevron (NOT inside any button) */}
          <div className="flex shrink-0 items-center gap-1.5">
            {canResume && (
              <button
                type="button"
                onClick={() => handleAction('resume')}
                disabled={actionLoading !== null}
                title="Resume"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(158,206,106,0.3)] bg-[rgba(158,206,106,0.1)] text-[#9ece6a] transition-all hover:bg-[rgba(158,206,106,0.2)] disabled:opacity-50"
              >
                {actionLoading === 'resume' ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              </button>
            )}
            {canPause && (
              <button
                type="button"
                onClick={() => handleAction('pause')}
                disabled={actionLoading !== null}
                title="Pause"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(224,175,104,0.3)] bg-[rgba(224,175,104,0.1)] text-[#e0af68] transition-all hover:bg-[rgba(224,175,104,0.2)] disabled:opacity-50"
              >
                {actionLoading === 'pause' ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <Pause className="h-3.5 w-3.5" />}
              </button>
            )}
            {canStop && (
              <button
                type="button"
                onClick={() => handleAction('stop')}
                disabled={actionLoading !== null}
                title="Stop"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(247,118,142,0.3)] bg-[rgba(247,118,142,0.1)] text-[#f7768e] transition-all hover:bg-[rgba(247,118,142,0.2)] disabled:opacity-50"
              >
                {actionLoading === 'stop' ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <Square className="h-3.5 w-3.5" />}
              </button>
            )}
            {canRetry && (
              <button
                type="button"
                onClick={() => void handleRetry()}
                disabled={actionLoading !== null}
                title="Retry failed accounts"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(122,162,247,0.3)] bg-[rgba(122,162,247,0.1)] text-[#7aa2f7] transition-all hover:bg-[rgba(122,162,247,0.2)] disabled:opacity-50"
              >
                {actionLoading === 'retry' ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={actionLoading !== null}
                title="Delete job"
                className="flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(247,118,142,0.16)] bg-transparent text-[#4a5578] transition-all hover:border-[rgba(247,118,142,0.4)] hover:bg-[rgba(247,118,142,0.08)] hover:text-[#f7768e] disabled:opacity-50"
              >
                {actionLoading === 'delete' ? <Loader className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex h-7 w-7 cursor-pointer items-center justify-center text-[#4a5578]"
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Summary stats row — clickable to expand */}
        <div
          role="button"
          tabIndex={-1}
          onClick={() => setExpanded((v) => !v)}
          className="flex cursor-pointer flex-wrap items-center gap-3 text-xs text-[#7f8bb3]"
        >
          {successCount > 0 && (
            <span className="flex items-center gap-1 text-[#9ece6a]">
              <CheckCircle className="h-3 w-3" />{successCount} posted
            </span>
          )}
          {uploadingCount > 0 && (
            <span className="flex items-center gap-1 text-[#7dcfff]">
              <Loader className="h-3 w-3 animate-spin" />{uploadingCount} uploading
            </span>
          )}
          {failCount > 0 && (
            <span className="flex items-center gap-1 text-[#f7768e]">
              <AlertCircle className="h-3 w-3" />{failCount} failed
            </span>
          )}
          {skippedCount > 0 && (
            <span className="flex items-center gap-1 text-[#565f89]">
              <Square className="h-3 w-3" />{skippedCount} skipped
            </span>
          )}
          {pendingCount > 0 && (
            <span className="flex items-center gap-1 text-[#7f8bb3]">
              <Clock className="h-3 w-3" />{pendingCount} pending
            </span>
          )}
          <span className="ml-auto font-mono text-[11px]">
            {new Date(job.createdAt).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Expanded per-account results */}
      {expanded && job.results.length > 0 && (
        <div className="border-t border-[rgba(162,179,229,0.1)] px-5 pb-4 pt-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[#4a5578]">
            Per-account results
          </p>
          <div className="space-y-1.5">
            {job.results.map((result) => (
              <div
                key={result.accountId}
                className="flex items-center justify-between gap-3 rounded-[0.9rem] border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.03)] px-3 py-2"
              >
                <span className="text-sm font-medium text-[#c0caf5]">@{result.username}</span>
                <div className="flex items-center gap-2">
                  {result.status === 'success' && (
                    <Badge variant="green"><CheckCircle className="h-3 w-3" />Posted</Badge>
                  )}
                  {result.status === 'uploading' && (
                    <Badge variant="blue"><Loader className="h-3 w-3 animate-spin" />Uploading</Badge>
                  )}
                  {result.status === 'failed' && (
                    <Badge variant="red"><AlertCircle className="h-3 w-3" />Failed</Badge>
                  )}
                  {result.status === 'skipped' && (
                    <Badge variant="gray"><Square className="h-3 w-3" />Skipped</Badge>
                  )}
                  {result.status === 'pending' && (
                    <Badge variant="gray"><Clock className="h-3 w-3" />Pending</Badge>
                  )}
                  {result.error && (
                    <span className="max-w-[18rem] truncate text-[11px] text-[#f7768e]" title={result.error}>
                      {result.error}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function CampaignPage() {
  const jobs      = usePostStore((s) => s.jobs);
  const removeJob = usePostStore((s) => s.removeJob);
  const filter    = usePostStore((s) => s.campaignFilter);
  const setFilter = usePostStore((s) => s.setCampaignFilter);

  // Real-time updates via SSE — replaces polling.
  // forceConnect=true because CampaignPage is the monitoring dashboard
  // and should always show live state.
  usePostJobStream(true);

  const filtered = filter === 'all' ? jobs : jobs.filter((j) => j.status === filter);
  const sorted   = [...filtered].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );

  const totalJobs    = jobs.length;
  const activeJobs   = jobs.filter((j) => ['pending', 'running', 'scheduled', 'paused'].includes(j.status)).length;
  const completedJobs = jobs.filter((j) => j.status === 'completed').length;
  const failedJobs   = jobs.filter((j) => j.status === 'failed' || j.status === 'partial' || j.status === 'stopped').length;

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Broadcast Control"
        title="Campaign Monitor"
        description="Track every post job across all accounts — live status, per-account results, and historical queue."
        icon={<Layers className="h-6 w-6 text-[#7dcfff]" />}
      >
        <div className="metric-grid">
          <HeaderStat label="Total Jobs" value={totalJobs} tone="cyan" />
          <HeaderStat label="Active" value={activeJobs} tone="blue" />
          <HeaderStat label="Completed" value={completedJobs} tone="green" />
          <HeaderStat label="Failed / Partial" value={failedJobs} tone="rose" />
        </div>
      </PageHeader>

      {/* Status filter chips */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map(({ value, label }) => {
          const count = value === 'all' ? jobs.length : jobs.filter((j) => j.status === value).length;
          if (value !== 'all' && count === 0) return null;
          return (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`cursor-pointer rounded-xl border px-3 py-1.5 text-[12px] font-medium transition-all duration-200 ${
                filter === value
                  ? 'border-[rgba(125,207,255,0.4)] bg-[rgba(125,207,255,0.14)] text-[#eef4ff]'
                  : 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] text-[#8e9ac0] hover:border-[rgba(162,179,229,0.28)] hover:text-[#c0caf5]'
              }`}
            >
              {label}
              {count > 0 && (
                <span className="ml-1.5 rounded-full bg-[rgba(255,255,255,0.08)] px-1.5 py-0.5 text-[10px]">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Job list */}
      {sorted.length === 0 ? (
        <Card className="py-18 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
            <Send className="h-7 w-7 text-[#7dcfff]" />
          </div>
          <p className="mt-5 text-lg font-semibold text-[#eef4ff]">
            {filter === 'all' ? 'No jobs yet' : `No ${filter} jobs`}
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8e9ac0]">
            {filter === 'all'
              ? 'Create your first broadcast job from the Broadcast page.'
              : 'Try a different status filter.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {sorted.map((job) => (
            <JobCard key={job.id} job={job} onDelete={removeJob} />
          ))}
        </div>
      )}
    </div>
  );
}
