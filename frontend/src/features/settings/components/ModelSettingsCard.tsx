import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { ChevronDown, Cpu, RefreshCw } from 'lucide-react';
import { cn } from '../../../lib/cn';
import { Card } from '../../../components/ui/Card';
import { PROVIDERS, type AIProvider } from '../../../store/settings';
import { ollamaApi, type OllamaModelEntry } from '../../../api/provider-settings';

interface Props {
  provider: AIProvider;
  model: string;
  setModel: (m: string) => void;
  effectiveBaseUrl: string;
}

const OLLAMA_MODEL_DEBOUNCE_MS = 300;

interface OllamaModelSelectProps {
  baseUrl: string;
  model: string;
  setModel: (m: string) => void;
}

function OllamaModelSelect({ baseUrl, model, setModel }: OllamaModelSelectProps) {
  const [models, setModels] = useState<OllamaModelEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [reachable, setReachable] = useState(true);
  const fetchSeq = useRef(0);

  const fetchModels = useCallback(
    async (url: string, options: { silent?: boolean } = {}) => {
      const seq = ++fetchSeq.current;
      setLoading(true);
      try {
        const response = await ollamaApi.listModels(url.trim() || undefined);
        if (seq !== fetchSeq.current) return;
        setModels(response.models);
        setReachable(true);
        if (response.models.length > 0 && !response.models.some((m) => m.id === model)) {
          setModel(response.models[0].id);
        }
      } catch (err) {
        if (seq !== fetchSeq.current) return;
        setModels([]);
        setReachable(false);
        if (!options.silent) {
          toast.error(err instanceof Error ? err.message : 'Failed to load Ollama models');
        }
      } finally {
        if (seq === fetchSeq.current) setLoading(false);
      }
    },
    [model, setModel],
  );

  // Debounced auto-fetch on base URL changes (and on first mount).
  useEffect(() => {
    const handle = window.setTimeout(() => {
      void fetchModels(baseUrl, { silent: true });
    }, OLLAMA_MODEL_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [baseUrl, fetchModels]);

  const placeholder = reachable ? 'No models reported by server' : 'Cannot reach server';
  const disabled = models.length === 0;

  return (
    <div className="space-y-2">
      <label className="field-label" htmlFor="settings-model-select">
        Model
      </label>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <select
            id="settings-model-select"
            value={disabled ? '' : model}
            onChange={(e) => setModel(e.target.value)}
            className="glass-select w-full text-sm disabled:cursor-not-allowed disabled:opacity-60"
            aria-label="Ollama model"
            disabled={disabled}
          >
            {disabled ? (
              <option value="" disabled>
                {loading ? 'Loading models…' : placeholder}
              </option>
            ) : (
              <>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}
                  </option>
                ))}
                {!models.some((m) => m.id === model) && model ? (
                  <option value={model}>{model} (not installed)</option>
                ) : null}
              </>
            )}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]"
            aria-hidden="true"
          />
        </div>
        <button
          type="button"
          onClick={() => void fetchModels(baseUrl)}
          disabled={loading}
          aria-label="Refresh models"
          title="Refresh models"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--color-border-fainter)] bg-[var(--color-surface-overlay-soft)] text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-muted)] hover:text-[var(--color-text-primary)] disabled:opacity-50"
        >
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} aria-hidden="true" />
        </button>
      </div>
      <p className="field-hint">
        {loading
          ? 'Fetching models from Ollama…'
          : reachable
            ? `${models.length} model${models.length === 1 ? '' : 's'} reported by ${baseUrl}`
            : `Cannot reach ${baseUrl} — check the base URL and that the server is running.`}
      </p>
    </div>
  );
}

export function ModelSettingsCard({ provider, model, setModel, effectiveBaseUrl }: Props) {
  const cfg = PROVIDERS[provider];
  const isOllama = provider === 'ollama';

  return (
    <Card className="space-y-5" id="settings-model">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[var(--color-accent-blue-bg)]">
          <Cpu className="h-4 w-4 text-[var(--color-accent-blue-soft)]" aria-hidden="true" />
        </div>
        <div>
          <p className="text-kicker">Model Defaults</p>
          <h2 className="mt-1 text-base font-semibold text-[var(--color-text-strong)]">Runtime model</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Default model for <span className="text-[var(--color-accent-violet)]">{cfg.label}</span>. Can be
            overridden per-conversation in the copilot.
          </p>
        </div>
      </div>

      {/* Model input — dynamic select for Ollama, free-text when no fixed model list, dropdown otherwise */}
      {isOllama ? (
        <OllamaModelSelect baseUrl={effectiveBaseUrl} model={model} setModel={setModel} />
      ) : (
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
                className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-muted)]"
                aria-hidden="true"
              />
            </div>
          )}
        </div>
      )}

      {/* Quick-pick chips — only shown when there are fixed models */}
      {!isOllama && cfg.models.length > 0 && (
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
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg-canvas)]',
                  m === model
                    ? 'border border-[var(--color-info-border)] bg-[var(--color-info-bg)] text-[var(--color-info-fg)]'
                    : 'border border-[var(--color-border-fainter)] bg-[var(--color-surface-overlay-soft)] text-[var(--color-text-muted)] hover:border-[var(--color-border-muted)] hover:text-[var(--color-text-primary)]',
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
