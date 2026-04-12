import { describe, expect, it } from 'vitest';
import {
  DirectContractError,
  getSyntheticSearchUserId,
  isSyntheticSearchThreadId,
  parseDirectInboxResult,
} from './direct';

describe('directApi contract normalization', () => {
  it('normalizes legacy inbox payloads into DirectThreadSummary shape', () => {
    const payload = {
      count: 1,
      threads: [
        {
          directThreadId: 'thread-1',
          participants: ['alice'],
          isPending: false,
          lastMessage: 'hello from legacy serializer',
        },
      ],
    };

    const result = parseDirectInboxResult(payload, 'inbox');
    expect(result.count).toBe(1);
    expect(result.threads).toHaveLength(1);
    expect(result.threads[0].participants[0]).toMatchObject({
      username: 'alice',
      userId: 0,
    });
    expect(result.threads[0].lastMessage?.text).toBe('hello from legacy serializer');
    expect(result.threads[0].lastMessage?.directThreadId).toBe('thread-1');
  });

  it('maps search users payloads to synthetic thread rows', () => {
    const result = parseDirectInboxResult(
      {
        count: 1,
        users: [
          {
            userId: 77,
            username: 'target_user',
            fullName: 'Target User',
          },
        ],
      },
      'search',
    );

    expect(result.threads).toHaveLength(1);
    expect(result.threads[0].directThreadId).toBe('search-user:77');
    expect(isSyntheticSearchThreadId(result.threads[0].directThreadId)).toBe(true);
    expect(getSyntheticSearchUserId(result.threads[0].directThreadId)).toBe(77);
    expect(result.threads[0].participants[0].username).toBe('target_user');
  });

  it('throws a contract error when required arrays are missing', () => {
    expect(() => parseDirectInboxResult({ count: 0 }, 'pending')).toThrow(DirectContractError);
  });
});
