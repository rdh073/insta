export interface MediaInsightSummary {
  mediaPk: number;
  reachCount: number | null;
  impressionCount: number | null;
  likeCount: number | null;
  commentCount: number | null;
  shareCount: number | null;
  saveCount: number | null;
  videoViewCount: number | null;
  extraMetrics: Record<string, unknown>;
}

export interface MediaInsightListResult {
  count: number;
  items: MediaInsightSummary[];
}

export interface AccountInsightSummary {
  followersCount: number | null;
  followingCount: number | null;
  mediaCount: number | null;
  impressionsLast7Days: number | null;
  reachLast7Days: number | null;
  profileViewsLast7Days: number | null;
  websiteClicksLast7Days: number | null;
  followerChangeLast7Days: number | null;
  extraMetrics: Record<string, unknown>;
}
