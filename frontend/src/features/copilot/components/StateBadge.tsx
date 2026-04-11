import { Loader } from 'lucide-react';
import { Badge } from '../../../components/ui/Badge';
import type { RunState } from '../../../store/copilot';

export function StateBadge({ state, isRunning }: { state: RunState; isRunning: boolean }) {
  if (state === 'idle') return null;
  const map: Record<RunState, { variant: 'blue' | 'green' | 'red' | 'yellow'; label: string }> = {
    idle: { variant: 'blue', label: 'idle' },
    running: { variant: 'blue', label: 'running' },
    waiting_approval: { variant: 'yellow', label: 'approval' },
    done: { variant: 'green', label: 'done' },
    error: { variant: 'red', label: 'error' },
  };
  const { variant, label } = map[state];
  return (
    <Badge variant={variant} className="capitalize">
      {isRunning && <Loader className="h-3 w-3 animate-spin" />}
      {label}
    </Badge>
  );
}
