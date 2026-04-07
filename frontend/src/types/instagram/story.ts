export interface StorySummary {
  pk: number;
  storyId: string;
  mediaType: number | null;
  takenAt: string | null;
  thumbnailUrl: string | null;
  videoUrl: string | null;
  viewerCount: number | null;
  ownerUsername: string | null;
}

export interface StoryDetail {
  summary: StorySummary;
  linkCount: number;
  mentionCount: number;
  hashtagCount: number;
  locationCount: number;
  stickerCount: number;
}

export interface StoryActionReceipt {
  actionId: string;
  success: boolean;
  reason: string;
}

export interface UserStoriesResult {
  count: number;
  items: StorySummary[];
}
