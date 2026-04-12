import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorBoundary } from './components/ui/ErrorBoundary';
import { authStatus } from './api/dashboard-oauth';
import { useSettingsStore } from './store/settings';
import { LoginPage } from './pages/LoginPage';

const AccountsPage = lazy(async () => import('./pages/AccountsPage').then((module) => ({ default: module.AccountsPage })));
const PostPage = lazy(async () => import('./pages/PostPage').then((module) => ({ default: module.PostPage })));
const ProxyPage = lazy(async () => import('./pages/ProxyPage').then((module) => ({ default: module.ProxyPage })));
const SettingsPage = lazy(async () => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })));
const DashboardPage = lazy(async () => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const TemplatesPage = lazy(async () => import('./pages/TemplatesPage').then((module) => ({ default: module.TemplatesPage })));
const ActivityPage = lazy(async () => import('./pages/ActivityPage').then((module) => ({ default: module.ActivityPage })));
const SmartEngagementPage = lazy(async () => import('./pages/SmartEngagementPage').then((module) => ({ default: module.SmartEngagementPage })));
const OperatorCopilotPage = lazy(async () => import('./pages/OperatorCopilotPage').then((module) => ({ default: module.OperatorCopilotPage })));
const OAuthCallbackPage = lazy(async () => import('./pages/OAuthCallbackPage').then((module) => ({ default: module.OAuthCallbackPage })));
const DirectPage = lazy(async () => import('./pages/DirectPage').then((module) => ({ default: module.DirectPage })));
const HighlightsPage = lazy(async () => import('./pages/HighlightsPage').then((module) => ({ default: module.HighlightsPage })));
const InsightsPage = lazy(async () => import('./pages/InsightsPage').then((module) => ({ default: module.InsightsPage })));
const DiscoveryPage = lazy(async () => import('./pages/DiscoveryPage').then((module) => ({ default: module.DiscoveryPage })));
const CampaignPage = lazy(async () => import('./pages/CampaignPage').then((module) => ({ default: module.CampaignPage })));
const RelationshipsPage = lazy(async () => import('./pages/RelationshipsPage').then((module) => ({ default: module.RelationshipsPage })));
const MediaPage = lazy(async () => import('./pages/MediaPage').then((module) => ({ default: module.MediaPage })));
const LogStreamPage = lazy(async () => import('./pages/LogStreamPage').then((module) => ({ default: module.LogStreamPage })));

/**
 * Checks if dashboard auth is enabled on the server. When it is and the user
 * has no token, redirects to /login. When auth is disabled, renders children
 * unconditionally.
 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(false);
  const token = useSettingsStore((s) => s.dashboardToken);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const navigate = useNavigate();

  useEffect(() => {
    authStatus(backendUrl)
      .then(({ enabled }) => {
        setAuthEnabled(enabled);
        if (enabled && !token) {
          navigate('/login', { replace: true });
        }
      })
      .finally(() => setChecking(false));
  // Re-check when backendUrl changes (settings page update).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUrl]);

  if (checking) return <RouteLoader />;
  if (authEnabled && !token) return null;
  return <>{children}</>;
}

function RouteLoader() {
  return (
    <div className="page-shell flex min-h-screen max-w-5xl items-center justify-center">
      <div className="glass-panel glass-panel-strong flex min-w-[18rem] items-center gap-3 rounded-[1.75rem] px-5 py-4 text-sm text-[var(--color-text-primary)]">
        <Loader2 className="h-4 w-4 animate-spin text-[var(--color-info-fg)]" />
        Loading control deck…
      </div>
    </div>
  );
}

/** Inner boundary that resets whenever the user navigates to a new route. */
function RouteErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <ErrorBoundary resetKeys={[location.pathname]}>
      {children}
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<RouteLoader />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
            <Route element={<AuthGuard><AppLayout /></AuthGuard>}>
              <Route path="/dashboard" element={<RouteErrorBoundary><DashboardPage /></RouteErrorBoundary>} />
              <Route path="/accounts" element={<RouteErrorBoundary><AccountsPage /></RouteErrorBoundary>} />
              <Route path="/" element={<Navigate to="/accounts" replace />} />
              <Route path="/post" element={<RouteErrorBoundary><PostPage /></RouteErrorBoundary>} />
              <Route path="/templates" element={<RouteErrorBoundary><TemplatesPage /></RouteErrorBoundary>} />
              <Route path="/proxy" element={<RouteErrorBoundary><ProxyPage /></RouteErrorBoundary>} />
              <Route path="/activity" element={<RouteErrorBoundary><ActivityPage /></RouteErrorBoundary>} />
              <Route path="/logstream" element={<RouteErrorBoundary><LogStreamPage /></RouteErrorBoundary>} />
              <Route path="/settings" element={<RouteErrorBoundary><SettingsPage /></RouteErrorBoundary>} />
              <Route path="/smart-engagement" element={<RouteErrorBoundary><SmartEngagementPage /></RouteErrorBoundary>} />
              <Route path="/operator-copilot" element={<RouteErrorBoundary><OperatorCopilotPage /></RouteErrorBoundary>} />
              <Route path="/media" element={<RouteErrorBoundary><MediaPage /></RouteErrorBoundary>} />
              <Route path="/stories" element={<Navigate to="/accounts" replace />} />
              <Route path="/direct" element={<RouteErrorBoundary><DirectPage /></RouteErrorBoundary>} />
              <Route path="/highlights" element={<RouteErrorBoundary><HighlightsPage /></RouteErrorBoundary>} />
              <Route path="/insights" element={<RouteErrorBoundary><InsightsPage /></RouteErrorBoundary>} />
              <Route path="/discovery" element={<RouteErrorBoundary><DiscoveryPage /></RouteErrorBoundary>} />
              <Route path="/campaign" element={<RouteErrorBoundary><CampaignPage /></RouteErrorBoundary>} />
              <Route path="/relationships" element={<RouteErrorBoundary><RelationshipsPage /></RouteErrorBoundary>} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
