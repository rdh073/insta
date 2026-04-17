import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AIProvider =
  | 'openai'
  | 'gemini'
  | 'deepseek'
  | 'antigravity'
  | 'openai_compatible'
  | 'ollama'
  | 'openai_codex'
  | 'claude_code';

interface ProviderConfig {
  label: string;
  placeholder: string;
  defaultModel: string;
  models: string[];
  hint: string;
  defaultBaseUrl?: string;
}

export const PROVIDERS: Record<AIProvider, ProviderConfig> = {
  openai: {
    label: 'OpenAI',
    placeholder: 'sk-...',
    defaultModel: 'gpt-5.4-mini',
    models: [
      'gpt-5.4',
      'gpt-5.4-mini',
      'gpt-5.4-nano',
      'gpt-5.4-pro',
      'gpt-5.3-chat-latest',
      'gpt-5.2',
      'gpt-5.2-pro',
      'gpt-5.1',
      'gpt-5',
      'gpt-5-pro',
      'gpt-4.1',
      'gpt-4.1-mini',
      'gpt-4o',
      'gpt-4o-mini',
      'o4-mini',
      'o3-pro',
      'o3',
      'o3-mini',
    ],
    hint: 'openai.com — GPT-5 family (flagship), GPT-4 legacy, and o-series reasoning',
  },
  gemini: {
    label: 'Google Gemini',
    placeholder: 'AIza...',
    defaultModel: 'gemini-2.5-flash',
    models: [
      'gemini-2.5-pro',
      'gemini-2.5-flash',
      'gemini-2.5-flash-lite',
      'gemini-3-pro-preview',
      'gemini-3.1-pro-preview',
      'gemini-3-flash-preview',
      'gemini-2.0-flash',
      'gemini-2.0-flash-lite',
    ],
    hint: 'aistudio.google.com — Gemini 2.5 Flash is free-tier friendly',
  },
  deepseek: {
    label: 'DeepSeek',
    placeholder: 'sk-...',
    defaultModel: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    hint: 'platform.deepseek.com — Very affordable pricing',
  },
  antigravity: {
    label: 'Antigravity',
    placeholder: 'sk-antigravity',
    defaultModel: 'claude-sonnet-4-5',
    models: [
      'claude-sonnet-4-5',
      'claude-opus-4-5',
      'claude-haiku-4-5',
      'claude-3-7-sonnet-20250219',
      'gpt-4o',
      'gpt-4o-mini',
      'gemini-2.0-flash',
    ],
    hint: 'Local Antigravity proxy — routes through your configured free/pro accounts',
    defaultBaseUrl: 'http://127.0.0.1:8045/v1',
  },
  openai_compatible: {
    label: 'OpenAI Compatible',
    placeholder: 'sk-... or leave empty',
    defaultModel: '',
    models: [],
    hint: 'Any OpenAI-compatible server — Ollama, LM Studio, vLLM, LocalAI, Groq, Together, Mistral, etc.',
    defaultBaseUrl: 'http://localhost:11434/v1',
  },
  ollama: {
    label: 'Ollama',
    placeholder: 'http://host:port/v1 (no API key)',
    defaultModel: 'llama3.2:3b',
    models: [],
    hint: 'Self-hosted or remote Ollama — no API key required',
    defaultBaseUrl: 'http://localhost:11434/v1',
  },
  openai_codex: {
    label: 'OpenAI Codex',
    placeholder: 'OAuth-managed (no direct API key)',
    defaultModel: 'gpt-5.3-codex',
    models: [
      'gpt-5',
      'gpt-5-codex',
      'gpt-5-codex-mini',
      'gpt-5.1',
      'gpt-5.1-codex',
      'gpt-5.1-codex-mini',
      'gpt-5.1-codex-max',
      'gpt-5.2',
      'gpt-5.2-codex',
      'gpt-5.3-codex',
      'gpt-5.3-codex-spark',
      'gpt-5.4',
      'codex-mini-latest',
    ],
    hint: 'openai.com — OAuth-managed. Complete OAuth onboarding from Settings.',
  },
  claude_code: {
    label: 'Claude Code',
    placeholder: 'OAuth-managed (no direct API key)',
    defaultModel: 'claude-sonnet-4-6',
    models: [
      'claude-opus-4-6',
      'claude-sonnet-4-6',
      'claude-opus-4-5-20251101',
      'claude-sonnet-4-5-20250929',
      'claude-haiku-4-5-20251001',
      'claude-opus-4-1-20250805',
      'claude-opus-4-20250514',
      'claude-sonnet-4-20250514',
      'claude-3-7-sonnet-20250219',
      'claude-3-5-haiku-20241022',
    ],
    hint: 'anthropic.com — OAuth-managed. Complete OAuth onboarding from Settings.',
  },
};

