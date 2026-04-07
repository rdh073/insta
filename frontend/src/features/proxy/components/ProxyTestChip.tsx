import { AlertCircle, CheckCircle2 } from 'lucide-react';
import type { ProxyCheckResult } from '../../../types';

export function ProxyTestChip({ result }: { result: ProxyCheckResult }) {
  if (result.reachable) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-[rgba(158,206,106,0.28)] bg-[rgba(158,206,106,0.12)] px-2.5 py-1 text-[11px] font-medium text-[#9ece6a]">
          <CheckCircle2 className="h-3 w-3" />
          Reachable · {result.latency_ms}ms
        </span>
        {result.ip_address && (
          <span className="rounded-full border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1 font-mono text-[11px] text-[#7f8bb3]">
            {result.ip_address}
          </span>
        )}
        {result.protocol && (
          <span className="rounded-full border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.08)] px-2.5 py-1 text-[11px] font-medium text-[#7dcfff]">
            {result.protocol}
          </span>
        )}
        {result.anonymity && (
          <span
            className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
              result.anonymity === 'elite'
                ? 'border-[rgba(187,154,247,0.28)] bg-[rgba(187,154,247,0.12)] text-[#bb9af7]'
                : 'border-[rgba(247,118,142,0.28)] bg-[rgba(247,118,142,0.12)] text-[#f7768e]'
            }`}
          >
            {result.anonymity}
          </span>
        )}
      </div>
    );
  }
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-[rgba(247,118,142,0.28)] bg-[rgba(247,118,142,0.12)] px-2.5 py-1 text-[11px] font-medium text-[#f7768e]">
      <AlertCircle className="h-3 w-3" />
      {result.error ?? 'Unreachable'}
    </span>
  );
}
