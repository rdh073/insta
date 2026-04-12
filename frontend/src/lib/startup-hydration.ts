import { ApiError } from '../api/client';

export type StartupHydrationFailure =
  | 'backend_unavailable'
  | 'unauthorized'
  | 'partial_failure';

interface StartupHydrationResultInput {
  backendReady: boolean;
  failures: unknown[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function getHydrationErrorStatus(error: unknown): number | null {
  if (error instanceof ApiError) {
    return error.status > 0 ? error.status : null;
  }
  if (isRecord(error) && typeof error.status === 'number') {
    return error.status > 0 ? error.status : null;
  }
  return null;
}

export function isUnauthorizedHydrationError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 401 || error.status === 403 || error.family === 'auth';
  }
  const status = getHydrationErrorStatus(error);
  return status === 401 || status === 403;
}

export function classifyStartupHydrationFailure(
  input: StartupHydrationResultInput
): StartupHydrationFailure | null {
  if (!input.backendReady) {
    return 'backend_unavailable';
  }
  if (input.failures.length === 0) {
    return null;
  }
  if (input.failures.some(isUnauthorizedHydrationError)) {
    return 'unauthorized';
  }
  return 'partial_failure';
}

export function shouldResetStartupStores(previousBackendUrl: string | null, nextBackendUrl: string): boolean {
  return previousBackendUrl === null || previousBackendUrl !== nextBackendUrl;
}

export function buildBulkHydrateSessionKey(backendUrl: string): string {
  const scope = backendUrl.trim() || 'default';
  return `insta_bulk_hydrated:${encodeURIComponent(scope)}`;
}
