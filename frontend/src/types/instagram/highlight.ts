import type { StorySummary } from './story';

export type { StorySummary };

export interface HighlightCoverSummary {
  mediaId: string | null;
  imageUrl: string | null;
  cropRect: number[];
}

export interface HighlightSummary {
  pk: string;
  highlightId: string;
  title: string | null;
  createdAt: string | null;
  isPinned: boolean | null;
  mediaCount: number | null;
  latestReelMedia: number | null;
  ownerUsername: string | null;
  cover: HighlightCoverSummary | null;
}

export interface HighlightDetail {
  summary: HighlightSummary;
  storyIds: string[];
  items: StorySummary[];
}

export interface HighlightActionReceipt {
  actionId: string;
  success: boolean;
  reason: string;
}

export interface UserHighlightsResult {
  count: number;
  items: HighlightSummary[];
}
