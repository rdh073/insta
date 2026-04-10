import { useEffect, useRef } from 'react';
import { resolveApiBaseUrl } from '../../../lib/api-base';
import { useSettingsStore } from '../../../store/settings';
import { useAccountStore } from '../../../store/accounts';
import { buildSseUrl } from '../../../api/sse-token';
import type { Account } from '../../../types';

interface AccountUpdatedEvent {
  type: 'account_updated';
  id: string;
  status?: Account['status'];
  error?: string;
  full_name?: string;
  profile_pic_url?: string;
  followers?: number;
  following?: number;
}

/**
 * Subscribes to the backend SSE stream at GET /api/accounts/events and
 * patches the Zustand account store whenever an account_updated event
 * arrives (e.g. after background profile hydration completes).
 *
 * Mount this hook once at the accounts page level — it opens a single
 * EventSource for the lifetime of the component.
 */
export function useAccountEvents(): void {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
  const patchAccount = useAccountStore((s) => s.patchAccount);
  const esRef = useRef<EventSource | null>(null);
  const mountedRef = useRef(true);
  const retryRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    retryRef.current = 0;
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
          try {
            const data = JSON.parse(evt.data) as AccountUpdatedEvent;
            if (data.type === 'account_updated' && data.id) {
              const patch: Record<string, unknown> = {};
              if (data.status !== undefined) patch.status = data.status;
              if (data.error !== undefined) patch.error = data.error;
              if (data.followers !== undefined) patch.followers = data.followers;
              if (data.following !== undefined) patch.following = data.following;
              if (data.full_name !== undefined) patch.fullName = data.full_name;
              if (data.profile_pic_url !== undefined) patch.avatar = data.profile_pic_url;
              patchAccount(data.id, patch);
            }
          } catch {
            // malformed event — ignore
          }
        };

        es.onerror = () => {
          // Close and reconnect with a fresh token (handles both transient
          // network drops and expired tokens after the 5-minute TTL).
          es.close();
          if (!mountedRef.current) return;
          const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
          retryRef.current += 1;
          setTimeout(() => {
            if (mountedRef.current) connect();
          }, delay);
        };
      }).catch(() => {
        if (!mountedRef.current) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
        retryRef.current += 1;
        setTimeout(() => {
          if (mountedRef.current) connect();
        }, delay);
      });
    }

    connect();

    return () => {
      mountedRef.current = false;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [backendUrl, backendApiKey, patchAccount]);
}
