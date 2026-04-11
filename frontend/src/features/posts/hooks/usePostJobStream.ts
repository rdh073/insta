/**
 * Shared hook that connects to the SSE post job stream.
 *
 * Automatically connects when there are active jobs (or always if forceConnect is true).
 * Reconnects on error with exponential backoff.
 * Updates the Zustand posts store — both PostPage and CampaignPage read from it.
 */

import { useEffect, useRef } from 'react';
import { postsApi } from '../../../api/posts';
import { usePostStore } from '../../../store/posts';

export function usePostJobStream(forceConnect = false) {
  const jobs = usePostStore((s) => s.jobs);
  const setJobs = usePostStore((s) => s.setJobs);
  const cleanupRef = useRef<(() => void) | null>(null);
  const retryRef = useRef(0);
  const mountedRef = useRef(true);

  const hasActiveJobs = jobs.some(
    (j) => j.status === 'pending' || j.status === 'running' || j.status === 'scheduled' || j.status === 'paused',
  );

  const shouldConnect = forceConnect || hasActiveJobs;

  useEffect(() => {
    mountedRef.current = true;

    if (!shouldConnect) {
      cleanupRef.current?.();
      cleanupRef.current = null;
      retryRef.current = 0;
      return;
    }

    function connect() {
      cleanupRef.current?.();
      cleanupRef.current = null;

      postsApi.streamJobs(
        (updatedJobs) => {
          setJobs(updatedJobs);
          retryRef.current = 0;
        },
        (_err) => {
          const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
          retryRef.current += 1;
          setTimeout(() => {
            if (mountedRef.current && cleanupRef.current !== undefined) connect();
          }, delay);
        },
      ).then((cleanup) => {
        if (!mountedRef.current) {
          // Component unmounted while token was being fetched — close immediately
          cleanup();
          return;
        }
        cleanupRef.current = cleanup;
      }).catch(() => {
        // Token fetch failed — retry with backoff
        const delay = Math.min(1000 * 2 ** retryRef.current, 15000);
        retryRef.current += 1;
        setTimeout(() => {
          if (mountedRef.current) connect();
        }, delay);
      });
    }

    connect();

    return () => {
      mountedRef.current = false;
      cleanupRef.current?.();
      cleanupRef.current = null;
    };
  }, [shouldConnect, setJobs]);
}