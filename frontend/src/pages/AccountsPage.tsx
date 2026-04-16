import { useRef, useState, useMemo, useEffect } from 'react';
import {
  CheckSquare,
  Download,
  Globe,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  UserPlus,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { accountsApi } from '../api/accounts';
import type { RateLimitEntry } from '../api/accounts';
import { ApiError } from '../api/client';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { useAccountStore } from '../store/accounts';
import { useAccountsUIStore } from '../store/accountsUI';
import type { Account } from '../types';
import {
  AccountDetail,
  AccountRow,
  AddAccountModal,
  BulkProxyModal,
  ImportModal,
  TOTPSetupModal,
} from '../features/accounts/components';
import { isChallengeFailure } from '../features/accounts/components/account-helpers';

export function AccountsPage() {
  const accounts = useAccountStore((s) => s.accounts);
  const setAccounts = useAccountStore((s) => s.setAccounts);
  const removeAccount = useAccountStore((s) => s.removeAccount);
  const patchPageAccount = useAccountStore((s) => s.patchAccount);
  const updatePageStatus = useAccountStore((s) => s.updateStatus);
  const activeId = useAccountStore((s) => s.activeId);
  const setActive = useAccountStore((s) => s.setActive);

  const [showAdd, setShowAdd] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [reloggingIds, setReloggingIds] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkProgress, setBulkProgress] = useState('');
  const [, setBusyAccountIds] = useState<Set<string>>(new Set());
  const [showBulkProxy, setShowBulkProxy] = useState(false);
  const [showTOTPSetup, setShowTOTPSetup] = useState(false);
  const [totpAccountId, setTOTPAccountId] = useState<string | undefined>();
  const searchQuery = useAccountsUIStore((s) => s.searchQuery);
  const setSearchQuery = useAccountsUIStore((s) => s.setSearchQuery);
  const [rateLimitMap, setRateLimitMap] = useState<Map<string, RateLimitEntry>>(new Map());
  const sessionInputRef = useRef<HTMLInputElement>(null);

  // Poll rate-limited accounts every 15 s
  useEffect(() => {
    const fetchLimited = () => {
      accountsApi.rateLimited().then((entries) => {
        setRateLimitMap(new Map(entries.map((e) => [e.account_id, e])));
      }).catch(() => {});
    };
    fetchLimited();
    const id = setInterval(fetchLimited, 15_000);
    return () => clearInterval(id);
  }, []);

  const handleClearRateLimit = (accountId: string) => {
    setRateLimitMap((prev) => {
      const next = new Map(prev);
      next.delete(accountId);
      return next;
    });
  };

  const handleQuickRelogin = async (account: Account) => {
    if (reloggingIds.has(account.id)) return;
    setReloggingIds((prev) => new Set(prev).add(account.id));
    updatePageStatus(account.id, 'logging_in');
    try {
      const updated = await accountsApi.relogin(account.id);
      patchPageAccount(account.id, { status: updated.status, lastError: updated.lastError ?? undefined, lastErrorCode: updated.lastErrorCode ?? undefined });
      toast.success(`@${account.username} re-authenticated`);
    } catch (err) {
      const e = err as ApiError;
      const code = e.code ?? '';
      const family = e.family ?? '';
      let msg = e.message || 'Relogin failed';
      let status: Account['status'] = 'error';
      if (code === 'two_factor_required') { msg = '2FA required'; status = '2fa_required'; }
      else if (isChallengeFailure(code, family)) { msg = 'Security challenge'; status = 'challenge'; }
      updatePageStatus(account.id, status, msg);
      toast.error(`@${account.username}: ${msg}`, { duration: 5000 });
    } finally {
      setReloggingIds((prev) => { const s = new Set(prev); s.delete(account.id); return s; });
    }
  };

  const errorAccounts = accounts.filter((a) => a.status === 'error' || a.status === 'challenge');
  const activeAccounts = accounts.filter((a) => a.status === 'active').length;
  const focusedAccount = accounts.find((a) => a.id === activeId) ?? null;

  const filteredAccounts = useMemo(() => {
    if (!searchQuery.trim()) return accounts;
    const q = searchQuery.toLowerCase();
    return accounts.filter(
      (a) =>
        a.username.toLowerCase().includes(q) ||
        (a.fullName?.toLowerCase().includes(q) ?? false) ||
        a.status.includes(q)
    );
  }, [accounts, searchQuery]);

  const toggleSelect = (id: string) =>
    setSelectedIds((cur) => (cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id]));

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds([]);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const list = await accountsApi.list();
      setAccounts(list);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setRefreshing(false);
    }
  };

  const handleExportSessions = async () => {
    try {
      const blob = await accountsApi.exportSessions();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `insta-sessions-${Date.now()}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  const handleImportSessions = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = await accountsApi.importSessions(file);
      imported.forEach((account) => useAccountStore.getState().upsertAccount(account));
      toast.success(`Restored ${imported.length} session(s)`);
    } catch (error) {
      toast.error((error as Error).message);
    }
    event.target.value = '';
  };

  const handleBulkRelogin = async () => {
    const total = selectedIds.length;
    if (!total) return;
    setBulkLoading(true);
    setBulkProgress(`0/${total}`);
    setBusyAccountIds(new Set(selectedIds));
    selectedIds.forEach((id) => updatePageStatus(id, 'logging_in'));

    let done = 0;
    let ok = 0;
    let fail = 0;
    const CONCURRENCY = 3;
    const queue = [...selectedIds];

    const worker = async () => {
      while (queue.length > 0) {
        const id = queue.shift();
        if (!id) break;
        try {
          const updated = await accountsApi.relogin(id);
          patchPageAccount(id, { status: updated.status, lastError: updated.lastError ?? undefined, lastErrorCode: updated.lastErrorCode ?? undefined });
          ok++;
        } catch {
          updatePageStatus(id, 'error');
          fail++;
        }
        done++;
        setBulkProgress(`${done}/${total}`);
      }
    };

    await Promise.all(Array.from({ length: CONCURRENCY }, worker));

    if (ok > 0) toast.success(`${ok}/${total} relogged in`);
    if (fail > 0) toast.error(`${fail} failed`);
    setBulkLoading(false);
    setBulkProgress('');
    setBusyAccountIds(new Set());
    exitSelectMode();
  };

  const handleBulkLogout = async () => {
    if (!selectedIds.length) return;
    setBulkLoading(true);
    try {
      const results = await accountsApi.bulkLogout(selectedIds);
      selectedIds.forEach((id) => removeAccount(id));
      const total = selectedIds.length;
      const plural = total !== 1 ? 's' : '';
      const ok = results.filter((r) => r.server_logout === 'success').length;
      const failed = results.filter((r) => r.server_logout === 'failed').length;
      const skipped = results.filter((r) => r.server_logout === 'not_present').length;
      const hasServerInfo = ok + failed + skipped > 0;
      if (hasServerInfo) {
        const message = `Logged out ${total} account${plural}. Server session invalidation: ${ok} ok, ${failed} failed, ${skipped} skipped.`;
        if (failed > 0) {
          toast(message, { duration: 6000 });
        } else {
          toast.success(message);
        }
      } else {
        toast.success(`${total} account${plural} removed`);
      }
      exitSelectMode();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkProxy = async (proxy: string) => {
    if (!selectedIds.length || !proxy.trim()) return;
    setBulkLoading(true);
    try {
      const results = await accountsApi.bulkSetProxy(selectedIds, proxy.trim());
      results.forEach((r) => patchPageAccount(r.id, { proxy: r.proxy, status: r.status as Account['status'] }));
      toast.success(`Proxy updated for ${selectedIds.length} account${selectedIds.length !== 1 ? 's' : ''}`);
      exitSelectMode();
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBulkLoading(false);
    }
  };

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Identity Operations"
        title="Account Workspace"
        description="Track live login state, recover sessions, import credential batches, and coordinate bulk actions."
        icon={<ShieldCheck className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          selectMode ? (
            <Button variant="ghost" size="sm" onClick={exitSelectMode}>
              <X className="h-4 w-4" />
              Exit select mode
            </Button>
          ) : (
            <>
              <Button variant="secondary" size="sm" onClick={handleRefresh} loading={refreshing}>
                <RefreshCw className="h-4 w-4" />
                Sync
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setSelectMode(true)}>
                <CheckSquare className="h-4 w-4" />
                Select
              </Button>
              <Button variant="secondary" size="sm" onClick={() => sessionInputRef.current?.click()}>
                <Download className="h-4 w-4" />
                Import Session
              </Button>
              <Button variant="secondary" size="sm" onClick={handleExportSessions}>
                <Download className="h-4 w-4 rotate-180" />
                Export Session
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setShowImport(true)}>
                <Upload className="h-4 w-4" />
                Import File
              </Button>
              <Button size="sm" onClick={() => setShowAdd(true)}>
                <UserPlus className="h-4 w-4" />
                Add Account
              </Button>
            </>
          )
        }
      >
        <div className="metric-grid">
          <HeaderStat label="Connected" value={accounts.length} tone="cyan" />
          <HeaderStat label="Active" value={activeAccounts} tone="green" />
          <HeaderStat label="Needs Attention" value={errorAccounts.length} tone="rose" />
          <HeaderStat label="Rate Limited" value={rateLimitMap.size} tone={rateLimitMap.size > 0 ? 'rose' : 'cyan'} />
        </div>
      </PageHeader>

      {accounts.length === 0 ? (
        <Card className="py-18 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
            <UserPlus className="h-7 w-7 text-[#7dcfff]" />
          </div>
          <p className="mt-5 text-lg font-semibold text-[#eef4ff]">No accounts connected</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8e9ac0]">
            Add a single account, restore a saved session bundle, or import a credential file to start managing the fleet.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              Import File
            </Button>
            <Button onClick={() => setShowAdd(true)}>
              Add Account
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_22rem] pb-24">
          {/* ── Left column: search + account list ──────────────── */}
          <div className="space-y-3">
            {/* Search bar */}
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#5a6a90]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search accounts..."
                className="glass-field w-full py-2.5 pl-10 pr-3 text-sm"
                aria-label="Search accounts"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-[#5a6a90] transition-colors hover:text-[#8e9ac0]"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Select mode toolbar */}
            {selectMode && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedIds(filteredAccounts.map((a) => a.id))}
                  className="glass-chip cursor-pointer text-xs"
                >
                  Select all ({filteredAccounts.length})
                </button>
                {errorAccounts.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelectedIds(errorAccounts.map((a) => a.id))}
                    className="glass-chip cursor-pointer text-xs !border-[rgba(247,118,142,0.18)] !bg-[rgba(247,118,142,0.12)] !text-[#ffc4d0]"
                  >
                    Errors ({errorAccounts.length})
                  </button>
                )}
                <button type="button" onClick={() => setSelectedIds([])} className="glass-chip cursor-pointer text-xs">
                  Clear
                </button>
              </div>
            )}

            {/* Account list */}
            <Card className="overflow-hidden p-1.5">
              <div className="max-h-[calc(100vh-22rem)] space-y-0.5 overflow-y-auto pr-0.5">
                {filteredAccounts.length === 0 ? (
                  <div className="py-8 text-center">
                    <p className="text-sm text-[#5a6a90]">
                      {searchQuery ? `No accounts matching "${searchQuery}"` : 'No accounts'}
                    </p>
                  </div>
                ) : (
                  filteredAccounts.map((account) => (
                    <AccountRow
                      key={account.id}
                      account={account}
                      isActive={activeId === account.id}
                      selectMode={selectMode}
                      selected={selectedIds.includes(account.id)}
                      onToggle={() => toggleSelect(account.id)}
                      onClick={() => {
                        const next = activeId === account.id ? null : account.id;
                        setActive(next);
                        if (next) {
                          const acc = filteredAccounts.find((a) => a.id === next);
                          const verifiedMs = acc?.lastVerifiedAt ? new Date(acc.lastVerifiedAt).getTime() : 0;
                          const staleSec = (Date.now() - verifiedMs) / 1000;
                          if (staleSec > 600) {
                            accountsApi.refreshCounts(next).catch(() => {});
                          }
                        }
                      }}
                      onRelogin={() => void handleQuickRelogin(account)}
                      relogging={reloggingIds.has(account.id)}
                      rateLimitInfo={rateLimitMap.get(account.id)}
                    />
                  ))
                )}
              </div>
              {searchQuery && filteredAccounts.length > 0 && (
                <p className="border-t border-[rgba(162,179,229,0.08)] px-3 py-2 text-[11px] text-[#5a6a90]">
                  {filteredAccounts.length} of {accounts.length} accounts
                </p>
              )}
            </Card>
          </div>

          {/* ── Right column: detail panel ──────────────── */}
          <div className="hidden lg:block">
            {focusedAccount ? (
              <AccountDetail
                key={focusedAccount.id}
                account={focusedAccount}
                onSetupTOTP={(id) => {
                  setTOTPAccountId(id);
                  setShowTOTPSetup(true);
                }}
                rateLimitInfo={rateLimitMap.get(focusedAccount.id)}
                onClearRateLimit={handleClearRateLimit}
              />
            ) : (
              <Card className="flex flex-col items-center justify-center py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
                  <ShieldCheck className="h-5 w-5 text-[#5a6a90]" />
                </div>
                <p className="mt-4 text-sm text-[#5a6a90]">Click an account to view details</p>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Mobile detail: show below list when active */}
      {focusedAccount && (
        <div className="lg:hidden pb-24">
          <AccountDetail
            key={focusedAccount.id}
            account={focusedAccount}
            onSetupTOTP={(id) => {
              setTOTPAccountId(id);
              setShowTOTPSetup(true);
            }}
            rateLimitInfo={rateLimitMap.get(focusedAccount.id)}
            onClearRateLimit={handleClearRateLimit}
          />
        </div>
      )}

      {selectMode && selectedIds.length > 0 && (
        <div className="fixed bottom-4 left-4 right-4 z-30 rounded-[1.6rem] border border-[rgba(162,179,229,0.16)] bg-[rgba(9,12,22,0.86)] p-4 shadow-[0_24px_54px_rgba(4,8,18,0.42)] backdrop-blur-2xl lg:left-[23rem] lg:right-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <span className="text-sm text-[#d6e0ff]">{selectedIds.length} selected</span>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" loading={bulkLoading} onClick={handleBulkRelogin}>
                <RotateCcw className="h-3.5 w-3.5" />
                {bulkProgress ? `Relogin ${bulkProgress}` : 'Relogin All'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowBulkProxy(true)}>
                <Globe className="h-3.5 w-3.5" />
                Set Proxy
              </Button>
              <Button size="sm" variant="danger" loading={bulkLoading} onClick={handleBulkLogout}>
                <Trash2 className="h-3.5 w-3.5" />
                Logout All
              </Button>
            </div>
          </div>
        </div>
      )}

      <input ref={sessionInputRef} type="file" accept=".json" className="hidden" onChange={handleImportSessions} aria-hidden="true" />

      <AddAccountModal open={showAdd} onClose={() => setShowAdd(false)} />
      <ImportModal open={showImport} onClose={() => setShowImport(false)} />
      <BulkProxyModal open={showBulkProxy} onClose={() => setShowBulkProxy(false)} onConfirm={handleBulkProxy} />
      <TOTPSetupModal open={showTOTPSetup} onClose={() => setShowTOTPSetup(false)} accountId={totpAccountId} />
    </div>
  );
}
