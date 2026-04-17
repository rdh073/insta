import { create } from 'zustand';
import type { DirectThreadSummary, DirectMessageSummary } from '../types/instagram/direct';

export type InboxTab = 'inbox' | 'pending';

interface DirectState {
  // In-memory only — session-level inbox state
  inboxTab: InboxTab;
  threads: DirectThreadSummary[];
  pendingThreads: DirectThreadSummary[];
  selectedThread: DirectThreadSummary | null;
  messages: DirectMessageSummary[];
  searchQuery: string;
  mutedThreadIds: Set<string>;
  unreadThreadIds: Set<string>;

  // Actions
  setInboxTab: (tab: InboxTab) => void;
  setThreads: (threads: DirectThreadSummary[]) => void;
  setPendingThreads: (threads: DirectThreadSummary[]) => void;
  removePendingThread: (threadId: string) => void;
  removeThread: (threadId: string) => void;
  setSelectedThread: (thread: DirectThreadSummary | null) => void;
  setMessages: (messages: DirectMessageSummary[]) => void;
  appendMessage: (msg: DirectMessageSummary) => void;
  removeMessage: (messageId: string) => void;
  setSearchQuery: (q: string) => void;
  setThreadMuted: (threadId: string, muted: boolean) => void;
  setThreadUnread: (threadId: string, unread: boolean) => void;
  clearSession: () => void;
}

export const useDirectStore = create<DirectState>()((set) => ({
  inboxTab: 'inbox',
  threads: [],
  pendingThreads: [],
  selectedThread: null,
  messages: [],
  searchQuery: '',
  mutedThreadIds: new Set<string>(),
  unreadThreadIds: new Set<string>(),

  setInboxTab: (inboxTab) => set({ inboxTab }),
  setThreads: (threads) => set({ threads }),
  setPendingThreads: (pendingThreads) => set({ pendingThreads }),
  removePendingThread: (threadId) =>
    set((s) => ({ pendingThreads: s.pendingThreads.filter((t) => t.directThreadId !== threadId) })),
  removeThread: (threadId) =>
    set((s) => ({
      threads: s.threads.filter((t) => t.directThreadId !== threadId),
      pendingThreads: s.pendingThreads.filter((t) => t.directThreadId !== threadId),
      selectedThread:
        s.selectedThread?.directThreadId === threadId ? null : s.selectedThread,
      messages: s.selectedThread?.directThreadId === threadId ? [] : s.messages,
    })),
  setSelectedThread: (selectedThread) => set({ selectedThread, messages: [] }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  removeMessage: (messageId) =>
    set((s) => ({ messages: s.messages.filter((m) => m.directMessageId !== messageId) })),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setThreadMuted: (threadId, muted) =>
    set((s) => {
      const next = new Set(s.mutedThreadIds);
      if (muted) next.add(threadId);
      else next.delete(threadId);
      return { mutedThreadIds: next };
    }),
  setThreadUnread: (threadId, unread) =>
    set((s) => {
      const next = new Set(s.unreadThreadIds);
      if (unread) next.add(threadId);
      else next.delete(threadId);
      return { unreadThreadIds: next };
    }),
  clearSession: () => set({
    threads: [],
    pendingThreads: [],
    selectedThread: null,
    messages: [],
    searchQuery: '',
    inboxTab: 'inbox',
    mutedThreadIds: new Set<string>(),
    unreadThreadIds: new Set<string>(),
  }),
}));
