import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import type { CopilotEvent } from './operator-copilot';
import { NetworkError, ServerError, StreamAbortedError, TransportContractError } from './operator-copilot';

function isAbortError(err: unknown): boolean {
  return (
    err instanceof Error &&
    (err.name === 'AbortError' || err.name === 'StreamAbortedError' || err.message === 'The user aborted a request.')
  );
}

function isSseContentType(contentType: string | null): boolean {
  if (!contentType) return false;
  return contentType.toLowerCase().includes('text/event-stream');
}

function buildSseContentTypeMismatchMessage(
  endpoint: string,
  contentType: string | null,
  detail: string,
): string {
  const contentTypeLabel = contentType?.trim() || 'unknown';
  const suffix = detail.trim() ? ` Backend detail: ${detail.trim().slice(0, 240)}` : '';
  return `Transport contract mismatch for ${endpoint}: expected text/event-stream but received ${contentTypeLabel}.${suffix}`;
}

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

function sseStream(
  url: string,
  body: unknown,
  endpoint: string,
  signal?: AbortSignal,
): ReadableStream<CopilotEvent> {
  return new ReadableStream<CopilotEvent>({
    async start(controller) {
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
        const message = response.body
          ? await readErrorMessage(response, `Server returned ${response.status}`)
          : `Server returned ${response.status} with no response body`;
        controller.error(new ServerError(message, response.status));
        return;
      }

      const contentType = response.headers.get('content-type');
      if (!isSseContentType(contentType)) {
        const detail = await readErrorMessage(response, '');
        controller.error(
          new TransportContractError(
            buildSseContentTypeMismatchMessage(endpoint, contentType, detail),
            response.status,
          ),
        );
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let sawEvent = false;

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
              const event = JSON.parse(raw) as CopilotEvent;
              sawEvent = true;
              controller.enqueue(event);
            } catch {
              // skip malformed lines
            }
          }
        }
      } catch (err) {
        if (isAbortError(err)) {
          controller.error(new StreamAbortedError());
        } else {
          controller.error(err);
        }
        return;
      } finally {
        signal?.removeEventListener('abort', onAbort);
      }

      if (!sawEvent) {
        controller.error(
          new TransportContractError(
            `Transport contract mismatch for ${endpoint}: Stream ended without any SSE data events.`,
            response.status,
          ),
        );
        return;
      }
      controller.close();
    },
  });
}

export const graphRunner = {
  run(
    endpoint: string,
    body: Record<string, unknown>,
    backendUrl?: string,
    signal?: AbortSignal,
  ): ReadableStream<CopilotEvent> {
    const url = buildApiUrl(endpoint, backendUrl);
    return sseStream(url, body, endpoint, signal);
  },

  resume(
    endpoint: string,
    body: Record<string, unknown>,
    backendUrl?: string,
    signal?: AbortSignal,
  ): ReadableStream<CopilotEvent> {
    const url = buildApiUrl(endpoint, backendUrl);
    return sseStream(url, body, endpoint, signal);
  },
};
