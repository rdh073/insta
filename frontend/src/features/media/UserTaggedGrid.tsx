import { useEffect } from 'react';
import { AtSign, Film, Image, Images, Loader } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { useUserTagged } from './useUserTagged';
import type { MediaSummary } from '../../types/instagram/media';
import { cn } from '../../lib/cn';

const MEDIA_TYPE_LABEL: Record<number, string> = {
  1: 'Photo',
  2: 'Video',
  8: 'Album',
};

function mediaTypeIcon(t: number) {
  if (t === 2) return <Film className="h-2.5 w-2.5" />;
  if (t === 8) return <Images className="h-2.5 w-2.5" />;
  return <Image className="h-2.5 w-2.5" />;
}

export function UserTaggedGrid({
  accountId,
  userId,
  selectedPk,
  onSelect,
}: {
  accountId: string;
  userId: number | null;
  selectedPk?: number | null;
  onSelect?: (item: MediaSummary) => void;
}) {
  const { tagged, loading, error, load } = useUserTagged(accountId, userId, 24);

  useEffect(() => {
    if (userId && tagged === null && !loading) {
      void load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  if (!userId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[#4a5578]">
        Load a user to see posts they’re tagged in.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-2 p-4">
        <p className="text-xs text-[#f7768e]">{error}</p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!tagged || tagged.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-sm text-[#4a5578]">
        <AtSign className="h-6 w-6" />
        <p>No tagged posts found.</p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {tagged.map((m) => {
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
                ? 'border-[rgba(125,207,255,0.40)] ring-1 ring-[rgba(125,207,255,0.24)]'
                : 'border-[rgba(162,179,229,0.10)] hover:border-[rgba(125,207,255,0.24)]',
            )}
          >
            {thumb ? (
              <img
                src={thumb}
                alt={m.captionText || 'tagged'}
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
                <AtSign className="h-2.5 w-2.5" />
                {MEDIA_TYPE_LABEL[m.mediaType] ?? 'Tagged'}
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
  );
}
