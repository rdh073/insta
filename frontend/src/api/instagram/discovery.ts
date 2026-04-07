import { api } from '../client';
import type { HashtagSummary, LocationSummary } from '../../types/instagram/discovery';
import type { MediaSummary } from '../../types/instagram/media';

export const discoveryApi = {
  searchHashtags: (accountId: string, query: string) =>
    api
      .get<Pick<HashtagSummary, 'id' | 'name' | 'mediaCount'>[]>(
        `/instagram/hashtag/${accountId}/search`,
        { params: { q: query } },
      )
      .then((r) => r.data),

  getHashtag: (accountId: string, name: string) =>
    api
      .get<HashtagSummary>(`/instagram/hashtag/${accountId}`, { params: { name } })
      .then((r) => r.data),

  getHashtagTopPosts: (accountId: string, name: string, amount = 12) =>
    api
      .get<{ hashtag: string; feed: string; count: number; posts: MediaSummary[] }>(
        `/instagram/hashtag/${accountId}/top-posts`,
        { params: { name, amount } },
      )
      .then((r) => r.data),

  getHashtagRecentPosts: (accountId: string, name: string, amount = 12) =>
    api
      .get<{ hashtag: string; feed: string; count: number; posts: MediaSummary[] }>(
        `/instagram/hashtag/${accountId}/recent-posts`,
        { params: { name, amount } },
      )
      .then((r) => r.data),

  searchLocations: (accountId: string, query: string, lat?: number, lng?: number) =>
    api
      .get<LocationSummary[]>(`/instagram/location/${accountId}/search`, {
        params: { query, lat, lng },
      })
      .then((r) => r.data),

  getLocation: (accountId: string, locationPk: number) =>
    api
      .get<LocationSummary>(`/instagram/location/${accountId}/${locationPk}`)
      .then((r) => r.data),

  getLocationTopPosts: (accountId: string, locationPk: number, amount = 12) =>
    api
      .get<MediaSummary[]>(`/instagram/location/${accountId}/${locationPk}/top-posts`, {
        params: { amount },
      })
      .then((r) => r.data),

  getLocationRecentPosts: (accountId: string, locationPk: number, amount = 12) =>
    api
      .get<MediaSummary[]>(`/instagram/location/${accountId}/${locationPk}/recent-posts`, {
        params: { amount },
      })
      .then((r) => r.data),
};
