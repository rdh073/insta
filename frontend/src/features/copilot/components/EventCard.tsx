import {
  AlertTriangle,
  Bot,
  ChevronRight,
  List,
  Play,
  Square,
  Wrench,
} from 'lucide-react';
import type { CopilotEvent } from '../../../api/operator-copilot';
import { Badge } from '../../../components/ui/Badge';
import { CollapsibleSection } from './CollapsibleSection';

type BadgeVariant = 'green' | 'red' | 'yellow' | 'blue' | 'gray';

export interface NormalizedPolicyResultEvent {
  flags: Record<string, string>;
  riskLevel: string | null;
  riskReasons: string[];
  needsApproval: boolean | null;
  proposedCalls: unknown[] | null;
  approvedCalls: unknown[] | null;
  hasModernPayload: boolean;
  hasLegacyPayload: boolean;
}

function asStringRecord(value: unknown): Record<string, string> {
  if (value == null || typeof value !== 'object' || Array.isArray(value)) return {};
  return Object.entries(value).reduce<Record<string, string>>((acc, [key, entryValue]) => {
    if (typeof entryValue === 'string') acc[key] = entryValue;
    return acc;
  }, {});
}

function asUnknownArray(value: unknown): unknown[] | null {
  return Array.isArray(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0);
}

export function normalizePolicyResultEvent(event: CopilotEvent): NormalizedPolicyResultEvent {
  const flags = asStringRecord(event.flags);
  const riskLevelRaw = typeof event.risk_level === 'string' ? event.risk_level.trim() : '';
  const riskLevel = riskLevelRaw.length > 0 ? riskLevelRaw : null;
  const riskReasons = asStringArray(event.risk_reasons);
  const explicitNeedsApproval = typeof event.needs_approval === 'boolean' ? event.needs_approval : null;
  const inferredNeedsApproval = Object.values(flags).some((classification) => classification.toLowerCase() === 'write_sensitive');
  const needsApproval = explicitNeedsApproval ?? (Object.keys(flags).length > 0 ? inferredNeedsApproval : null);

  const proposedCalls = asUnknownArray(event.proposed_calls);
  const approvedCalls = asUnknownArray(event.approved_calls);

  return {
    flags,
    riskLevel,
    riskReasons,
    needsApproval,
    proposedCalls,
    approvedCalls,
    hasModernPayload:
      Object.keys(flags).length > 0 ||
      riskLevel !== null ||
      riskReasons.length > 0 ||
      explicitNeedsApproval !== null,
    hasLegacyPayload: proposedCalls !== null || approvedCalls !== null,
  };
}

function riskLevelBadgeVariant(level: string | null): BadgeVariant {
  if (level == null) return 'gray';
  const normalized = level.toLowerCase();
  if (normalized === 'low') return 'green';
  if (normalized === 'medium') return 'yellow';
  if (normalized === 'high' || normalized === 'critical') return 'red';
  return 'gray';
}

function flagBadgeVariant(classification: string): BadgeVariant {
  const normalized = classification.toLowerCase();
  if (normalized === 'read_only') return 'green';
  if (normalized === 'write_sensitive') return 'yellow';
  if (normalized === 'blocked') return 'red';
  return 'gray';
}

