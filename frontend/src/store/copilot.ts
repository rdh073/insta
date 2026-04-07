import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CopilotEvent } from '../api/operator-copilot';

export type RunState = 'idle' | 'running' | 'waiting_approval' | 'done' | 'error';

export interface ChatTurn {
  userPrompt: string;
  attachment?: { name: string; lines: number };
  events: CopilotEvent[];
}

export interface CopilotSession {
  threadId?: string;
  turns: ChatTurn[];
  runState: RunState;
  approvalPayload?: Record<string, unknown>;
}

interface CopilotStore {
  session: CopilotSession;
  setSession: (updater: CopilotSession | ((prev: CopilotSession) => CopilotSession)) => void;
  resetSession: () => void;
}

const EMPTY_SESSION: CopilotSession = { turns: [], runState: 'idle' };

export const useCopilotStore = create<CopilotStore>()(
  persist(
    (set) => ({
      session: EMPTY_SESSION,

      setSession: (updater) =>
        set((s) => ({
          session: typeof updater === 'function' ? updater(s.session) : updater,
        })),

      resetSession: () => set({ session: EMPTY_SESSION }),
    }),
    {
      name: 'insta-copilot-session',
      // Only persist turns + threadId — skip transient runState/approvalPayload
      partialize: (s) => ({
        session: {
          threadId: s.session.threadId,
          turns: s.session.turns,
        },
      }),
      merge: (persisted, current) => {
        const p = persisted as Partial<CopilotStore> | undefined;
        return {
          ...current,
          session: { ...EMPTY_SESSION, ...p?.session },
        };
      },
    },
  ),
);
