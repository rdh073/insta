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
