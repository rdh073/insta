import { api } from '../client';
import type {
  AccountInsightSummary,
  MediaInsightListResult,
  MediaInsightSummary,
} from '../../types/instagram/insight';

export type InsightPostType = 'ALL' | 'PHOTO' | 'VIDEO' | 'CAROUSEL';
export type InsightTimeFrame = 'TWO_YEARS' | 'ONE_YEAR' | 'SIX_MONTHS' | 'MONTH' | 'WEEK';
export type InsightOrdering =
  | 'REACH_COUNT'
  | 'IMPRESSIONS'
  | 'ENGAGEMENT'
  | 'LIKE_COUNT'
  | 'COMMENT_COUNT'
  | 'SHARE_COUNT'
  | 'SAVE_COUNT';

export const insightsApi = {
  getAccountInsight: (accountId: string) =>
    api
      .get<AccountInsightSummary>(`/instagram/insight/${accountId}/account`)
      .then((r) => r.data),

  getMediaInsight: (accountId: string, mediaPk: number) =>
    api
      .get<MediaInsightSummary>(`/instagram/insight/${accountId}/media/${mediaPk}`)
      .then((r) => r.data),

  listMediaInsights: (
    accountId: string,
    params?: {
      post_type?: InsightPostType;
      time_frame?: InsightTimeFrame;
      ordering?: InsightOrdering;
      count?: number;
    },
  ) =>
    api
      .get<MediaInsightListResult>(`/instagram/insight/${accountId}/list`, { params })
      .then((r) => r.data),
};
