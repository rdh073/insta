import { Bot } from 'lucide-react';
import { QUICK_SUGGESTIONS } from './copilot-helpers';

export function CopilotEmptyState({
  onSuggestionClick,
}: {
  onSuggestionClick: (text: string) => void;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[rgba(125,207,255,0.14)] bg-[rgba(125,207,255,0.08)]">
        <Bot className="h-8 w-8 text-[#4a7a9a]" />
      </div>
      <div>
        <p className="text-base font-semibold text-[#c0caf5]">Ready</p>
        <p className="mt-1 text-sm text-[#4a5578]">Send a prompt or type <code className="font-mono text-[#7dcfff]">/</code> for commands</p>
      </div>
      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {QUICK_SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSuggestionClick(s)}
            className="cursor-pointer rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5 text-left text-xs text-[#8e9ac0] transition-colors duration-150 hover:border-[rgba(125,207,255,0.18)] hover:bg-[rgba(125,207,255,0.06)] hover:text-[#c0d8f0]"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
