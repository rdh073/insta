import { startTransition, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AlertTriangle, Waves, Zap } from 'lucide-react';
import { Toaster } from 'react-hot-toast';
import { accountsApi } from '../../api/accounts';
import { postsApi } from '../../api/posts';
import { describeBackend } from '../../lib/api-base';
import { useAccountStore } from '../../store/accounts';
import { usePostStore } from '../../store/posts';
import { PROVIDERS, useSettingsStore } from '../../store/settings';
import { useAccountEvents } from '../../features/accounts/hooks/useAccountEvents';
import { Sidebar } from './Sidebar';

const routeMeta: Array<{
  startsWith: string;
  label: string;
  title: string;
  subtitle: string;
}> = [
  { startsWith: '/dashboard', label: 'Realtime Monitoring', title: 'Fleet Dashboard', subtitle: 'Live account health, posting throughput, and exception tracking.' },
  { startsWith: '/post', label: 'Broadcast Control', title: 'Publishing Queue', subtitle: 'Compose, target, and dispatch multi-account media jobs.' },
  { startsWith: '/templates', label: 'Content Systems', title: 'Template Library', subtitle: 'Reusable caption blocks, campaign language, and operator-ready snippets.' },
  { startsWith: '/proxy', label: 'Routing Matrix', title: 'Proxy Routing', subtitle: 'Per-account network paths, selection sets, and backend-managed assignment.' },
  { startsWith: '/activity', label: 'Audit Feed', title: 'Activity Timeline', subtitle: 'Operational events across authentication, posting, and routing changes.' },
  { startsWith: '/settings', label: 'Control Plane', title: 'System Settings', subtitle: 'Backend target, provider routing, OAuth, and model defaults.' },
  { startsWith: '/smart-engagement', label: 'Risk Engine', title: 'Smart Engagement', subtitle: 'Reviewable recommendations with safety signals and approval checkpoints.' },
  { startsWith: '/operator-copilot', label: 'Command Layer', title: 'Operator Copilot', subtitle: 'Streaming AI guidance with tool approvals and slash-command workflows.' },
  { startsWith: '/media', label: 'Instagram', title: 'Media Browser', subtitle: 'Browse posts, manage comments — post, reply, like, pin, or delete.' },
  { startsWith: '/direct', label: 'Instagram', title: 'Direct Messages', subtitle: 'Browse inbox threads, read messages, and send replies.' },
  { startsWith: '/highlights', label: 'Instagram', title: 'Highlights', subtitle: 'Manage story highlights — rename, add stories, and delete.' },
  { startsWith: '/insights', label: 'Instagram', title: 'Insights', subtitle: 'Media analytics — reach, impressions, engagement metrics per post.' },
  { startsWith: '/discovery', label: 'Instagram', title: 'Hashtag Discovery', subtitle: 'Search hashtags, browse top and recent posts for content research.' },
  { startsWith: '/campaign', label: 'Broadcast Control', title: 'Campaign Monitor', subtitle: 'Track every post job across all accounts — live status and per-account results.' },
  { startsWith: '/accounts', label: 'Identity Operations', title: 'Account Workspace', subtitle: 'Session health, relogin actions, and account lifecycle controls.' },
];

