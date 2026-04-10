import { CheckSquare, Clock, Loader, RotateCcw, Square } from 'lucide-react';
import type { RateLimitEntry } from '../../../api/accounts';
import type { Account } from '../../../types';
import { AccountAvatar } from './AccountAvatar';
import { statusBadge } from './StatusBadge';
import { formatCooldown, NON_ACTIVE_STATUSES } from './account-helpers';

export function AccountRow({
  account,
  isActive,
  selectMode,
  selected,
  onToggle,
  onClick,
  onRelogin,
  relogging,
  rateLimitInfo,
}: {
  account: Account;
  isActive: boolean;
  selectMode: boolean;
  selected: boolean;
  onToggle: () => void;
  onClick: () => void;
  onRelogin: () => void;
  relogging: boolean;
  rateLimitInfo?: RateLimitEntry;
}) {
  const handleClick = () => {
    if (selectMode) onToggle();
    else onClick();
  };

  const showReauth = NON_ACTIVE_STATUSES.has(account.status) && !selectMode;

  return (
    <div
      onClick={handleClick}
      className={`flex cursor-pointer items-center gap-3 rounded-[1rem] px-3 py-2.5 transition-all duration-150 ${
        selectMode && selected
          ? 'bg-[rgba(125,207,255,0.10)] ring-1 ring-[rgba(125,207,255,0.24)]'
          : isActive
            ? 'bg-[rgba(187,154,247,0.10)] ring-1 ring-[rgba(187,154,247,0.22)]'
            : 'hover:bg-[rgba(255,255,255,0.04)]'
      }`}
    >
      {selectMode && (
        <div className="shrink-0" onClick={(e) => { e.stopPropagation(); onToggle(); }}>
          {selected
            ? <CheckSquare className="h-4 w-4 text-[#7dcfff]" />
            : <Square className="h-4 w-4 text-[#5a6a90]" />}
        </div>
      )}

      <AccountAvatar username={account.username} avatar={account.avatar} size="sm" />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-[#eef4ff]">@{account.username}</p>
        {account.fullName && (
          <p className="truncate text-xs text-[#7f8bb3]">{account.fullName}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        <div className="flex flex-col items-end gap-1">
          {statusBadge(account, true)}
          {rateLimitInfo && (
            <span className="flex items-center gap-1 rounded-full border border-[rgba(255,158,100,0.24)] bg-[rgba(255,158,100,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[#ffb07a]">
              <Clock className="h-2.5 w-2.5" />
              {formatCooldown(rateLimitInfo.retry_after)}
            </span>
          )}
        </div>

        {showReauth && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onRelogin(); }}
            disabled={relogging}
            title="Re-authenticate"
            className="cursor-pointer rounded-lg p-1.5 text-[#5a6a90] transition-colors duration-150 hover:bg-[rgba(122,162,247,0.12)] hover:text-[#7aa2f7] disabled:opacity-40"
          >
            {relogging
              ? <Loader className="h-3.5 w-3.5 animate-spin" />
              : <RotateCcw className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
    </div>
  );
}
