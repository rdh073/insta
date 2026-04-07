import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Loader, MessageCircle, Search, Send, User } from 'lucide-react';
import { directApi } from '../api/instagram/direct';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { DirectThreadSummary, DirectMessageSummary } from '../types/instagram/direct';
import { Button } from '../components/ui/Button';
import { cn } from '../lib/cn';

function ThreadRow({
  thread,
  selected,
  onClick,
}: {
  thread: DirectThreadSummary;
  selected: boolean;
  onClick: () => void;
}) {
  const names = thread.participants.map((p) => `@${p.username}`).join(', ');
  const preview = thread.lastMessage?.text ?? '—';
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full cursor-pointer rounded-xl border px-3 py-2.5 text-left transition-colors duration-150',
        selected
          ? 'border-[rgba(125,207,255,0.24)] bg-[rgba(125,207,255,0.08)]'
          : 'border-transparent hover:border-[rgba(162,179,229,0.10)] hover:bg-[rgba(255,255,255,0.02)]',
      )}
    >
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
          <User className="h-3.5 w-3.5 text-[#6a7aa0]" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-[#c0caf5]">{names}</p>
          <p className="truncate text-[11px] text-[#4a5578]">{preview}</p>
        </div>
        {thread.isPending && (
          <span className="glass-chip !px-1.5 !py-0.5 !text-[9px] text-[#e0af68]">Pending</span>
        )}
      </div>
    </button>
  );
}

function MessageBubble({ msg, myUserId }: { msg: DirectMessageSummary; myUserId?: number }) {
  const isMine = myUserId != null && msg.senderUserId === myUserId;
  return (
    <div className={cn('flex', isMine ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[75%] rounded-2xl px-3 py-2 text-sm leading-5',
          isMine
            ? 'rounded-br-sm border border-[rgba(122,162,247,0.18)] bg-[rgba(122,162,247,0.12)] text-[#dce6ff]'
            : 'rounded-bl-sm border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.04)] text-[#c0caf5]',
        )}
      >
        {msg.text ?? <span className="italic text-[#4a5578]">[{msg.itemType ?? 'unsupported'}]</span>}
        {msg.sentAt && (
          <p className="mt-0.5 text-[10px] text-[#374060]">
            {new Date(msg.sentAt).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}

export function DirectPage() {
  const { accountId, setAccountId } = useAccountPicker();
  const [threads, setThreads] = useState<DirectThreadSummary[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedThread, setSelectedThread] = useState<DirectThreadSummary | null>(null);
  const [messages, setMessages] = useState<DirectMessageSummary[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [composeText, setComposeText] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accountId) return;
    void loadInbox();
  }, [accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadInbox() {
    setLoadingThreads(true);
    try {
      const result = await directApi.listInbox(accountId, 30);
      setThreads(result.threads);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoadingThreads(false);
    }
  }

  async function handleSearch(q: string) {
    setSearchQuery(q);
    if (!q.trim()) {
      void loadInbox();
      return;
    }
    setLoadingThreads(true);
    try {
      const result = await directApi.searchThreads(accountId, q.trim());
      setThreads(result.threads);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoadingThreads(false);
    }
  }

  async function selectThread(thread: DirectThreadSummary) {
    setSelectedThread(thread);
    setLoadingMessages(true);
    setMessages([]);
    try {
      const result = await directApi.getThread(accountId, thread.directThreadId, 30);
      setMessages(result.messages);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoadingMessages(false);
    }
  }

  async function handleSend() {
    if (!composeText.trim() || !selectedThread) return;
    setSending(true);
    try {
      const msg = await directApi.sendToThread(accountId, selectedThread.directThreadId, composeText.trim());
      setMessages((prev) => [...prev, msg]);
      setComposeText('');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: thread list */}
      <div className="flex w-72 shrink-0 flex-col border-r border-[rgba(162,179,229,0.10)]">
        {/* Account + search */}
        <div className="shrink-0 space-y-2 border-b border-[rgba(162,179,229,0.08)] p-3">
          <AccountPicker value={accountId} onChange={(id) => { setAccountId(id); setSelectedThread(null); setMessages([]); }} />
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#4a5578]" />
            <input
              value={searchQuery}
              onChange={(e) => void handleSearch(e.target.value)}
              placeholder="Search threads…"
              className="glass-field w-full pl-8 text-sm"
            />
          </div>
        </div>

        {/* Thread list */}
        <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-0.5">
          {loadingThreads && (
            <div className="flex h-20 items-center justify-center">
              <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
            </div>
          )}
          {!loadingThreads && threads.length === 0 && (
            <p className="p-4 text-center text-xs text-[#4a5578]">No threads</p>
          )}
          {threads.map((t) => (
            <ThreadRow
              key={t.directThreadId}
              thread={t}
              selected={selectedThread?.directThreadId === t.directThreadId}
              onClick={() => void selectThread(t)}
            />
          ))}
        </div>
      </div>

      {/* Right: message pane */}
      <div className="flex flex-1 flex-col min-w-0">
        {!selectedThread ? (
          <div className="flex h-full items-center justify-center flex-col gap-3 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[rgba(125,207,255,0.14)] bg-[rgba(125,207,255,0.08)]">
              <MessageCircle className="h-5 w-5 text-[#4a7a9a]" />
            </div>
            <p className="text-sm text-[#4a5578]">Select a thread to read messages</p>
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-5 py-3">
              <p className="text-sm font-medium text-[#c0caf5]">
                {selectedThread.participants.map((p) => `@${p.username}`).join(', ')}
              </p>
              <p className="font-mono text-[10px] text-[#374060]">{selectedThread.directThreadId}</p>
            </div>

            {/* Messages */}
            <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4 space-y-2">
              {loadingMessages && (
                <div className="flex h-20 items-center justify-center">
                  <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
                </div>
              )}
              {messages.map((m) => (
                <MessageBubble key={m.directMessageId} msg={m} />
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Compose */}
            <div className="shrink-0 border-t border-[rgba(162,179,229,0.08)] p-3">
              <div className="flex gap-2">
                <textarea
                  value={composeText}
                  onChange={(e) => setComposeText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void handleSend(); } }}
                  rows={2}
                  placeholder="Write a message… (Enter to send)"
                  className="glass-textarea flex-1 resize-none text-sm"
                />
                <Button size="sm" loading={sending} onClick={() => void handleSend()} className="self-end">
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
