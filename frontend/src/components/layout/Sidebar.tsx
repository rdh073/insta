import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowLeftRight,
  BarChart2,
  Bookmark,
  Bot,
  FileText,
  Globe,
  Grid2x2,
  Hash,
  ImagePlus,
  Layers,
  LayoutDashboard,
  Lock,
  Menu,
  MessageCircle,
  Settings,
  Sparkles,
  Terminal,
  Users,
  Waves,
  X,
} from 'lucide-react';
import { cn } from '../../lib/cn';
import { useSettingsStore } from '../../store/settings';

const navGroups = [
  {
    label: 'Control',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/accounts', label: 'Accounts', icon: Users },
      { to: '/post', label: 'Broadcast', icon: ImagePlus },
      { to: '/campaign', label: 'Campaign', icon: Layers },
      { to: '/templates', label: 'Templates', icon: FileText },
    ],
  },
  {
    label: 'Automation',
    items: [
      { to: '/smart-engagement', label: 'Engagement', icon: Sparkles },
      { to: '/relationships', label: 'Relationships', icon: ArrowLeftRight },
      { to: '/operator-copilot', label: 'Copilot', icon: Bot },
      { to: '/activity', label: 'Activity', icon: Activity },
      { to: '/logstream', label: 'Log Stream', icon: Terminal },
    ],
  },
  {
    label: 'Infrastructure',
    items: [
      { to: '/proxy', label: 'Proxy', icon: Globe },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
  {
    label: 'Instagram',
    items: [
      { to: '/media', label: 'Media', icon: Grid2x2 },
      { to: '/direct', label: 'Direct', icon: MessageCircle },
      { to: '/highlights', label: 'Highlights', icon: Bookmark },
      { to: '/insights', label: 'Insights', icon: BarChart2 },
      { to: '/discovery', label: 'Discovery', icon: Hash },
    ],
  },
];

interface SidebarProps {
  backendLabel: string;
  providerLabel: string;
  syncing: boolean;
  activeJobs: number;
}

function NavItem({
  to,
  label,
  icon: Icon,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          'group flex cursor-pointer items-center gap-2.5 rounded-xl border px-2.5 py-2 text-[13px] font-medium transition-all duration-200',
          isActive
            ? 'border-[var(--color-info-border)] bg-[linear-gradient(135deg,rgba(0,120,212,0.24),rgba(79,193,255,0.14)_55%,rgba(187,154,247,0.12))] text-[var(--color-text-strong)]'
            : 'border-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border-faint)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)]',
        )
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={cn(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200',
              isActive
                ? 'border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-fg)]'
                : 'border-[var(--color-border-fainter)] bg-[var(--color-surface-overlay-soft)] text-[var(--color-text-subtle)] group-hover:text-[var(--color-text-primary)]',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
          </div>
          <span className="min-w-0 flex-1 truncate">{label}</span>
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({ backendLabel, providerLabel, syncing, activeJobs }: SidebarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();
  const dashboardToken = useSettingsStore((s) => s.dashboardToken);
  const lockSession = useSettingsStore((s) => s.lockSession);

  const handleLock = () => {
    lockSession();
    navigate('/login', { replace: true });
  };

  return (
    <>
      <div className="sticky top-0 z-40 border-b border-[var(--color-border-faint)] bg-[rgba(11,15,24,0.90)] backdrop-blur-2xl lg:hidden">
        {/* Top bar: brand + status + hamburger */}
        <div className="flex items-center justify-between gap-3 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text-primary)]"
              aria-label="Open navigation menu"
            >
              <Menu className="h-4 w-4" />
            </button>
            <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">Insta Console</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {activeJobs > 0 && (
              <span className="rounded-full bg-[rgba(86,156,214,0.16)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-accent-blue-soft)]">
                {activeJobs}
              </span>
            )}
            <span className="glass-chip !px-2 !py-1 !text-[11px]">
              <span className={cn('h-1.5 w-1.5 rounded-full bg-[var(--color-success-fg)]', syncing && 'animate-pulse')} />
              {syncing ? 'Sync' : 'Live'}
            </span>
          </div>
        </div>

        {/* Bottom tab bar: 5 primary Control items */}
        <nav className="flex border-t border-[var(--color-border-fainter)]" aria-label="Mobile navigation">
          {navGroups[0].items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  'flex flex-1 cursor-pointer flex-col items-center gap-1 py-2.5 text-[10px] font-medium transition-colors duration-200',
                  isActive ? 'text-[var(--color-info-fg)]' : 'text-[var(--color-text-disabled)] hover:text-[var(--color-text-primary)]',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn('h-5 w-5', isActive && 'drop-shadow-[0_0_6px_rgba(79,193,255,0.55)]')} />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Mobile slide-in drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-[rgba(6,10,18,0.74)] backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          {/* Drawer panel */}
          <aside className="absolute left-0 top-0 flex h-full w-72 flex-col border-r border-[var(--color-border-faint)] bg-[rgba(10,14,22,0.96)] px-3 py-4 backdrop-blur-2xl">
            {/* Drawer header */}
            <div className="mb-4 flex items-center justify-between gap-2 px-1">
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="glass-panel glass-panel-soft flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border-[var(--color-info-border)]">
                  <Waves className="h-4 w-4 text-[var(--color-info-fg)]" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">Insta Console</p>
                  <p className="truncate text-[11px] text-[var(--color-text-subtle)]">{backendLabel}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[var(--color-border-faint)] bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text-primary)]"
                aria-label="Close navigation menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Nav groups */}
            <nav className="flex-1 overflow-y-auto" aria-label="Full navigation">
              {navGroups.map((group, index) => (
                <section key={group.label} className={cn(index > 0 && 'mt-4')}>
                  <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-disabled)]">{group.label}</p>
                  <div className="space-y-0.5">
                    {group.items.map((item) => (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.to === '/'}
                        onClick={() => setDrawerOpen(false)}
                        className={({ isActive }) =>
                          cn(
                            'group flex cursor-pointer items-center gap-2.5 rounded-xl border px-2.5 py-2 text-[13px] font-medium transition-all duration-200',
                            isActive
                              ? 'border-[var(--color-info-border)] bg-[linear-gradient(135deg,rgba(0,120,212,0.24),rgba(79,193,255,0.14)_55%,rgba(187,154,247,0.12))] text-[var(--color-text-strong)]'
                              : 'border-transparent text-[var(--color-text-muted)] hover:border-[var(--color-border-faint)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)]',
                          )
                        }
                      >
                        {({ isActive }) => (
                          <>
                            <div
                              className={cn(
                                'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200',
                                isActive
                                  ? 'border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-fg)]'
                                  : 'border-[var(--color-border-fainter)] bg-[var(--color-surface-overlay-soft)] text-[var(--color-text-subtle)] group-hover:text-[var(--color-text-primary)]',
                              )}
                            >
                              <item.icon className="h-3.5 w-3.5" />
                            </div>
                            <span className="min-w-0 flex-1 truncate">{item.label}</span>
                          </>
                        )}
                      </NavLink>
                    ))}
                  </div>
                </section>
              ))}
            </nav>

            {/* Footer */}
            <div className="mt-3 flex items-center gap-2 border-t border-[var(--color-border-fainter)] px-1 pt-3">
              <p className="min-w-0 flex-1 truncate text-[11px] text-[var(--color-text-disabled)]">{providerLabel}</p>
              {activeJobs > 0 && (
                <span className="shrink-0 rounded-full bg-[rgba(86,156,214,0.16)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-accent-blue-soft)]">
                  {activeJobs} jobs
                </span>
              )}
              {dashboardToken && (
                <button
                  type="button"
                  onClick={handleLock}
                  title="Lock — return to password portal"
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-[var(--color-error-border)] bg-[rgba(248,81,73,0.08)] text-[var(--color-error-fg)] transition-colors hover:bg-[rgba(248,81,73,0.16)] cursor-pointer"
                  aria-label="Lock session"
                >
                  <Lock className="h-3 w-3" />
                </button>
              )}
            </div>
          </aside>
        </div>
      )}


      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-[var(--color-border-faint)] bg-[rgba(10,14,22,0.76)] px-3 py-4 backdrop-blur-2xl lg:flex">
        {/* Compact brand row */}
        <div className="mb-4 flex items-center justify-between gap-2 px-1">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="glass-panel glass-panel-soft flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border-[var(--color-info-border)]">
              <Waves className="h-4 w-4 text-[var(--color-info-fg)]" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--color-text-strong)]">Insta Console</p>
              <p className="truncate text-[11px] text-[var(--color-text-subtle)]">{backendLabel}</p>
            </div>
          </div>
          <span className="glass-chip shrink-0 !px-2 !py-1 !text-[11px]">
            <span className={cn('h-1.5 w-1.5 rounded-full bg-[var(--color-success-fg)]', syncing && 'animate-pulse')} />
            {syncing ? 'Sync' : 'Live'}
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto" aria-label="Main navigation">
          {navGroups.map((group, index) => (
            <section key={group.label} className={cn(index > 0 && 'mt-4')}>
              <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-disabled)]">{group.label}</p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavItem key={item.to} {...item} />
                ))}
              </div>
            </section>
          ))}
        </nav>

        {/* Footer: provider · active jobs · lock */}
        <div className="mt-3 flex items-center gap-2 border-t border-[var(--color-border-fainter)] px-1 pt-3">
          <p className="min-w-0 flex-1 truncate text-[11px] text-[var(--color-text-disabled)]">{providerLabel}</p>
          {activeJobs > 0 && (
            <span className="shrink-0 rounded-full bg-[rgba(86,156,214,0.16)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-accent-blue-soft)]">
              {activeJobs} jobs
            </span>
          )}
          {dashboardToken && (
            <button
              type="button"
              onClick={handleLock}
              title="Lock — return to password portal"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border border-[var(--color-error-border)] bg-[rgba(248,81,73,0.08)] text-[var(--color-error-fg)] transition-colors hover:bg-[rgba(248,81,73,0.16)] cursor-pointer"
              aria-label="Lock session"
            >
              <Lock className="h-3 w-3" />
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
