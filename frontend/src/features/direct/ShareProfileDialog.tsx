import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { Loader, Search, User } from 'lucide-react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { directApi } from '../../api/instagram/direct';
import type { DirectThreadSummary } from '../../types/instagram/direct';
import { cn } from '../../lib/cn';

interface Props {
  open: boolean;
  onClose: () => void;
  accountId: string;
  userId: number;
  username: string;
}

export function ShareProfileDialog({
  open,
  onClose,
  accountId,
  userId,
  username,
}: Props) {
  const [threads, setThreads] = useState<DirectThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open || !accountId) return;
    let cancelled = false;
    setLoading(true);
    setSelected(new Set());
    directApi
      .listInbox(accountId, 50)
      .then((result) => {
        if (!cancelled) setThreads(result.threads);
      })
      .catch((e) => {
        if (!cancelled) toast.error((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, accountId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return threads;
    return threads.filter((t) =>
      t.participants.some((p) => p.username.toLowerCase().includes(q)),
    );
  }, [threads, query]);

  function toggle(threadId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(threadId)) next.delete(threadId);
      else next.add(threadId);
      return next;
    });
  }

  async function handleShare() {
    const threadIds = Array.from(selected);
    if (threadIds.length === 0) {
      toast.error('Pick at least one thread');
      return;
    }
    if (threadIds.length > 32) {
      toast.error('You can share into at most 32 threads at a time');
      return;
    }
    setSharing(true);
    try {
      await directApi.shareProfileToThreads(accountId, threadIds, userId);
      toast.success(`Shared @${username} to ${threadIds.length} thread(s)`);
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSharing(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Share @${username} to DMs`}>
      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#4a5578]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter threads by participant…"
            className="glass-field w-full pl-8 text-sm"
          />
        </div>

        <div className="max-h-80 overflow-y-auto rounded-xl border border-[rgba(162,179,229,0.10)]">
          {loading && (
            <div className="flex h-20 items-center justify-center">
              <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <p className="p-6 text-center text-xs text-[#4a5578]">
              {threads.length === 0 ? 'No threads yet' : 'No matching threads'}
            </p>
          )}
          {!loading &&
            filtered.map((t) => {
              const names = t.participants.map((p) => `@${p.username}`).join(', ');
              const checked = selected.has(t.directThreadId);
              return (
                <button
                  key={t.directThreadId}
                  type="button"
                  onClick={() => toggle(t.directThreadId)}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-2 border-b border-[rgba(162,179,229,0.06)] px-3 py-2.5 text-left last:border-b-0 transition-colors',
                    checked
                      ? 'bg-[rgba(125,207,255,0.08)]'
                      : 'hover:bg-[rgba(255,255,255,0.02)]',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    readOnly
                    aria-hidden
                    tabIndex={-1}
                    className="pointer-events-none h-3.5 w-3.5 accent-[#7dcfff]"
                  />
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
                    <User className="h-3.5 w-3.5 text-[#6a7aa0]" />
                  </div>
                  <p className="truncate text-xs font-medium text-[#c0caf5]">{names}</p>
                </button>
              );
            })}
        </div>

        <div className="flex items-center justify-between">
          <p className="text-[11px] text-[#6a7aa0]">
            {selected.size} thread{selected.size === 1 ? '' : 's'} selected
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={sharing}>
              Cancel
            </Button>
            <Button
              size="sm"
              loading={sharing}
              disabled={selected.size === 0}
              onClick={() => void handleShare()}
            >
              Share
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
