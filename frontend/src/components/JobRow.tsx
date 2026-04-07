import { Check, AlertCircle, Loader, Clock } from 'lucide-react';
import { Card } from './ui/Card';
import { Badge } from './ui/Badge';
import type { PostJob } from '../types';

export function JobRow({ job }: { job: PostJob }) {
  const successCount = job.results.filter((r) => r.status === 'success').length;
  const failCount = job.results.filter((r) => r.status === 'failed').length;

  return (
    <Card glow className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="flex-1 line-clamp-2 text-sm leading-relaxed text-[#dbe5ff]">
          {job.caption || <span className="italic text-[#647196]">no caption</span>}
        </p>
        <div className="flex gap-1.5 items-center shrink-0">
          {job.status === 'running'     && <Badge variant="blue"><Loader className="w-3 h-3 animate-spin" />Running</Badge>}
          {job.status === 'completed'   && <Badge variant="green"><Check className="w-3 h-3" />Done</Badge>}
          {job.status === 'partial'     && <Badge variant="yellow"><AlertCircle className="w-3 h-3" />Partial</Badge>}
          {job.status === 'failed'      && <Badge variant="red"><AlertCircle className="w-3 h-3" />Failed</Badge>}
          {job.status === 'scheduled'   && <Badge variant="blue"><Clock className="w-3 h-3" />Scheduled</Badge>}
          {job.status === 'pending'     && <Badge variant="gray"><Clock className="w-3 h-3" />Pending</Badge>}
          {job.status === 'needs_media' && <Badge variant="yellow"><AlertCircle className="w-3 h-3" />Needs Media</Badge>}
        </div>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-[#7f8bb3]">
        <span>{job.targets.length} target{job.targets.length !== 1 ? 's' : ''}</span>
        {successCount > 0 && <span className="text-[#9ece6a]">{successCount} posted</span>}
        {failCount > 0    && <span className="text-[#f7768e]">{failCount} failed</span>}
        <span className="ml-auto rounded-full border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 font-mono text-[11px] text-[#7f8bb3]">
          {new Date(job.createdAt).toLocaleString()}
        </span>
      </div>

      {job.results.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {job.results.map((r) => (
            <Badge
              key={r.accountId}
              variant={r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'gray'}
            >
              @{r.username}
            </Badge>
          ))}
        </div>
      )}
    </Card>
  );
}
