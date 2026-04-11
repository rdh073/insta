import type { Account } from '../../../types';

/** Returns the partial username after the last `@` before the cursor, or null. */
export function atMentionAtCursor(text: string, cursor: number): string | null {
  const before = text.slice(0, cursor);
  const match = before.match(/@(\w*)$/);
  return match ? match[1] : null;
}

/** Replace the `@partial` at cursor with `@username ` */
export function replaceAtMention(
  text: string,
  cursor: number,
  username: string,
): { text: string; cursor: number } {
  const before = text.slice(0, cursor);
  const after = text.slice(cursor);
  const replaced = before.replace(/@\w*$/, `@${username} `);
  return { text: replaced + after, cursor: replaced.length };
}

export const STATUS_DOT: Record<Account['status'], string> = {
  active: 'bg-[#9ece6a]',
  idle: 'bg-[#4a5578]',
  logging_in: 'bg-[#e0af68]',
  error: 'bg-[#f7768e]',
  challenge: 'bg-[#ff9db0]',
  '2fa_required': 'bg-[#e0af68]',
};

export interface AttachedFile {
  name: string;
  content: string;
  lines: number;
  sizeKb: number;
}

export const MAX_FILE_KB = 512;
export const ACCEPTED_FILE_TYPES = '.txt,.csv,.json,.jsonl';

export const QUICK_SUGGESTIONS = [
  'List all active accounts and their status',
  'Show recent engagement activity for the last 7 days',
  'Recommend hashtags for a travel photography post',
  'Check proxy health and report any issues',
];
