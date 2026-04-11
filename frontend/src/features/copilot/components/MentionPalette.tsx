import { buildProxyImageUrl } from '../../../lib/api-base';
import { cn } from '../../../lib/cn';
import type { Account } from '../../../types';
import { STATUS_DOT } from './copilot-helpers';

export function MentionPalette({
  accounts,
  activeIndex,
  onHover,
  onPick,
  backendUrl,
  backendApiKey,
}: {
  accounts: Account[];
  activeIndex: number;
  onHover: (index: number) => void;
  onPick: (account: Account) => void;
  backendUrl: string;
  backendApiKey: string;
}) {
  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-xl border border-[rgba(125,207,255,0.14)] bg-[rgba(9,12,22,0.97)] shadow-[0_16px_40px_rgba(4,8,18,0.55)] backdrop-blur-2xl">
      <div className="flex items-center gap-2 border-b border-[rgba(162,179,229,0.07)] px-3 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-[#4a5578]">Accounts</span>
        <span className="ml-auto text-[10px] text-[#2e3556]">↑↓ navigate · Enter select · Esc close</span>
      </div>
      {accounts.map((acc, i) => (
        <button
          key={acc.id}
          type="button"
          onMouseEnter={() => onHover(i)}
          onMouseDown={(e) => { e.preventDefault(); onPick(acc); }}
          className={cn(
            'flex w-full cursor-pointer items-center gap-3 px-3 py-2 text-left transition-colors duration-100',
            i === activeIndex ? 'bg-[rgba(125,207,255,0.09)]' : 'hover:bg-[rgba(255,255,255,0.03)]',
          )}
        >
          {/* Avatar / initials */}
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

          {/* Username + status */}
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-medium text-[#c0caf5]">
              <span className="text-[#7dcfff]">@</span>{acc.username}
            </p>
            <p className="text-[11px] capitalize text-[#4a5578]">{acc.status}</p>
          </div>

          {/* Keyboard hint for highlighted item */}
          {i === activeIndex && (
            <span className="shrink-0 text-[10px] text-[#2e3556]">↵</span>
          )}
        </button>
      ))}
    </div>
  );
}
