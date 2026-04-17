import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { mediaApi } from '../../api/instagram/media';
import { useMediaStore } from '../../store/media';
import type { PublicUserProfile } from '../../types/instagram/user';

export function useMediaLikers(accountId: string, mediaId: string | null) {
  const cached = useMediaStore((s) =>
    mediaId ? (s.likersByMediaId[mediaId] ?? null) : null,
  );
  const setLikers = useMediaStore((s) => s.setLikers);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accountId || !mediaId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await mediaApi.listMediaLikers(accountId, mediaId);
      setLikers(mediaId, result.users);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [accountId, mediaId, setLikers]);

  return {
    likers: cached as PublicUserProfile[] | null,
    loading,
    error,
    load,
  };
}
