import { useEffect } from 'react';
import { Heart, Loader, ShieldCheck } from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { useMediaLikers } from './useMediaLikers';

export function MediaLikersPanel({
  accountId,
  mediaId,
}: {
  accountId: string;
  mediaId: string;
}) {
  const { likers, loading, error, load } = useMediaLikers(accountId, mediaId);

  useEffect(() => {
    if (likers === null && !loading) {
      void load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mediaId]);

  if (loading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <Loader className="h-4 w-4 animate-spin text-[#7dcfff]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-xs text-[#f7768e]">{error}</p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!likers || likers.length === 0) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-xs text-[#4a5578]">No likers loaded yet.</p>
        <Button size="sm" onClick={() => void load()}>
          Load likers
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-[11px] text-[#4a5578]">
          <Heart className="h-3 w-3 text-[#f7768e]" />
          {likers.length} likers
        </p>
        <Button size="sm" variant="secondary" onClick={() => void load()}>
          Refresh
        </Button>
      </div>
      <div className="space-y-1.5">
        {likers.map((u) => (
          <div
            key={u.pk}
            className="glass-panel-soft flex items-center gap-2.5 px-2.5 py-1.5"
          >
            {u.profilePicUrl ? (
              <img
                src={u.profilePicUrl}
                alt={u.username}
                className="h-7 w-7 rounded-full object-cover"
                loading="lazy"
              />
            ) : (
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[rgba(125,207,255,0.12)] text-[10px] text-[#7dcfff]">
                {u.username.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1 truncate text-[11px] font-medium text-[#7dcfff]">
                @{u.username}
                {u.isVerified && <ShieldCheck className="h-2.5 w-2.5 text-[#9ece6a]" />}
              </p>
              {u.fullName && (
                <p className="truncate text-[10px] text-[#4a5578]">{u.fullName}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
