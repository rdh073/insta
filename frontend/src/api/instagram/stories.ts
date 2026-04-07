import { api } from '../client';
import type { StoryDetail, StoryActionReceipt, UserStoriesResult } from '../../types/instagram/story';

export const storiesApi = {
  getPkFromUrl: (url: string) =>
    api
      .get<{ storyPk: number }>('/instagram/story/pk-from-url', { params: { url } })
      .then((r) => r.data),

  getStory: (accountId: string, storyPk: number) =>
    api.get<StoryDetail>(`/instagram/story/${accountId}/${storyPk}`).then((r) => r.data),

  listUserStories: (accountId: string, userId: number, amount?: number) =>
    api
      .get<UserStoriesResult>(`/instagram/story/${accountId}/user/${userId}`, {
        params: amount != null ? { amount } : undefined,
      })
      .then((r) => r.data),

  publishStory: (body: {
    account_id: string;
    media_kind: 'photo' | 'video';
    media_path: string;
    caption?: string;
    thumbnail_path?: string;
    audience?: 'default' | 'close_friends';
    dry_run?: boolean;
  }) => api.post<StoryDetail>('/instagram/story/publish', body).then((r) => r.data),

  deleteStory: (accountId: string, storyPk: number, dryRun = false) =>
    api
      .post<StoryActionReceipt>('/instagram/story/delete', {
        account_id: accountId,
        story_pk: storyPk,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  markSeen: (accountId: string, storyPks: number[], skippedPks: number[] = []) =>
    api
      .post<StoryActionReceipt>('/instagram/story/mark-seen', {
        account_id: accountId,
        story_pks: storyPks,
        skipped_story_pks: skippedPks,
      })
      .then((r) => r.data),
};
