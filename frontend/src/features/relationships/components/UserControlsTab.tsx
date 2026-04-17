import { useMemo, useState } from 'react';
import { UserCog } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { useAccountStore } from '../../../store/accounts';
import { UserRelationshipControls } from './UserRelationshipControls';

export function UserControlsTab() {
  const accounts = useAccountStore((s) => s.accounts);
  const activeAccounts = useMemo(
    () => accounts.filter((a) => a.status === 'active'),
    [accounts],
  );

  const [accountId, setAccountId] = useState<string>(() => activeAccounts[0]?.id ?? '');
  const [targetInput, setTargetInput] = useState('');

  const cleanedTarget = targetInput.trim().replace(/^@/, '');

  return (
    <div className="space-y-5">
      <Card>
        <div className="space-y-4 p-1">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[0.9rem] bg-[rgba(187,154,247,0.12)] text-[#bb9af7]">
              <UserCog className="h-5 w-5" />
            </div>
            <div>
              <p className="field-label mb-1">Per-user controls</p>
              <p className="field-hint">
                Choose an acting account and a target user to mute their posts/stories or toggle push
                notifications. Settings are scoped to the acting account.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5">
              <span className="field-label">Acting account</span>
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="glass-select"
              >
                {activeAccounts.length === 0 ? (
                  <option value="">No active accounts</option>
                ) : (
                  activeAccounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      @{acc.username}
                    </option>
                  ))
                )}
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="field-label">Target username</span>
              <input
                value={targetInput}
                onChange={(e) => setTargetInput(e.target.value)}
                placeholder="@someone"
                className="glass-field font-mono"
              />
            </label>
          </div>
        </div>
      </Card>

      {accountId && cleanedTarget ? (
        <UserRelationshipControls accountId={accountId} targetUsername={cleanedTarget} />
      ) : (
        <Card>
          <p className="text-sm text-[#7f8bb3]">
            Select an acting account and enter a target username to unlock the mute and notification
            toggles.
          </p>
        </Card>
      )}
    </div>
  );
}
