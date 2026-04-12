import { api } from './client';
import type { Account, PostJob } from '../types';

const CONTRACT_ERROR_PREFIX = 'Dashboard API contract mismatch';

const POST_JOB_STATUSES = new Set<PostJob['status']>([
  'pending',
  'needs_media',
  'scheduled',
  'running',
  'paused',
  'completed',
  'partial',
  'failed',
  'stopped',
]);

export class DashboardContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DashboardContractError';
  }
}

interface DashboardAccounts {
  total: number;
  active: number;
  error: number;
  idle: number;
}

interface DashboardRecentJobTarget {
  accountId: string;
  scheduledAt?: string;
}

interface DashboardRecentJob {
  id: string;
  caption: string;
  status: PostJob['status'];
  targets: DashboardRecentJobTarget[];
}

interface DashboardTopAccount {
  id: string;
  username: string;
  followers: number;
  status: string;
}

interface DashboardJobsToday {
  total: number;
  completed: number;
  partial: number;
  failed: number;
}

type DashboardErrorAccount = Pick<Account, 'id' | 'username' | 'proxy'>;

export interface DashboardData {
  contract_version: 1;
  accounts: DashboardAccounts;
  error_accounts: DashboardErrorAccount[];
  jobs_today: DashboardJobsToday;
  recent_jobs: DashboardRecentJob[];
  top_accounts: DashboardTopAccount[];
}