interface SettingsStore {
  backendUrl: string;
  backendApiKey: string;
  provider: AIProvider;
  model: string;
  dashboardToken: string;
  apiKeys: Record<AIProvider, string>;
  providerBaseUrls: Partial<Record<AIProvider, string>>;
  setBackendUrl: (u: string) => void;
  setBackendApiKey: (key: string) => void;
  setConnection: (backendUrl: string, backendApiKey: string) => void;
  setProvider: (p: AIProvider) => void;
  setModel: (m: string) => void;
  setDashboardToken: (token: string) => void;
  lockSession: () => void;
  setApiKey: (provider: AIProvider, key: string) => void;
  setProviderBaseUrl: (provider: AIProvider, url: string) => void;
}

const LEGACY_BACKEND_URL = 'http://localhost:8000';
const DEFAULT_BACKEND_URL = import.meta.env.VITE_BACKEND_URL?.trim() || '';
const DEFAULT_BACKEND_API_KEY = import.meta.env.VITE_BACKEND_API_KEY?.trim() || '';

const EMPTY_API_KEYS: Record<AIProvider, string> = {
  openai: '',
  gemini: '',
  deepseek: '',
  antigravity: 'sk-antigravity',
  openai_compatible: '',
  ollama: '',
  openai_codex: '',
  claude_code: '',
};

function normalizePersistedSettings(
  persistedState: Partial<SettingsStore> | undefined
): Partial<SettingsStore> {
  if (!persistedState) {
    return {};
  }

  const normalized: Partial<SettingsStore> = { ...persistedState };

  if (!normalized.backendUrl || normalized.backendUrl === LEGACY_BACKEND_URL) {
    normalized.backendUrl = DEFAULT_BACKEND_URL;
  }

  // If the env var is set and the user hasn't saved a key yet, use the env default.
  if (!normalized.backendApiKey && DEFAULT_BACKEND_API_KEY) {
    normalized.backendApiKey = DEFAULT_BACKEND_API_KEY;
  }

  // Backfill any provider keys that were added after the persisted snapshot was
  // written (e.g. 'ollama'). Existing keys are preserved.
  normalized.apiKeys = { ...EMPTY_API_KEYS, ...(normalized.apiKeys ?? {}) };

  return normalized;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      backendUrl: DEFAULT_BACKEND_URL,
      backendApiKey: DEFAULT_BACKEND_API_KEY,
      provider: 'openai',
      model: 'gpt-5.4-mini',
      dashboardToken: '',
      apiKeys: {
        openai: '',
        gemini: '',
        deepseek: '',
        antigravity: 'sk-antigravity',
        openai_compatible: '',
        ollama: '',
        openai_codex: '',
        claude_code: '',
      },
      providerBaseUrls: {},
      setBackendUrl: (backendUrl) => set({ backendUrl }),
      setBackendApiKey: (backendApiKey) => set({ backendApiKey }),
      setConnection: (backendUrl, backendApiKey) => set({ backendUrl, backendApiKey }),
      setDashboardToken: (dashboardToken) => set({ dashboardToken }),
      lockSession: () => set({ dashboardToken: '' }),
      setProvider: (provider) =>
        set((state) => ({
          provider,
          model:
            state.provider === provider
              ? state.model
              : PROVIDERS[provider].defaultModel,
        })),
      setModel: (model) => set({ model }),
      setApiKey: (provider, key) =>
        set((state) => ({ apiKeys: { ...state.apiKeys, [provider]: key } })),
      setProviderBaseUrl: (provider, url) =>
        set((state) => ({ providerBaseUrls: { ...state.providerBaseUrls, [provider]: url } })),
    }),
    {
      name: 'insta-settings',
      partialize: (s) => ({
        backendUrl: s.backendUrl,
        backendApiKey: s.backendApiKey,
        provider: s.provider,
        model: s.model,
        dashboardToken: s.dashboardToken,
        apiKeys: s.apiKeys,
        providerBaseUrls: s.providerBaseUrls,
      }),
      merge: (persistedState, currentState) => ({
        ...currentState,
        ...normalizePersistedSettings(persistedState as Partial<SettingsStore> | undefined),
      }),
    }
  )
);