export function AppLayout() {
  const location = useLocation();
  const setAccounts = useAccountStore((state) => state.setAccounts);
  const { connectionLost } = useAccountEvents();
  const setJobs = usePostStore((state) => state.setJobs);
  const jobs = usePostStore((state) => state.jobs);
  const backendUrl = useSettingsStore((state) => state.backendUrl);
  const provider = useSettingsStore((state) => state.provider);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const waitForBackend = async (maxRetries = 10, delayMs = 2000): Promise<boolean> => {
      for (let i = 0; i < maxRetries; i++) {
        if (cancelled) return false;
        try {
          const baseUrl = backendUrl?.trim() || '';
          const healthUrl = baseUrl ? `${baseUrl.replace(/\/+$/, '')}/health` : '/api/../health';
          const res = await fetch(healthUrl, { signal: AbortSignal.timeout(3000) });
          if (res.ok) return true;
        } catch {
          // backend not ready yet
        }
        await new Promise((r) => setTimeout(r, delayMs));
      }
      return false;
    };

    const hydrate = async () => {
      startTransition(() => {
        setAccounts([]);
        setJobs([]);
      });
      setSyncing(true);

      // Wait for backend before fetching data — avoids ECONNREFUSED spam
      const ready = await waitForBackend();
      if (cancelled) return;

      if (ready) {
        const [accountsResult, jobsResult] = await Promise.allSettled([accountsApi.list(), postsApi.list()]);

        if (cancelled) return;

        startTransition(() => {
          if (accountsResult.status === 'fulfilled') {
            setAccounts(accountsResult.value);
          }
          if (jobsResult.status === 'fulfilled') {
            setJobs(jobsResult.value);
          }
        });

        // Fire-and-forget: hydrate follower/following counts for all active accounts.
        // Results arrive via SSE account_updated events — no need to await.
        // Guard: only call once per session tab to avoid hammering Instagram on
        // rapid reconnects or navigation (server also enforces a 5-min cooldown).
        const SESSION_KEY = 'insta_bulk_hydrated';
        if (!sessionStorage.getItem(SESSION_KEY)) {
          sessionStorage.setItem(SESSION_KEY, Date.now().toString());
          accountsApi.bulkHydrateProfiles().catch(() => {/* best-effort */});
        }
      }

      setSyncing(false);
    };

    hydrate();
    return () => {
      cancelled = true;
    };
  }, [backendUrl, setAccounts, setJobs]);

  const currentMeta =
    routeMeta.find((item) => location.pathname.startsWith(item.startsWith)) ?? routeMeta[routeMeta.length - 1];
  const activeJobs = jobs.filter((job) => ['pending', 'running', 'scheduled'].includes(job.status)).length;

  return (
    <div className="relative min-h-screen overflow-hidden text-[#c0caf5]">
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -left-32 top-0 h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgba(125,207,255,0.14),transparent_68%)] blur-3xl" />
        <div className="absolute right-[-9rem] top-[8rem] h-[32rem] w-[32rem] rounded-full bg-[radial-gradient(circle,rgba(122,162,247,0.16),transparent_68%)] blur-3xl" />
        <div className="absolute bottom-[-12rem] left-[26%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(187,154,247,0.18),transparent_70%)] blur-3xl" />
      </div>

      <div className="relative z-10 flex h-dvh flex-col lg:flex-row">
        <Sidebar
          backendLabel={describeBackend(backendUrl)}
          providerLabel={PROVIDERS[provider].label}
          syncing={syncing}
          activeJobs={activeJobs}
        />

        <main className="min-w-0 flex-1 flex flex-col overflow-hidden">
          <header className="shrink-0 border-b border-[rgba(162,179,229,0.12)] bg-[rgba(9,12,22,0.82)] backdrop-blur-2xl z-30">
            <div className="page-shell !max-w-[120rem] py-2.5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="hidden lg:block shrink-0">
                    <div className="glass-chip">
                      <Waves className="h-3 w-3 text-[#7dcfff]" />
                      {currentMeta.label}
                    </div>
                  </div>
                  <p className="truncate text-sm font-semibold text-[#eef4ff]">{currentMeta.title}</p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <span className="glass-chip">
                    <span className={`h-1.5 w-1.5 rounded-full bg-[#9ece6a] ${syncing ? 'animate-pulse' : ''}`} />
                    {syncing ? 'Syncing' : 'Live'}
                  </span>
                  {activeJobs > 0 && (
                    <span className="glass-chip">
                      <Zap className="h-3 w-3 text-[#7aa2f7]" />
                      {activeJobs}
                    </span>
                  )}
                  <span className="sr-only" aria-live="polite">
                    {syncing ? 'Syncing account and job state.' : 'Account and job state synced.'}
                  </span>
                </div>
              </div>
            </div>
          </header>

          {connectionLost && (
            <div
              role="alert"
              className="shrink-0 flex items-center gap-2 border-b border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.08)] px-4 py-2 text-sm text-[#f7768e]"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>
                Live connection lost — account updates may be stale.{' '}
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="cursor-pointer underline underline-offset-2 hover:text-[#ff9db0]"
                >
                  Reload
                </button>
              </span>
            </div>
          )}

          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
            <Outlet />
          </div>
        </main>
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'linear-gradient(180deg, rgba(18,24,39,0.94), rgba(10,14,24,0.92))',
            color: '#eef4ff',
            border: '1px solid rgba(162,179,229,0.16)',
            backdropFilter: 'blur(24px)',
            boxShadow: '0 24px 60px rgba(4,8,18,0.42)',
            fontFamily: 'Fira Sans, sans-serif',
            fontSize: '14px',
            borderRadius: '18px',
          },
          success: { iconTheme: { primary: '#9ece6a', secondary: '#0b1020' } },
          error: { iconTheme: { primary: '#f7768e', secondary: '#0b1020' } },
        }}
      />
    </div>
  );
}
