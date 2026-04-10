import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { HashtagSummary } from '../types/instagram/discovery';
import type { MediaSummary } from '../types/instagram/media';

type Feed = 'top' | 'recent';

interface DiscoveryState {
  // Persisted preferences
  hashtagInput: string;
  feed: Feed;
  amount: number;

  // In-memory results
  hashtag: HashtagSummary | null;
  posts: MediaSummary[];
  loading: boolean;

  // Actions
  setHashtagInput: (v: string) => void;
  setFeed: (v: Feed) => void;
  setAmount: (v: number) => void;
  setHashtag: (h: HashtagSummary | null) => void;
  setPosts: (posts: MediaSummary[]) => void;
  setLoading: (v: boolean) => void;
  clearResults: () => void;
}

export const useDiscoveryStore = create<DiscoveryState>()(
  persist(
    (set) => ({
      hashtagInput: '',
      feed: 'top',
      amount: 24,
      hashtag: null,
      posts: [],
      loading: false,

      setHashtagInput: (hashtagInput) => set({ hashtagInput }),
      setFeed: (feed) => set({ feed }),
      setAmount: (amount) => set({ amount }),
      setHashtag: (hashtag) => set({ hashtag }),
      setPosts: (posts) => set({ posts }),
      setLoading: (loading) => set({ loading }),
      clearResults: () => set({ hashtag: null, posts: [] }),
    }),
    {
      name: 'insta-discovery',
      partialize: (s) => ({
        hashtagInput: s.hashtagInput,
        feed: s.feed,
        amount: s.amount,
      }),
    },
  ),
);
