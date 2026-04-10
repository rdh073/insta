import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SmartEngagementResponse } from '../api/smart-engagement';

interface AccountResult {
  accountId: string;
  username: string;
  response: SmartEngagementResponse;
}

interface SmartEngagementStore {
  // Persisted preferences
  goal: string;
  mode: 'recommendation' | 'execute';
  maxTargets: number;
  selectedIds: string[];

  // In-memory run state
  results: AccountResult[];
  loading: boolean;
  progress: string;
  resumeLoading: boolean;

  // Actions
  setGoal: (v: string) => void;
  setMode: (v: 'recommendation' | 'execute') => void;
  setMaxTargets: (v: number) => void;
  setSelectedIds: (ids: string[]) => void;
  setResults: (r: AccountResult[]) => void;
  setLoading: (v: boolean) => void;
  setProgress: (v: string) => void;
  setResumeLoading: (v: boolean) => void;
  updateResult: (accountId: string, response: SmartEngagementResponse) => void;
  clearResults: () => void;
}

export const useSmartEngagementStore = create<SmartEngagementStore>()(
  persist(
    (set) => ({
      goal: '',
      mode: 'recommendation',
      maxTargets: 5,
      selectedIds: [],
      results: [],
      loading: false,
      progress: '',
      resumeLoading: false,

      setGoal: (goal) => set({ goal }),
      setMode: (mode) => set({ mode }),
      setMaxTargets: (maxTargets) => set({ maxTargets }),
      setSelectedIds: (selectedIds) => set({ selectedIds }),
      setResults: (results) => set({ results }),
      setLoading: (loading) => set({ loading }),
      setProgress: (progress) => set({ progress }),
      setResumeLoading: (resumeLoading) => set({ resumeLoading }),
      updateResult: (accountId, response) =>
        set((s) => ({
          results: s.results.map((r) =>
            r.accountId === accountId ? { ...r, response } : r,
          ),
        })),
      clearResults: () => set({ results: [], progress: '' }),
    }),
    {
      name: 'insta-smart-engagement',
      partialize: (s) => ({
        goal: s.goal,
        mode: s.mode,
        maxTargets: s.maxTargets,
        selectedIds: s.selectedIds,
      }),
    },
  ),
);