function failContract(message: string): never {
  throw new DashboardContractError(`${CONTRACT_ERROR_PREFIX}: ${message}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function parseNumberField(parentName: string, key: string, value: unknown): number {
  const parsed = asNumber(value);
  if (parsed == null) {
    return failContract(`${parentName}.${key} must be a number`);
  }
  return parsed;
}

function parseStringField(parentName: string, key: string, value: unknown): string {
  const parsed = asString(value);
  if (parsed == null) {
    return failContract(`${parentName}.${key} must be a string`);
  }
  return parsed;
}

function parseNonEmptyStringField(parentName: string, key: string, value: unknown): string {
  const parsed = parseStringField(parentName, key, value);
  if (!parsed) {
    return failContract(`${parentName}.${key} must be a non-empty string`);
  }
  return parsed;
}

function parseAccounts(raw: unknown): DashboardAccounts {
  if (!isRecord(raw)) {
    return failContract('accounts must be an object');
  }
  return {
    total: parseNumberField('accounts', 'total', raw.total),
    active: parseNumberField('accounts', 'active', raw.active),
    error: parseNumberField('accounts', 'error', raw.error),
    idle: parseNumberField('accounts', 'idle', raw.idle),
  };
}

function parseErrorAccount(raw: unknown): DashboardErrorAccount {
  if (!isRecord(raw)) {
    return failContract('error_accounts[] contains a non-object value');
  }
  const id = parseNonEmptyStringField('error_accounts[]', 'id', raw.id);
  const username = parseNonEmptyStringField('error_accounts[]', 'username', raw.username);
  const proxy = raw.proxy;
  if (proxy != null && typeof proxy !== 'string') {
    return failContract('error_accounts[].proxy must be a string or null');
  }
  return {
    id,
    username,
    proxy: proxy ?? undefined,
  };
}

function parseJobsToday(raw: unknown): DashboardJobsToday {
  if (!isRecord(raw)) {
    return failContract('jobs_today must be an object');
  }
  return {
    total: parseNumberField('jobs_today', 'total', raw.total),
    completed: parseNumberField('jobs_today', 'completed', raw.completed),
    partial: parseNumberField('jobs_today', 'partial', raw.partial),
    failed: parseNumberField('jobs_today', 'failed', raw.failed),
  };
}

function parseRecentJobTarget(raw: unknown): DashboardRecentJobTarget {
  if (!isRecord(raw)) {
    return failContract('recent_jobs[].targets[] contains a non-object value');
  }
  const accountId = parseNonEmptyStringField('recent_jobs[].targets[]', 'accountId', raw.accountId);
  const scheduledAt = raw.scheduledAt;
  if (scheduledAt != null && typeof scheduledAt !== 'string') {
    return failContract('recent_jobs[].targets[].scheduledAt must be a string or null');
  }
  return {
    accountId,
    scheduledAt: scheduledAt ?? undefined,
  };
}

function parseRecentJobStatus(value: unknown): PostJob['status'] {
  const status = asString(value);
  if (!status || !POST_JOB_STATUSES.has(status as PostJob['status'])) {
    return failContract('recent_jobs[].status must be a known post job status');
  }
  return status as PostJob['status'];
}

function parseRecentJob(raw: unknown): DashboardRecentJob {
  if (!isRecord(raw)) {
    return failContract('recent_jobs[] contains a non-object value');
  }
  if (!Array.isArray(raw.targets)) {
    return failContract('recent_jobs[].targets must be an array');
  }
  return {
    id: parseNonEmptyStringField('recent_jobs[]', 'id', raw.id),
    caption: parseStringField('recent_jobs[]', 'caption', raw.caption),
    status: parseRecentJobStatus(raw.status),
    targets: raw.targets.map(parseRecentJobTarget),
  };
}

function parseTopAccount(raw: unknown): DashboardTopAccount {
  if (!isRecord(raw)) {
    return failContract('top_accounts[] contains a non-object value');
  }
  return {
    id: parseNonEmptyStringField('top_accounts[]', 'id', raw.id),
    username: parseNonEmptyStringField('top_accounts[]', 'username', raw.username),
    followers: parseNumberField('top_accounts[]', 'followers', raw.followers),
    status: parseNonEmptyStringField('top_accounts[]', 'status', raw.status),
  };
}

function pickErrorAccounts(payload: Record<string, unknown>, accounts: Record<string, unknown>): unknown {
  return payload.error_accounts ?? accounts.errorAccounts;
}

function pickJobsToday(payload: Record<string, unknown>): unknown {
  return payload.jobs_today ?? payload.jobsToday;
}

function pickRecentJobs(payload: Record<string, unknown>): unknown {
  return payload.recent_jobs ?? payload.recentJobs;
}

function pickTopAccounts(payload: Record<string, unknown>): unknown {
  return payload.top_accounts ?? payload.topAccounts;
}

export function parseDashboardResult(payload: unknown): DashboardData {
  if (!isRecord(payload)) {
    return failContract('response must be an object');
  }

  const accountsRaw = payload.accounts;
  if (!isRecord(accountsRaw)) {
    return failContract('accounts must be an object');
  }

  const errorAccountsRaw = pickErrorAccounts(payload, accountsRaw);
  const jobsTodayRaw = pickJobsToday(payload);
  const recentJobsRaw = pickRecentJobs(payload);
  const topAccountsRaw = pickTopAccounts(payload);

  if (!Array.isArray(errorAccountsRaw)) {
    return failContract('error_accounts must be an array');
  }
  if (!Array.isArray(recentJobsRaw)) {
    return failContract('recent_jobs must be an array');
  }
  if (!Array.isArray(topAccountsRaw)) {
    return failContract('top_accounts must be an array');
  }

  return {
    contract_version: 1,
    accounts: parseAccounts(accountsRaw),
    error_accounts: errorAccountsRaw.map(parseErrorAccount),
    jobs_today: parseJobsToday(jobsTodayRaw),
    recent_jobs: recentJobsRaw.map(parseRecentJob),
    top_accounts: topAccountsRaw.map(parseTopAccount),
  };
}

export const dashboardApi = {
  get: () => api.get<unknown>('/dashboard').then((r) => parseDashboardResult(r.data)),
  relogin: (id: string) => api.post<Account>(`/accounts/${id}/relogin`).then((r) => r.data),
};
