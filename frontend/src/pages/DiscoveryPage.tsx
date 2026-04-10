import toast from 'react-hot-toast';
import {
  Film,
  Hash,
  Heart,
  Image,
  Images,
  Loader,
  MessageCircle,
  TrendingUp,
  Clock,
} from 'lucide-react';
import { discoveryApi } from '../api/instagram/discovery';
import { AccountPicker, useAccountPicker } from '../components/instagram/AccountPicker';
import type { HashtagSummary } from '../types/instagram/discovery';
import type { MediaSummary } from '../types/instagram/media';
import { Button } from '../components/ui/Button';
import { useDiscoveryStore } from '../store/discovery';
import { cn } from '../lib/cn';

type Feed = 'top' | 'recent';

function fmt(n: number | null) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function mediaIcon(t: number) {
  if (t === 2) return <Film className="h-3 w-3" />;
  if (t === 8) return <Images className="h-3 w-3" />;
  return <Image className="h-3 w-3" />;
}

function MediaCard({ media }: { media: MediaSummary }) {
  const thumb = media.resources[0]?.thumbnailUrl ?? null;
  return (
    <div className="group relative aspect-square w-full overflow-hidden rounded-2xl border border-[rgba(162,179,229,0.10)] transition-all duration-200 hover:border-[rgba(125,207,255,0.24)]">
      {thumb ? (
        <img src={thumb} alt={media.captionText || 'media'} className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)] text-[#4a5578]">
          {mediaIcon(media.mediaType)}
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-1 bg-gradient-to-t from-[rgba(4,6,14,0.82)] to-transparent p-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <span className="flex items-center gap-1 text-[10px] text-[#9aa7cf]">
          <Heart className="h-2.5 w-2.5 text-[#f7768e]" /> {fmt(media.likeCount)}
        </span>
        <span className="flex items-center gap-1 text-[10px] text-[#9aa7cf]">
          <MessageCircle className="h-2.5 w-2.5 text-[#7dcfff]" /> {fmt(media.commentCount)}
        </span>
      </div>
      <div className="absolute right-1.5 top-1.5">
        <span className="glass-chip !px-1.5 !py-0.5 !text-[9px]">
          {mediaIcon(media.mediaType)}
        </span>
      </div>
    </div>
  );
}

function HashtagCard({ hashtag }: { hashtag: HashtagSummary }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl border border-[rgba(125,207,255,0.14)] bg-[rgba(125,207,255,0.06)] px-5 py-4">
      {hashtag.profilePicUrl ? (
        <img src={hashtag.profilePicUrl} alt="" className="h-12 w-12 rounded-full object-cover" />
      ) : (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.10)]">
          <Hash className="h-5 w-5 text-[#7dcfff]" />
        </div>
      )}
      <div>
        <p className="text-base font-semibold text-[#eef4ff]">#{hashtag.name}</p>
        <p className="text-sm text-[#7aa2f7]">
          {hashtag.mediaCount != null ? `${fmt(hashtag.mediaCount)} posts` : 'Post count unavailable'}
        </p>
        <p className="font-mono text-[10px] text-[#374060]">id {hashtag.id}</p>
      </div>
    </div>
  );
}

export function DiscoveryPage() {
  const { accountId, setAccountId } = useAccountPicker();

  const hashtagInput = useDiscoveryStore((s) => s.hashtagInput);
  const feed         = useDiscoveryStore((s) => s.feed);
  const amount       = useDiscoveryStore((s) => s.amount);
  const hashtag      = useDiscoveryStore((s) => s.hashtag);
  const posts        = useDiscoveryStore((s) => s.posts);

  const setHashtagInput = useDiscoveryStore((s) => s.setHashtagInput);
  const setFeed         = useDiscoveryStore((s) => s.setFeed);
  const setAmount       = useDiscoveryStore((s) => s.setAmount);
  const setHashtag      = useDiscoveryStore((s) => s.setHashtag);
  const setPosts        = useDiscoveryStore((s) => s.setPosts);
  const setLoading      = useDiscoveryStore((s) => s.setLoading);
  const loading         = useDiscoveryStore((s) => s.loading);
  const clearResults    = useDiscoveryStore((s) => s.clearResults);

  async function handleLoad() {
    const name = hashtagInput.trim().replace(/^#/, '');
    if (!accountId || !name) return;

    setLoading(true);
    clearResults();

    try {
      const [meta, feed_result] = await Promise.all([
        discoveryApi.getHashtag(accountId, name),
        feed === 'top'
          ? discoveryApi.getHashtagTopPosts(accountId, name, amount)
          : discoveryApi.getHashtagRecentPosts(accountId, name, amount),
      ]);
      setHashtag(meta);
      setPosts(feed_result.posts);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function switchFeed(next: Feed) {
    setFeed(next);
    if (!hashtag || !accountId) return;
    const name = hashtag.name;
    setLoading(true);
    setPosts([]);
    try {
      const result = next === 'top'
        ? await discoveryApi.getHashtagTopPosts(accountId, name, amount)
        : await discoveryApi.getHashtagRecentPosts(accountId, name, amount);
      setPosts(result.posts);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="shrink-0 border-b border-[rgba(162,179,229,0.08)] px-5 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <AccountPicker value={accountId} onChange={setAccountId} className="w-48" />

          <div className="relative">
            <Hash className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#4a5578]" />
            <input
              value={hashtagInput}
              onChange={(e) => setHashtagInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void handleLoad(); }}
              placeholder="hashtag name"
              className="glass-field w-44 pl-8 text-sm"
            />
          </div>

          <select
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="glass-select text-sm"
          >
            {[12, 24, 48, 72].map((n) => (
              <option key={n} value={n}>{n} posts</option>
            ))}
          </select>

          <Button size="sm" loading={loading} onClick={() => void handleLoad()}>
            Search
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {!hashtag && !loading && (
          <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
            Enter a hashtag name and click Search
          </div>
        )}

        {loading && (
          <div className="flex h-40 items-center justify-center">
            <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
          </div>
        )}

        {hashtag && (
          <div className="mx-auto max-w-4xl space-y-5">
            <HashtagCard hashtag={hashtag} />

            <div className="flex items-center justify-between">
              <div className="flex gap-1 rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.02)] p-1">
                <button
                  type="button"
                  onClick={() => void switchFeed('top')}
                  className={cn(
                    'flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-150',
                    feed === 'top'
                      ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                      : 'text-[#6a7aa0] hover:text-[#c0caf5]',
                  )}
                >
                  <TrendingUp className="h-3 w-3" /> Top posts
                </button>
                <button
                  type="button"
                  onClick={() => void switchFeed('recent')}
                  className={cn(
                    'flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-150',
                    feed === 'recent'
                      ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                      : 'text-[#6a7aa0] hover:text-[#c0caf5]',
                  )}
                >
                  <Clock className="h-3 w-3" /> Recent
                </button>
              </div>
              {posts.length > 0 && (
                <span className="glass-chip text-[#7aa2f7]">{posts.length} posts</span>
              )}
            </div>

            {loading && (
              <div className="flex h-24 items-center justify-center">
                <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
              </div>
            )}
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
              {posts.map((m) => (
                <MediaCard key={m.pk} media={m} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
