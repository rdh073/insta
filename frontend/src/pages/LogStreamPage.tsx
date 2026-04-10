import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowDown,
  Terminal,
  Trash2,
  Pause,
  Play,
  Download,
  Bug,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { buildSseUrl } from '../api/sse-token';
import { buildApiUrl, resolveApiBaseUrl } from '../lib/api-base';
import { useSettingsStore } from '../store/settings';
import { useLogStreamStore, nextLogId } from '../store/logStream';
import type { LogRecord } from '../store/logStream';
import { cn } from '../lib/cn';

// ─── Level config ─────────────────────────────────────────────────────────────

interface LevelStyle {
  label: string;
  line: string;
  badge: string;
  minno: number;
}

const LEVEL_STYLES: Record<string, LevelStyle> = {
  DEBUG:    { label: 'DBG', minno: 10, line: 'text-[#565f89]',                                        badge: 'text-[#565f89]  bg-[rgba(86,95,137,0.15)]  border-[rgba(86,95,137,0.25)]' },
  INFO:     { label: 'INF', minno: 20, line: 'text-[#a9b1d6]',                                        badge: 'text-[#7dcfff]  bg-[rgba(125,207,255,0.10)] border-[rgba(125,207,255,0.22)]' },
  WARNING:  { label: 'WRN', minno: 30, line: 'text-[#e0af68]',                                        badge: 'text-[#e0af68]  bg-[rgba(224,175,104,0.10)] border-[rgba(224,175,104,0.22)]' },
  ERROR:    { label: 'ERR', minno: 40, line: 'text-[#f7768e]',                                        badge: 'text-[#f7768e]  bg-[rgba(247,118,142,0.10)] border-[rgba(247,118,142,0.22)]' },
  CRITICAL: { label: 'CRT', minno: 50, line: 'text-[#ff5f87] font-semibold',                          badge: 'text-[#ff5f87]  bg-[rgba(255,95,135,0.15)]  border-[rgba(255,95,135,0.30)]' },
};

function styleFor(level: string): LevelStyle {
  return LEVEL_STYLES[level] ?? LEVEL_STYLES.DEBUG;
}

