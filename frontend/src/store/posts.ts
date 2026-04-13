import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { PostJob } from '../types';

type StatusFilter = 'all' | PostJob['status'];

interface PostStore {
  jobs: PostJob[];
  campaignFilter: StatusFilter;
  streamError: string | null;
  setJobs: (jobs: PostJob[]) => void;
  addJob: (job: PostJob) => void;
  updateJob: (job: PostJob) => void;
  removeJob: (id: string) => void;
  setCampaignFilter: (v: StatusFilter) => void;
  setStreamError: (message: string | null) => void;
}

export const usePostStore = create<PostStore>()(
  persist(
    (set) => ({
      jobs: [],
      campaignFilter: 'all',
      streamError: null,
      setJobs: (jobs) => set({ jobs }),
      addJob: (job) => set((s) => ({ jobs: [job, ...s.jobs] })),
      updateJob: (job) =>
        set((s) => ({ jobs: s.jobs.map((j) => (j.id === job.id ? job : j)) })),
      removeJob: (id) =>
        set((s) => ({ jobs: s.jobs.filter((j) => j.id !== id) })),
      setCampaignFilter: (campaignFilter) => set({ campaignFilter }),
      setStreamError: (streamError) => set({ streamError }),
    }),
    {
      name: 'insta-posts',
      partialize: (s) => ({ campaignFilter: s.campaignFilter }),
    },
  ),
);