export function EventCard({ event }: { event: CopilotEvent }) {
  switch (event.type) {
    case 'run_start':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <Play className="h-3 w-3 shrink-0 text-[#9ece6a]" />
          <span className="text-xs text-[#4a5a7a]">run started</span>
          {event.thread_id != null && (
            <span className="font-mono text-[11px] text-[#374060]">{String(event.thread_id).slice(0, 12)}…</span>
          )}
        </div>
      );

    case 'node_update':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <ChevronRight className="h-3 w-3 shrink-0 text-[#374060]" />
          <span className="font-mono text-[11px] italic text-[#3e4e6e]">
            {event.node ? String(event.node) : 'node'}
          </span>
        </div>
      );

    case 'plan_ready':
      return (
        <CollapsibleSection title="execution_plan">
          <pre className="code-block text-xs">{JSON.stringify(event.execution_plan ?? event, null, 2)}</pre>
        </CollapsibleSection>
      );

    case 'policy_result': {
      const policy = normalizePolicyResultEvent(event);
      const flagEntries = Object.entries(policy.flags);
      const policyDetails = {
        ...(flagEntries.length > 0 ? { flags: policy.flags } : {}),
        ...(policy.riskLevel != null ? { risk_level: policy.riskLevel } : {}),
        ...(policy.riskReasons.length > 0 ? { risk_reasons: policy.riskReasons } : {}),
        ...(policy.needsApproval != null ? { needs_approval: policy.needsApproval } : {}),
        ...(policy.proposedCalls != null ? { proposed_calls: policy.proposedCalls } : {}),
        ...(policy.approvedCalls != null ? { approved_calls: policy.approvedCalls } : {}),
      };

      return (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <List className="h-3.5 w-3.5 shrink-0 text-[#7aa2f7]" />
            <span className="text-xs font-medium text-[#8e9ac0]">policy_check</span>
            {policy.riskLevel != null && (
              <Badge variant={riskLevelBadgeVariant(policy.riskLevel)}>
                risk {policy.riskLevel}
              </Badge>
            )}
            {policy.needsApproval != null && (
              <Badge variant={policy.needsApproval ? 'red' : 'green'}>
                {policy.needsApproval ? 'approval required' : 'no approval'}
              </Badge>
            )}
            {flagEntries.length > 0 && <Badge variant="blue">{flagEntries.length} flags</Badge>}
            {policy.proposedCalls != null && <Badge variant="blue">{policy.proposedCalls.length} proposed</Badge>}
            {policy.approvedCalls != null && <Badge variant="green">{policy.approvedCalls.length} approved</Badge>}
          </div>
          {flagEntries.length > 0 && (
            <div className="rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
              <p className="text-[11px] font-medium text-[#8e9ac0]">tool flags</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {flagEntries.map(([toolName, classification]) => (
                  <Badge
                    key={`${toolName}:${classification}`}
                    variant={flagBadgeVariant(classification)}
                    className="font-mono"
                  >
                    {toolName}: {classification}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {policy.riskReasons.length > 0 && (
            <div className="rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
              <p className="text-[11px] font-medium text-[#8e9ac0]">risk reasons</p>
              <ul className="mt-1.5 space-y-1 text-xs text-[#9fb0d8]">
                {policy.riskReasons.map((reason, index) => (
                  <li key={`${reason}-${index}`} className="font-mono leading-5">
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(policy.hasModernPayload || policy.hasLegacyPayload) && (
            <CollapsibleSection title="policy_details">
              <pre className="code-block text-xs">{JSON.stringify(policyDetails, null, 2)}</pre>
            </CollapsibleSection>
          )}
        </div>
      );
    }

    case 'tool_result': {
      const toolName = event.tool_name ? String(event.tool_name) : 'tool';
      return (
        <CollapsibleSection title={`tool_result · ${toolName}`}>
          <div className="mb-2 flex items-center gap-2">
            <Wrench className="h-3.5 w-3.5 text-[#e0af68]" />
            <span className="font-mono text-xs text-[#d4b896]">{toolName}</span>
          </div>
          <pre className="code-block text-xs">{JSON.stringify(event.result ?? event, null, 2)}</pre>
        </CollapsibleSection>
      );
    }

    case 'final_response':
      return (
        <div className="flex gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.10)]">
            <Bot className="h-4 w-4 text-[#7dcfff]" />
          </div>
          <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-[rgba(125,207,255,0.12)] bg-[rgba(122,162,247,0.07)] px-4 py-3">
            <p className="whitespace-pre-wrap text-sm leading-6 text-[#eef4ff]">
              {event.text ? String(event.text) : JSON.stringify(event)}
            </p>
          </div>
        </div>
      );

    case 'run_finish':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <Square className="h-3 w-3 shrink-0 text-[#9ece6a]" />
          <span className="text-xs text-[#4a6a4a]">run complete</span>
          <Badge variant="green">done</Badge>
        </div>
      );

    case 'run_error':
      return (
        <div className="rounded-xl border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.07)] px-3 py-2.5 text-sm">
          <div className="flex items-center gap-2 text-[#ffccd7]">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">run_error</span>
          </div>
          {event.message != null && (
            <p className="mt-1 font-mono text-xs text-[#f78e9e]">{String(event.message)}</p>
          )}
        </div>
      );

    default:
      return (
        <CollapsibleSection title={`event:${event.type}`}>
          <pre className="code-block text-xs text-[#9fb0d8]">{JSON.stringify(event, null, 2)}</pre>
        </CollapsibleSection>
      );
  }
}