const MIN_LEVEL_OPTIONS = [
  { label: 'DEBUG', value: 10 },
  { label: 'INFO',  value: 20 },
  { label: 'WARN',  value: 30 },
  { label: 'ERROR', value: 40 },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTs(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number, w = 2) => String(n).padStart(w, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}

function downloadNdjson(lines: LogRecord[]) {
  const text = lines.map((l) => JSON.stringify({ ts: l.ts, level: l.level, name: l.name, msg: l.msg })).join('\n');
  const blob = new Blob([text], { type: 'application/x-ndjson' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `logstream-${Date.now()}.ndjson`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function LogStreamPage() {
  const backendUrl    = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);

  const lines       = useLogStreamStore((s) => s.lines);
  const total       = useLogStreamStore((s) => s.total);
  const connected   = useLogStreamStore((s) => s.connected);
  const paused      = useLogStreamStore((s) => s.paused);
  const minLevel    = useLogStreamStore((s) => s.minLevel);
  const nameFilter  = useLogStreamStore((s) => s.nameFilter);
  const autoScroll  = useLogStreamStore((s) => s.autoScroll);
  const verboseMode = useLogStreamStore((s) => s.verboseMode);

  const addLine       = useLogStreamStore((s) => s.addLine);
  const clearLines    = useLogStreamStore((s) => s.clearLines);
  const setConnected  = useLogStreamStore((s) => s.setConnected);
  const setPaused     = useLogStreamStore((s) => s.setPaused);
  const setMinLevel   = useLogStreamStore((s) => s.setMinLevel);
  const setNameFilter = useLogStreamStore((s) => s.setNameFilter);
  const setAutoScroll = useLogStreamStore((s) => s.setAutoScroll);
  const setVerboseMode = useLogStreamStore((s) => s.setVerboseMode);

  const [verbosePending, setVerbosePending] = useState(false);

  const termRef    = useRef<HTMLDivElement>(null);
  const esRef      = useRef<EventSource | null>(null);
  const pausedRef  = useRef(false);
  const mountedRef = useRef(true);
  const retryRef   = useRef(0);

  // Keep ref in sync so SSE callback reads current paused state without stale closure
  pausedRef.current = paused;

  // ── Verbose mode sync ─────────────────────────────────────────────────────
  // On mount, sync the UI toggle with the actual backend log level.
  useEffect(() => {
    const url = buildApiUrl('/logs/verbose', backendUrl);
    const headers: Record<string, string> = {};
    const key = backendApiKey?.trim();
    if (key) headers['x-api-key'] = key;
    fetch(url, { headers })
      .then((r) => r.json())
      .then((d: { enabled: boolean }) => setVerboseMode(d.enabled))
      .catch(() => { /* ignore — server might not have the endpoint yet */ });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUrl]);

  const toggleVerbose = useCallback(async () => {
    setVerbosePending(true);
    const next = !verboseMode;
    try {
      const url = buildApiUrl('/logs/verbose', backendUrl);
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const key = backendApiKey?.trim();
      if (key) headers['x-api-key'] = key;
      await fetch(url, { method: 'POST', headers, body: JSON.stringify({ enabled: next }) });
      setVerboseMode(next);
    } catch {
      // keep existing state on error
    } finally {
      setVerbosePending(false);
    }
  }, [verboseMode, backendUrl, backendApiKey, setVerboseMode]);

  // ── SSE connection ────────────────────────────────────────────────────────

  const connect = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;

    const apiBase = resolveApiBaseUrl(backendUrl);

    buildSseUrl('/logs/stream', apiBase)
      .then((url) => {
        if (!mountedRef.current) return;

        const es = new EventSource(url);
        esRef.current = es;

        es.onopen = () => {
          retryRef.current = 0;
          setConnected(true);
        };

        es.onmessage = (evt) => {
          if (pausedRef.current) return;
          try {
            const raw = JSON.parse(evt.data as string) as Omit<LogRecord, 'id'>;
            addLine({ ...raw, id: nextLogId() });
          } catch {
            // malformed — ignore
          }
        };

        es.onerror = () => {
          es.close();
          setConnected(false);
          if (!mountedRef.current) return;
          const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
          retryRef.current += 1;
          setTimeout(() => { if (mountedRef.current) connect(); }, delay);
        };
      })
      .catch(() => {
        setConnected(false);
        if (!mountedRef.current) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 30_000);
        retryRef.current += 1;
        setTimeout(() => { if (mountedRef.current) connect(); }, delay);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backendUrl, backendApiKey]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!autoScroll || !termRef.current) return;
    termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [lines, autoScroll]);

  // ── Filtered view ─────────────────────────────────────────────────────────

  const visible = lines.filter(
    (l) =>
      l.levelno >= minLevel &&
      (nameFilter === '' || l.name.toLowerCase().includes(nameFilter.toLowerCase())),
  );

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="page-shell max-w-6xl flex flex-col gap-4" style={{ height: 'calc(100vh - 2rem)' }}>
      <PageHeader
        eyebrow="Infrastructure"
        title="Log Stream"
        description="Live Python logging output streamed from the backend process over SSE."
        icon={<Terminal className="h-6 w-6 text-[#9ece6a]" />}
        actions={
          <div className="flex items-center gap-2">
            {/* Connection indicator */}
            <span className="flex items-center gap-1.5 text-xs font-mono">
              <span className="relative flex h-2 w-2">
                {connected && !paused && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#9ece6a] opacity-50" />
                )}
                <span className={cn(
                  'relative inline-flex h-2 w-2 rounded-full',
                  connected && !paused ? 'bg-[#9ece6a]' : connected ? 'bg-[#e0af68]' : 'bg-[#f7768e]',
                )} />
              </span>
              <span className={connected ? paused ? 'text-[#e0af68]' : 'text-[#9ece6a]' : 'text-[#f7768e]'}>
                {connected ? paused ? 'PAUSED' : 'LIVE' : 'DISCONNECTED'}
              </span>
            </span>

            <Button
              variant={paused ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setPaused(!paused)}
            >
              {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
              {paused ? 'Resume' : 'Pause'}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={clearLines}
            >
              <Trash2 className="h-4 w-4" />
            </Button>

            <Button
              variant="secondary"
              size="sm"
              disabled={visible.length === 0}
              onClick={() => downloadNdjson(visible)}
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        }
      />

      {/* Filter bar */}
      <div className="glass-panel flex flex-wrap items-end gap-3 p-3 shrink-0">
        <div className="space-y-1">
          <label className="field-label" htmlFor="ls-minlevel">Min level</label>
          <select
            id="ls-minlevel"
            value={minLevel}
            onChange={(e) => setMinLevel(Number(e.target.value))}
            className="glass-select text-sm w-32"
          >
            {MIN_LEVEL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-36 space-y-1">
          <label className="field-label" htmlFor="ls-name">Logger name</label>
          <input
            id="ls-name"
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
            placeholder="instagrapi, httpx, app…"
            className="glass-field text-sm"
          />
        </div>

        <div className="flex items-center gap-2 pb-0.5">
          <button
            type="button"
            role="checkbox"
            aria-checked={autoScroll}
            onClick={() => setAutoScroll(!autoScroll)}
            className={cn(
              'flex h-8 items-center gap-2 rounded-lg border px-3 text-xs font-medium transition-colors cursor-pointer',
              autoScroll
                ? 'border-[rgba(125,207,255,0.28)] bg-[rgba(125,207,255,0.10)] text-[#7dcfff]'
                : 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] text-[#7a8aae] hover:text-[#c0caf5]',
            )}
          >
            <ArrowDown className="h-3.5 w-3.5" />
            Auto-scroll
          </button>

          <button
            type="button"
            role="checkbox"
            aria-checked={verboseMode}
            disabled={verbosePending}
            onClick={toggleVerbose}
            title="Toggle instagrapi DEBUG logging at runtime"
            className={cn(
              'flex h-8 items-center gap-2 rounded-lg border px-3 text-xs font-medium transition-colors cursor-pointer disabled:opacity-50',
              verboseMode
                ? 'border-[rgba(187,154,247,0.30)] bg-[rgba(187,154,247,0.12)] text-[#bb9af7]'
                : 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] text-[#7a8aae] hover:text-[#c0caf5]',
            )}
          >
            <Bug className="h-3.5 w-3.5" />
            Verbose
          </button>
        </div>

        <span className="pb-0.5 font-mono text-[11px] text-[#59658c] self-end ml-auto">
          {visible.length.toLocaleString()} / {total.toLocaleString()} lines
        </span>
      </div>

      {/* Terminal */}
      <div
        ref={termRef}
        className="flex-1 overflow-y-auto rounded-2xl border border-[rgba(162,179,229,0.10)] bg-[#0a0c12] p-3 font-mono text-[12px] leading-[1.6]"
        style={{ minHeight: 0 }}
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
          setAutoScroll(atBottom);
        }}
      >
        {visible.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <Terminal className="mx-auto h-8 w-8 text-[#2a2f45] mb-3" />
              <p className="text-[#3a4060] text-sm">
                {connected
                  ? 'Waiting for log records… Enable Verbose to see instagrapi DEBUG traces.'
                  : 'Connecting to backend…'}
              </p>
            </div>
          </div>
        ) : (
          visible.map((line) => <LogLine key={line.id} line={line} />)
        )}
      </div>
    </div>
  );
}

// ─── Terminal row ─────────────────────────────────────────────────────────────

function LogLine({ line }: { line: LogRecord }) {
  const style = styleFor(line.level);

  return (
    <div className={cn('flex gap-2 hover:bg-[rgba(255,255,255,0.025)] rounded px-1 -mx-1 group', style.line)}>
      {/* Timestamp */}
      <span className="shrink-0 text-[#3a4060] group-hover:text-[#59658c] w-[92px]">
        {fmtTs(line.ts)}
      </span>

      {/* Level badge */}
      <span
        className={cn(
          'shrink-0 inline-flex w-[34px] items-center justify-center rounded border text-[9px] font-bold uppercase tracking-wider',
          style.badge,
        )}
      >
        {style.label}
      </span>

      {/* Logger name */}
      <span className="shrink-0 w-[160px] truncate text-[#3d4a6b] group-hover:text-[#59658c]" title={line.name}>
        {line.name}
      </span>

      {/* Message — preserve newlines for tracebacks */}
      <span className="flex-1 break-all whitespace-pre-wrap min-w-0">
        {line.msg}
      </span>
    </div>
  );
}
