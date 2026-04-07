export function resolveApiBaseUrl(rawBackendUrl?: string): string {
  const value = rawBackendUrl?.trim();
  if (!value) return '/api';

  if (value.startsWith('/')) {
    const normalized = value.replace(/\/+$/, '');
    return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
  }

  try {
    const url = new URL(value);
    const normalizedPath = url.pathname.replace(/\/+$/, '');
    url.pathname = normalizedPath.endsWith('/api') ? normalizedPath : `${normalizedPath}/api`;
    url.search = '';
    url.hash = '';
    return url.toString().replace(/\/+$/, '');
  } catch {
    return '/api';
  }
}


export function buildApiUrl(path: string, rawBackendUrl?: string): string {
  const baseUrl = resolveApiBaseUrl(rawBackendUrl).replace(/\/+$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}


export function describeBackend(rawBackendUrl?: string): string {
  const value = rawBackendUrl?.trim();
  if (!value) return 'Same origin';

  try {
    const url = new URL(value);
    return url.host;
  } catch {
    return value;
  }
}
