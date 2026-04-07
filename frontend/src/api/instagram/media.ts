import { api } from '../client';
import type { MediaSummary, MediaOembedSummary, UserMediasResult } from '../../types/instagram/media';

export const mediaApi = {
  getByPk: (accountId: string, mediaPk: number) =>
    api.get<MediaSummary>(`/instagram/media/${accountId}/pk/${mediaPk}`).then((r) => r.data),

  getByCode: (accountId: string, code: string) =>
    api.get<MediaSummary>(`/instagram/media/${accountId}/code/${code}`).then((r) => r.data),

  getUserMedias: (accountId: string, userId: number, amount = 12) =>
    api
      .get<UserMediasResult>(`/instagram/media/${accountId}/user/${userId}`, { params: { amount } })
      .then((r) => r.data),

  getOembed: (accountId: string, url: string) =>
    api
      .get<MediaOembedSummary>(`/instagram/media/${accountId}/oembed`, { params: { url } })
      .then((r) => r.data),
};
