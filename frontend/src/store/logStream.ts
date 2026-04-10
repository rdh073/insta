import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface LogRecord {
  id: number;
  ts: string;      // ISO-8601 ms
  level: string;   // DEBUG / INFO / WARNING / ERROR / CRITICAL
  levelno: number; // 10 / 20 / 30 / 40 / 50
  name: string;    // logger name
  msg: string;     // formatted message
}

const MAX_LINES = 2000;
let _nextId = 0;
export function nextLogId() { return ++_nextId; }

interface LogStreamState {
  // Runtime — in-memory only, lost on page refresh
  lines: LogRecord[];
  total: number;
  connected: boolean;
  paused: boolean;

  // Preferences — persisted to localStorage
  minLevel: number;
  nameFilter: string;
  autoScroll: boolean;
  verboseMode: boolean;

  // Actions
  addLine: (record: LogRecord) => void;
  clearLines: () => void;
  setConnected: (v: boolean) => void;
  setPaused: (v: boolean) => void;
  setMinLevel: (v: number) => void;
  setNameFilter: (v: string) => void;
  setAutoScroll: (v: boolean) => void;
  setVerboseMode: (v: boolean) => void;
}

export const useLogStreamStore = create<LogStreamState>()(
  persist(
    (set) => ({
      lines: [],
      total: 0,
      connected: false,
      paused: false,
      minLevel: 10,
      nameFilter: '',
      autoScroll: true,
      verboseMode: false,

      addLine: (record) =>
        set((s) => {
          const next = [...s.lines, record];
          return {
            lines: next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next,
            total: s.total + 1,
          };
        }),

      clearLines: () => set({ lines: [], total: 0 }),
      setConnected: (connected) => set({ connected }),
      setPaused: (paused) => set({ paused }),
      setMinLevel: (minLevel) => set({ minLevel }),
      setNameFilter: (nameFilter) => set({ nameFilter }),
      setAutoScroll: (autoScroll) => set({ autoScroll }),
      setVerboseMode: (verboseMode) => set({ verboseMode }),
    }),
    {
      name: 'insta-log-stream',
      // Only persist user preferences — never serialise log lines to localStorage
      partialize: (s) => ({
        minLevel: s.minLevel,
        nameFilter: s.nameFilter,
        autoScroll: s.autoScroll,
        verboseMode: s.verboseMode,
      }),
    },
  ),
);
