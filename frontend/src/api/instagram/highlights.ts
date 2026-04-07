import { api } from '../client';
import type {
  HighlightDetail,
  HighlightActionReceipt,
  UserHighlightsResult,
} from '../../types/instagram/highlight';

export const highlightsApi = {
  getPkFromUrl: (url: string) =>
    api
      .get<{ highlightPk: number }>('/instagram/highlight/pk-from-url', { params: { url } })
      .then((r) => r.data),

  getHighlight: (accountId: string, highlightPk: number) =>
    api
      .get<HighlightDetail>(`/instagram/highlight/${accountId}/${highlightPk}`)
      .then((r) => r.data),

  listUserHighlights: (accountId: string, userId: number, amount = 0) =>
    api
      .get<UserHighlightsResult>(`/instagram/highlight/${accountId}/user/${userId}`, {
        params: { amount },
      })
      .then((r) => r.data),

  createHighlight: (body: {
    account_id: string;
    title: string;
    story_ids: number[];
    cover_story_id?: number;
    crop_rect?: number[];
    dry_run?: boolean;
  }) => api.post<HighlightDetail>('/instagram/highlight/create', body).then((r) => r.data),

  changeTitle: (accountId: string, highlightPk: number, title: string, dryRun = false) =>
    api
      .post<HighlightDetail>('/instagram/highlight/change-title', {
        account_id: accountId,
        highlight_pk: highlightPk,
        title,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  addStories: (accountId: string, highlightPk: number, storyIds: number[], dryRun = false) =>
    api
      .post<HighlightDetail>('/instagram/highlight/add-stories', {
        account_id: accountId,
        highlight_pk: highlightPk,
        story_ids: storyIds,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  removeStories: (accountId: string, highlightPk: number, storyIds: number[], dryRun = false) =>
    api
      .post<HighlightDetail>('/instagram/highlight/remove-stories', {
        account_id: accountId,
        highlight_pk: highlightPk,
        story_ids: storyIds,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  deleteHighlight: (accountId: string, highlightPk: number, dryRun = false) =>
    api
      .post<HighlightActionReceipt>('/instagram/highlight/delete', {
        account_id: accountId,
        highlight_pk: highlightPk,
        dry_run: dryRun,
      })
      .then((r) => r.data),
};
