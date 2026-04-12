import { Key, ShieldCheck } from 'lucide-react';
import { cn } from '../../../lib/cn';
import { PROVIDERS, type AIProvider } from '../../../store/settings';

interface ProviderCardProps {
  id: AIProvider;
  active: boolean;
  onClick: () => void;
}

function ProviderCard({ id, active, onClick }: ProviderCardProps) {
  const cfg = PROVIDERS[id];
  const isOAuth = id === 'openai_codex' || id === 'claude_code';

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'group cursor-pointer rounded-[1.25rem] border p-4 text-left transition-all duration-200',
        'min-h-[2.75rem]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-canvas)]',
        active
          ? 'border-[var(--color-info-border)] bg-[var(--color-info-bg)] shadow-[0_0_24px_var(--color-info-shadow)]'
          : 'border-[var(--color-border-faint)] bg-[var(--color-surface-overlay-soft)] hover:border-[var(--color-border-muted)] hover:bg-[var(--color-surface-overlay)]',
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.7rem] transition-colors duration-200',
            active
              ? 'bg-[var(--color-info-bg-strong)] text-[var(--color-info-fg)]'
              : 'bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)] group-hover:text-[var(--color-text-primary)]',
          )}
        >
          {isOAuth ? (
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Key className="h-4 w-4" aria-hidden="true" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              'text-sm font-semibold transition-colors duration-200',
              active ? 'text-[var(--color-text-strong)]' : 'text-[var(--color-text-muted)] group-hover:text-[var(--color-text-strong)]',
            )}
          >
            {cfg.label}
          </p>
          <p className="mt-0.5 truncate text-xs text-[var(--color-text-subtle)]">
            {isOAuth ? 'OAuth' : 'API Key'} &middot; {cfg.models.length > 0 ? `${cfg.models.length} models` : 'custom model'}
          </p>
        </div>
        {active && (
          <div
            className="h-2 w-2 shrink-0 rounded-full bg-[var(--color-info-fg)] shadow-[0_0_6px_var(--color-info-glow)]"
            aria-hidden="true"
          />
        )}
      </div>
    </button>
  );
}

interface Props {
  provider: AIProvider;
  onProviderChange: (p: AIProvider) => void;
}

export function ProviderSelectorGrid({ provider, onProviderChange }: Props) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" role="group" aria-label="Select AI provider">
      {(Object.keys(PROVIDERS) as AIProvider[]).map((id) => (
        <ProviderCard
          key={id}
          id={id}
          active={provider === id}
          onClick={() => onProviderChange(id)}
        />
      ))}
    </div>
  );
}
