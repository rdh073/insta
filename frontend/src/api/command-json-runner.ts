import { buildApiUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import type { CopilotEvent } from './operator-copilot';
import { NetworkError, ServerError, StreamAbortedError } from './operator-copilot';

interface SmartEngagementRecommendation {
  target?: string;
  action_type?: string;
  draft_content?: string;
  reasoning?: string;
}

interface SmartEngagementRisk {
  level?: string;
  reasoning?: string;
}

interface SmartEngagementDecision {
  decision?: string;
}

interface SmartEngagementResponse {
  mode?: string;
  status?: string;
  thread_id?: string;
  interrupted?: boolean;
  interrupt_payload?: Record<string, unknown>;
  outcome_reason?: string;
  recommendation?: SmartEngagementRecommendation;
  risk?: SmartEngagementRisk;
  decision?: SmartEngagementDecision;
  execution?: Record<string, unknown>;
}

function isAbortError(err: unknown): boolean {
  return (
    err instanceof Error &&
    (err.name === 'AbortError' || err.name === 'StreamAbortedError' || err.message === 'The user aborted a request.')
  );
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

function isJsonContentType(contentType: string | null): boolean {
  if (!contentType) return false;
  const normalized = contentType.toLowerCase();
  return normalized.includes('application/json') || normalized.includes('+json');
}

function summarizeSmartEngagement(response: SmartEngagementResponse, resumed: boolean): string {
  const parts: string[] = [];
  const phase = resumed ? 'resume' : 'run';
  const status = response.status || 'unknown';

  if (response.interrupted) {
    parts.push(`Smart engagement ${phase} paused for approval (${status}).`);
  } else {
    parts.push(`Smart engagement ${phase} completed (${status}).`);
  }

  const actionType = response.recommendation?.action_type;
  const target = response.recommendation?.target;
  if (actionType && target) {
    parts.push(`Recommendation: ${actionType} -> ${target}.`);
  } else if (target) {
    parts.push(`Recommendation target: ${target}.`);
  }

  if (response.risk?.level) {
    parts.push(`Risk: ${response.risk.level}.`);
  }

  if (response.decision?.decision) {
    parts.push(`Decision: ${response.decision.decision}.`);
  }

  if (response.execution) {
    parts.push('Execution result is available.');
  }

  if (response.outcome_reason) {
    parts.push(response.outcome_reason);
  }

  return parts.join(' ');
}

function getThreadId(response: SmartEngagementResponse, fallbackThreadId: unknown): string {
  if (typeof response.thread_id === 'string' && response.thread_id.trim()) {
    return response.thread_id;
  }
  if (typeof fallbackThreadId === 'string' && fallbackThreadId.trim()) {
    return fallbackThreadId;
  }
  return `json-${Date.now()}`;
}

function mapSmartEngagementEvents(
  response: SmartEngagementResponse,
  fallbackThreadId: unknown,
  resumed: boolean,
): CopilotEvent[] {
  const threadId = getThreadId(response, fallbackThreadId);
  const events: CopilotEvent[] = [
    { type: 'run_start', thread_id: threadId, resumed },
  ];

  if (response.interrupted) {
    events.push({
      type: 'final_response',
      text: summarizeSmartEngagement(response, resumed),
      payload: response,
    });
    events.push({
      type: 'approval_required',
      thread_id: threadId,
      payload: {
        ...(response.interrupt_payload ?? {}),
        thread_id: threadId,
        command: 'engage',
        status: response.status,
        recommendation: response.recommendation ?? null,
        risk: response.risk ?? null,
      },
    });
    return events;
  }

  if (response.status === 'error') {
    events.push({
      type: 'run_error',
      message: response.outcome_reason || 'Smart engagement failed.',
      payload: response,
    });
  } else {
    events.push({
      type: 'final_response',
      text: summarizeSmartEngagement(response, resumed),
      payload: response,
    });
  }

  events.push({
    type: 'run_finish',
    thread_id: threadId,
    stop_reason: response.status || (response.status === 'error' ? 'error' : 'done'),
  });
  return events;
}

function mapJsonEvents(
  endpoint: string,
  data: unknown,
  fallbackThreadId: unknown,
  resumed: boolean,
): CopilotEvent[] {
  if (endpoint.startsWith('/ai/smart-engagement/') && data && typeof data === 'object') {
    return mapSmartEngagementEvents(data as SmartEngagementResponse, fallbackThreadId, resumed);
  }

  const threadId =
    typeof fallbackThreadId === 'string' && fallbackThreadId.trim() ? fallbackThreadId : `json-${Date.now()}`;
  return [
    { type: 'run_start', thread_id: threadId, resumed },
    { type: 'final_response', text: JSON.stringify(data, null, 2) },
    { type: 'run_finish', thread_id: threadId, stop_reason: 'done' },
  ];
}

function jsonEventStream(
  endpoint: string,
  body: Record<string, unknown>,
  backendUrl?: string,
  signal?: AbortSignal,
  resumed = false,
): ReadableStream<CopilotEvent> {
  const url = buildApiUrl(endpoint, backendUrl);

  return new ReadableStream<CopilotEvent>({
    async start(controller) {
      if (signal?.aborted) {
        controller.error(new StreamAbortedError());
        return;
      }

      let response: Response;
      try {
        const apiKey = useSettingsStore.getState().backendApiKey?.trim();
        const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'application/json' };
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

      if (!response.ok) {
        const detail = await readErrorMessage(response, `Server returned ${response.status}`);
        controller.error(new ServerError(detail, response.status));
        return;
      }

      const contentType = response.headers.get('content-type');
      if (!isJsonContentType(contentType)) {
        const bodyText = (await response.text().catch(() => '')).trim();
        const contentTypeLabel = contentType || 'unknown';
        const suffix = bodyText ? ` Response body: ${bodyText.slice(0, 240)}` : '';
        controller.error(
          new ServerError(
            `Transport contract mismatch for ${endpoint}: expected application/json but received ${contentTypeLabel}.${suffix}`,
            response.status,
          ),
        );
        return;
      }

      let data: unknown;
      try {
        data = await response.json();
      } catch {
        controller.error(
          new ServerError(
            `Transport contract mismatch for ${endpoint}: backend returned invalid JSON.`,
            response.status,
          ),
        );
        return;
      }

      const fallbackThreadId = body.threadId ?? body.thread_id;
      for (const event of mapJsonEvents(endpoint, data, fallbackThreadId, resumed)) {
        controller.enqueue(event);
      }
      controller.close();
    },
  });
}

export const commandJsonRunner = {
  run(
    endpoint: string,
    body: Record<string, unknown>,
    backendUrl?: string,
    signal?: AbortSignal,
  ): ReadableStream<CopilotEvent> {
    return jsonEventStream(endpoint, body, backendUrl, signal, false);
  },

  resume(
    endpoint: string,
    body: Record<string, unknown>,
    backendUrl?: string,
    signal?: AbortSignal,
  ): ReadableStream<CopilotEvent> {
    return jsonEventStream(endpoint, body, backendUrl, signal, true);
  },
};
