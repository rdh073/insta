import { create } from 'zustand';
import type { PostJob } from '../types';

interface PostStore {
  jobs: PostJob[];
  setJobs: (jobs: PostJob[]) => void;
  addJob: (job: PostJob) => void;
  updateJob: (job: PostJob) => void;
  removeJob: (id: string) => void;
}

export const usePostStore = create<PostStore>()((set) => ({
  jobs: [],
  setJobs: (jobs) => set({ jobs }),
  addJob: (job) => set((s) => ({ jobs: [job, ...s.jobs] })),
  updateJob: (job) =>
    set((s) => ({ jobs: s.jobs.map((j) => (j.id === job.id ? job : j)) })),
  removeJob: (id) =>
    set((s) => ({ jobs: s.jobs.filter((j) => j.id !== id) })),
}));
