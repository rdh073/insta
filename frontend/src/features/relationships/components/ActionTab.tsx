import { useCallback, useMemo, useState } from 'react';
import { Square as StopIcon, UserMinus, UserPlus } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { selectActiveAccounts, useAccountStore } from '../../../store/accounts';
import { useFollowAction } from '../hooks/useFollowAction';
import { AccountChip } from './AccountChip';
import { ResultRow } from './ResultRow';

function parseUsernames(raw: string): string[] {
  return raw
    .split(/[\n,;]+/)
    .map((s) => s.trim().replace(/^@/, ''))
    .filter(Boolean)
    .filter((v, i, arr) => arr.indexOf(v) === i);
}

export function ActionTab({ action }: { action: 'follow' | 'unfollow' }) {
  const accounts = useAccountStore((s) => s.accounts);
  const activeAccounts = useMemo(() => selectActiveAccounts({ accounts }), [accounts]);

  const [selectedAccountIds, setSelectedAccountIds] = useState<Set<string>>(new Set());
  const [targetInput, setTargetInput] = useState('');
  const { running, results, progress, execute, cancel, clearResults } = useFollowAction(action);

  const targets = useMemo(() => parseUsernames(targetInput), [targetInput]);

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

  const clearSelection = useCallback(() => setSelectedAccountIds(new Set()), []);

  return (
    <div className="space-y-5">
      {/* Account selector */}
      <Card>
        <div className="space-y-3 p-4">
          <div className="flex items-center justify-between">
            <p className="field-label">
              {action === 'follow' ? 'Acting Accounts (followers)' : 'Acting Accounts (unfollowers)'}
            </p>
            <div className="flex gap-1.5">
              <button type="button" onClick={selectAll} className="glass-chip cursor-pointer hover:text-[#7dcfff]">Select all</button>
              <button type="button" onClick={clearSelection} className="glass-chip cursor-pointer hover:text-[#f7768e]">Clear</button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeAccounts.length === 0 ? (
              <p className="text-sm text-[#59658c]">No active accounts. Activate accounts on the Accounts page first.</p>
            ) : (
              activeAccounts.map((acc) => (
                <AccountChip key={acc.id} account={acc} selected={selectedAccountIds.has(acc.id)} onToggle={() => toggleAccount(acc.id)} />
              ))
            )}
          </div>
          <p className="field-hint">{selectedAccountIds.size} of {activeAccounts.length} selected</p>
        </div>
      </Card>

      {/* Target usernames */}
      <Card>
        <div className="space-y-3 p-4">
          <p className="field-label">Target Usernames</p>
          <textarea
            value={targetInput}
            onChange={(e) => setTargetInput(e.target.value)}
            placeholder={'Enter usernames separated by newlines or commas\ne.g. alice, bob, charlie\n@diana\neve'}
            rows={5}
            className="glass-textarea w-full font-mono text-[13px]"
          />
          <div className="flex items-center justify-between">
            <p className="field-hint">{targets.length} target{targets.length !== 1 ? 's' : ''} parsed</p>
            {targets.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {targets.slice(0, 8).map((t) => <span key={t} className="glass-chip font-mono">@{t}</span>)}
                {targets.length > 8 && <span className="glass-chip">+{targets.length - 8} more</span>}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Execute */}
      <div className="flex items-center gap-3">
        {running ? (
          <Button variant="danger" size="lg" onClick={cancel}>
            <StopIcon className="h-4 w-4" />
            Cancel
          </Button>
        ) : (
          <Button
            variant={action === 'follow' ? 'primary' : 'danger'}
            size="lg"
            disabled={selectedAccountIds.size === 0 || targets.length === 0}
            onClick={() => execute(selectedAccountIds, targets)}
          >
            {action === 'follow' ? <UserPlus className="h-4 w-4" /> : <UserMinus className="h-4 w-4" />}
            {action === 'follow' ? 'Follow' : 'Unfollow'} {targets.length} user{targets.length !== 1 ? 's' : ''} from {selectedAccountIds.size} account{selectedAccountIds.size !== 1 ? 's' : ''}
          </Button>
        )}
        {results.length > 0 && !running && (
          <button type="button" onClick={clearResults} className="text-sm text-[#7f8bb3] hover:text-[#f7768e] transition-colors cursor-pointer">
            Clear results
          </button>
        )}
      </div>

      {/* Progress bar */}
      {running && progress.total > 0 && (
        <div className="space-y-1.5">
          <div className="h-2 overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
            <div
              className="h-full rounded-full bg-[linear-gradient(90deg,#7aa2f7,#7dcfff)] transition-[width] duration-300"
              style={{ width: `${Math.round((progress.completed / progress.total) * 100)}%` }}
            />
          </div>
          <p className="text-[12px] text-[#7f8bb3]">{progress.completed} / {progress.total} completed</p>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <Card>
          <div className="space-y-2 p-4">
            <div className="flex items-center justify-between">
              <p className="field-label">Results</p>
              <div className="flex gap-3 text-[12px]">
                <span className="text-[#9ece6a]">{results.filter((r) => r.success).length} succeeded</span>
                <span className="text-[#f7768e]">{results.filter((r) => !r.success).length} failed</span>
              </div>
            </div>
            <div className="max-h-64 space-y-1.5 overflow-y-auto">
              {results.map((r, i) => <ResultRow key={i} r={r} />)}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
