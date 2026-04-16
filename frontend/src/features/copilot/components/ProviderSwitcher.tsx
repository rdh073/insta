import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { CheckCircle, ChevronDown, RefreshCw } from 'lucide-react';
import { fetchProviderModels } from '../../../api/operator-copilot';
import { useSettingsStore, PROVIDERS } from '../../../store/settings';
import type { AIProvider } from '../../../store/settings';
import { cn } from '../../../lib/cn';

const OAUTH_PROVIDERS: AIProvider[] = ['openai_codex', 'claude_code'];
const KEYLESS_PROVIDERS: AIProvider[] = ['ollama'];

export function ProviderSwitcher() {
  const provider = useSettingsStore((s) => s.provider);
  const model = useSettingsStore((s) => s.model);
  const apiKeys = useSettingsStore((s) => s.apiKeys);
  const providerBaseUrls = useSettingsStore((s) => s.providerBaseUrls);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const setProvider = useSettingsStore((s) => s.setProvider);
  const setModel = useSettingsStore((s) => s.setModel);
  const [open, setOpen] = useState(false);
  const [fetchedModels, setFetchedModels] = useState<Partial<Record<AIProvider, string[]>>>({});
  const [loadingModels, setLoadingModels] = useState<AIProvider | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  const configuredProviders = (Object.keys(PROVIDERS) as AIProvider[]).filter((p) => {
    if (OAUTH_PROVIDERS.includes(p)) return true;
    if (KEYLESS_PROVIDERS.includes(p)) return true;
    return (apiKeys[p] ?? '').trim().length > 0;
  });

  if (configuredProviders.length === 0) return null;

  const currentConfig = PROVIDERS[provider];

  async function handleFetchModels(e: React.MouseEvent, p: AIProvider) {
    e.stopPropagation();
    setLoadingModels(p);
    try {
      const models = await fetchProviderModels(
        p,
        apiKeys[p] ?? '',
        providerBaseUrls[p] || undefined,
        backendUrl,
      );
      setFetchedModels((prev) => ({ ...prev, [p]: models }));
      if (p === provider && models.length > 0 && !models.includes(model)) {
        setModel(models[0]);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to fetch models');
    } finally {
      setLoadingModels(null);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((c) => !c)}
        className="flex items-center gap-1.5 rounded-lg border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1.5 text-xs text-[#8e9ac0] transition-colors hover:border-[rgba(125,207,255,0.18)] hover:text-[#c0d8f0]"
      >
        <span className="font-medium">{currentConfig.label}</span>
        <span className="text-[#4a5578]">·</span>
        <span className="font-mono text-[11px]">{model}</span>
        <ChevronDown className={cn('h-3 w-3 text-[#4a5578] transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 min-w-[240px] overflow-hidden rounded-xl border border-[rgba(162,179,229,0.12)] bg-[rgba(9,12,22,0.96)] shadow-[0_16px_40px_rgba(4,8,18,0.5)] backdrop-blur-2xl">
          <div className="border-b border-[rgba(162,179,229,0.08)] px-3 py-2">
            <p className="text-[11px] text-[#4a5578]">Switch AI Provider</p>
          </div>
          {configuredProviders.map((p) => {
            const cfg = PROVIDERS[p];
            const isActive = p === provider;
            const isOAuth = OAUTH_PROVIDERS.includes(p);
            const availableModels = fetchedModels[p] ?? cfg.models;
            const isFetching = loadingModels === p;

            return (
              <div
                key={p}
                className={cn(
                  'border-b border-[rgba(162,179,229,0.06)] last:border-0',
                  isActive && 'bg-[rgba(125,207,255,0.05)]',
                )}
              >
                <div className="flex items-center">
                  <button
                    type="button"
                    onClick={() => {
                      setProvider(p);
                      setOpen(false);
                    }}
                    className={cn(
                      'flex flex-1 items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]',
                      isActive ? 'text-[#7dcfff]' : 'text-[#8e9ac0]',
                    )}
                  >
                    <div>
                      <p className="text-xs font-medium">{cfg.label}</p>
                      <p className="mt-0.5 font-mono text-[11px] text-[#4a5578]">
                        {isActive ? model : cfg.defaultModel}
                      </p>
                    </div>
                    {isActive && <CheckCircle className="h-3.5 w-3.5 shrink-0" />}
                  </button>
                  {!isOAuth && (
                    <button
                      type="button"
                      title="Fetch models from provider"
                      onClick={(e) => void handleFetchModels(e, p)}
                      disabled={isFetching}
                      className="mr-2 shrink-0 rounded-md p-1 text-[#4a5578] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-[#7dcfff] disabled:opacity-40"
                    >
                      <RefreshCw className={cn('h-3 w-3', isFetching && 'animate-spin')} />
                    </button>
                  )}
                </div>
                {isActive && availableModels.length > 1 && (
                  <div className="px-3 pb-2.5">
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full rounded-lg border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.04)] px-2 py-1.5 font-mono text-[11px] text-[#c0d8f0] outline-none"
                    >
                      {availableModels.map((m) => (
                        <option key={m} value={m} className="bg-[#090c16]">
                          {m}
                        </option>
                      ))}
                    </select>
                    {fetchedModels[p] && (
                      <p className="mt-1 text-[10px] text-[#374060]">{fetchedModels[p]!.length} models from provider</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
