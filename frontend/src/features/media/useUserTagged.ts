import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { mediaApi } from '../../api/instagram/media';
import { useMediaStore } from '../../store/media';
import type { MediaSummary } from '../../types/instagram/media';

export function useUserTagged(
  accountId: string,
  userId: number | null,
  amount = 24,
) {
  const cached = useMediaStore((s) =>
    userId ? (s.taggedByUserId[String(userId)] ?? null) : null,
  );
  const setTagged = useMediaStore((s) => s.setTagged);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accountId || !userId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await mediaApi.listUserTaggedMedia(accountId, userId, amount);
      setTagged(userId, result.posts);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [accountId, userId, amount, setTagged]);

  return {
    tagged: cached as MediaSummary[] | null,
    loading,
    error,
    load,
  };
}
