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
