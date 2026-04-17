import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Activity,
  AlertTriangle,
  AtSign,
  Check,
  CheckCircle,
  ChevronDown,
  Edit3,
  FileText,
  Flame,
  Handshake,
  Hash,
  Heart,
  MessageCircle,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Target,
  Users,
  XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { smartEngagementApi } from '../api/smart-engagement';
import type { ResumeRequest, SmartEngagementRequest, SmartEngagementResponse } from '../api/smart-engagement';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { useAccountStore } from '../store/accounts';
import { useSettingsStore } from '../store/settings';
import { getValidSelectedIds, useSmartEngagementStore } from '../store/smartEngagement';
import { buildProxyImageUrl } from '../lib/api-base';
import { cn } from '../lib/cn';
import type { Account } from '../types';

// ─── Goal templates ──────────────────────────────────────────────────────────

const GOAL_TEMPLATES: Array<{ label: string; goal: string; icon: LucideIcon }> = [
  { label: 'Like niche posts', goal: 'like educational and informative posts in niche', icon: Heart },
  { label: 'Comment on follower posts', goal: 'leave thoughtful comments on recent follower posts', icon: MessageCircle },
  { label: 'Engage with hashtags', goal: 'engage with top posts under relevant niche hashtags', icon: Hash },
  { label: 'Warm up cold leads', goal: 'engage with potential leads who recently interacted with profile', icon: Flame },
  { label: 'Reply to mentions', goal: 'reply to story mentions and post tags', icon: AtSign },
  { label: 'Support collaborators', goal: 'like and comment on recent posts from collaboration partners', icon: Handshake },
];

// ─── Status dot color ────────────────────────────────────────────────────────

const STATUS_DOT: Record<Account['status'], string> = {
  active: 'bg-[#9ece6a]',
  idle: 'bg-[#4a5578]',
  logging_in: 'bg-[#e0af68]',
  error: 'bg-[#f7768e]',
  challenge: 'bg-[#ff9db0]',
  '2fa_required': 'bg-[#e0af68]',
};

// ─── Account multi-select picker ─────────────────────────────────────────────

function AccountMultiPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const accounts = useAccountStore((s) => s.accounts);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
  const activeAccounts = accounts.filter((a) => a.status === 'active');
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const filtered = query.trim()
    ? activeAccounts.filter((a) => a.username.toLowerCase().includes(query.toLowerCase()))
    : activeAccounts;

  const allSelected = activeAccounts.length > 0 && activeAccounts.every((a) => selected.includes(a.id));
  const allFilteredSelected = filtered.length > 0 && filtered.every((a) => selected.includes(a.id));

  useEffect(() => {
    if (!open) { setQuery(''); return; }
    setTimeout(() => searchRef.current?.focus(), 30);
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  function toggleAll() {
    if (allSelected) {
      onChange([]);
    } else {
      onChange(activeAccounts.map((a) => a.id));
    }
  }

  function toggleFiltered() {
    if (allFilteredSelected) {
      onChange(selected.filter((id) => !filtered.find((a) => a.id === id)));
    } else {
      const newIds = filtered.map((a) => a.id).filter((id) => !selected.includes(id));
      onChange([...selected, ...newIds]);
    }
  }

  function toggleOne(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id));
    } else {
      onChange([...selected, id]);
    }
  }

  // Label for trigger button
  const selectedAccounts = activeAccounts.filter((a) => selected.includes(a.id));
  let triggerLabel: string;
  if (allSelected && activeAccounts.length > 0) {
    triggerLabel = `All Active (${activeAccounts.length})`;
  } else if (selectedAccounts.length === 0) {
    triggerLabel = 'Select accounts…';
  } else if (selectedAccounts.length === 1) {
    triggerLabel = `@${selectedAccounts[0].username}`;
  } else {
    triggerLabel = `@${selectedAccounts[0].username} +${selectedAccounts.length - 1} more`;
  }

  if (activeAccounts.length === 0) {
    return (
      <div className="rounded-xl border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.06)] px-3 py-2.5 text-sm text-[#ffccd7]">
        No active accounts — log in at least one account first.
      </div>
    );
  }

  const isSearching = query.trim().length > 0;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl border border-[rgba(162,179,229,0.16)] bg-[rgba(10,14,24,0.52)] px-3 py-2.5 text-sm text-[#c0caf5] transition-colors hover:border-[rgba(125,207,255,0.3)]"
      >
        <div className="flex min-w-0 items-center gap-2">
          <Users className="h-3.5 w-3.5 shrink-0 text-[#7aa2f7]" />
          <span className="truncate">{triggerLabel}</span>
        </div>
        <ChevronDown className={cn('h-3.5 w-3.5 shrink-0 text-[#4a5578] transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-0 right-0 z-50 mt-1 flex max-h-80 flex-col overflow-hidden rounded-xl border border-[rgba(125,207,255,0.14)] bg-[rgba(9,12,22,0.97)] shadow-[0_12px_36px_rgba(4,8,18,0.5)] backdrop-blur-2xl">
          {/* Search input */}
          <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-3 py-2">
            <div className="flex items-center gap-2 rounded-lg border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1.5">
              <Search className="h-3.5 w-3.5 shrink-0 text-[#4a5578]" />
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search accounts…"
                className="min-w-0 flex-1 bg-transparent text-[13px] text-[#c0caf5] outline-none placeholder:text-[#4a5578]"
              />
              {query && (
                <button type="button" onClick={() => setQuery('')} className="cursor-pointer text-[#4a5578] hover:text-[#c0caf5]">
                  <XCircle className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Select All / Select Filtered */}
          <button
            type="button"
            onClick={isSearching ? toggleFiltered : toggleAll}
            className="flex w-full shrink-0 cursor-pointer items-center gap-3 border-b border-[rgba(162,179,229,0.08)] px-3 py-2.5 text-left transition-colors hover:bg-[rgba(125,207,255,0.06)]"
          >
            <div className={cn(
              'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
              (isSearching ? allFilteredSelected : allSelected)
                ? 'border-[#7dcfff] bg-[rgba(125,207,255,0.2)]'
                : 'border-[rgba(162,179,229,0.2)] bg-transparent',
            )}>
              {(isSearching ? allFilteredSelected : allSelected) && <Check className="h-2.5 w-2.5 text-[#7dcfff]" />}
            </div>
            <span className="text-[13px] font-semibold text-[#7dcfff]">
              {isSearching ? `Select all matching (${filtered.length})` : `All Active Accounts`}
            </span>
            {!isSearching && <Badge variant="blue" className="ml-auto">{activeAccounts.length}</Badge>}
          </button>

          {/* Individual accounts — scrollable */}
          <div className="overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-center text-[13px] text-[#4a5578]">No accounts match "{query}"</div>
            ) : (
              filtered.map((acc) => {
                const checked = selected.includes(acc.id);
                return (
                  <button
                    key={acc.id}
                    type="button"
                    onClick={() => toggleOne(acc.id)}
                    className="flex w-full cursor-pointer items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-[rgba(255,255,255,0.03)]"
                  >
                    <div className={cn(
                      'flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors',
                      checked
                        ? 'border-[#7dcfff] bg-[rgba(125,207,255,0.2)]'
                        : 'border-[rgba(162,179,229,0.2)] bg-transparent',
                    )}>
                      {checked && <Check className="h-2.5 w-2.5 text-[#7dcfff]" />}
                    </div>

                    {/* Avatar */}
                    <div className="relative shrink-0">
                      {acc.avatar ? (
                        <img src={buildProxyImageUrl(acc.avatar, backendUrl, backendApiKey)} alt={acc.username} className="h-7 w-7 rounded-full object-cover" />
                      ) : (
                        <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.06)] text-[11px] font-semibold uppercase text-[#7aa2f7]">
                          {acc.username.slice(0, 2)}
                        </div>
                      )}
                      <span className={cn('absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[rgba(9,12,22,1)]', STATUS_DOT[acc.status])} />
                    </div>

                    <span className="truncate text-[13px] text-[#c0caf5]">@{acc.username}</span>
                    {checked && <Check className="ml-auto h-3.5 w-3.5 shrink-0 text-[#7dcfff]" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Shared badges ───────────────────────────────────────────────────────────

function RiskBadge({ level }: { level?: string }) {
  if (!level) return null;
  const normalized = level.toLowerCase();
  const variant = normalized === 'low' ? 'green' : normalized === 'medium' ? 'yellow' : 'red';
  return (
    <Badge variant={variant} className="capitalize">
      <Shield className="h-3 w-3" />
      {level}
    </Badge>
  );
}

type BadgeVariant = 'green' | 'red' | 'yellow' | 'blue' | 'gray';

const STATUS_VARIANTS: Record<string, BadgeVariant> = {
  done: 'green',
  completed: 'green',
  action_executed: 'green',
  recommendation_only: 'blue',
  interrupted: 'yellow',
  risk_threshold_exceeded: 'yellow',
  no_candidates: 'yellow',
  error: 'red',
  approval_rejected: 'red',
  account_not_ready: 'red',
  approval_limit_reached: 'red',
  discovery_limit_reached: 'red',
  invariant_violated: 'red',
  not_approved: 'red',
  missing_data: 'red',
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function statusVariant(status: string): BadgeVariant {
  const normalized = status.trim().toLowerCase();
  return STATUS_VARIANTS[normalized] ?? 'gray';
}

function statusLabel(status: string): string {
  const normalized = status.trim();
  if (!normalized) return 'unknown';
  return normalized.replace(/_/g, ' ');
}

function getEditPrefill(response: SmartEngagementResponse): string {
  const payload = asRecord(response.interrupt_payload);
  const draftAction = asRecord(payload?.draft_action);
  const draftPayload = asRecord(payload?.draft_payload);

  const candidates = [
    payload?.content,
    payload?.draft_content,
    draftAction?.content,
    draftPayload?.content,
    response.recommendation?.draft_content,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate;
    }
  }
  return '';
}

function StatusBadge({ status, interrupted }: { status: string; interrupted: boolean }) {
  if (interrupted) {
    return (
      <Badge variant="yellow">
        <AlertTriangle className="h-3 w-3" />
        Awaiting approval
      </Badge>
    );
  }
  return <Badge variant={statusVariant(status)}>{statusLabel(status)}</Badge>;
}

// ─── Result panel per account ────────────────────────────────────────────────

function EngagementResult({
  username,
  response,
  onDecision,
  resumeLoading,
}: {
  username: string;
  response: SmartEngagementResponse;
  onDecision: (threadId: string, decision: ResumeRequest['decision'], content?: string) => void;
  resumeLoading: boolean;
}) {
  const [editState, setEditState] = useState<'idle' | 'editing'>('idle');
  const [editContent, setEditContent] = useState('');

  return (
    <div className="space-y-3">
      {/* Account header */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-[#7dcfff]">@{username}</span>
        <StatusBadge status={response.status} interrupted={response.interrupted} />
        {response.mode && <Badge variant="blue" className="capitalize">{response.mode}</Badge>}
      </div>

      {response.outcome_reason && <p className="text-sm text-[#8e9ac0]">{response.outcome_reason}</p>}

      {/* Recommendation */}
      {response.recommendation && (
        <div className="rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Target className="h-3.5 w-3.5 text-[#7dcfff]" />
            <span className="text-xs font-semibold text-[#9aa7cf]">Recommendation</span>
          </div>
          {response.recommendation.target && (
            <p className="text-sm text-[#dce6ff]"><strong className="text-[#7dcfff]">Target:</strong> {response.recommendation.target}</p>
          )}
          {response.recommendation.action_type && (
            <Badge variant="blue" className="capitalize">{response.recommendation.action_type}</Badge>
          )}
          {response.recommendation.draft_content && (
            <div className="code-block text-sm">{response.recommendation.draft_content}</div>
          )}
          {response.recommendation.reasoning && (
            <p className="text-xs text-[#8e9ac0]">{response.recommendation.reasoning}</p>
          )}
        </div>
      )}

      {/* Risk */}
      {response.risk && (
        <div className="flex items-center gap-2 text-sm">
          <Shield className="h-3.5 w-3.5 text-[#e0af68]" />
          <RiskBadge level={response.risk.level} />
          {response.risk.reasoning && (
            <span className="text-xs text-[#8e9ac0]">{response.risk.reasoning}</span>
          )}
        </div>
      )}

      {/* Approval */}
      {response.interrupted && response.thread_id && (
        <div className="rounded-xl border border-[rgba(224,175,104,0.20)] bg-[rgba(224,175,104,0.05)] p-3 space-y-2">
          {editState === 'editing' ? (
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={3}
                placeholder="Enter edited content…"
                className="glass-textarea text-sm"
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={() => { onDecision(response.thread_id!, 'edited', editContent); }} loading={resumeLoading}>
                  <CheckCircle className="h-3.5 w-3.5" /> Submit
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditState('idle')} disabled={resumeLoading}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => onDecision(response.thread_id!, 'approved')} loading={resumeLoading}>
                <CheckCircle className="h-3.5 w-3.5" /> Approve
              </Button>
              <Button size="sm" variant="danger" onClick={() => onDecision(response.thread_id!, 'rejected')} disabled={resumeLoading}>
                <XCircle className="h-3.5 w-3.5" /> Reject
              </Button>
              <Button size="sm" variant="secondary" onClick={() => {
                setEditContent(getEditPrefill(response));
                setEditState('editing');
              }} disabled={resumeLoading}>
                <Edit3 className="h-3.5 w-3.5" /> Edit
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Decision */}
      {response.decision?.decision && (
        <div className="flex items-center gap-2 text-sm">
          <FileText className="h-3.5 w-3.5 text-[#7dcfff]" />
          <Badge variant="blue" className="capitalize">{response.decision.decision}</Badge>
          {response.decision.notes && <span className="text-xs text-[#8e9ac0]">{response.decision.notes}</span>}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────

interface AccountResult {
  accountId: string;
  username: string;
  response: SmartEngagementResponse;
}

export function SmartEngagementPage() {
  const accounts = useAccountStore((s) => s.accounts);
  const activeAccounts = accounts.filter((a) => a.status === 'active');
  const activeAccountIds = activeAccounts.map((a) => a.id);
  const activeAccountIdsKey = activeAccountIds.join('|');
  const firstActiveAccountId = activeAccounts[0]?.id ?? '';

  const goal = useSmartEngagementStore((s) => s.goal);
  const setGoal = useSmartEngagementStore((s) => s.setGoal);
  const selectedIds = useSmartEngagementStore((s) => s.selectedIds);
  const setSelectedIds = useSmartEngagementStore((s) => s.setSelectedIds);
  const pruneSelectedIds = useSmartEngagementStore((s) => s.pruneSelectedIds);
  const mode = useSmartEngagementStore((s) => s.mode);
  const setMode = useSmartEngagementStore((s) => s.setMode);
  const maxTargets = useSmartEngagementStore((s) => s.maxTargets);
  const setMaxTargets = useSmartEngagementStore((s) => s.setMaxTargets);
  const loading = useSmartEngagementStore((s) => s.loading);
  const setLoading = useSmartEngagementStore((s) => s.setLoading);
  const progress = useSmartEngagementStore((s) => s.progress);
  const setProgress = useSmartEngagementStore((s) => s.setProgress);
  const results = useSmartEngagementStore((s) => s.results);
  const setResults = useSmartEngagementStore((s) => s.setResults);
  const resumeLoading = useSmartEngagementStore((s) => s.resumeLoading);
  const setResumeLoading = useSmartEngagementStore((s) => s.setResumeLoading);
  const validSelectedIds = getValidSelectedIds(selectedIds, activeAccountIds);

  useEffect(() => {
    pruneSelectedIds(activeAccountIds);
  }, [activeAccountIdsKey, pruneSelectedIds]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-select first active account on mount if nothing is persisted
  useEffect(() => {
    if (selectedIds.length === 0 && firstActiveAccountId) {
      setSelectedIds([firstActiveAccountId]);
    }
  }, [selectedIds.length, firstActiveAccountId, setSelectedIds]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!goal.trim()) { toast.error('Select a goal or type a custom one'); return; }
    if (validSelectedIds.length === 0) { toast.error('Select at least one active account'); return; }

    setLoading(true);
    setResults([]);
    const accountsToRun = activeAccounts.filter((a) => validSelectedIds.includes(a.id));

    try {
      const newResults: AccountResult[] = [];

      for (let i = 0; i < accountsToRun.length; i++) {
        const acc = accountsToRun[i];
        setProgress(`Running @${acc.username} (${i + 1}/${accountsToRun.length})…`);

        const payload: SmartEngagementRequest = {
          execution_mode: mode,
          goal: goal.trim(),
          account_id: acc.id,
          max_targets: maxTargets,
          max_actions_per_target: 3,
        };

        try {
          const resp = await smartEngagementApi.recommend(payload);
          newResults.push({ accountId: acc.id, username: acc.username, response: resp });
        } catch (error) {
          newResults.push({
            accountId: acc.id,
            username: acc.username,
            response: {
              mode, status: 'error', interrupted: false,
              outcome_reason: error instanceof Error ? error.message : 'Request failed',
              brief_audit: [], audit_trail: [],
            },
          });
        }
      }

      setResults(newResults);
      const successCount = newResults.filter((r) => r.response.status !== 'error').length;
      if (successCount > 0) toast.success(`Done: ${successCount}/${accountsToRun.length} accounts processed`);
    } finally {
      setLoading(false);
      setProgress('');
    }
  }

  async function handleDecision(threadId: string, decision: ResumeRequest['decision'], content?: string) {
    setResumeLoading(true);
    try {
      const payload: ResumeRequest = { thread_id: threadId, decision, content };
      const resp = await smartEngagementApi.resume(payload);
      const updated = results.map((r) =>
        r.response.thread_id === threadId ? { ...r, response: resp } : r,
      );
      setResults(updated);
      toast.success(`Decision: ${decision}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Resume failed');
    } finally {
      setResumeLoading(false);
    }
  }

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Risk Engine"
        title="Smart Engagement"
        description="Select accounts, pick an engagement goal, and let the AI plan safe engagement actions. Review recommendations before anything goes live."
        icon={<Sparkles className="h-6 w-6 text-[#bb9af7]" />}
      >
        <div className="metric-grid">
          <HeaderStat label="Active Accounts" value={activeAccounts.length} tone="green" />
          <HeaderStat label="Selected" value={validSelectedIds.length} tone="cyan" />
          <HeaderStat label="Mode" value={mode} tone="violet" />
        </div>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">

        {/* ── Left: Config panel ── */}
        <Card className="space-y-5">
          <div>
            <p className="text-kicker">Run Configuration</p>
            <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Setup</h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Account picker */}
            <div className="space-y-2">
              <label className="field-label">Accounts</label>
              <AccountMultiPicker selected={validSelectedIds} onChange={setSelectedIds} />
            </div>

            {/* Goal templates */}
            <div className="space-y-2">
              <label className="field-label">Goal</label>
              <div className="flex flex-wrap gap-1.5">
                {GOAL_TEMPLATES.map((t) => {
                  const Icon = t.icon;
                  return (
                    <button
                      key={t.label}
                      type="button"
                      onClick={() => setGoal(t.goal)}
                      className={cn(
                        'flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-medium transition-all duration-150',
                        goal === t.goal
                          ? 'border-[rgba(187,154,247,0.35)] bg-[rgba(187,154,247,0.14)] text-[#f0e0ff]'
                          : 'border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] text-[#8e9ac0] hover:border-[rgba(162,179,229,0.24)] hover:text-[#c0caf5]',
                      )}
                    >
                      <Icon className="h-3 w-3 shrink-0" />
                      {t.label}
                    </button>
                  );
                })}
              </div>
              <input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="Or type a custom engagement goal…"
                className="glass-field text-sm"
              />
            </div>

            {/* Mode */}
            <div className="space-y-2">
              <label className="field-label">Execution Mode</label>
              <div className="grid gap-2 sm:grid-cols-2">
                {(['recommendation', 'execute'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setMode(value)}
                    className={cn(
                      'cursor-pointer rounded-xl border px-3 py-2.5 text-left transition-all duration-200',
                      mode === value
                        ? 'border-[rgba(187,154,247,0.32)] bg-[rgba(187,154,247,0.14)] text-[#f5efff]'
                        : 'border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] text-[#8f9bc4]',
                    )}
                  >
                    <span className="block text-sm font-semibold capitalize">{value}</span>
                    <span className="mt-0.5 block text-[11px] text-[#8e9ac0]">
                      {value === 'execute' ? 'Live actions (if backend enabled)' : 'Review-only recommendations'}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {mode === 'execute' && (
              <div className="rounded-xl border border-[rgba(224,175,104,0.22)] bg-[rgba(224,175,104,0.08)] p-3 text-xs text-[#f6d19e]">
                Execute mode triggers real actions — use only when intended.
              </div>
            )}

            {/* Max targets */}
            <div className="space-y-2">
              <label className="field-label" htmlFor="engagement-targets">Max Targets</label>
              <input
                id="engagement-targets"
                type="number"
                min={1}
                max={20}
                value={maxTargets}
                onChange={(e) => setMaxTargets(Math.min(20, Math.max(1, Number(e.target.value))))}
                className="glass-field text-sm"
              />
            </div>

            <Button type="submit" className="w-full" loading={loading} disabled={validSelectedIds.length === 0}>
              {!loading && <Sparkles className="h-4 w-4" />}
              {loading ? progress || 'Running…' : `Run for ${validSelectedIds.length} account${validSelectedIds.length === 1 ? '' : 's'}`}
            </Button>
          </form>

          {/* Copilot hint */}
          <div className="rounded-xl border border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.02)] px-3 py-2">
            <p className="text-[11px] text-[#374060]">
              Tip: you can also use <code className="font-mono text-[#7dcfff]">/engage @username goal</code> in the Copilot chat.
            </p>
          </div>
        </Card>

        {/* ── Right: Results ── */}
        <div className="space-y-4">
          {!loading && results.length === 0 && (
            <Card className="py-18 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
                <Target className="h-7 w-7 text-[#7dcfff]" />
              </div>
              <p className="mt-5 text-lg font-semibold text-[#eef4ff]">Select accounts and a goal to get started</p>
              <p className="mt-2 text-sm text-[#8e9ac0]">
                Pick a template or write your own goal, then run recommendations.
              </p>
            </Card>
          )}

          {loading && (
            <Card className="py-18 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
                <RefreshCw className="h-7 w-7 animate-spin text-[#7dcfff]" />
              </div>
              <p className="mt-5 text-lg font-semibold text-[#eef4ff]">{progress || 'Running smart engagement…'}</p>
            </Card>
          )}

          {!loading && results.length > 0 && (
            <div className="space-y-4">
              {results.map((r) => (
                <Card key={r.accountId} className="space-y-4">
                  <EngagementResult
                    username={r.username}
                    response={r.response}
                    onDecision={handleDecision}
                    resumeLoading={resumeLoading}
                  />
                </Card>
              ))}

              {/* Audit trail — collapsed */}
              {results.some((r) => r.response.brief_audit.length > 0) && (
                <Card className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-[#7dcfff]" />
                    <h3 className="text-sm font-semibold text-[#9aa7cf]">Audit Trail</h3>
                  </div>
                  <div className="max-h-48 space-y-2 overflow-y-auto">
                    {results.flatMap((r) =>
                      r.response.brief_audit.slice(-3).map((event, i) => (
                        <pre key={`${r.accountId}-${i}`} className="code-block text-xs text-[#9fb0d8]">
                          <span className="text-[#7dcfff]">@{r.username}</span>{' '}
                          {typeof event === 'string' ? event : JSON.stringify(event, null, 2)}
                        </pre>
                      )),
                    )}
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
