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
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[rgba(125,207,255,0.12)]">
          <Globe className="h-4 w-4 text-[#7dcfff]" aria-hidden="true" />
        </div>
        <div>
          <p className="text-kicker">Backend Access</p>
          <h2 className="mt-1 text-base font-semibold text-[#eef4ff]">Connection target</h2>
          <p className="mt-1 text-sm text-[#8e9ac0]">
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
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] bg-[rgba(187,154,247,0.12)]">
          <KeyRound className="h-4 w-4 text-[#bb9af7]" aria-hidden="true" />
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
            ? 'border-[rgba(247,118,142,0.20)] bg-[rgba(247,118,142,0.05)]'
            : 'border-[rgba(158,206,106,0.16)] bg-[rgba(158,206,106,0.05)]'
        }`}
      >
        <Unplug
          className={`mt-0.5 h-4 w-4 shrink-0 ${urlError ? 'text-[#f7768e]' : 'text-[#9ece6a]'}`}
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-medium text-[#eef4ff]">{backendLabel}</p>
          <p className="mt-1 text-xs text-[#8e9ac0]">
            {apiKey ? 'API key configured — sent with every request.' : 'No API key set — server must have API_KEY disabled.'}
          </p>
        </div>
      </div>
    </Card>
  );
}
