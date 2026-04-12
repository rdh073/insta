import { useEffect, useRef, useState } from 'react';
import { resolveApiBaseUrl } from '../../../lib/api-base';
import { useSettingsStore } from '../../../store/settings';
import { useAccountStore } from '../../../store/accounts';
import { buildSseUrl } from '../../../api/sse-token';
import type { Account } from '../../../types';

interface AccountUpdatedEvent {
  type: 'account_updated';
  id: string;
  status?: Account['status'];
  lastError?: string | null;
  last_error?: string | null;
  lastErrorCode?: string | null;
  last_error_code?: string | null;
  /** Legacy key emitted by older backend/frontend versions. */
  error?: string;
  full_name?: string;
  profile_pic_url?: string;
  avatar?: string;
  followers?: number;
  following?: number;
}

const MAX_RETRIES = 10;

/**
 * Subscribes to the backend SSE stream at GET /api/accounts/events and
 * patches the Zustand account store whenever an account_updated event
 * arrives (e.g. after background profile hydration completes).
 *
 * Mount this hook once at the accounts page level — it opens a single
 * EventSource for the lifetime of the component.
 *
 * Reconnects with exponential backoff up to {@link MAX_RETRIES} times.
 * After exhausting retries, stops reconnecting and sets `connectionLost`
 * so the caller can display a banner.
 */
export function useAccountEvents(): { connectionLost: boolean } {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
  const patchAccount = useAccountStore((s) => s.patchAccount);
  const esRef = useRef<EventSource | null>(null);
  const mountedRef = useRef(true);
  const retryRef = useRef(0);
  const [connectionLost, setConnectionLost] = useState(false);

  useEffect(() => {
    mountedRef.current = true;
    retryRef.current = 0;
    setConnectionLost(false);
    const apiBase = resolveApiBaseUrl(backendUrl);

    function connect() {
      esRef.current?.close();
      esRef.current = null;

      buildSseUrl('/accounts/events', apiBase).then((url) => {
        if (!mountedRef.current) return;

        const es = new EventSource(url);
        esRef.current = es;

        es.onmessage = (evt) => {
          retryRef.current = 0; // reset backoff on successful message
          setConnectionLost(false);
          try {
            const data = JSON.parse(evt.data) as AccountUpdatedEvent;
            if (data.type === 'account_updated' && data.id) {
              const patch: Record<string, unknown> = {};
              if (data.status !== undefined) patch.status = data.status;
              const normalizedLastError = data.lastError ?? data.last_error ?? data.error;
              if (normalizedLastError !== undefined) {
                patch.lastError = normalizedLastError ?? undefined;
              }
              const normalizedLastErrorCode = data.lastErrorCode ?? data.last_error_code;
              if (normalizedLastErrorCode !== undefined) {
                patch.lastErrorCode = normalizedLastErrorCode ?? undefined;
              }
              if (data.followers !== undefined) patch.followers = data.followers;
              if (data.following !== undefined) patch.following = data.following;
              if (data.full_name !== undefined) patch.fullName = data.full_name;
              // Accept both keys for backward compatibility during deployments
              const avatarUrl = data.avatar ?? data.profile_pic_url;
              if (avatarUrl !== undefined) patch.avatar = avatarUrl;
              patchAccount(data.id, patch);
            }
          } catch {
            // malformed event — ignore silently
          }
        };

        es.onerror = () => {
          es.close();
          scheduleReconnect();
        };
      }).catch(() => {
        scheduleReconnect();
      });
    }

    function scheduleReconnect() {
      if (!mountedRef.current) return;
      if (retryRef.current >= MAX_RETRIES) {
        setConnectionLost(true);
        return;
      }
      const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
      retryRef.current += 1;
      setTimeout(() => {
        if (mountedRef.current) connect();
      }, delay);
    }

    connect();

    return () => {
      mountedRef.current = false;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [backendUrl, backendApiKey, patchAccount]);

  return { connectionLost };
}
