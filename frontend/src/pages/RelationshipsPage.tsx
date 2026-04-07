import { useMemo, useState } from 'react';
import { ArrowLeftRight, UserMinus, UserPlus, Users } from 'lucide-react';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { useAccountStore } from '../store/accounts';
import { ActionTab } from '../features/relationships/components/ActionTab';
import { CrossFollowTab } from '../features/relationships/components/CrossFollowTab';
import type { RelationshipTab } from '../features/relationships/types';

const tabs = [
  { id: 'follow' as RelationshipTab, label: 'Follow', icon: UserPlus },
  { id: 'unfollow' as RelationshipTab, label: 'Unfollow', icon: UserMinus },
  { id: 'cross-follow' as RelationshipTab, label: 'Cross-Follow', icon: ArrowLeftRight },
] as const;

export function RelationshipsPage() {
  const [tab, setTab] = useState<RelationshipTab>('follow');
  const accounts = useAccountStore((s) => s.accounts);
  const activeCount = useMemo(() => accounts.filter((a) => a.status === 'active').length, [accounts]);

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Social Graph"
        title="Relationships"
        description="Follow, unfollow, and cross-follow users across multiple managed accounts."
        icon={<Users className="h-6 w-6 text-[#bb9af7]" />}
      >
        <div className="metric-grid mt-2">
          <HeaderStat label="Total Accounts" value={accounts.length} tone="blue" />
          <HeaderStat label="Active" value={activeCount} tone="green" />
        </div>
      </PageHeader>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] p-1">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-[1rem] px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
              tab === id
                ? 'bg-[rgba(187,154,247,0.12)] text-[#bb9af7]'
                : 'text-[#7f8bb3] hover:text-[#eef4ff]'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'follow' && <ActionTab action="follow" />}
      {tab === 'unfollow' && <ActionTab action="unfollow" />}
      {tab === 'cross-follow' && <CrossFollowTab />}
    </div>
  );
}
