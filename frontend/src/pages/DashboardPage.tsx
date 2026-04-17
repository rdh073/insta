import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  Calendar,
  CheckCircle,
  Globe,
  Layers,
  RefreshCw,
  RotateCcw,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { dashboardApi, type DashboardData } from '../api/dashboard';
import { getErrorMessage } from '../lib/error';
import { SingleFlightRequestRunner } from '../lib/single-flight';
import { useAccountStore } from '../store/accounts';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';

function pct(value: number, total: number) {
  if (!total) return 0;
  return Math.round((value / total) * 100);
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.FC<{ className?: string }>;
  label: string;
  value: number | string;
  sub?: string;
  tone: 'blue' | 'green' | 'violet' | 'rose';
}) {
  const toneClasses =
    tone === 'green'
      ? 'text-[var(--color-success-fg)] border-[var(--color-success-border)] bg-[var(--color-success-bg)]'
      : tone === 'violet'
        ? 'text-[var(--color-accent-violet)] border-[var(--color-info-border)] bg-[var(--color-accent-violet-bg-soft)]'
        : tone === 'rose'
          ? 'text-[var(--color-error-fg)] border-[var(--color-error-border)] bg-[var(--color-error-bg)]'
          : 'text-[var(--color-info-fg)] border-[var(--color-info-border)] bg-[var(--color-info-bg)]';

  return (
    <Card glow className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-kicker !text-[0.62rem]">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-[var(--color-text-strong)]">{value}</p>
          {sub && <p className="mt-2 text-sm text-[var(--color-text-muted)]">{sub}</p>}
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-[1.2rem] border ${toneClasses}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Card>
  );
}

function MetricBar({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const percent = pct(value, total);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="text-[var(--color-text-muted)]">{label}</span>
        <span className="font-mono text-[var(--color-text-strong)]">
          {value} <span className="text-[var(--color-text-muted)]">({percent}%)</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[var(--color-surface-overlay)]">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${percent}%`, background: color }} />
      </div>
    </div>
  );
}

