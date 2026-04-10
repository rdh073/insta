import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type ProxyTab = 'routing' | 'pool';

interface ProxyStore {
  tab: ProxyTab;
  setTab: (v: ProxyTab) => void;
}

export const useProxyStore = create<ProxyStore>()(
  persist(
    (set) => ({
      tab: 'routing',
      setTab: (tab) => set({ tab }),
    }),
    {
      name: 'insta-proxy',
    },
  ),
);
