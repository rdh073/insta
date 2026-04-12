import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/client';
import {
  buildBulkHydrateSessionKey,
  classifyStartupHydrationFailure,
  getHydrationErrorStatus,
  isUnauthorizedHydrationError,
  shouldResetStartupStores,
} from './startup-hydration';

describe('startup hydration helpers', () => {
  it('classifies backend unavailability separately from API failures', () => {
    expect(classifyStartupHydrationFailure({ backendReady: false, failures: [] })).toBe('backend_unavailable');
  });

  it('classifies auth failures as unauthorized', () => {
    const err = new ApiError('Invalid or missing API key', 401, 'backend_api_key_invalid', 'auth');
    expect(isUnauthorizedHydrationError(err)).toBe(true);
    expect(classifyStartupHydrationFailure({ backendReady: true, failures: [err] })).toBe('unauthorized');
  });

  it('classifies non-auth failures as partial', () => {
    const err = new ApiError('timeout', 504);
    expect(isUnauthorizedHydrationError(err)).toBe(false);
    expect(classifyStartupHydrationFailure({ backendReady: true, failures: [err] })).toBe('partial_failure');
  });

  it('extracts known status codes for telemetry', () => {
    const err = new ApiError('boom', 429);
    expect(getHydrationErrorStatus(err)).toBe(429);
    expect(getHydrationErrorStatus(new Error('x'))).toBeNull();
  });

  it('only resets startup stores on first load or backend URL switch', () => {
    expect(shouldResetStartupStores(null, 'http://localhost:8000')).toBe(true);
    expect(shouldResetStartupStores('http://localhost:8000', 'http://localhost:8000')).toBe(false);
    expect(shouldResetStartupStores('http://localhost:8000', 'http://10.0.0.2:8000')).toBe(true);
  });

  it('scopes bulk hydrate guard by backend URL', () => {
    expect(buildBulkHydrateSessionKey('')).toBe('insta_bulk_hydrated:default');
    expect(buildBulkHydrateSessionKey('http://localhost:8000')).toBe(
      'insta_bulk_hydrated:http%3A%2F%2Flocalhost%3A8000'
    );
  });
});
