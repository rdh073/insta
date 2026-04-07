import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import type { CopilotEvent } from './operator-copilot';
import { StreamAbortedError } from './operator-copilot';

function isAbortError(err: unknown): boolean {
  return (
    err instanceof Error &&
    (err.name === 'AbortError' || err.name === 'StreamAbortedError' || err.message === 'The user aborted a request.')
  );
}

function sseStream(url: string, body: unknown, signal?: AbortSignal): ReadableStream<CopilotEvent> {
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
          controller.error(err);
        }
        return;
      }

      if (!response.ok || !response.body) {
        const message = response.body
          ? (await response.text().catch(() => `HTTP ${response.status}`)) ||
            `HTTP ${response.status}`
          : `HTTP ${response.status}: Streaming response body unavailable`;
        controller.error(new Error(message));
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

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
    return sseStream(url, body, signal);
  },

  resume(
    endpoint: string,
    body: Record<string, unknown>,
    backendUrl?: string,
    signal?: AbortSignal,
  ): ReadableStream<CopilotEvent> {
    const url = buildApiUrl(endpoint, backendUrl);
    return sseStream(url, body, signal);
  },
};
