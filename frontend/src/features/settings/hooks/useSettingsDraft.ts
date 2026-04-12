import { useState, useCallback, useEffect } from 'react';
import toast from 'react-hot-toast';
import { describeBackend } from '../../../lib/api-base';
import { PROVIDERS, useSettingsStore, type AIProvider } from '../../../store/settings';
import { providerSettingsApi } from '../../../api/provider-settings';

export interface SettingsDraft {
  // Draft state
  draftBackendUrl: string;
  setDraftBackendUrl: (v: string) => void;
  draftBackendApiKey: string;
  setDraftBackendApiKey: (v: string) => void;
  draftProvider: AIProvider;
  handleProviderChange: (next: AIProvider) => void;
  draftModel: string;
  setDraftModel: (m: string) => void;
  draftApiKeys: Record<AIProvider, string>;
  setDraftApiKeys: React.Dispatch<React.SetStateAction<Record<AIProvider, string>>>;
  draftBaseUrls: Partial<Record<AIProvider, string>>;
  setDraftBaseUrls: React.Dispatch<React.SetStateAction<Partial<Record<AIProvider, string>>>>;
  // Computed
  isDirty: boolean;
  backendLabel: string;
  isOAuthProvider: boolean;
  activeAuthMode: 'OAuth' | 'API Key';
  effectiveBaseUrl: string;
  // Actions
  handleSave: () => void;
}

export function useSettingsDraft(): SettingsDraft {
  const storeBackendUrl = useSettingsStore((s) => s.backendUrl);
  const storeProvider = useSettingsStore((s) => s.provider);
  const storeModel = useSettingsStore((s) => s.model);
  const storeApiKeys = useSettingsStore((s) => s.apiKeys);
  const storeProviderBaseUrls = useSettingsStore((s) => s.providerBaseUrls);

  const storeBackendApiKey = useSettingsStore((s) => s.backendApiKey);

  const setConnection = useSettingsStore((s) => s.setConnection);
  const setProvider = useSettingsStore((s) => s.setProvider);
  const setModel = useSettingsStore((s) => s.setModel);
  const setApiKey = useSettingsStore((s) => s.setApiKey);
  const setProviderBaseUrl = useSettingsStore((s) => s.setProviderBaseUrl);

  const [draftBackendUrl, setDraftBackendUrl] = useState(storeBackendUrl);
  const [draftBackendApiKey, setDraftBackendApiKey] = useState(storeBackendApiKey);
  const [draftProvider, setDraftProvider] = useState<AIProvider>(storeProvider);
  const [draftModel, setDraftModel] = useState(storeModel);
  const [draftApiKeys, setDraftApiKeys] = useState<Record<AIProvider, string>>({
    ...storeApiKeys,
  });
  const [draftBaseUrls, setDraftBaseUrls] = useState<Partial<Record<AIProvider, string>>>({
    ...storeProviderBaseUrls,
  });

  const isDirty =
    draftBackendUrl !== storeBackendUrl ||
    draftBackendApiKey !== storeBackendApiKey ||
    draftProvider !== storeProvider ||
    draftModel !== storeModel ||
    (Object.keys(draftApiKeys) as AIProvider[]).some(
      (k) => draftApiKeys[k] !== storeApiKeys[k],
    ) ||
    (Object.keys(draftBaseUrls) as AIProvider[]).some(
      (k) => draftBaseUrls[k] !== storeProviderBaseUrls[k],
    );

  const handleProviderChange = useCallback((next: AIProvider) => {
    setDraftProvider(next);
    setDraftModel(PROVIDERS[next].defaultModel);
  }, []);

  const handleSave = useCallback(() => {
    setConnection(draftBackendUrl, draftBackendApiKey);
    setProvider(draftProvider);
    setModel(draftModel);
    (Object.keys(draftApiKeys) as AIProvider[]).forEach((p) => setApiKey(p, draftApiKeys[p]));
    (Object.keys(draftBaseUrls) as AIProvider[]).forEach((p) => {
      if (draftBaseUrls[p] !== undefined) setProviderBaseUrl(p, draftBaseUrls[p]!);
    });

    // Persist provider settings to backend (fire-and-forget — localStorage is primary)
    const providerPayload: Record<string, { api_key: string; model: string; base_url?: string | null }> = {};
    (Object.keys(PROVIDERS) as AIProvider[]).forEach((p) => {
      const apiKey = draftApiKeys[p] ?? '';
      const baseUrl = draftBaseUrls[p] ?? null;
      if (apiKey || baseUrl) {
        // Only save providers that have something set (avoid cluttering backend with empty entries)
        providerPayload[p] = {
          api_key: apiKey,
          model: p === draftProvider ? draftModel : PROVIDERS[p].defaultModel,
          base_url: baseUrl || null,
        };
      }
    });
    if (Object.keys(providerPayload).length > 0) {
      providerSettingsApi.save(providerPayload).catch(() => {
        // Backend sync failure is non-fatal — local save already succeeded
      });
    }

    toast.success('Settings saved');
  }, [
    draftBackendUrl,
    draftBackendApiKey,
    draftProvider,
    draftModel,
    draftApiKeys,
    draftBaseUrls,
    setConnection,
    setProvider,
    setModel,
    setApiKey,
    setProviderBaseUrl,
  ]);

  // Load base_url overrides from backend on mount (base_url only — api_key is masked server-side)
  useEffect(() => {
    providerSettingsApi.get().then((data) => {
      setDraftBaseUrls((prev) => {
        const merged = { ...prev };
        for (const [provider, entry] of Object.entries(data.providers)) {
          // Only fill in missing base_url from backend; don't overwrite local edits
          if (entry.base_url && !(provider in prev)) {
            merged[provider as AIProvider] = entry.base_url;
          }
        }
        return merged;
      });
    }).catch(() => {
      // Backend may not be reachable yet — silently ignore
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const backendLabel = describeBackend(draftBackendUrl);
  const isOAuthProvider = draftProvider === 'openai_codex' || draftProvider === 'claude_code';
  const activeAuthMode: 'OAuth' | 'API Key' = isOAuthProvider ? 'OAuth' : 'API Key';
  const effectiveBaseUrl =
    draftBaseUrls[draftProvider] ?? PROVIDERS[draftProvider].defaultBaseUrl ?? '';

  return {
    draftBackendUrl,
    setDraftBackendUrl,
    draftBackendApiKey,
    setDraftBackendApiKey,
    draftProvider,
    handleProviderChange,
    draftModel,
    setDraftModel,
    draftApiKeys,
    setDraftApiKeys,
    draftBaseUrls,
    setDraftBaseUrls,
    isDirty,
    backendLabel,
    isOAuthProvider,
    activeAuthMode,
    effectiveBaseUrl,
    handleSave,
  };
}
