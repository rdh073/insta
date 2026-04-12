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
  pruneSelectedIds: (activeAccountIds: string[]) => void;
  setResults: (r: AccountResult[]) => void;
  setLoading: (v: boolean) => void;
  setProgress: (v: string) => void;
  setResumeLoading: (v: boolean) => void;
  updateResult: (accountId: string, response: SmartEngagementResponse) => void;
  clearResults: () => void;
}

export function getValidSelectedIds(selectedIds: string[], activeAccountIds: string[]): string[] {
  const activeSet = new Set(activeAccountIds);
  const seen = new Set<string>();
  const valid: string[] = [];

  for (const id of selectedIds) {
    if (!activeSet.has(id) || seen.has(id)) {
      continue;
    }
    seen.add(id);
    valid.push(id);
  }

  return valid;
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
      setSelectedIds: (selectedIds) => set({ selectedIds: getValidSelectedIds(selectedIds, selectedIds) }),
      pruneSelectedIds: (activeAccountIds) =>
        set((state) => ({
          selectedIds: getValidSelectedIds(state.selectedIds, activeAccountIds),
        })),
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
