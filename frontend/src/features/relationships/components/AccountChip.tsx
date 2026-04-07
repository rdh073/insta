import { CheckSquare, Square } from 'lucide-react';
import type { Account } from '../../../types';

interface Props {
  account: Account;
  selected: boolean;
  onToggle: () => void;
}

export function AccountChip({ account, selected, onToggle }: Props) {
  const isActive = account.status === 'active';
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={!isActive}
      className={`group flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-[13px] font-medium transition-all duration-200 ${
        selected
          ? 'border-[rgba(125,207,255,0.36)] bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
          : isActive
            ? 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.03)] text-[#95a3cb] hover:border-[rgba(125,207,255,0.24)] hover:text-[#d8e4ff]'
            : 'cursor-not-allowed border-[rgba(162,179,229,0.08)] bg-[rgba(255,255,255,0.01)] text-[#4a5578] opacity-50'
      }`}
    >
      {selected ? <CheckSquare className="h-3.5 w-3.5" /> : <Square className="h-3.5 w-3.5" />}
      <span className="font-mono text-[12px]">@{account.username}</span>
      {isActive && <span className="h-1.5 w-1.5 rounded-full bg-[#9ece6a]" />}
    </button>
  );
}
