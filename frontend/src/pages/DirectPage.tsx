import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { CheckCheck, Clock, Loader, MessageCircle, Search, Send, Trash2, User } from 'lucide-react';
import { directApi, getSyntheticSearchUserId } from '../api/instagram/direct';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { DirectThreadSummary, DirectMessageSummary } from '../types/instagram/direct';
import { Button } from '../components/ui/Button';
import { useDirectStore } from '../store/direct';
import type { InboxTab } from '../store/direct';
import { cn } from '../lib/cn';

// ─── Thread row ───────────────────────────────────────────────────────────────

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

// ─── Message bubble ───────────────────────────────────────────────────────────

function MessageBubble({
  msg,
  myUserId,
  onDelete,
}: {
  msg: DirectMessageSummary;
  myUserId?: number;
  onDelete: (id: string) => void;
}) {
  const isMine = myUserId != null && msg.senderUserId === myUserId;
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    onDelete(msg.directMessageId);
  }

  return (
    <div className={cn('group flex items-end gap-1.5', isMine ? 'justify-end' : 'justify-start')}>
      {/* Delete button — only shown on own messages */}
      {isMine && (
        <button
          type="button"
          disabled={deleting}
          onClick={handleDelete}
          title="Delete message"
          className="mb-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[#374060] opacity-0 transition-opacity group-hover:opacity-100 hover:bg-[rgba(247,118,142,0.12)] hover:text-[#f7768e] disabled:opacity-30"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DirectPage() {
  const { accountId, setAccountId } = useAccountPicker();

  const inboxTab       = useDirectStore((s) => s.inboxTab);
  const threads        = useDirectStore((s) => s.threads);
  const pendingThreads = useDirectStore((s) => s.pendingThreads);
  const selectedThread = useDirectStore((s) => s.selectedThread);
  const messages       = useDirectStore((s) => s.messages);
  const searchQuery    = useDirectStore((s) => s.searchQuery);

  const setInboxTab        = useDirectStore((s) => s.setInboxTab);
  const setThreads         = useDirectStore((s) => s.setThreads);
  const setPendingThreads  = useDirectStore((s) => s.setPendingThreads);
  const removePendingThread = useDirectStore((s) => s.removePendingThread);
  const setSelectedThread  = useDirectStore((s) => s.setSelectedThread);
  const setMessages        = useDirectStore((s) => s.setMessages);
  const appendMessage      = useDirectStore((s) => s.appendMessage);
  const removeMessage      = useDirectStore((s) => s.removeMessage);
  const setSearchQuery     = useDirectStore((s) => s.setSearchQuery);
  const clearSession       = useDirectStore((s) => s.clearSession);

  const [loadingThreads, setLoadingThreads] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [composeText, setComposeText] = useState('');
  const [sending, setSending] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load inbox when account changes
  useEffect(() => {
    if (!accountId) return;
    void loadInbox();
  }, [accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load pending when tab switches to pending
  useEffect(() => {
    if (!accountId || inboxTab !== 'pending') return;
    void loadPending();
  }, [accountId, inboxTab]); // eslint-disable-line react-hooks/exhaustive-deps

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

  async function loadPending() {
    setLoadingThreads(true);
    try {
      const result = await directApi.listPending(accountId, 30);
      setPendingThreads(result.threads);
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
    setLoadingMessages(true);
    try {
      let resolved = thread;
      const syntheticUserId = getSyntheticSearchUserId(thread.directThreadId);
      if (syntheticUserId != null) {
        resolved = await directApi.findOrCreate(accountId, [syntheticUserId]);
      }

      setSelectedThread(resolved);
      const result = await directApi.getThread(accountId, resolved.directThreadId, 30);
      setMessages(result.messages);
      // Mark as seen silently — failure is non-critical
      directApi.markSeen(accountId, resolved.directThreadId).catch(() => undefined);
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
      appendMessage(msg);
      setComposeText('');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  async function handleDeleteMessage(messageId: string) {
    if (!selectedThread) return;
    try {
      await directApi.deleteMessage(accountId, selectedThread.directThreadId, messageId);
      removeMessage(messageId);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function handleApprovePending(thread: DirectThreadSummary) {
    setApproving(thread.directThreadId);
    try {
      const receipt = await directApi.approvePending(accountId, thread.directThreadId);
      if (receipt.success) {
        removePendingThread(thread.directThreadId);
        toast.success('Request approved');
        // Load inbox so the now-approved thread appears there
        void loadInbox();
      } else {
        toast.error(receipt.reason || 'Approval failed');
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setApproving(null);
    }
  }

  const displayedThreads = inboxTab === 'pending' ? pendingThreads : threads;

  const TABS: { id: InboxTab; label: string }[] = [
    { id: 'inbox', label: 'Inbox' },
    { id: 'pending', label: 'Pending' },
  ];

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: thread list */}
      <div className="flex w-72 shrink-0 flex-col border-r border-[rgba(162,179,229,0.10)]">
        {/* Account + search */}
        <div className="shrink-0 space-y-2 border-b border-[rgba(162,179,229,0.08)] p-3">
          <AccountPicker
            value={accountId}
            onChange={(id) => { setAccountId(id); clearSession(); }}
          />
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#4a5578]" />
            <input
              value={searchQuery}
              onChange={(e) => void handleSearch(e.target.value)}
              placeholder="Search threads…"
              className="glass-field w-full pl-8 text-sm"
            />
          </div>
          {/* Inbox / Pending tabs */}
          <div className="flex gap-1 rounded-lg border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] p-0.5">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setInboxTab(tab.id)}
                className={cn(
                  'flex-1 cursor-pointer rounded-md py-1 text-[11px] font-medium transition-colors duration-150',
                  inboxTab === tab.id
                    ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                    : 'text-[#6a7aa0] hover:text-[#c0caf5]',
                )}
              >
                {tab.label}
                {tab.id === 'pending' && pendingThreads.length > 0 && (
                  <span className="ml-1 inline-flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-[rgba(224,175,104,0.20)] px-1 text-[9px] font-bold text-[#e0af68]">
                    {pendingThreads.length}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Thread list */}
        <div className="flex-1 min-h-0 overflow-y-auto p-2 space-y-0.5">
          {loadingThreads && (
            <div className="flex h-20 items-center justify-center">
              <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
            </div>
          )}
          {!loadingThreads && displayedThreads.length === 0 && (
            <p className="p-4 text-center text-xs text-[#4a5578]">
              {inboxTab === 'pending' ? 'No pending requests' : 'No threads'}
            </p>
          )}

          {inboxTab === 'inbox' &&
            threads.map((t) => (
              <ThreadRow
                key={t.directThreadId}
                thread={t}
                selected={selectedThread?.directThreadId === t.directThreadId}
                onClick={() => void selectThread(t)}
              />
            ))}

          {inboxTab === 'pending' &&
            pendingThreads.map((t) => (
              <div key={t.directThreadId} className="space-y-1">
                <ThreadRow
                  thread={t}
                  selected={selectedThread?.directThreadId === t.directThreadId}
                  onClick={() => void selectThread(t)}
                />
                <button
                  type="button"
                  disabled={approving === t.directThreadId}
                  onClick={() => void handleApprovePending(t)}
                  className="ml-9 flex cursor-pointer items-center gap-1 text-[11px] text-[#9ece6a] hover:text-[#c3e88d] disabled:opacity-40"
                >
                  {approving === t.directThreadId ? (
                    <Loader className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCheck className="h-3 w-3" />
                  )}
                  Approve
                </button>
              </div>
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
              <div className="flex items-center gap-2">
                <p className="flex-1 text-sm font-medium text-[#c0caf5]">
                  {selectedThread.participants.map((p) => `@${p.username}`).join(', ')}
                </p>
                {selectedThread.isPending && (
                  <span className="flex items-center gap-1 text-[11px] text-[#e0af68]">
                    <Clock className="h-3 w-3" /> Pending
                  </span>
                )}
              </div>
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
                <MessageBubble
                  key={m.directMessageId}
                  msg={m}
                  onDelete={handleDeleteMessage}
                />
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
