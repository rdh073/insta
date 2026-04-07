import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  Globe,
  Loader,
  RefreshCw,
  Search,
  Square,
  Trash2,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { accountsApi } from '../../../api/accounts';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import { Modal } from '../../../components/ui/Modal';
import { HeaderStat } from '../../../components/ui/PageHeader';
import { useAccountStore } from '../../../store/accounts';
import type { Account, ProxyCheckResult } from '../../../types';
import { ProxyTestChip } from './ProxyTestChip';

function AccountProxyCard({
  account,
  selected,
  onToggle,
  onEdit,
}: {
  account: Account;
  selected: boolean;
  onToggle: () => void;
  onEdit: () => void;
}) {
  return (
    <Card glow className="p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <button type="button" onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-4 text-left">
          <div className="mt-0.5 shrink-0">
            {selected ? (
              <CheckCircle2 className="h-5 w-5 text-[#9ece6a]" />
            ) : (
              <Square className="h-5 w-5 text-[#7f8bb3]" />
            )}
          </div>
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.2rem] border border-[rgba(125,207,255,0.16)] bg-[linear-gradient(135deg,rgba(122,162,247,0.22),rgba(125,207,255,0.12)_60%,rgba(187,154,247,0.18))] text-sm font-semibold uppercase text-[#eef4ff]">
            {account.username[0]}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-[#eef4ff]">@{account.username}</p>
              <span className="glass-chip !text-[11px] capitalize">{account.status}</span>
            </div>
            <p className="mt-2 truncate text-sm text-[#8e9ac0]">
              {account.proxy?.trim() ? account.proxy : 'Direct connection'}
            </p>
          </div>
        </button>
        <Button size="sm" variant="secondary" onClick={onEdit}>
          <Globe className="h-4 w-4" />
          {account.proxy?.trim() ? 'Edit route' : 'Set route'}
        </Button>
      </div>
    </Card>
  );
}

export function AccountRoutingTab() {
  const accounts = useAccountStore((s) => s.accounts);
  const setAccounts = useAccountStore((s) => s.setAccounts);
  const upsertAccount = useAccountStore((s) => s.upsertAccount);
  const patchAccount = useAccountStore((s) => s.patchAccount);
  const [search, setSearch] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkProxy, setBulkProxy] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [draftProxy, setDraftProxy] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [modalCheckResult, setModalCheckResult] = useState<ProxyCheckResult | null>(null);
  const [modalChecking, setModalChecking] = useState(false);
  const [bulkCheckResult, setBulkCheckResult] = useState<ProxyCheckResult | null>(null);
  const [bulkChecking, setBulkChecking] = useState(false);

  const filteredAccounts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return [...accounts]
      .filter((a) => {
        if (!query) return true;
        return (
          a.username.toLowerCase().includes(query) ||
          (a.proxy ?? '').toLowerCase().includes(query) ||
          a.status.toLowerCase().includes(query)
        );
      })
      .sort((l, r) => {
        const lp = l.proxy?.trim() ? 1 : 0;
        const rp = r.proxy?.trim() ? 1 : 0;
        if (lp !== rp) return rp - lp;
        return l.username.localeCompare(r.username);
      });
  }, [accounts, search]);

  const accountsWithProxy = accounts.filter((a) => a.proxy?.trim()).length;
  const directAccounts = accounts.length - accountsWithProxy;

  const toggleSelected = (id: string) =>
    setSelectedIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      setAccounts(await accountsApi.list());
      toast.success('Proxy view synced');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  const openEditor = (account: Account) => {
    setEditing(account);
    setDraftProxy(account.proxy ?? '');
    setModalCheckResult(null);
  };

  const handleModalTest = async () => {
    if (!draftProxy.trim()) return;
    setModalChecking(true);
    setModalCheckResult(null);
    try {
      setModalCheckResult(await accountsApi.checkProxy(draftProxy.trim()));
    } catch {
      setModalCheckResult({ proxy_url: draftProxy, reachable: false, latency_ms: null, ip_address: null, error: 'Request failed', protocol: null, anonymity: null });
    } finally {
      setModalChecking(false);
    }
  };

  const handleBulkTest = async () => {
    if (!bulkProxy.trim()) return;
    setBulkChecking(true);
    setBulkCheckResult(null);
    try {
      setBulkCheckResult(await accountsApi.checkProxy(bulkProxy.trim()));
    } catch {
      setBulkCheckResult({ proxy_url: bulkProxy, reachable: false, latency_ms: null, ip_address: null, error: 'Request failed', protocol: null, anonymity: null });
    } finally {
      setBulkChecking(false);
    }
  };

  const handleSaveAccountProxy = async () => {
    if (!editing) return;
    setSavingId(editing.id);
    try {
      const updated = await accountsApi.setProxy(editing.id, draftProxy.trim());
      upsertAccount(updated);
      toast.success(draftProxy.trim() ? `Proxy updated for @${updated.username}` : `Proxy cleared for @${updated.username}`);
      setEditing(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSavingId(null);
    }
  };

  const handleBulkApply = async () => {
    if (!selectedIds.length) { toast.error('Select at least one account'); return; }
    setBulkLoading(true);
    try {
      const results = await accountsApi.bulkSetProxy(selectedIds, bulkProxy.trim());
      results.forEach((r) => patchAccount(r.id, { proxy: r.proxy }));
      const n = selectedIds.length;
      toast.success(bulkProxy.trim() ? `Applied proxy to ${n} account${n === 1 ? '' : 's'}` : `Cleared proxy on ${n} account${n === 1 ? '' : 's'}`);
      setSelectedIds([]);
      setBulkProxy('');
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBulkLoading(false);
    }
  };

  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <HeaderStat label="Tracked" value={accounts.length} tone="cyan" />
        <HeaderStat label="Proxy Assigned" value={accountsWithProxy} tone="green" />
        <HeaderStat label="Direct" value={directAccounts} tone="violet" />
        <HeaderStat label="Selected" value={selectedIds.length} tone="amber" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="space-y-5">
          <div>
            <p className="text-kicker">Bulk Apply</p>
            <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Selection controls</h2>
            <p className="mt-2 text-sm text-[#8e9ac0]">Set one route across selected accounts. Leave blank to clear routing.</p>
          </div>
          <div className="space-y-2">
            <Input
              label="Proxy URL"
              value={bulkProxy}
              onChange={(e) => { setBulkProxy(e.target.value); setBulkCheckResult(null); }}
              placeholder="http://user:pass@host:port or socks5://host:port"
              hint="Applied through the backend bulk proxy endpoint."
            />
            {bulkCheckResult && <ProxyTestChip result={bulkCheckResult} />}
          </div>
          <div className="rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-4">
            <p className="text-kicker !text-[0.62rem]">Selection</p>
            <p className="mt-3 text-3xl font-semibold text-[#eef4ff]">{selectedIds.length}</p>
            <p className="mt-1 text-sm text-[#8e9ac0]">account{selectedIds.length === 1 ? '' : 's'} selected</p>
          </div>
          <div className="grid gap-3">
            {bulkProxy.trim() && (
              <Button variant="secondary" onClick={handleBulkTest} loading={bulkChecking} disabled={bulkChecking}>
                {bulkChecking ? <Loader className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                Test Proxy
              </Button>
            )}
            <Button onClick={handleBulkApply} loading={bulkLoading}>
              <Globe className="h-4 w-4" />
              {bulkProxy.trim() ? 'Apply Proxy' : 'Clear Proxy'}
            </Button>
            <Button variant="secondary" onClick={() => setSelectedIds(filteredAccounts.map((a) => a.id))}>
              Select Visible
            </Button>
            <Button variant="ghost" onClick={() => setSelectedIds([])} disabled={selectedIds.length === 0}>
              <Trash2 className="h-4 w-4" />
              Clear Selection
            </Button>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="space-y-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-kicker">Account Routing</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Live route list</h2>
                <p className="mt-2 text-sm text-[#8e9ac0]">Search by account, proxy URL, or session state.</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative lg:w-72">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8bb3]" />
                  <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search accounts or proxy…" className="glass-field pl-10 text-sm" />
                </div>
                <Button variant="secondary" size="sm" onClick={handleRefresh} loading={refreshing}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>

          {filteredAccounts.length === 0 ? (
            <Card className="py-18 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
                <Globe className="h-7 w-7 text-[#7dcfff]" />
              </div>
              <p className="mt-5 text-lg font-semibold text-[#eef4ff]">No matching accounts</p>
              <p className="mt-2 text-sm text-[#8e9ac0]">Adjust the search or sync from the backend.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredAccounts.map((a) => (
                <AccountProxyCard key={a.id} account={a} selected={selectedIds.includes(a.id)} onToggle={() => toggleSelected(a.id)} onEdit={() => openEditor(a)} />
              ))}
            </div>
          )}
        </div>
      </div>

      <Modal open={editing !== null} onClose={() => { setEditing(null); setModalCheckResult(null); }} title={editing ? `Proxy for @${editing.username}` : 'Proxy editor'}>
        <div className="space-y-4">
          <div className="space-y-2">
            <Input label="Proxy URL" value={draftProxy} onChange={(e) => { setDraftProxy(e.target.value); setModalCheckResult(null); }} placeholder="Leave blank to remove proxy routing" hint="Supports HTTP, HTTPS, SOCKS4, and SOCKS5 URLs." autoFocus />
            {modalCheckResult && <ProxyTestChip result={modalCheckResult} />}
          </div>
          <div className="rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-4 text-sm text-[#8e9ac0]">
            Current status: <span className="text-[#eef4ff]">{editing?.status}</span>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" className="flex-1" onClick={() => { setEditing(null); setModalCheckResult(null); }}>Cancel</Button>
            {draftProxy.trim() && (
              <Button variant="secondary" onClick={handleModalTest} loading={modalChecking} disabled={modalChecking}>
                {modalChecking ? <Loader className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                Test
              </Button>
            )}
            <Button className="flex-1" loading={savingId === editing?.id} onClick={handleSaveAccountProxy}>
              {draftProxy.trim() ? 'Save Proxy' : 'Clear Proxy'}
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
