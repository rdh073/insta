import { api } from '../client';
import type {
  MediaActionReceipt,
  MediaOembedSummary,
  MediaSummary,
  UserMediasResult,
} from '../../types/instagram/media';

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

  editCaption: (accountId: string, mediaId: string, caption: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/edit', {
        account_id: accountId,
        media_id: mediaId,
        caption,
      })
      .then((r) => r.data),

  delete: (accountId: string, mediaId: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/delete', {
        account_id: accountId,
        media_id: mediaId,
      })
      .then((r) => r.data),

  pin: (accountId: string, mediaId: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/pin', {
        account_id: accountId,
        media_id: mediaId,
      })
      .then((r) => r.data),

  unpin: (accountId: string, mediaId: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/unpin', {
        account_id: accountId,
        media_id: mediaId,
      })
      .then((r) => r.data),

  archive: (accountId: string, mediaId: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/archive', {
        account_id: accountId,
        media_id: mediaId,
      })
      .then((r) => r.data),

  unarchive: (accountId: string, mediaId: string) =>
    api
      .post<MediaActionReceipt>('/instagram/media/unarchive', {
        account_id: accountId,
        media_id: mediaId,
      })
      .then((r) => r.data),

  save: (accountId: string, mediaId: string, collectionPk?: number | null) =>
    api
      .post<MediaActionReceipt>('/instagram/media/save', {
        account_id: accountId,
        media_id: mediaId,
        collection_pk: collectionPk ?? null,
      })
      .then((r) => r.data),

  unsave: (accountId: string, mediaId: string, collectionPk?: number | null) =>
    api
      .post<MediaActionReceipt>('/instagram/media/unsave', {
        account_id: accountId,
        media_id: mediaId,
        collection_pk: collectionPk ?? null,
      })
      .then((r) => r.data),
};
