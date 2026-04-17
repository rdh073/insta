import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { mediaApi } from '../../api/instagram/media';
import { useMediaStore } from '../../store/media';
import type { MediaSummary } from '../../types/instagram/media';

export function useUserClips(
  accountId: string,
  userId: number | null,
  amount = 24,
) {
  const cached = useMediaStore((s) =>
    userId ? (s.clipsByUserId[String(userId)] ?? null) : null,
  );
  const setClips = useMediaStore((s) => s.setClips);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accountId || !userId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await mediaApi.listUserClips(accountId, userId, amount);
      setClips(userId, result.posts);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [accountId, userId, amount, setClips]);

  return {
    clips: cached as MediaSummary[] | null,
    loading,
    error,
    load,
  };
}
