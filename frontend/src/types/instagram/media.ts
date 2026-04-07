export interface ResourceSummary {
  pk: number;
  mediaType: number;
  thumbnailUrl: string | null;
  videoUrl: string | null;
}

// mediaType: 1=photo, 2=video, 8=album
export interface MediaSummary {
  pk: number;
  mediaId: string;
  code: string;
  owner: string | null;
  captionText: string;
  likeCount: number;
  commentCount: number;
  mediaType: number;
  productType: string;
  takenAt: string | null;
  resources: ResourceSummary[];
}

export interface MediaOembedSummary {
  mediaId: string;
  authorName: string | null;
  authorUrl: string | null;
  authorId: number | null;
  title: string | null;
  providerName: string | null;
  html: string | null;
  thumbnailUrl: string | null;
  width: number | null;
  height: number | null;
  canView: boolean | null;
}

export interface UserMediasResult {
  count: number;
  posts: MediaSummary[];
}
