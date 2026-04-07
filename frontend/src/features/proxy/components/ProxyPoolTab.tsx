import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Database,
  FolderOpen,
  Loader,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { proxiesApi } from '../../../api/proxies';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import type { PoolProxy, ProxyCheckResult, ProxyImportSummary, ProxyRecheckSummary } from '../../../types';
import { ProxyTestChip } from './ProxyTestChip';

function ProtocolBadge({ protocol }: { protocol: string }) {
  const colors: Record<string, string> = {
    http: 'border-[rgba(125,207,255,0.22)] bg-[rgba(125,207,255,0.10)] text-[#7dcfff]',
    https: 'border-[rgba(158,206,106,0.22)] bg-[rgba(158,206,106,0.10)] text-[#9ece6a]',
    socks4: 'border-[rgba(187,154,247,0.22)] bg-[rgba(187,154,247,0.10)] text-[#bb9af7]',
    socks5: 'border-[rgba(187,154,247,0.22)] bg-[rgba(187,154,247,0.10)] text-[#bb9af7]',
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${colors[protocol] ?? 'border-[rgba(162,179,229,0.18)] text-[#7f8bb3]'}`}>
      {protocol}
    </span>
  );
}

function LatencyBadge({ ms }: { ms: number }) {
  const color = ms < 300 ? '#9ece6a' : ms < 800 ? '#e0af68' : '#f7768e';
  return (
    <span className="font-mono text-[11px]" style={{ color }}>
      {ms.toFixed(0)}ms
    </span>
  );
}

function ImportSummaryBar({ summary }: { summary: ProxyImportSummary }) {
  const stats = [
    { label: 'Total', value: summary.total, color: '#7f8bb3' },
    { label: 'Saved', value: summary.saved, color: '#9ece6a' },
    { label: 'Transparent', value: summary.skipped_transparent, color: '#f7768e' },
    { label: 'Duplicate', value: summary.skipped_duplicate, color: '#e0af68' },
    { label: 'Existing', value: summary.skipped_existing, color: '#7dcfff' },
    { label: 'Failed', value: summary.failed, color: '#f7768e' },
  ];
  return (
    <div className="rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-4">
      <p className="mb-3 text-kicker !text-[0.62rem]">Import result</p>
      <div className="flex flex-wrap gap-4">
        {stats.map(({ label, value, color }) => (
          <div key={label} className="text-center">
            <p className="text-xl font-semibold" style={{ color }}>{value}</p>
            <p className="text-[11px] text-[#7f8bb3]">{label}</p>
          </div>
        ))}
      </div>
      {summary.errors.length > 0 && (
        <div className="mt-3 space-y-1">
          {summary.errors.slice(0, 5).map((err, i) => (
            <p key={i} className="truncate text-[11px] text-[#f7768e]">{err}</p>
          ))}
          {summary.errors.length > 5 && (
            <p className="text-[11px] text-[#7f8bb3]">+{summary.errors.length - 5} more errors</p>
          )}
        </div>
      )}
    </div>
  );
}

export function ProxyPoolTab() {
  const [pool, setPool] = useState<PoolProxy[]>([]);
  const [loadingPool, setLoadingPool] = useState(false);
  const [importText, setImportText] = useState('');
  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<ProxyImportSummary | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setImportText((prev) => (prev.trim() ? prev.trimEnd() + '\n' + text : text));
      setImportSummary(null);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const [checkUrl, setCheckUrl] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<ProxyCheckResult | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [rechecking, setRechecking] = useState(false);
  const [recheckSummary, setRecheckSummary] = useState<ProxyRecheckSummary | null>(null);

  const fetchPool = async () => {
    setLoadingPool(true);
    try {
      setPool(await proxiesApi.list());
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoadingPool(false);
    }
  };

  useEffect(() => { fetchPool(); }, []);

  const handleImport = async () => {
    if (!importText.trim()) { toast.error('Paste at least one proxy line'); return; }
    setImporting(true);
    setImportSummary(null);
    try {
      const summary = await proxiesApi.import(importText.trim());
      setImportSummary(summary);
      if (summary.saved > 0) {
        toast.success(`${summary.saved} elite prox${summary.saved === 1 ? 'y' : 'ies'} saved`);
        await fetchPool();
      } else {
        toast('No new proxies saved', { icon: '\u26a0\ufe0f' });
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (host: string, port: number) => {
    const key = `${host}:${port}`;
    setDeletingKey(key);
    try {
      await proxiesApi.delete(host, port);
      setPool((cur) => cur.filter((p) => !(p.host === host && p.port === port)));
      toast.success(`Removed ${key}`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setDeletingKey(null);
    }
  };

  const handleCheck = async () => {
    if (!checkUrl.trim()) return;
    setChecking(true);
    setCheckResult(null);
    try {
      setCheckResult(await proxiesApi.check(checkUrl.trim()));
    } catch {
      setCheckResult({ proxy_url: checkUrl, reachable: false, latency_ms: null, ip_address: null, error: 'Request failed', protocol: null, anonymity: null });
    } finally {
      setChecking(false);
    }
  };

  const handleRecheck = async () => {
    setRechecking(true);
    setRecheckSummary(null);
    try {
      const summary = await proxiesApi.recheck();
      setRecheckSummary(summary);
      toast.success(`Recheck done \u2014 ${summary.alive} alive, ${summary.removed} removed`);
      await fetchPool();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setRechecking(false);
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return pool;
    return pool.filter((p) => p.url.toLowerCase().includes(q) || p.protocol.includes(q) || p.anonymity.includes(q));
  }, [pool, search]);

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      <div className="space-y-5">
        <Card className="space-y-4">
          <div>
            <p className="text-kicker">Import Proxies</p>
            <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Paste or load file</h2>
            <p className="mt-2 text-sm text-[#8e9ac0]">
              Supported formats: <code className="text-[#7dcfff]">ip:port</code>, <code className="text-[#7dcfff]">proto:ip:port</code>, <code className="text-[#7dcfff]">proto://ip:port</code>
            </p>
          </div>
          <textarea
            value={importText}
            onChange={(e) => { setImportText(e.target.value); setImportSummary(null); }}
            placeholder={'1.2.3.4:8080\nhttp://5.6.7.8:3128\nsocks5://9.10.11.12:1080'}
            rows={8}
            className="glass-textarea w-full resize-y font-mono text-xs"
          />
          {importSummary && <ImportSummaryBar summary={importSummary} />}
          <input ref={fileInputRef} type="file" accept=".txt,.csv,text/plain" className="hidden" onChange={handleFileChange} />
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => fileInputRef.current?.click()} className="flex-1">
              <FolderOpen className="h-4 w-4" />
              Browse file
            </Button>
            <Button onClick={handleImport} loading={importing} className="flex-1">
              <Upload className="h-4 w-4" />
              Import &amp; Check
            </Button>
          </div>
        </Card>

        <Card className="space-y-4">
          <div>
            <p className="text-kicker">Single Check</p>
            <h2 className="mt-2 text-lg font-semibold text-[#eef4ff]">Test a proxy URL</h2>
          </div>
          <div className="space-y-2">
            <Input label="Proxy URL" value={checkUrl} onChange={(e) => { setCheckUrl(e.target.value); setCheckResult(null); }} placeholder="http://host:port or socks5://host:port" />
            {checkResult && <ProxyTestChip result={checkResult} />}
          </div>
          <Button variant="secondary" onClick={handleCheck} loading={checking} disabled={!checkUrl.trim() || checking}>
            {checking ? <Loader className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            Check
          </Button>
        </Card>
      </div>

      <div className="space-y-4">
        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-kicker">Elite Pool</p>
              <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">{pool.length} stored prox{pool.length === 1 ? 'y' : 'ies'}</h2>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative w-56">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8bb3]" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Filter proxies…" className="glass-field pl-10 text-sm" />
              </div>
              <Button variant="secondary" size="sm" onClick={handleRecheck} loading={rechecking} disabled={pool.length === 0 || rechecking}>
                <Zap className="h-4 w-4" />
                Recheck All
              </Button>
              <Button variant="secondary" size="sm" onClick={fetchPool} loading={loadingPool}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>
          {recheckSummary && (
            <div className="rounded-[1.2rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-4">
              <p className="mb-3 text-kicker !text-[0.62rem]">Recheck result</p>
              <div className="flex flex-wrap gap-4">
                {[
                  { label: 'Total', value: recheckSummary.total, color: '#7f8bb3' },
                  { label: 'Alive', value: recheckSummary.alive, color: '#9ece6a' },
                  { label: 'Removed', value: recheckSummary.removed, color: '#f7768e' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="text-center">
                    <p className="text-xl font-semibold" style={{ color }}>{value}</p>
                    <p className="text-[11px] text-[#7f8bb3]">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {filtered.length === 0 ? (
          <Card className="py-16 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
              <Database className="h-7 w-7 text-[#7dcfff]" />
            </div>
            <p className="mt-5 text-lg font-semibold text-[#eef4ff]">{pool.length === 0 ? 'Pool is empty' : 'No matches'}</p>
            <p className="mt-2 text-sm text-[#8e9ac0]">{pool.length === 0 ? 'Import a proxy list to populate the pool.' : 'Clear the search filter.'}</p>
          </Card>
        ) : (
          <div className="space-y-2">
            {filtered.map((p) => {
              const key = `${p.host}:${p.port}`;
              return (
                <Card key={key} className="px-5 py-4">
                  <div className="flex items-center gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-medium text-[#eef4ff]">{p.url}</span>
                        <ProtocolBadge protocol={p.protocol} />
                        <span className="rounded-full border border-[rgba(187,154,247,0.22)] bg-[rgba(187,154,247,0.10)] px-2 py-0.5 text-[11px] font-medium text-[#bb9af7]">{p.anonymity}</span>
                        <LatencyBadge ms={p.latencyMs} />
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(p.host, p.port)} loading={deletingKey === key} className="shrink-0 !text-[#f7768e] hover:!bg-[rgba(247,118,142,0.1)]">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
