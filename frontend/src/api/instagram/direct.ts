import { api } from '../client';
import type {
  DirectThreadSummary,
  DirectThreadDetail,
  DirectMessageSummary,
  DirectActionReceipt,
  DirectInboxResult,
  DirectMessagesResult,
} from '../../types/instagram/direct';

export const directApi = {
  listInbox: (accountId: string, amount = 20) =>
    api
      .get<DirectInboxResult>(`/instagram/direct/${accountId}/inbox`, { params: { amount } })
      .then((r) => r.data),

  listPending: (accountId: string, amount = 20) =>
    api
      .get<DirectInboxResult>(`/instagram/direct/${accountId}/pending`, { params: { amount } })
      .then((r) => r.data),

  getThread: (accountId: string, threadId: string, amount = 20) =>
    api
      .get<DirectThreadDetail>(`/instagram/direct/${accountId}/thread/${threadId}`, {
        params: { amount },
      })
      .then((r) => r.data),

  listMessages: (accountId: string, threadId: string, amount = 20) =>
    api
      .get<DirectMessagesResult>(
        `/instagram/direct/${accountId}/thread/${threadId}/messages`,
        { params: { amount } },
      )
      .then((r) => r.data),

  searchThreads: (accountId: string, query: string) =>
    api
      .get<DirectInboxResult>(`/instagram/direct/${accountId}/search`, { params: { query } })
      .then((r) => r.data),

  findOrCreate: (accountId: string, participantUserIds: number[], dryRun = false) =>
    api
      .post<DirectThreadSummary>('/instagram/direct/find-or-create', {
        account_id: accountId,
        participant_user_ids: participantUserIds,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  sendToThread: (accountId: string, threadId: string, text: string, dryRun = false) =>
    api
      .post<DirectMessageSummary>('/instagram/direct/send-thread', {
        account_id: accountId,
        direct_thread_id: threadId,
        text,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  sendToUsers: (accountId: string, userIds: number[], text: string, dryRun = false) =>
    api
      .post<DirectMessageSummary>('/instagram/direct/send-users', {
        account_id: accountId,
        user_ids: userIds,
        text,
        dry_run: dryRun,
      })
      .then((r) => r.data),

  deleteMessage: (accountId: string, threadId: string, messageId: string, dryRun = false) =>
    api
      .post<DirectActionReceipt>('/instagram/direct/delete-message', {
        account_id: accountId,
        direct_thread_id: threadId,
        direct_message_id: messageId,
        dry_run: dryRun,
      })
      .then((r) => r.data),
};
