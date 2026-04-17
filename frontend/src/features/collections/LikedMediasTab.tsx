import { useEffect } from 'react';
import { Film, Heart, Image, Images, Loader } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import type { MediaSummary } from '../../types/instagram/media';
import { cn } from '../../lib/cn';
import { useLikedMedias } from './useLikedMedias';

const MEDIA_TYPE_LABEL: Record<number, string> = { 1: 'Photo', 2: 'Video', 8: 'Album' };

function mediaTypeIcon(t: number) {
  if (t === 2) return <Film className="h-2.5 w-2.5" />;
  if (t === 8) return <Images className="h-2.5 w-2.5" />;
  return <Image className="h-2.5 w-2.5" />;
}

export function LikedMediasTab({
  accountId,
  selectedPk,
  onSelect,
}: {
  accountId: string;
  selectedPk?: number | null;
  onSelect?: (item: MediaSummary) => void;
}) {
  const { liked, hasMore, loading, error, load, loadMore } = useLikedMedias(accountId, 24);

  useEffect(() => {
    if (accountId && liked.length === 0 && !loading) {
      void load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  if (!accountId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
        Select an account to see its liked posts.
      </div>
    );
  }

  if (loading && liked.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
      </div>
    );
  }

  if (error && liked.length === 0) {
    return (
      <div className="flex flex-col items-start gap-2 p-4">
        <p className="text-xs text-[#f7768e]">{error}</p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Retry
        </Button>
      </div>
    );
  }

  if (liked.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-sm text-[#4a5578]">
        <Heart className="h-6 w-6" />
        <p>No liked posts found.</p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {liked.map((m) => {
          const thumb = m.resources[0]?.thumbnailUrl ?? null;
          const isSelected = selectedPk === m.pk;
          return (
            <button
              key={m.pk}
              type="button"
              onClick={() => onSelect?.(m)}
              className={cn(
                'group relative aspect-square w-full cursor-pointer overflow-hidden rounded-2xl border transition-all duration-200',
                isSelected
                  ? 'border-[rgba(247,118,142,0.40)] ring-1 ring-[rgba(247,118,142,0.24)]'
                  : 'border-[rgba(162,179,229,0.10)] hover:border-[rgba(247,118,142,0.24)]',
              )}
            >
              {thumb ? (
                <img
                  src={thumb}
                  alt={m.captionText || 'liked'}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-[rgba(255,255,255,0.03)]">
                  {mediaTypeIcon(m.mediaType)}
                </div>
              )}
              <div className="absolute left-1.5 top-1.5">
                <span className="glass-chip !px-1.5 !py-0.5 !text-[9px]">
                  <Heart className="h-2.5 w-2.5 text-[#f7768e]" />
                  {MEDIA_TYPE_LABEL[m.mediaType] ?? 'Liked'}
                </span>
              </div>
              {m.owner && (
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[rgba(4,6,14,0.82)] to-transparent p-2 text-[10px] text-[#9aa7cf] opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                  @{m.owner}
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-center gap-2 py-2">
        {hasMore ? (
          <Button
            size="sm"
            variant="secondary"
            loading={loading}
            onClick={() => void loadMore()}
          >
            Load more
          </Button>
        ) : (
          <span className="text-xs text-[#4a5578]">End of liked history</span>
        )}
      </div>
    </div>
  );
}
