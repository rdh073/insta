import { api } from '../client';
import type {
  DirectParticipantSummary,
  DirectThreadSummary,
  DirectThreadDetail,
  DirectMessageSummary,
  DirectActionReceipt,
  DirectInboxResult,
  DirectMessagesResult,
} from '../../types/instagram/direct';

const CONTRACT_ERROR_PREFIX = 'Direct API contract mismatch';
export const DIRECT_SEARCH_SYNTHETIC_PREFIX = 'search-user:';

export class DirectContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DirectContractError';
  }
}

interface DirectSearchUser {
  userId: number;
  username: string;
  fullName: string | null;
  profilePicUrl: string | null;
  isPrivate: boolean | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function asNullableString(value: unknown): string | null {
  return value == null ? null : asString(value);
}

function asNullableBoolean(value: unknown): boolean | null {
  return value == null ? null : asBoolean(value);
}

function asNullableNumber(value: unknown): number | null {
  return value == null ? null : asNumber(value);
}

function failContract(message: string): never {
  throw new DirectContractError(`${CONTRACT_ERROR_PREFIX}: ${message}`);
}

function parseParticipant(raw: unknown): DirectParticipantSummary {
  if (typeof raw === 'string') {
    return {
      userId: 0,
      username: raw,
      fullName: null,
      profilePicUrl: null,
      isPrivate: null,
    };
  }

  if (!isRecord(raw)) {
    return failContract('participants[] contains a non-object value');
  }

  const username = asString(raw.username);
  if (!username) {
    return failContract('participant.username must be a string');
  }

  return {
    userId: asNumber(raw.userId) ?? 0,
    username,
    fullName: asNullableString(raw.fullName),
    profilePicUrl: asNullableString(raw.profilePicUrl),
    isPrivate: asNullableBoolean(raw.isPrivate),
  };
}

function parseMessage(raw: unknown, fallbackThreadId: string): DirectMessageSummary | null {
  if (raw == null) {
    return null;
  }

  if (typeof raw === 'string') {
    return {
      directMessageId: `legacy-last:${fallbackThreadId}`,
      directThreadId: fallbackThreadId,
      senderUserId: null,
      sentAt: null,
      itemType: 'text',
      text: raw,
      isShhMode: null,
    };
  }

  if (!isRecord(raw)) {
    return failContract('lastMessage must be an object, string, or null');
  }

  return {
    directMessageId: asString(raw.directMessageId) ?? `legacy-last:${fallbackThreadId}`,
    directThreadId: asString(raw.directThreadId) ?? fallbackThreadId,
    senderUserId: asNullableNumber(raw.senderUserId),
    sentAt: asNullableString(raw.sentAt),
    itemType: asNullableString(raw.itemType),
    text: asNullableString(raw.text),
    isShhMode: asNullableBoolean(raw.isShhMode),
  };
}

function parseThread(raw: unknown): DirectThreadSummary {
  if (!isRecord(raw)) {
    return failContract('threads[] contains a non-object value');
  }

  const directThreadId = asString(raw.directThreadId);
  if (!directThreadId) {
    return failContract('thread.directThreadId must be a string');
  }

  const participantsRaw = raw.participants;
  if (!Array.isArray(participantsRaw)) {
    return failContract('thread.participants must be an array');
  }

  return {
    directThreadId,
    pk: asNullableNumber(raw.pk),
    participants: participantsRaw.map(parseParticipant),
    lastMessage: parseMessage(raw.lastMessage, directThreadId),
    isPending: asBoolean(raw.isPending) ?? false,
  };
}

function parseSearchUser(raw: unknown): DirectSearchUser {
  if (!isRecord(raw)) {
    return failContract('users[] contains a non-object value');
  }

  const userId = asNumber(raw.userId);
  const username = asString(raw.username);
  if (userId == null || !username) {
    return failContract('search user must include userId:number and username:string');
  }

  return {
    userId,
    username,
    fullName: asNullableString(raw.fullName),
    profilePicUrl: asNullableString(raw.profilePicUrl),
    isPrivate: asNullableBoolean(raw.isPrivate),
  };
}

function toSyntheticThread(user: DirectSearchUser): DirectThreadSummary {
  return {
    directThreadId: `${DIRECT_SEARCH_SYNTHETIC_PREFIX}${user.userId}`,
    pk: null,
    participants: [
      {
        userId: user.userId,
        username: user.username,
        fullName: user.fullName,
        profilePicUrl: user.profilePicUrl,
        isPrivate: user.isPrivate,
      },
    ],
    lastMessage: null,
    isPending: false,
  };
}

export function parseDirectInboxResult(
  payload: unknown,
  source: 'inbox' | 'pending' | 'search',
): DirectInboxResult {
  if (!isRecord(payload)) {
    return failContract(`${source} response must be an object`);
  }

  const count = asNumber(payload.count);
  const threadsRaw = payload.threads;
  if (Array.isArray(threadsRaw)) {
    const threads = threadsRaw.map(parseThread);
    return {
      count: count ?? threads.length,
      threads,
    };
  }

  if (source === 'search' && Array.isArray(payload.users)) {
    const users = payload.users.map(parseSearchUser);
    const threads = users.map(toSyntheticThread);
    return {
      count: count ?? threads.length,
      threads,
    };
  }

  return failContract(`${source} response must include threads[]`);
}

export function isSyntheticSearchThreadId(threadId: string): boolean {
  return threadId.startsWith(DIRECT_SEARCH_SYNTHETIC_PREFIX);
}

export function getSyntheticSearchUserId(threadId: string): number | null {
  if (!isSyntheticSearchThreadId(threadId)) {
    return null;
  }
  const raw = threadId.slice(DIRECT_SEARCH_SYNTHETIC_PREFIX.length);
  const userId = Number(raw);
  return Number.isFinite(userId) ? userId : null;
}

export const directApi = {
  listInbox: (accountId: string, amount = 20) =>
    api
      .get<unknown>(`/instagram/direct/${accountId}/inbox`, { params: { amount } })
      .then((r) => parseDirectInboxResult(r.data, 'inbox')),

  listPending: (accountId: string, amount = 20) =>
    api
      .get<unknown>(`/instagram/direct/${accountId}/pending`, { params: { amount } })
      .then((r) => parseDirectInboxResult(r.data, 'pending')),

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
      .get<unknown>(`/instagram/direct/${accountId}/search`, { params: { query } })
      .then((r) => parseDirectInboxResult(r.data, 'search')),

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

  approvePending: (accountId: string, threadId: string) =>
    api
      .post<DirectActionReceipt>('/instagram/direct/approve-pending', {
        account_id: accountId,
        direct_thread_id: threadId,
      })
      .then((r) => r.data),

  markSeen: (accountId: string, threadId: string) =>
    api
      .post<DirectActionReceipt>('/instagram/direct/mark-seen', {
        account_id: accountId,
        direct_thread_id: threadId,
      })
      .then((r) => r.data),
};
