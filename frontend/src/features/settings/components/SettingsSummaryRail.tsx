import { Save, AlertCircle, CheckCircle2, Database, Server, Key, Cpu } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { PROVIDERS, type AIProvider } from '../../../store/settings';

interface Props {
  backendLabel: string;
  provider: AIProvider;
  activeAuthMode: 'OAuth' | 'API Key' | 'Self-hosted';
  effectiveBaseUrl: string;
  model: string;
  isDirty: boolean;
  onSave: () => void;
}

interface SummaryRowProps {
  icon: React.ElementType;
  label: string;
  value: string;
  tone?: 'cyan' | 'violet' | 'green' | 'amber' | 'blue';
}

const toneColors = {
  cyan: 'text-[var(--color-info-fg)]',
  violet: 'text-[var(--color-accent-violet)]',
  green: 'text-[var(--color-success-fg)]',
  amber: 'text-[var(--color-warning-fg)]',
  blue: 'text-[var(--color-accent-blue-soft)]',
};

function SummaryRow({ icon: Icon, label, value, tone = 'blue' }: SummaryRowProps) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-[var(--color-surface-overlay)]">
        <Icon className="h-3.5 w-3.5 text-[var(--color-text-subtle)]" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-[var(--color-text-subtle)]">{label}</p>
        <p className={`mt-0.5 truncate text-sm font-medium ${toneColors[tone]}`}>{value}</p>
      </div>
    </div>
  );
}

export function SettingsSummaryRail({
  backendLabel,
  provider,
  activeAuthMode,
  effectiveBaseUrl,
  model,
  isDirty,
  onSave,
}: Props) {
  const cfg = PROVIDERS[provider];

  return (
    <div className="space-y-4">
      {/* Draft summary card */}
      <div className="glass-panel rounded-[1.65rem] p-4 space-y-1">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,var(--color-surface-overlay-strong),transparent)]" />
        <p className="text-kicker !text-[0.6rem] mb-2">Draft runtime</p>

        <SummaryRow icon={Server} label="Backend" value={backendLabel || 'Same origin'} tone="cyan" />

        <div className="h-px bg-[var(--color-border-fainter)]" />

        <SummaryRow icon={Key} label="Provider" value={cfg.label} tone="violet" />

        <SummaryRow
          icon={Key}
          label="Auth mode"
          value={activeAuthMode}
          tone={activeAuthMode === 'OAuth' ? 'green' : activeAuthMode === 'Self-hosted' ? 'cyan' : 'amber'}
        />

        {effectiveBaseUrl && (
          <>
            <div className="h-px bg-[var(--color-border-fainter)]" />
            <SummaryRow icon={Database} label="Base URL" value={effectiveBaseUrl} tone="blue" />
          </>
        )}

        <div className="h-px bg-[var(--color-border-fainter)]" />

        <SummaryRow icon={Cpu} label="Model" value={model} tone="blue" />
      </div>

      {/* Save panel */}
      <div className="glass-panel rounded-[1.65rem] p-4 space-y-3">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,var(--color-surface-overlay-strong),transparent)]" />

        {/* Dirty state indicator */}
        <div className="flex items-center gap-2">
          {isDirty ? (
            <>
              <AlertCircle className="h-3.5 w-3.5 shrink-0 text-[var(--color-warning-fg)]" aria-hidden="true" />
              <p className="text-xs font-medium text-[var(--color-warning-fg)]">Unsaved changes</p>
            </>
          ) : (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[var(--color-success-fg)]" aria-hidden="true" />
              <p className="text-xs font-medium text-[var(--color-success-fg)]">Saved locally</p>
            </>
          )}
        </div>

        <Button onClick={onSave} className="w-full" disabled={!isDirty}>
          <Save className="h-4 w-4" aria-hidden="true" />
          Save Settings
        </Button>

        <p className="text-xs text-[var(--color-text-subtle)] leading-relaxed">
          All settings persist to localStorage. Use SQL persistence with an ENCRYPTION_KEY for
          production deployments.
        </p>
      </div>
    </div>
  );
}
