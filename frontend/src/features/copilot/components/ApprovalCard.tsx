import { useState } from 'react';
import { AlertTriangle, CheckCircle, Edit3, XCircle } from 'lucide-react';
import { Badge } from '../../../components/ui/Badge';
import { Button } from '../../../components/ui/Button';

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
  const [jsonText, setJsonText] = useState(() => {
    const calls = payload.proposed_calls ?? payload.tool_calls ?? [];
    return JSON.stringify(calls, null, 2);
  });
  const [parseError, setParseError] = useState('');

  function handleSubmitEdit() {
    try {
      const parsed = JSON.parse(jsonText) as Record<string, unknown>[];
      onDecision('edited', parsed);
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
          {JSON.stringify(payload.proposed_calls ?? payload.tool_calls ?? payload, null, 2)}
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
