import { AlertCircle, CheckCircle2 } from 'lucide-react';
import type { JobResult } from '../types';

export function ResultRow({ r }: { r: JobResult }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-[rgba(162,179,229,0.1)] bg-[rgba(255,255,255,0.02)] px-3 py-2 text-[13px]">
      {r.success ? (
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[#9ece6a]" />
      ) : (
        <AlertCircle className="h-3.5 w-3.5 shrink-0 text-[#f7768e]" />
      )}
      <span className="font-mono text-[#8b93b8]">@{r.account}</span>
      <span className="text-[#59658c]">{r.action === 'follow' ? '\u2192' : '\u2190'}</span>
      <span className="font-mono text-[#c0caf5]">@{r.target}</span>
      {r.error && <span className="ml-auto text-[12px] text-[#f7768e]">{r.error}</span>}
    </div>
  );
}
