import { useRef, useState } from 'react';
import { Save } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { useSettingsDraft } from '../hooks/useSettingsDraft';
import { useProviderOAuth } from '../hooks/useProviderOAuth';
import { SettingsSectionNav, type SettingsSection } from './SettingsSectionNav';
import { ConnectionSettingsCard } from './ConnectionSettingsCard';
import { ProviderSelectorGrid } from './ProviderSelectorGrid';
import { ProviderAccessCard } from './ProviderAccessCard';
import { ModelSettingsCard } from './ModelSettingsCard';
import { SettingsSummaryRail } from './SettingsSummaryRail';

function validateBackendUrl(url: string): string | undefined {
  if (!url.trim()) return undefined; // Empty = same origin, allowed
  try {
    new URL(url);
    return undefined;
  } catch {
    return 'Enter a valid URL (e.g. http://localhost:8000)';
  }
}

export function SettingsWorkspace() {
  const draft = useSettingsDraft();
  const oauth = useProviderOAuth(draft.draftProvider, draft.draftBackendUrl);

  const [activeSection, setActiveSection] = useState<SettingsSection>('connection');

  const connectionRef = useRef<HTMLDivElement>(null);
  const providerRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);

  const sectionRefs: Record<SettingsSection, React.RefObject<HTMLDivElement | null>> = {
    connection: connectionRef,
    provider: providerRef,
    model: modelRef,
  };

  const handleNavigate = (section: SettingsSection) => {
    setActiveSection(section);
    const target = sectionRefs[section].current;
    if (!target) return;

    const scroller = target.closest('.overflow-y-auto') as HTMLElement | null;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobile = window.matchMedia('(max-width: 1023px)').matches;
    const behavior: ScrollBehavior = prefersReducedMotion || isMobile ? 'auto' : 'smooth';

    if (scroller) {
      const targetTop =
        target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 12;
      scroller.scrollTo({ top: Math.max(0, targetTop), behavior });
      return;
    }

    target.scrollIntoView({ behavior, block: 'start' });
  };

  const urlError = validateBackendUrl(draft.draftBackendUrl);

  return (
    <div className="space-y-6">
      {/* Section navigator */}
      <SettingsSectionNav activeSection={activeSection} onNavigate={handleNavigate} />

      {/* Responsive layout: main content + sticky rail */}
      <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start xl:gap-6">
        {/* Main content column */}
        <div className="space-y-6">
          {/* Connection section */}
          <section ref={connectionRef} aria-labelledby="section-connection-heading">
            <h2 id="section-connection-heading" className="sr-only">
              Connection
            </h2>
            <ConnectionSettingsCard
              url={draft.draftBackendUrl}
              setUrl={draft.setDraftBackendUrl}
              backendLabel={draft.backendLabel}
              urlError={urlError}
              apiKey={draft.draftBackendApiKey}
              setApiKey={draft.setDraftBackendApiKey}
            />
          </section>

          {/* AI Provider section */}
          <section ref={providerRef} aria-labelledby="section-provider-heading">
            <h2 id="section-provider-heading" className="sr-only">
              AI Provider
            </h2>
            <Card className="space-y-5">
              <div>
                <p className="text-kicker">AI Routing</p>
                <h3 className="mt-2 text-base font-semibold text-[var(--color-text-strong)]">Provider selection</h3>
                <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">
                  Pick the runtime provider and wire credentials or OAuth-managed access.
                </p>
              </div>

              <ProviderSelectorGrid
                provider={draft.draftProvider}
                onProviderChange={draft.handleProviderChange}
              />

              <ProviderAccessCard
                provider={draft.draftProvider}
                isOAuthProvider={draft.isOAuthProvider}
                effectiveBaseUrl={draft.effectiveBaseUrl}
                onBaseUrlChange={(v) =>
                  draft.setDraftBaseUrls((prev) => ({ ...prev, [draft.draftProvider]: v }))
                }
                apiKey={draft.draftApiKeys[draft.draftProvider]}
                onApiKeyChange={(v) =>
                  draft.setDraftApiKeys((prev) => ({ ...prev, [draft.draftProvider]: v }))
                }
                oauth={oauth}
              />
            </Card>
          </section>

          {/* Model section */}
          <section ref={modelRef} aria-labelledby="section-model-heading">
            <h2 id="section-model-heading" className="sr-only">
              Runtime Model
            </h2>
            <ModelSettingsCard
              provider={draft.draftProvider}
              model={draft.draftModel}
              setModel={draft.setDraftModel}
              effectiveBaseUrl={draft.effectiveBaseUrl}
            />
          </section>

          {/* Mobile save bar — shown only below xl breakpoint */}
          <div className="xl:hidden">
            <div className="glass-panel rounded-[1.65rem] p-4 space-y-3">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,var(--color-surface-overlay-strong),transparent)]" />
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm text-[var(--color-text-muted)]">
                  {draft.isDirty ? (
                    <span className="text-[var(--color-warning-fg)]">Unsaved changes</span>
                  ) : (
                    <span className="text-[var(--color-success-fg)]">Saved locally</span>
                  )}
                </p>
                <Button onClick={draft.handleSave} disabled={!draft.isDirty}>
                  <Save className="h-4 w-4" aria-hidden="true" />
                  Save Settings
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Sticky summary rail — desktop only */}
        <aside className="hidden xl:block" aria-label="Settings summary">
          <div className="sticky top-4">
            <SettingsSummaryRail
              backendLabel={draft.backendLabel}
              provider={draft.draftProvider}
              activeAuthMode={draft.activeAuthMode}
              effectiveBaseUrl={draft.effectiveBaseUrl}
              model={draft.draftModel}
              isDirty={draft.isDirty}
              onSave={draft.handleSave}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
