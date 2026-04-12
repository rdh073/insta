import { useState } from 'react';
import { AlertTriangle, CheckCircle, Edit3, XCircle } from 'lucide-react';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

const CALL_KEYS = ['proposed_tool_calls', 'proposed_calls', 'tool_calls', 'edited_calls'] as const;

export function normalizeEditedCalls(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is Record<string, unknown> => !!asRecord(item));
  }
  const single = asRecord(value);
  return single ? [single] : [];
}

function extractExplicitCalls(payload: Record<string, unknown>): Record<string, unknown>[] {
  for (const key of CALL_KEYS) {
    const normalized = normalizeEditedCalls(payload[key]);
    if (normalized.length > 0) {
      return normalized;
    }
  }
  return [];
}

export function buildEditableDraft(payload: Record<string, unknown>): Record<string, unknown>[] {
  const explicitCalls = extractExplicitCalls(payload);
  if (explicitCalls.length > 0) {
    return explicitCalls;
  }

  if (typeof payload.caption === 'string' && payload.caption.trim()) {
    return [{ edited_caption: payload.caption.trim() }];
  }

  if (typeof payload.policy_decision === 'string' && payload.policy_decision.trim()) {
    return [{ override_policy: payload.policy_decision.trim() }];
  }

  const draftAction = asRecord(payload.draft_action);
  if (draftAction && typeof draftAction.content === 'string' && draftAction.content.trim()) {
    return [{ content: draftAction.content.trim() }];
  }

  if (typeof payload.proxy_candidate === 'string' && payload.proxy_candidate.trim()) {
    return [{ proxy: payload.proxy_candidate.trim() }];
  }

  return [];
}

export function ApprovalCard({
  payload,
  onDecision,
  loading,
}: {
  payload: Record<string, unknown>;
  onDecision: (result: 'approved' | 'rejected' | 'edited', editedCalls?: Record<string, unknown>[]) => void;
  loading: boolean;
}) {
  const [editMode, setEditMode] = useState(false);
  const [editableDraft] = useState<Record<string, unknown>[]>(() => buildEditableDraft(payload));
  const [jsonText, setJsonText] = useState(() => {
    return JSON.stringify(editableDraft, null, 2);
  });
  const [parseError, setParseError] = useState('');

  function handleSubmitEdit() {
    try {
      const parsed = JSON.parse(jsonText) as unknown;
      const normalized = normalizeEditedCalls(parsed);
      if (normalized.length === 0) {
        setParseError('Edited payload must be an object or an array of objects.');
        return;
      }
      onDecision('edited', normalized);
    } catch {
      setParseError('Invalid JSON — fix the payload before submitting.');
    }
  }

  return (
    <div className="rounded-2xl border border-[rgba(224,175,104,0.28)] bg-[rgba(224,175,104,0.06)] p-4 space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-[#e0af68]" />
        <span className="text-sm font-semibold text-[#f0d080]">Approval Required</span>
        <Badge variant="yellow">waiting</Badge>
      </div>

      {editMode ? (
        <div className="space-y-2">
          <textarea
            id="copilot-approval-payload"
            name="copilotApprovalPayload"
            value={jsonText}
            onChange={(e) => { setJsonText(e.target.value); setParseError(''); }}
            rows={8}
            className="glass-textarea font-mono text-xs"
          />
          {parseError && <p className="text-xs text-[#ff9db0]">{parseError}</p>}
        </div>
      ) : (
        <pre className="code-block max-h-64 text-xs overflow-auto">
          {JSON.stringify(editableDraft.length > 0 ? editableDraft : payload, null, 2)}
        </pre>
      )}

      <div className="flex flex-wrap gap-2">
        {editMode ? (
          <>
            <Button size="sm" onClick={handleSubmitEdit} loading={loading}>
              <CheckCircle className="h-3.5 w-3.5" /> Submit
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditMode(false)} disabled={loading}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" onClick={() => onDecision('approved')} loading={loading}>
              <CheckCircle className="h-3.5 w-3.5" /> Approve
            </Button>
            <Button size="sm" variant="danger" onClick={() => onDecision('rejected')} disabled={loading}>
              <XCircle className="h-3.5 w-3.5" /> Reject
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditMode(true)} disabled={loading}>
              <Edit3 className="h-3.5 w-3.5" /> Edit
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
