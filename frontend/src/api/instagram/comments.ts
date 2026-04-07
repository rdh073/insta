import { api } from '../client';
import type { CommentSummary, CommentPage, CommentActionReceipt } from '../../types/instagram/comment';

interface ListCommentsResult {
  count: number;
  comments: CommentSummary[];
}

export const commentsApi = {
  listComments: (accountId: string, mediaId: string, amount = 0) =>
    api
      .get<ListCommentsResult>(`/instagram/comment/${accountId}/${mediaId}`, {
        params: { amount },
      })
      .then((r) => r.data),

  listCommentsPage: (
    accountId: string,
    mediaId: string,
    pageSize = 20,
    cursor?: string,
  ) =>
    api
      .get<CommentPage>(`/instagram/comment/${accountId}/${mediaId}/page`, {
        params: { page_size: pageSize, cursor },
      })
      .then((r) => r.data),

  createComment: (
    accountId: string,
    mediaId: string,
    text: string,
    replyToCommentId?: number,
    dryRun = false,
  ) =>
    api
      .post<CommentSummary>('/instagram/comment', {
        account_id: accountId,
        media_id: mediaId,
        text,
        reply_to_comment_id: replyToCommentId,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  deleteComment: (accountId: string, mediaId: string, commentId: number, dryRun = false) =>
    api
      .post<CommentActionReceipt>('/instagram/comment/delete', {
        account_id: accountId,
        media_id: mediaId,
        comment_id: commentId,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  likeComment: (accountId: string, commentId: number) =>
    api
      .post<CommentActionReceipt>('/instagram/comment/like', {
        account_id: accountId,
        comment_id: commentId,
      })
      .then((r) => r.data),

  unlikeComment: (accountId: string, commentId: number) =>
    api
      .post<CommentActionReceipt>('/instagram/comment/unlike', {
        account_id: accountId,
        comment_id: commentId,
      })
      .then((r) => r.data),

  pinComment: (accountId: string, mediaId: string, commentId: number) =>
    api
      .post<CommentActionReceipt>('/instagram/comment/pin', {
        account_id: accountId,
        media_id: mediaId,
        comment_id: commentId,
      })
      .then((r) => r.data),

  unpinComment: (accountId: string, mediaId: string, commentId: number) =>
    api
      .post<CommentActionReceipt>('/instagram/comment/unpin', {
        account_id: accountId,
        media_id: mediaId,
        comment_id: commentId,
      })
      .then((r) => r.data),
};
