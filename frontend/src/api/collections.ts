import { api } from './client';
import type { MediaSummary } from '../types/instagram/media';

export interface LikedMediasResult {
  count: number;
  posts: MediaSummary[];
}

export const collectionsApi = {
  listLikedMedias: (accountId: string, amount = 21, lastMediaPk = 0) =>
    api
      .get<LikedMediasResult>(`/instagram/collection/${accountId}/liked`, {
        params: { amount, last_media_pk: lastMediaPk },
      })
      .then((r) => r.data),
};
