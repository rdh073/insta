export interface CommentSummary {
  pk: number;
  text: string;
  author: string;
  likeCount: number | null;
  hasLiked: boolean | null;
  createdAt: string | null;
}

export interface CommentPage {
  count: number;
  nextCursor: string | null;
  comments: CommentSummary[];
}

export interface CommentActionReceipt {
  actionId: string;
  success: boolean;
  reason: string;
}
