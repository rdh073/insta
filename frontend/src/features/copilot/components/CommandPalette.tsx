import { Terminal } from 'lucide-react';
import type { SlashCommand } from '../../../lib/slash-commands';

export function CommandPalette({
  suggestions,
  onPick,
  textareaRef,
}: {
  suggestions: SlashCommand[];
  onPick: (message: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-xl border border-[rgba(162,179,229,0.12)] bg-[rgba(9,12,22,0.96)] shadow-[0_16px_40px_rgba(4,8,18,0.5)] backdrop-blur-2xl">
      {suggestions.map((cmd) => (
        <button
          key={cmd.name}
          type="button"
          onMouseDown={(e) => {
            e.preventDefault();
            onPick(`/${cmd.name} `);
            textareaRef.current?.focus();
          }}
          className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]"
        >
          <Terminal className="h-3.5 w-3.5 shrink-0 text-[#7dcfff]" />
          <div className="min-w-0 flex-1">
            <span className="font-mono text-xs text-[#d4f1ff]">/{cmd.name}</span>
            <span className="ml-2 text-[11px] text-[#4a5578]">{cmd.argSchema}</span>
          </div>
          <span className="max-w-[14rem] truncate text-[11px] text-[#4a5578]">{cmd.description}</span>
        </button>
      ))}
    </div>
  );
}
