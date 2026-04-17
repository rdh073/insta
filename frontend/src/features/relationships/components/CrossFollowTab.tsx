import { useCallback, useMemo, useState } from 'react';
import { ArrowLeftRight, CheckCircle2, Loader, Minus, RefreshCw } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { selectActiveAccounts, useAccountStore } from '../../../store/accounts';
import { useCrossFollow } from '../hooks/useCrossFollow';
import { AccountChip } from './AccountChip';
import { ResultRow } from './ResultRow';

export function CrossFollowTab() {
  const accounts = useAccountStore((s) => s.accounts);
  const activeAccounts = useMemo(() => selectActiveAccounts({ accounts }), [accounts]);

  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<string>>(new Set());
  const selectedCount = selectedAccountIds.size;
  const pairCount = Math.floor(selectedCount * (selectedCount - 1) / 2);

  const { pairs, checking, executing, results, missingCount, checkRelationships, executeCrossFollow } =
    useCrossFollow(selectedAccountIds);

  const toggleAccount = useCallback((id: string) => {
    setSelectedAccountIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedAccountIds(new Set(activeAccounts.map((a) => a.id)));
  }, [activeAccounts]);

  return (
    <div className="space-y-5">
      {/* Account selector */}
      <Card>
        <div className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="field-label">Select Accounts for Cross-Follow</p>
            <button type="button" onClick={selectAll} className="glass-chip cursor-pointer hover:text-[#7dcfff]">Select all</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeAccounts.length < 2 ? (
              <p className="text-sm text-[#59658c]">Need at least 2 active accounts for cross-follow.</p>
            ) : (
              activeAccounts.map((acc) => (
                <AccountChip key={acc.id} account={acc} selected={selectedAccountIds.has(acc.id)} onToggle={() => toggleAccount(acc.id)} />
              ))
            )}
          </div>
          <p className="field-hint">{selectedCount} selected ({pairCount} pairs to check)</p>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <Button variant="secondary" size="lg" loading={checking} disabled={selectedCount < 2} onClick={checkRelationships}>
          <RefreshCw className="h-4 w-4" />
          Check Relationships
        </Button>
        {pairs.length > 0 && missingCount > 0 && (
          <Button variant="primary" size="lg" loading={executing} onClick={executeCrossFollow}>
            <ArrowLeftRight className="h-4 w-4" />
            Follow Missing ({missingCount * 2} actions max)
          </Button>
        )}
      </div>

      {/* Relationship matrix */}
      {pairs.length > 0 && (
        <Card>
          <div className="space-y-2 p-4">
            <p className="field-label">Relationship Matrix</p>
            <div className="space-y-2">
              {pairs.map((pair, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-[rgba(162,179,229,0.1)] bg-[rgba(255,255,255,0.02)] px-3 py-2.5 text-[13px]">
                  <span className="min-w-[100px] font-mono text-[#c0caf5]">@{pair.a}</span>
                  <FollowBadge value={pair.aFollowsB} />
                  <ArrowLeftRight className="h-3.5 w-3.5 text-[#59658c]" />
                  <FollowBadge value={pair.bFollowsA} />
                  <span className="min-w-[100px] text-right font-mono text-[#c0caf5]">@{pair.b}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <div className="space-y-2 p-4">
            <p className="field-label">Cross-Follow Results</p>
            <div className="max-h-64 space-y-1.5 overflow-y-auto">
              {results.map((r, i) => <ResultRow key={i} r={r} />)}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function FollowBadge({ value }: { value: boolean | null }) {
  if (value === true) {
    return (
      <span className="flex items-center gap-1 rounded-full border border-[rgba(158,206,106,0.28)] bg-[rgba(158,206,106,0.1)] px-2 py-0.5 text-[11px] text-[#9ece6a]">
        <CheckCircle2 className="h-3 w-3" /> follows
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="flex items-center gap-1 rounded-full border border-[rgba(247,118,142,0.28)] bg-[rgba(247,118,142,0.1)] px-2 py-0.5 text-[11px] text-[#f7768e]">
        <Minus className="h-3 w-3" /> not following
      </span>
    );
  }
  return (
    <span className="glass-chip text-[11px]">
      <Loader className="h-3 w-3 animate-spin" /> checking
    </span>
  );
}