function JobsBarChart({ data }: { data: DashboardData['jobs_today'] | null }) {
  const bars = [
    { label: 'Completed', value: data?.completed ?? 0, color: 'var(--color-success-fg)' },
    { label: 'Partial', value: data?.partial ?? 0, color: 'var(--color-warning-fg)' },
    { label: 'Failed', value: data?.failed ?? 0, color: 'var(--color-error-fg)' },
  ];
  const max = Math.max(...bars.map((bar) => bar.value), 1);

  return (
    <div className="flex h-full flex-col justify-between">
      <div className="flex min-h-[13rem] items-end gap-4">
        {bars.map((bar) => (
          <div key={bar.label} className="flex flex-1 flex-col items-center gap-3">
            <span className="font-mono text-sm text-[var(--color-text-strong)]">{bar.value}</span>
            <div className="flex w-full items-end rounded-t-[1rem] bg-[var(--color-surface-overlay-soft)]">
              <div
                className="w-full rounded-t-[1rem] transition-all duration-700"
                style={{
                  minHeight: bar.value > 0 ? '1rem' : 0,
                  height: `${(bar.value / max) * 10}rem`,
                  background: `linear-gradient(180deg, ${bar.color}, ${bar.color}55)`,
                  boxShadow: `0 18px 38px ${bar.color}30`,
                }}
              />
            </div>
            <span className="text-xs text-[var(--color-text-muted)]">{bar.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AccountRow({
  account,
  rank,
}: {
  account: { id: string; username: string; followers: number; status: string };
  rank: number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-[1.2rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] px-4 py-3">
      <span className="w-6 text-center font-mono text-xs text-[var(--color-text-muted)]">#{rank}</span>
      <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[var(--color-info-border)] bg-[linear-gradient(135deg,rgba(0,120,212,0.24),var(--color-info-bg)_60%,rgba(187,154,247,0.18))] text-sm font-semibold uppercase text-[var(--color-text-strong)]">
        {account.username[0]}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">@{account.username}</p>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">{account.status}</p>
      </div>
      <span className="font-mono text-sm text-[var(--color-text-strong)]">
        {account.followers > 0 ? account.followers.toLocaleString() : '—'}
      </span>
    </div>
  );
}

function RecentJobRow({ job }: { job: DashboardData['recent_jobs'][number] }) {
  const statusColor =
    job.status === 'completed'
      ? 'var(--color-success-fg)'
      : job.status === 'failed'
        ? 'var(--color-error-fg)'
        : job.status === 'partial'
          ? 'var(--color-warning-fg)'
          : 'var(--color-info-fg)';

  return (
    <div className="flex items-center gap-3 rounded-[1.2rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] px-4 py-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)]">
        <Calendar className="h-4 w-4 text-[var(--color-info-fg)]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-[var(--color-text-strong)]">{job.caption?.slice(0, 56) || 'Untitled post'}</p>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          {job.targets?.length ?? 0} account{(job.targets?.length ?? 0) !== 1 ? 's' : ''}
        </p>
      </div>
      <span
        className="rounded-full px-2.5 py-1 text-[11px] font-semibold"
        style={{ color: statusColor, background: `${statusColor}18`, border: `1px solid ${statusColor}2b` }}
      >
        {job.status}
      </span>
    </div>
  );
}

function ErrorAccountRow({
  account,
  loading,
  onRelogin,
}: {
  account: DashboardData['error_accounts'][0];
  loading: boolean;
  onRelogin: () => void;
}) {
  return (
    <div className="rounded-[1.25rem] border border-[var(--color-error-border)] bg-[var(--color-error-bg)] p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[var(--color-error-border)] bg-[var(--color-error-bg)] text-sm font-semibold uppercase text-[var(--color-text-strong)]">
          {account.username[0]}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">@{account.username}</p>
          {account.proxy && (
            <p className="mt-1 flex items-center gap-1 text-xs text-[var(--color-text-primary)]">
              <Globe className="h-3 w-3" />
              {account.proxy}
            </p>
          )}
        </div>
      </div>
      <Button size="sm" variant="secondary" className="mt-4 w-full" loading={loading} onClick={onRelogin}>
        <RotateCcw className="h-3.5 w-3.5" />
        Relogin
      </Button>
    </div>
  );
}

export function DashboardPage() {
  const upsertAccount = useAccountStore((s) => s.upsertAccount);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [relogining, setRelogining] = useState<Record<string, boolean>>({});
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const mountedRef = useRef(true);
  const requestRunnerRef = useRef(new SingleFlightRequestRunner());

  const load = useCallback(
    async ({
      showLoading = true,
      cancelPrevious = false,
    }: {
      showLoading?: boolean;
      cancelPrevious?: boolean;
    } = {}) => {
      if (showLoading && mountedRef.current) {
        setLoading(true);
      }

      const result = await requestRunnerRef.current.run(
        (signal) => dashboardApi.get({ signal }),
        { cancelPrevious },
      );

      if (!mountedRef.current) {
        return result;
      }

      if (result.kind === 'success') {
        setData(result.value);
        setLastRefreshed(new Date());
      } else if (result.kind === 'error') {
        toast.error(getErrorMessage(result.error, 'Failed to load dashboard'));
      }

      if (showLoading && (result.kind !== 'aborted' || !requestRunnerRef.current.isInFlight())) {
        setLoading(false);
      }

      return result;
    },
    [],
  );

  const refreshNow = useCallback(async () => {
    await load({ showLoading: true, cancelPrevious: true });
  }, [load]);

  useEffect(() => {
    mountedRef.current = true;
    const runner = requestRunnerRef.current;

    void load({ showLoading: true, cancelPrevious: true });

    return () => {
      mountedRef.current = false;
      runner.abortCurrent();
    };
  }, [load]);

  const handleRelogin = async (id: string) => {
    setRelogining((current) => ({ ...current, [id]: true }));
    try {
      const account = await dashboardApi.relogin(id);
      upsertAccount(account);
      toast.success(`@${account.username} relogged in`);
      await load({ showLoading: false, cancelPrevious: true });
    } catch (error) {
      toast.error(getErrorMessage(error, 'Relogin failed'));
    } finally {
      setRelogining((current) => ({ ...current, [id]: false }));
    }
  };

  const stats = data?.accounts;
  const total = stats?.total ?? 0;
  const lastRefresh = lastRefreshed
    ? lastRefreshed.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Realtime Monitoring"
        title="Fleet Dashboard"
        description="A live view across connected identities, job outcomes, and error buckets so operators can spot drift before it compounds."
        icon={<TrendingUp className="h-6 w-6 text-[var(--color-info-fg)]" />}
        actions={
          <Button variant="secondary" size="sm" onClick={() => void refreshNow()} loading={loading}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        }
      >
        <div className="metric-grid">
          <HeaderStat label="Last Refresh" value={lastRefresh} tone="cyan" />
          <HeaderStat label="Accounts" value={stats?.total ?? '—'} tone="blue" />
          <HeaderStat label="Active" value={stats?.active ?? '—'} tone="green" />
          <HeaderStat label="Errors" value={stats?.error ?? '—'} tone="rose" />
        </div>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Users} label="Total Accounts" value={stats?.total ?? '—'} tone="blue" />
        <StatCard
          icon={CheckCircle}
          label="Active"
          value={stats?.active ?? '—'}
          sub={total ? `${pct(stats?.active ?? 0, total)}% of fleet` : undefined}
          tone="green"
        />
        <StatCard
          icon={AlertCircle}
          label="Errors"
          value={stats?.error ?? '—'}
          sub={(stats?.error ?? 0) > 0 ? 'Needs attention' : 'All clear'}
          tone="rose"
        />
        <StatCard icon={Layers} label="Idle" value={stats?.idle ?? '—'} tone="violet" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <Card className="space-y-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Job Flow</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-strong)]">Posts today</h2>
            </div>
            <span className="glass-chip">Total {data?.jobs_today?.total ?? 0}</span>
          </div>
          <JobsBarChart data={data?.jobs_today ?? null} />
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Leaderboard</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-strong)]">Top accounts</h2>
            </div>
            <TrendingUp className="h-4 w-4 text-[var(--color-success-fg)]" />
          </div>

          {(data?.top_accounts?.length ?? 0) === 0 ? (
            <div className="rounded-[1.35rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] p-6 text-sm text-[var(--color-text-muted)]">
              No accounts yet.
            </div>
          ) : (
            <div className="space-y-3">
              {data!.top_accounts.slice(0, 5).map((account, index) => (
                <AccountRow key={account.id} account={account} rank={index + 1} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Queue Snapshot</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-strong)]">Recent jobs</h2>
            </div>
            <Activity className="h-4 w-4 text-[var(--color-info-fg)]" />
          </div>

          {(data?.recent_jobs?.length ?? 0) === 0 ? (
            <div className="rounded-[1.35rem] border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] p-6 text-sm text-[var(--color-text-muted)]">
              No recent jobs.
            </div>
          ) : (
            <div className="space-y-3">
              {data!.recent_jobs.slice(0, 6).map((job) => (
                <RecentJobRow key={job.id} job={job} />
              ))}
            </div>
          )}
        </Card>

        <Card className="space-y-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Fleet Balance</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-strong)]">Breakdown</h2>
            </div>
            <Zap className="h-4 w-4 text-[var(--color-warning-fg)]" />
          </div>

          <MetricBar label="Active" value={stats?.active ?? 0} total={total} color="linear-gradient(90deg,var(--color-success-fg),var(--color-info-fg))" />
          <MetricBar label="Idle" value={stats?.idle ?? 0} total={total} color="linear-gradient(90deg,var(--color-accent-violet),var(--color-accent-blue-soft))" />
          <MetricBar label="Errors" value={stats?.error ?? 0} total={total} color="linear-gradient(90deg,var(--color-error-fg),var(--color-warning-fg))" />
        </Card>
      </div>

      {(data?.error_accounts?.length ?? 0) > 0 && (
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <p className="text-kicker">Exception Queue</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-strong)]">
                Needs attention <span className="text-[var(--color-error-fg)]">({data!.error_accounts.length})</span>
              </h2>
            </div>
            <a
              href="/"
              className="ml-auto inline-flex items-center gap-2 text-sm font-medium text-[var(--color-text-muted)] transition-colors duration-200 hover:text-[var(--color-text-strong)]"
            >
              Manage accounts
              <ArrowUpRight className="h-4 w-4" />
            </a>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {data!.error_accounts.map((account) => (
              <ErrorAccountRow
                key={account.id}
                account={account}
                loading={relogining[account.id] ?? false}
                onRelogin={() => void handleRelogin(account.id)}
              />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
