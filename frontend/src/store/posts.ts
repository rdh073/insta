import { create } from 'zustand';
import type { PostJob } from '../types';

interface PostStore {
  jobs: PostJob[];
  setJobs: (jobs: PostJob[]) => void;
  addJob: (job: PostJob) => void;
  updateJob: (job: PostJob) => void;
}

export const usePostStore = create<PostStore>()((set) => ({
  jobs: [],
  setJobs: (jobs) => set({ jobs }),
  addJob: (job) => set((s) => ({ jobs: [job, ...s.jobs] })),
  updateJob: (job) =>
    set((s) => ({ jobs: s.jobs.map((j) => (j.id === job.id ? job : j)) })),
}));
