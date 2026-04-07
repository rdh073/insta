import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';

export interface CopilotRunRequest {
  message: string;
  threadId?: string;
  provider?: 'openai' | 'gemini' | 'deepseek' | 'antigravity' | 'openai_codex' | 'claude_code';
  model?: string;
  apiKey?: string;
  providerBaseUrl?: string;
  fileName?: string;
  fileContent?: string;
  signal?: AbortSignal;
}

export interface CopilotResumeRequest {
  threadId: string;
  approvalResult: 'approved' | 'rejected' | 'edited';
  editedCalls?: Record<string, unknown>[];
  signal?: AbortSignal;
}

export interface CopilotEvent {
  type:
    | 'run_start'
    | 'node_update'
    | 'approval_required'
    | 'plan_ready'
    | 'policy_result'
    | 'tool_result'
    | 'final_response'
    | 'run_finish'
    | 'run_error'
    | (string & {});
  [key: string]: unknown;
}

// ── Error types ────────────────────────────────────────────────────────────────

export class NetworkError extends Error {
  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = 'NetworkError';
    this.cause = cause;
  }
}

export class ServerError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
  ) {
    super(message);
    this.name = 'ServerError';
    this.status = status;
    this.code = code;
  }
}

export class StreamAbortedError extends Error {
  constructor() {
    super('Stream was cancelled.');
    this.name = 'StreamAbortedError';
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object') {
      const d = detail as { message?: unknown; code?: unknown };
      if (typeof d.message === 'string' && typeof d.code === 'string') return `${d.code}: ${d.message}`;
      if (typeof d.message === 'string') return d.message;
      if (typeof d.code === 'string') return d.code;
    }
  } catch {
    // fall through
  }
  return (await response.text().catch(() => '')) || fallback;
}

function isAbortError(err: unknown): boolean {
  return (
    err instanceof Error &&
    (err.name === 'AbortError' || err.name === 'StreamAbortedError' || err.message === 'The user aborted a request.')
  );
}

// ── SSE stream ─────────────────────────────────────────────────────────────────

function sseStream(url: string, body: unknown, signal?: AbortSignal): ReadableStream<CopilotEvent> {
  return new ReadableStream<CopilotEvent>({
    async start(controller) {
      // Bail immediately if already aborted before the fetch starts
      if (signal?.aborted) {
        controller.error(new StreamAbortedError());
        return;
      }

      let response: Response;
      try {
        const apiKey = useSettingsStore.getState().backendApiKey?.trim();
        const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream' };
        if (apiKey) headers['X-API-Key'] = apiKey;
        response = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          signal,
        });
      } catch (err) {
        if (isAbortError(err)) {
          controller.error(new StreamAbortedError());
        } else {
          controller.error(
            new NetworkError(
              'Could not reach the backend. Check that the server is running and the backend URL is correct.',
              err,
            ),
          );
        }
        return;
      }

      if (!response.ok || !response.body) {
        const detail = response.body
          ? await readErrorMessage(response, `Server returned ${response.status}`)
          : `Server returned ${response.status} with no response body`;
        controller.error(new ServerError(detail, response.status));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // Abort listener — cancel the reader when signal fires
      const onAbort = () => { void reader.cancel(); };
      signal?.addEventListener('abort', onAbort, { once: true });

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data:')) continue;
            const raw = trimmed.slice(5).trim();
            if (!raw || raw === '[DONE]') continue;
            try {
              controller.enqueue(JSON.parse(raw) as CopilotEvent);
            } catch {
              // skip malformed SSE lines
            }
          }
        }
      } catch (err) {
        if (isAbortError(err) || signal?.aborted) {
          controller.error(new StreamAbortedError());
        } else {
          controller.error(new NetworkError('Stream interrupted unexpectedly.', err));
        }
        return;
      } finally {
        signal?.removeEventListener('abort', onAbort);
      }

      controller.close();
    },
  });
}

// ── Public API ─────────────────────────────────────────────────────────────────

export async function fetchProviderModels(
  provider: string,
  apiKey: string,
  providerBaseUrl: string | undefined,
  backendUrl?: string,
): Promise<string[]> {
  const url = buildApiUrl('/ai/providers/models', backendUrl);
  let res: Response;
  const backendApiKey = useSettingsStore.getState().backendApiKey?.trim();
  const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
  if (backendApiKey) fetchHeaders['X-API-Key'] = backendApiKey;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: fetchHeaders,
      body: JSON.stringify({ provider, apiKey, providerBaseUrl }),
    });
  } catch (err) {
    throw new NetworkError(
      'Could not reach the backend to fetch models. Check the backend URL in Settings.',
      err,
    );
  }
  if (!res.ok) {
    const detail = await readErrorMessage(res, `HTTP ${res.status}`);
    throw new ServerError(detail, res.status);
  }
  const data = (await res.json()) as { models: string[] };
  return data.models;
}

export const operatorCopilotApi = {
  stream(req: CopilotRunRequest, backendUrl?: string): ReadableStream<CopilotEvent> {
    const url = buildApiUrl('/ai/chat/graph', backendUrl);
    const body = {
      message: req.message,
      threadId: req.threadId,
      provider: req.provider,
      model: req.model,
      apiKey: req.apiKey,
      providerBaseUrl: req.providerBaseUrl,
      fileName: req.fileName,
      fileContent: req.fileContent,
    };
    return sseStream(url, body, req.signal);
  },

  resume(req: CopilotResumeRequest, backendUrl?: string): ReadableStream<CopilotEvent> {
    const url = buildApiUrl('/ai/chat/graph/resume', backendUrl);
    const body = {
      threadId: req.threadId,
      approvalResult: req.approvalResult,
      editedCalls: req.editedCalls,
    };
    return sseStream(url, body, req.signal);
  },
};
