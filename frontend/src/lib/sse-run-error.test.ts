import { describe, expect, it } from 'vitest';
import {
  formatStreamRunError,
  parseStreamRunError,
  toStreamRunError,
} from './sse-run-error';

describe('sse run_error helpers', () => {
  it('parses structured run_error payloads', () => {
    const parsed = parseStreamRunError(
      JSON.stringify({
        type: 'run_error',
        code: 'stream_error',
        message: 'Transport failed',
        run_id: 'run-1',
        thread_id: 'thread-1',
      }),
    );

    expect(parsed).toEqual({
      type: 'run_error',
      code: 'stream_error',
      message: 'Transport failed',
      run_id: 'run-1',
      thread_id: 'thread-1',
    });
  });

  it('returns null for non-run_error payloads', () => {
    expect(parseStreamRunError({ type: 'account_updated', id: 'acct-1' })).toBeNull();
    expect(parseStreamRunError('not-json')).toBeNull();
  });

  it('formats diagnostics consistently', () => {
    const message = formatStreamRunError(
      {
        type: 'run_error',
        code: 'stream_error',
        message: 'Transport failed',
        run_id: 'run-1',
        thread_id: 'thread-1',
      },
      'Account event stream',
    );

    expect(message).toContain('Account event stream: Transport failed');
    expect(message).toContain('code=stream_error');
    expect(message).toContain('run_id=run-1');
    expect(message).toContain('thread_id=thread-1');
  });

  it('falls back to a sanitized default when payload is malformed', () => {
    expect(toStreamRunError('invalid')).toEqual({
      type: 'run_error',
      code: 'stream_error',
      message: 'Stream interrupted by an internal transport error.',
    });
  });
});
