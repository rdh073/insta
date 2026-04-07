import { ChevronDown, Cpu } from 'lucide-react';
import { cn } from '../../../lib/cn';
import { Card } from '../../../components/ui/Card';
import { PROVIDERS, type AIProvider } from '../../../store/settings';

interface Props {
  provider: AIProvider;
  model: string;
  setModel: (m: string) => void;
}

export function ModelSettingsCard({ provider, model, setModel }: Props) {
  const cfg = PROVIDERS[provider];

  return (
    <Card className="space-y-5" id="settings-model">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[rgba(122,162,247,0.12)]">
          <Cpu className="h-4 w-4 text-[#7aa2f7]" aria-hidden="true" />
        </div>
        <div>
          <p className="text-kicker">Model Defaults</p>
          <h2 className="mt-1 text-base font-semibold text-[#eef4ff]">Runtime model</h2>
          <p className="mt-1 text-sm text-[#8e9ac0]">
            Default model for <span className="text-[#bb9af7]">{cfg.label}</span>. Can be
            overridden per-conversation in the copilot.
          </p>
        </div>
      </div>

      {/* Model input — free-text when no fixed model list, dropdown otherwise */}
      <div className="space-y-2">
        <label className="field-label" htmlFor="settings-model-select">
          Model
        </label>
        {cfg.models.length === 0 ? (
          <input
            id="settings-model-select"
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g. llama3, mistral, qwen2.5-coder"
            className="glass-field w-full text-sm"
            aria-label="AI model"
          />
        ) : (
          <div className="relative">
            <select
              id="settings-model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="glass-select text-sm"
              aria-label="AI model"
            >
              {cfg.models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
              {!cfg.models.includes(model) && <option value={model}>{model}</option>}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8bb3]"
              aria-hidden="true"
            />
          </div>
        )}
      </div>

      {/* Quick-pick chips — only shown when there are fixed models */}
      {cfg.models.length > 0 && (
        <div className="space-y-2">
          <p className="text-kicker !text-[0.6rem]">Available models for {cfg.label}</p>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Quick pick model">
            {cfg.models.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setModel(m)}
                aria-pressed={m === model}
                className={cn(
                  'cursor-pointer rounded-full px-3 py-1.5 text-xs font-medium transition-all duration-150',
                  'min-h-[2.25rem]',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7dcfff]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b1020]',
                  m === model
                    ? 'border border-[rgba(125,207,255,0.32)] bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                    : 'border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] text-[#7f8bb3] hover:border-[rgba(162,179,229,0.20)] hover:text-[#b0bae0]',
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
