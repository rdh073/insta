export interface StreamRunErrorEvent {
  type: 'run_error';
  code: string;
  message: string;
  run_id?: string;
  thread_id?: string;
}

const DEFAULT_CODE = 'stream_error';
const DEFAULT_MESSAGE = 'Stream interrupted by an internal transport error.';

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asOptionalString(value: unknown): string | undefined {
  if (typeof value !== 'string' || value.trim() === '') {
    return undefined;
  }
  return value;
}

function parsePayload(rawPayload: unknown): Record<string, unknown> | null {
  if (typeof rawPayload === 'string') {
    try {
      return asRecord(JSON.parse(rawPayload));
    } catch {
      return null;
    }
  }

  return asRecord(rawPayload);
}

export function parseStreamRunError(rawPayload: unknown): StreamRunErrorEvent | null {
  const payload = parsePayload(rawPayload);
  if (!payload) {
    return null;
  }
  if (payload.type !== 'run_error') {
    return null;
  }

  return {
    type: 'run_error',
    code: asOptionalString(payload.code) ?? DEFAULT_CODE,
    message: asOptionalString(payload.message) ?? DEFAULT_MESSAGE,
    run_id: asOptionalString(payload.run_id),
    thread_id: asOptionalString(payload.thread_id),
  };
}

export function toStreamRunError(rawPayload: unknown): StreamRunErrorEvent {
  return (
    parseStreamRunError(rawPayload) ?? {
      type: 'run_error',
      code: DEFAULT_CODE,
      message: DEFAULT_MESSAGE,
    }
  );
}

export function formatStreamRunError(error: StreamRunErrorEvent, streamLabel: string): string {
  const diagnostics = [`code=${error.code}`];
  if (error.run_id) diagnostics.push(`run_id=${error.run_id}`);
  if (error.thread_id) diagnostics.push(`thread_id=${error.thread_id}`);
  return `${streamLabel}: ${error.message} (${diagnostics.join(', ')})`;
}
