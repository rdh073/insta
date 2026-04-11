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
      const proposed = event.proposed_calls as unknown[] | undefined;
      const approved = event.approved_calls as unknown[] | undefined;
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <List className="h-3.5 w-3.5 shrink-0 text-[#7aa2f7]" />
            <span className="text-xs font-medium text-[#8e9ac0]">policy_check</span>
            {proposed && <Badge variant="blue">{proposed.length} proposed</Badge>}
            {approved && <Badge variant="green">{approved.length} approved</Badge>}
          </div>
          {(proposed || approved) && (
            <CollapsibleSection title="policy_details">
              <pre className="code-block text-xs">
                {JSON.stringify({ proposed_calls: proposed, approved_calls: approved }, null, 2)}
              </pre>
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
