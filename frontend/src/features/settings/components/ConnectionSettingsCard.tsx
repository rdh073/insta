import { Unplug, Globe, KeyRound } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';

interface Props {
  url: string;
  setUrl: (v: string) => void;
  backendLabel: string;
  urlError?: string;
  apiKey: string;
  setApiKey: (v: string) => void;
}

export function ConnectionSettingsCard({ url, setUrl, backendLabel, urlError, apiKey, setApiKey }: Props) {
  return (
    <Card className="space-y-5" id="settings-connection">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[var(--color-info-bg)]">
          <Globe className="h-4 w-4 text-[var(--color-info-fg)]" aria-hidden="true" />
        </div>
        <div>
          <p className="text-kicker">Backend Access</p>
          <h2 className="mt-1 text-base font-semibold text-[var(--color-text-strong)]">Connection target</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Drives all frontend API requests and the backend-managed OAuth callback flow.
          </p>
        </div>
      </div>

      <Input
        id="settings-backend-url"
        label="Backend URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://localhost:8000"
        hint="Used by all API requests and OAuth exchange endpoints."
        error={urlError}
      />

      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[var(--color-accent-violet-bg-soft)]">
          <KeyRound className="h-4 w-4 text-[var(--color-accent-violet)]" aria-hidden="true" />
        </div>
        <div className="flex-1">
          <p className="field-label mb-1">API Key</p>
          <Input
            id="settings-backend-api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Leave empty if server has no API_KEY set"
            hint="Sent as X-API-Key header on every request. Set API_KEY env var on the server to enable."
          />
        </div>
      </div>

      <div
        className={`flex items-start gap-3 rounded-[1.25rem] border p-4 ${
          urlError
            ? 'border-[var(--color-error-border)] bg-[var(--color-error-bg)]'
            : 'border-[var(--color-success-border)] bg-[var(--color-success-bg)]'
        }`}
      >
        <Unplug
          className={`mt-0.5 h-4 w-4 shrink-0 ${urlError ? 'text-[var(--color-error-fg)]' : 'text-[var(--color-success-fg)]'}`}
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-medium text-[var(--color-text-strong)]">{backendLabel}</p>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            {apiKey ? 'API key configured — sent with every request.' : 'No API key set — server must have API_KEY disabled.'}
          </p>
        </div>
      </div>
    </Card>
  );
}
