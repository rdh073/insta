import { useState } from 'react';
import { Database, Globe, Shield } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { AccountRoutingTab } from '../features/proxy/components/AccountRoutingTab';
import { ProxyPoolTab } from '../features/proxy/components/ProxyPoolTab';

type Tab = 'routing' | 'pool';

export function ProxyPage() {
  const [tab, setTab] = useState<Tab>('routing');

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Proxy Management"
        title="Proxy &amp; Routing"
        description="Manage per-account proxy routing and maintain a reusable pool of vetted elite proxies."
        icon={<Shield className="h-6 w-6 text-[#7dcfff]" />}
      />

      {/* Tab bar */}
      <div className="flex gap-1 rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] p-1">
        {(
          [
            { id: 'routing' as Tab, label: 'Account Routing', icon: Globe },
            { id: 'pool'    as Tab, label: 'Proxy Pool',      icon: Database },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-[1rem] px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
              tab === id
                ? 'bg-[rgba(125,207,255,0.12)] text-[#7dcfff]'
                : 'text-[#7f8bb3] hover:text-[#eef4ff]'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'routing' ? <AccountRoutingTab /> : <ProxyPoolTab />}
    </div>
  );
}
