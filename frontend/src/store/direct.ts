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

  // Actions
  setInboxTab: (tab: InboxTab) => void;
  setThreads: (threads: DirectThreadSummary[]) => void;
  setPendingThreads: (threads: DirectThreadSummary[]) => void;
  removePendingThread: (threadId: string) => void;
  setSelectedThread: (thread: DirectThreadSummary | null) => void;
  setMessages: (messages: DirectMessageSummary[]) => void;
  appendMessage: (msg: DirectMessageSummary) => void;
  removeMessage: (messageId: string) => void;
  setSearchQuery: (q: string) => void;
  clearSession: () => void;
}

export const useDirectStore = create<DirectState>()((set) => ({
  inboxTab: 'inbox',
  threads: [],
  pendingThreads: [],
  selectedThread: null,
  messages: [],
  searchQuery: '',

  setInboxTab: (inboxTab) => set({ inboxTab }),
  setThreads: (threads) => set({ threads }),
  setPendingThreads: (pendingThreads) => set({ pendingThreads }),
  removePendingThread: (threadId) =>
    set((s) => ({ pendingThreads: s.pendingThreads.filter((t) => t.directThreadId !== threadId) })),
  setSelectedThread: (selectedThread) => set({ selectedThread, messages: [] }),
  setMessages: (messages) => set({ messages }),
  appendMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  removeMessage: (messageId) =>
    set((s) => ({ messages: s.messages.filter((m) => m.directMessageId !== messageId) })),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  clearSession: () => set({
    threads: [],
    pendingThreads: [],
    selectedThread: null,
    messages: [],
    searchQuery: '',
    inboxTab: 'inbox',
  }),
}));
