export interface Account {
  id: string;
  username: string;
  sessionFile?: string;
  proxy?: string;
  status: 'idle' | 'logging_in' | 'active' | 'error' | 'challenge' | '2fa_required';
  error?: string;
  avatar?: string;
  followers?: number;
  following?: number;
  fullName?: string;
  totpEnabled?: boolean;
  // Session health tracking
  lastVerifiedAt?: string;  // ISO timestamp of last successful Instagram interaction
  lastError?: string;
  lastErrorCode?: string;
}

export interface PostTarget {
  accountId: string;
  scheduledAt?: string;
}

export interface PostJob {
  id: string;
  caption: string;
  mediaUrls: string[];
  mediaType: 'photo' | 'reels' | 'video' | 'album' | 'igtv';
  targets: PostTarget[];
  status: 'pending' | 'needs_media' | 'scheduled' | 'running' | 'paused' | 'completed' | 'partial' | 'failed' | 'stopped';
  results: PostResult[];
  createdAt: string;
}

export interface PostResult {
  accountId: string;
  username: string;
  status: 'pending' | 'uploading' | 'success' | 'failed' | 'skipped';
  mediaId?: string;
  error?: string;
}

export interface Proxy {
  id: string;
  url: string;
  type: 'http' | 'https' | 'socks5';
  assignedTo?: string[];
}

export interface AIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export interface CaptionTemplate {
  id: string;
  name: string;
  caption: string;
  tags: string[];
  createdAt: string;
  usageCount: number;
}

export interface ActivityLogEntry {
  ts: string;
  account_id: string;
  username: string;
  event: string;
  detail: string;
  status: string;
}

export interface BulkAccountResult {
  id: string;
  username?: string;
  status: string;
  error?: string;
  proxy?: string;
}

export interface ProxyCheckResult {
  proxy_url: string | null;
  reachable: boolean;
  latency_ms: number | null;
  ip_address: string | null;
  error: string | null;
  protocol: string | null;
  anonymity: string | null;
}

export interface PoolProxy {
  host: string;
  port: number;
  protocol: 'http' | 'https' | 'socks4' | 'socks5';
  anonymity: 'transparent' | 'elite';
  latencyMs: number;
  url: string;
}

export interface ProxyRecheckSummary {
  total: number;
  alive: number;
  removed: number;
}

export interface ProxyImportSummary {
  total: number;
  saved: number;
  skipped_transparent: number;
  skipped_duplicate: number;
  skipped_existing: number;
  failed: number;
  errors: string[];
}
