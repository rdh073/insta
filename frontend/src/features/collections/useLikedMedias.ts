import { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import { collectionsApi } from '../../api/collections';
import { useCollectionsStore } from '../../store/collections';

export function useLikedMedias(accountId: string, amount = 21) {
  const page = useCollectionsStore((s) =>
    accountId ? s.getLiked(accountId) : { items: [], lastMediaPk: 0, hasMore: true },
  );
  const setLiked = useCollectionsStore((s) => s.setLiked);
  const appendLiked = useCollectionsStore((s) => s.appendLiked);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await collectionsApi.listLikedMedias(accountId, amount, 0);
      const last = result.posts.at(-1);
      setLiked(accountId, {
        items: result.posts,
        lastMediaPk: last?.pk ?? 0,
        hasMore: result.count >= amount,
      });
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [accountId, amount, setLiked]);

  const loadMore = useCallback(async () => {
    if (!accountId || !page.hasMore || page.lastMediaPk <= 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await collectionsApi.listLikedMedias(accountId, amount, page.lastMediaPk);
      const last = result.posts.at(-1);
      appendLiked(accountId, {
        items: result.posts,
        lastMediaPk: last?.pk ?? page.lastMediaPk,
        hasMore: result.count >= amount,
      });
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [accountId, amount, page.hasMore, page.lastMediaPk, appendLiked]);

  return {
    liked: page.items,
    hasMore: page.hasMore,
    loading,
    error,
    load,
    loadMore,
  };
}
