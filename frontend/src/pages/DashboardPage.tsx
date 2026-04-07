import { useCallback, useEffect, useState } from 'react';
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
import { useAccountStore } from '../store/accounts';
import type { PostJob } from '../types';
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
      ? 'text-[#9ece6a] border-[rgba(158,206,106,0.18)] bg-[rgba(158,206,106,0.12)]'
      : tone === 'violet'
        ? 'text-[#bb9af7] border-[rgba(187,154,247,0.18)] bg-[rgba(187,154,247,0.12)]'
        : tone === 'rose'
          ? 'text-[#f7768e] border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.12)]'
          : 'text-[#7dcfff] border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.12)]';

  return (
    <Card glow className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-kicker !text-[0.62rem]">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-[#eef4ff]">{value}</p>
          {sub && <p className="mt-2 text-sm text-[#8e9ac0]">{sub}</p>}
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
        <span className="text-[#8e9ac0]">{label}</span>
        <span className="font-mono text-[#eef4ff]">
          {value} <span className="text-[#7f8bb3]">({percent}%)</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-[rgba(255,255,255,0.05)]">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${percent}%`, background: color }} />
      </div>
    </div>
  );
}

function JobsBarChart({ data }: { data: DashboardData['jobs_today'] | null }) {
  const bars = [
    { label: 'Completed', value: data?.completed ?? 0, color: '#9ece6a' },
    { label: 'Partial', value: data?.partial ?? 0, color: '#e0af68' },
    { label: 'Failed', value: data?.failed ?? 0, color: '#f7768e' },
  ];
  const max = Math.max(...bars.map((bar) => bar.value), 1);

  return (
    <div className="flex h-full flex-col justify-between">
      <div className="flex min-h-[13rem] items-end gap-4">
        {bars.map((bar) => (
          <div key={bar.label} className="flex flex-1 flex-col items-center gap-3">
            <span className="font-mono text-sm text-[#eef4ff]">{bar.value}</span>
            <div className="flex w-full items-end rounded-t-[1rem] bg-[rgba(255,255,255,0.03)]">
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
            <span className="text-xs text-[#8e9ac0]">{bar.label}</span>
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
    <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-4 py-3">
      <span className="w-6 text-center font-mono text-xs text-[#7f8bb3]">#{rank}</span>
      <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[rgba(125,207,255,0.16)] bg-[linear-gradient(135deg,rgba(122,162,247,0.22),rgba(125,207,255,0.12)_60%,rgba(187,154,247,0.18))] text-sm font-semibold uppercase text-[#eef4ff]">
        {account.username[0]}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-[#eef4ff]">@{account.username}</p>
        <p className="mt-1 text-xs text-[#8e9ac0]">{account.status}</p>
      </div>
      <span className="font-mono text-sm text-[#eef4ff]">
        {account.followers > 0 ? account.followers.toLocaleString() : '—'}
      </span>
    </div>
  );
}

function RecentJobRow({ job }: { job: PostJob }) {
  const statusColor =
    job.status === 'completed'
      ? '#9ece6a'
      : job.status === 'failed'
        ? '#f7768e'
        : job.status === 'partial'
          ? '#e0af68'
          : '#7dcfff';

  return (
    <div className="flex items-center gap-3 rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-4 py-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
        <Calendar className="h-4 w-4 text-[#7dcfff]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-[#eef4ff]">{job.caption?.slice(0, 56) || 'Untitled post'}</p>
        <p className="mt-1 text-xs text-[#8e9ac0]">
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
    <div className="rounded-[1.25rem] border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.08)] p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.12)] text-sm font-semibold uppercase text-[#ffd0d8]">
          {account.username[0]}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-[#eef4ff]">@{account.username}</p>
          {account.proxy && (
            <p className="mt-1 flex items-center gap-1 text-xs text-[#ffccd6]">
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await dashboardApi.get();
      setData(next);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to load dashboard'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const timer = setInterval(() => {
      void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [load]);

  const handleRelogin = async (id: string) => {
    setRelogining((current) => ({ ...current, [id]: true }));
    try {
      const account = await dashboardApi.relogin(id);
      upsertAccount(account);
      toast.success(`@${account.username} relogged in`);
      const nextData = await dashboardApi.get();
      setData(nextData);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Relogin failed'));
    } finally {
      setRelogining((current) => ({ ...current, [id]: false }));
    }
  };

  const stats = data?.accounts;
  const total = stats?.total ?? 0;
  const lastRefresh = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Realtime Monitoring"
        title="Fleet Dashboard"
        description="A live view across connected identities, job outcomes, and error buckets so operators can spot drift before it compounds."
        icon={<TrendingUp className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          <Button variant="secondary" size="sm" onClick={() => void load()} loading={loading}>
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
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Posts today</h2>
            </div>
            <span className="glass-chip">Total {data?.jobs_today?.total ?? 0}</span>
          </div>
          <JobsBarChart data={data?.jobs_today ?? null} />
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Leaderboard</p>
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Top accounts</h2>
            </div>
            <TrendingUp className="h-4 w-4 text-[#9ece6a]" />
          </div>

          {(data?.top_accounts?.length ?? 0) === 0 ? (
            <div className="rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-6 text-sm text-[#8e9ac0]">
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
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Recent jobs</h2>
            </div>
            <Activity className="h-4 w-4 text-[#7dcfff]" />
          </div>

          {(data?.recent_jobs?.length ?? 0) === 0 ? (
            <div className="rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-6 text-sm text-[#8e9ac0]">
              No recent jobs.
            </div>
          ) : (
            <div className="space-y-3">
              {(data!.recent_jobs as PostJob[]).slice(0, 6).map((job) => (
                <RecentJobRow key={job.id} job={job} />
              ))}
            </div>
          )}
        </Card>

        <Card className="space-y-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-kicker">Fleet Balance</p>
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Breakdown</h2>
            </div>
            <Zap className="h-4 w-4 text-[#e0af68]" />
          </div>

          <MetricBar label="Active" value={stats?.active ?? 0} total={total} color="linear-gradient(90deg,#9ece6a,#7dcfff)" />
          <MetricBar label="Idle" value={stats?.idle ?? 0} total={total} color="linear-gradient(90deg,#bb9af7,#7aa2f7)" />
          <MetricBar label="Errors" value={stats?.error ?? 0} total={total} color="linear-gradient(90deg,#f7768e,#e0af68)" />
        </Card>
      </div>

      {(data?.error_accounts?.length ?? 0) > 0 && (
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <p className="text-kicker">Exception Queue</p>
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">
                Needs attention <span className="text-[#f7768e]">({data!.error_accounts.length})</span>
              </h2>
            </div>
            <a
              href="/"
              className="ml-auto inline-flex items-center gap-2 text-sm font-medium text-[#8e9ac0] transition-colors duration-200 hover:text-[#eef4ff]"
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
