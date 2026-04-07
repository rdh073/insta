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
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7dcfff]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1020]',
        active
          ? 'border-[rgba(125,207,255,0.36)] bg-[rgba(125,207,255,0.10)] shadow-[0_0_24px_rgba(125,207,255,0.06)]'
          : 'border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] hover:border-[rgba(162,179,229,0.22)] hover:bg-[rgba(255,255,255,0.05)]',
      )}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.7rem] transition-colors duration-200',
            active
              ? 'bg-[rgba(125,207,255,0.18)] text-[#7dcfff]'
              : 'bg-[rgba(255,255,255,0.06)] text-[#7f8bb3] group-hover:text-[#b0bae0]',
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
              active ? 'text-[#eef6ff]' : 'text-[#8f9bc4] group-hover:text-[#eef4ff]',
            )}
          >
            {cfg.label}
          </p>
          <p className="mt-0.5 truncate text-xs text-[#59658c]">
            {isOAuth ? 'OAuth' : 'API Key'} &middot; {cfg.models.length > 0 ? `${cfg.models.length} models` : 'custom model'}
          </p>
        </div>
        {active && (
          <div
            className="h-2 w-2 shrink-0 rounded-full bg-[#7dcfff] shadow-[0_0_6px_rgba(125,207,255,0.5)]"
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
