/**
 * Extract user-friendly error message from API errors
 */
export function getErrorMessage(error: unknown, fallback = 'An error occurred'): string {
  // Axios/HTTP error with response data
  if (error && typeof error === 'object') {
    const err = error as {
      response?: { data?: { detail?: unknown } };
      message?: unknown;
    };

    // Try to get detail from API response
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail) {
      return detail;
    }

    // Try to get message property
    const message = err.message;
    if (typeof message === 'string' && message) {
      return message;
    }
  }

  // Error object with message
  if (error instanceof Error) {
    return error.message || fallback;
  }

  // String error
  if (typeof error === 'string') {
    return error;
  }

  return fallback;
}
