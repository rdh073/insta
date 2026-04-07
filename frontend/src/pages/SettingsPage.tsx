import { ShieldCheck } from 'lucide-react';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { PROVIDERS, useSettingsStore } from '../store/settings';
import { describeBackend } from '../lib/api-base';
import { SettingsWorkspace } from '../features/settings/components/SettingsWorkspace';

export function SettingsPage() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const provider = useSettingsStore((s) => s.provider);
  const model = useSettingsStore((s) => s.model);
  const apiKeys = useSettingsStore((s) => s.apiKeys);

  const cfg = PROVIDERS[provider];
  const backendLabel = describeBackend(backendUrl);
  const isOAuthProvider = provider === 'openai_codex' || provider === 'claude_code';
  // Show a dot in the Auth stat if the active provider has a key or OAuth is in use
  const hasKey = isOAuthProvider || Boolean(apiKeys[provider]);

  return (
    <div className="page-shell max-w-[90rem] space-y-6">
      <PageHeader
        eyebrow="Control Plane"
        title="System Settings"
        description="Backend routing, AI provider credentials, and model defaults."
        icon={<ShieldCheck className="h-6 w-6 text-[#7dcfff]" />}
      >
        <div className="metric-grid">
          <HeaderStat label="Backend" value={backendLabel || 'Same origin'} tone="cyan" />
          <HeaderStat label="Provider" value={cfg.label} tone="violet" />
          <HeaderStat label="Model" value={model} tone="blue" />
          <HeaderStat
            label="Auth"
            value={isOAuthProvider ? 'OAuth' : hasKey ? 'API Key ✓' : 'API Key'}
            tone={isOAuthProvider ? 'green' : 'amber'}
          />
        </div>
      </PageHeader>

      <SettingsWorkspace />
    </div>
  );
}
