import { api } from './client';

export interface ProviderSettingEntry {
  api_key_masked: string;
  model: string;
  base_url: string | null;
}

export interface ProviderSettingsResponse {
  providers: Record<string, ProviderSettingEntry>;
}

export interface ProviderSettingPayload {
  api_key: string;
  model: string;
  base_url?: string | null;
}

export interface SaveProviderSettingsResponse {
  saved: Record<string, ProviderSettingEntry>;
  errors?: Record<string, string>;
}

export interface OllamaModelEntry {
  id: string;
  owned_by: string;
}

export interface OllamaModelsResponse {
  base_url: string;
  models: OllamaModelEntry[];
}

export interface OllamaHealthResponse {
  ok: boolean;
  base_url: string;
  model_count: number;
  latency_ms: number;
}

export const providerSettingsApi = {
  get: () =>
    api
      .get<ProviderSettingsResponse>('/dashboard/provider-settings')
      .then((r) => r.data),

  save: (settings: Record<string, ProviderSettingPayload>) =>
    api
      .put<SaveProviderSettingsResponse>('/dashboard/provider-settings', { settings })
      .then((r) => r.data),
};

export const ollamaApi = {
  listModels: (baseUrl?: string) =>
    api
      .get<OllamaModelsResponse>('/dashboard/providers/ollama/models', {
        params: baseUrl ? { base_url: baseUrl } : undefined,
      })
      .then((r) => r.data),

  health: (baseUrl?: string) =>
    api
      .get<OllamaHealthResponse>('/dashboard/providers/ollama/health', {
        params: baseUrl ? { base_url: baseUrl } : undefined,
      })
      .then((r) => r.data),
};
