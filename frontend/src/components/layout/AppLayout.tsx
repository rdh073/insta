import { Suspense, startTransition, useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AlertTriangle, Loader2, Waves, Zap } from 'lucide-react';
import { Toaster } from 'react-hot-toast';
import { accountsApi } from '../../api/accounts';
import { postsApi } from '../../api/posts';
import { describeBackend } from '../../lib/api-base';
import {
  buildBulkHydrateSessionKey,
  shouldResetStartupStores,
} from '../../lib/startup-hydration';
import { useAccountStore } from '../../store/accounts';
import { usePostStore } from '../../store/posts';
import { PROVIDERS, useSettingsStore } from '../../store/settings';
import { useAccountEvents } from '../../features/accounts/hooks/useAccountEvents';
import { Sidebar } from './Sidebar';
import { runStartupHydration } from './startup-hydrate';

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
  { startsWith: '/relationships', label: 'Social Graph', title: 'Relationships', subtitle: 'Follow, unfollow, and cross-follow users across multiple managed accounts.' },
  { startsWith: '/logstream', label: 'Infrastructure', title: 'Log Stream', subtitle: 'Live Python logging output streamed from the backend process over SSE.' },
  { startsWith: '/accounts', label: 'Identity Operations', title: 'Account Workspace', subtitle: 'Session health, relogin actions, and account lifecycle controls.' },
];

export function AppLayout() {
  const location = useLocation();
  const setAccounts = useAccountStore((state) => state.setAccounts);
  const { connectionLost, streamError } = useAccountEvents();
  const setJobs = usePostStore((state) => state.setJobs);
  const jobs = usePostStore((state) => state.jobs);
  const backendUrl = useSettingsStore((state) => state.backendUrl);
  const backendApiKey = useSettingsStore((state) => state.backendApiKey);
  const dashboardToken = useSettingsStore((state) => state.dashboardToken);
  const provider = useSettingsStore((state) => state.provider);
  const [syncing, setSyncing] = useState(false);
  const previousBackendUrlRef = useRef<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cleanupFired = false;
    const normalizedBackendUrl = backendUrl.trim();
    const shouldReset = shouldResetStartupStores(previousBackendUrlRef.current, normalizedBackendUrl);
    previousBackendUrlRef.current = normalizedBackendUrl;

    const waitForBackend = async (
      outerSignal: AbortSignal,
      maxRetries = 10,
      delayMs = 2000,
    ): Promise<boolean> => {
      for (let i = 0; i < maxRetries; i++) {
        if (outerSignal.aborted) return false;
        try {
          const baseUrl = normalizedBackendUrl;
          const healthUrl = baseUrl ? `${baseUrl.replace(/\/+$/, '')}/health` : '/api/../health';
          const perAttempt = AbortSignal.any([outerSignal, AbortSignal.timeout(3000)]);
          const res = await fetch(healthUrl, { signal: perAttempt });
          if (res.ok) return true;
        } catch {
          if (outerSignal.aborted) return false;
          // backend not ready yet
        }
        if (outerSignal.aborted) return false;
        await new Promise((r) => setTimeout(r, delayMs));
      }
      return false;
    };

    void runStartupHydration({
      signal: controller.signal,
      listAccounts: (signal) => accountsApi.list(signal),
      listPosts: (signal) => postsApi.list(signal),
      bulkHydrateProfiles: (signal) => accountsApi.bulkHydrateProfiles(signal),
      waitForBackend,
      setAccounts,
      setJobs,
      isStoreEmpty: () =>
        useAccountStore.getState().accounts.length === 0 &&
        usePostStore.getState().jobs.length === 0,
      isCleanupFired: () => cleanupFired,
      sessionStore: sessionStorage,
      sessionKey: buildBulkHydrateSessionKey(normalizedBackendUrl),
      commit: (update) => startTransition(update),
      setSyncing,
      resetStores: shouldReset,
      backendUrlLabel: normalizedBackendUrl || '(vite-proxy)',
    });

    return () => {
      cleanupFired = true;
      controller.abort();
    };
  }, [backendUrl, backendApiKey, dashboardToken, setAccounts, setJobs]);

  const currentMeta =
    routeMeta.find((item) => location.pathname.startsWith(item.startsWith)) ?? routeMeta[routeMeta.length - 1];
  const activeJobs = jobs.filter((job) => ['pending', 'running', 'scheduled'].includes(job.status)).length;

  return (
    <div className="relative min-h-screen overflow-hidden text-[var(--color-text-primary)]">
      <div className="pointer-events-none fixed inset-0 z-0">
        <div className="absolute -left-32 top-0 h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgba(79,193,255,0.14),transparent_68%)] blur-3xl" />
        <div className="absolute right-[-9rem] top-[8rem] h-[32rem] w-[32rem] rounded-full bg-[radial-gradient(circle,rgba(0,120,212,0.16),transparent_68%)] blur-3xl" />
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
          <header className="z-30 shrink-0 border-b border-[var(--color-border-faint)] bg-[rgba(11,15,24,0.84)] backdrop-blur-2xl">
            <div className="page-shell !max-w-[120rem] py-2.5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="hidden lg:block shrink-0">
                    <div className="glass-chip">
                      <Waves className="h-3 w-3 text-[var(--color-info-fg)]" />
                      {currentMeta.label}
                    </div>
                  </div>
                  <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">{currentMeta.title}</p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <span className="glass-chip">
                    <span className={`h-1.5 w-1.5 rounded-full bg-[var(--color-success-fg)] ${syncing ? 'animate-pulse' : ''}`} />
                    {syncing ? 'Syncing' : 'Live'}
                  </span>
                  {activeJobs > 0 && (
                    <span className="glass-chip">
                      <Zap className="h-3 w-3 text-[var(--color-accent-blue-soft)]" />
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

          {(connectionLost || streamError) && (
            <div
              role="alert"
              className="flex shrink-0 items-center gap-2 border-b border-[var(--color-error-border)] bg-[var(--color-error-bg)] px-4 py-2 text-sm text-[var(--color-error-fg)]"
            >
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>
                {streamError ? `${streamError}. ` : 'Live connection lost — account updates may be stale. '}
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="cursor-pointer underline underline-offset-2 hover:text-[var(--color-text-strong)]"
                >
                  Reload
                </button>
              </span>
            </div>
          )}

          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center p-6">
                  <div className="glass-panel glass-panel-strong flex items-center gap-3 rounded-[1.75rem] px-5 py-4 text-sm text-[var(--color-text-primary)]">
                    <Loader2 className="h-4 w-4 animate-spin text-[var(--color-info-fg)]" />
                    Loading…
                  </div>
                </div>
              }
            >
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>

      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'linear-gradient(180deg, rgba(22, 28, 42, 0.95), rgba(12, 17, 28, 0.93))',
            color: 'var(--color-text-strong)',
            border: '1px solid var(--color-border-subtle)',
            backdropFilter: 'blur(24px)',
            boxShadow: '0 24px 60px rgba(4,8,18,0.42)',
            fontFamily: 'Fira Sans, sans-serif',
            fontSize: '14px',
            borderRadius: '18px',
          },
          success: { iconTheme: { primary: 'var(--color-success-fg)', secondary: 'var(--color-bg-canvas)' } },
          error: { iconTheme: { primary: 'var(--color-error-fg)', secondary: 'var(--color-bg-canvas)' } },
        }}
      />
    </div>
  );
}
