import type { DirectParticipantSummary } from './user';

export type { DirectParticipantSummary };

export interface DirectMessageSummary {
  directMessageId: string;
  directThreadId: string | null;
  senderUserId: number | null;
  sentAt: string | null;
  itemType: string | null;
  text: string | null;
  isShhMode: boolean | null;
}

export interface DirectThreadSummary {
  directThreadId: string;
  pk: number | null;
  participants: DirectParticipantSummary[];
  lastMessage: DirectMessageSummary | null;
  isPending: boolean;
}

export interface DirectThreadDetail {
  summary: DirectThreadSummary;
  messages: DirectMessageSummary[];
}

export interface DirectActionReceipt {
  actionId: string;
  success: boolean;
  reason: string;
}

export interface DirectInboxResult {
  count: number;
  threads: DirectThreadSummary[];
}

export interface DirectMessagesResult {
  count: number;
  messages: DirectMessageSummary[];
}
