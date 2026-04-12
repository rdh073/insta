import { useState } from 'react';
import { Check, AlertCircle, Loader, Clock, Pause, Play, Square } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import { postsApi } from '../api/posts';
import type { PostJob } from '../types';

export function JobRow({ job }: { job: PostJob }) {
  const successCount = job.results.filter((r) => r.status === 'success').length;
  const failCount = job.results.filter((r) => r.status === 'failed').length;
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>, label: string) => {
    setBusy(true);
    try {
      await fn();
    } catch {
      toast.error(`Failed to ${label} job`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card glow className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="flex-1 line-clamp-2 text-sm leading-relaxed text-[var(--color-text-primary)]">
          {job.caption || <span className="italic text-[var(--color-text-disabled)]">no caption</span>}
        </p>
        <div className="flex gap-1.5 items-center shrink-0">
          {job.status === 'running'     && <Badge variant="blue"><Loader className="w-3 h-3 animate-spin" />Running</Badge>}
          {job.status === 'completed'   && <Badge variant="green"><Check className="w-3 h-3" />Done</Badge>}
          {job.status === 'partial'     && <Badge variant="yellow"><AlertCircle className="w-3 h-3" />Partial</Badge>}
          {job.status === 'failed'      && <Badge variant="red"><AlertCircle className="w-3 h-3" />Failed</Badge>}
          {job.status === 'stopped'     && <Badge variant="red"><Square className="w-3 h-3" />Stopped</Badge>}
          {job.status === 'scheduled'   && <Badge variant="blue"><Clock className="w-3 h-3" />Scheduled</Badge>}
          {job.status === 'pending'     && <Badge variant="gray"><Clock className="w-3 h-3" />Pending</Badge>}
          {job.status === 'paused'      && <Badge variant="yellow"><Pause className="w-3 h-3" />Paused</Badge>}
          {job.status === 'needs_media' && <Badge variant="yellow"><AlertCircle className="w-3 h-3" />Needs Media</Badge>}

          {job.status === 'running' && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => act(() => postsApi.pause(job.id), 'pause')}
                className="cursor-pointer rounded-lg border border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] px-2 py-1 text-[11px] text-[var(--color-warning-fg)] transition-colors hover:bg-[rgba(224,175,104,0.2)] disabled:opacity-50"
                title="Pause job"
              >
                <Pause className="h-3 w-3" />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => act(() => postsApi.stop(job.id), 'stop')}
                className="cursor-pointer rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-2 py-1 text-[11px] text-[var(--color-error-fg)] transition-colors hover:bg-[rgba(248,81,73,0.2)] disabled:opacity-50"
                title="Stop job"
              >
                <Square className="h-3 w-3" />
              </button>
            </>
          )}

          {job.status === 'paused' && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => act(() => postsApi.resume(job.id), 'resume')}
                className="cursor-pointer rounded-lg border border-[var(--color-success-border)] bg-[var(--color-success-bg)] px-2 py-1 text-[11px] text-[var(--color-success-fg)] transition-colors hover:bg-[rgba(158,206,106,0.2)] disabled:opacity-50"
                title="Resume job"
              >
                <Play className="h-3 w-3" />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => act(() => postsApi.stop(job.id), 'stop')}
                className="cursor-pointer rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-2 py-1 text-[11px] text-[var(--color-error-fg)] transition-colors hover:bg-[rgba(248,81,73,0.2)] disabled:opacity-50"
                title="Stop job"
              >
                <Square className="h-3 w-3" />
              </button>
            </>
          )}

          {(job.status === 'pending' || job.status === 'scheduled') && (
            <button
              type="button"
              disabled={busy}
              onClick={() => act(() => postsApi.stop(job.id), 'stop')}
              className="cursor-pointer rounded-lg border border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-2 py-1 text-[11px] text-[var(--color-error-fg)] transition-colors hover:bg-[rgba(248,81,73,0.2)] disabled:opacity-50"
              title="Cancel job"
            >
              <Square className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-[var(--color-text-muted)]">
        <span>{job.targets.length} target{job.targets.length !== 1 ? 's' : ''}</span>
        {successCount > 0 && <span className="text-[var(--color-success-fg)]">{successCount} posted</span>}
        {failCount > 0    && <span className="text-[var(--color-error-fg)]">{failCount} failed</span>}
        <span className="ml-auto rounded-full border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] px-2.5 py-1 font-mono text-[11px] text-[var(--color-text-muted)]">
          {new Date(job.createdAt).toLocaleString()}
        </span>
      </div>

      {job.results.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {job.results.map((r) => (
            <Badge
              key={r.accountId}
              variant={r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'gray'}
              title={r.error}
            >
              @{r.username}
            </Badge>
          ))}
        </div>
      )}
    </Card>
  );
}
