import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  AlertTriangle,
  Bot,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Edit3,
  List,
  Loader,
  Paperclip,
  Play,
  PlusCircle,
  RefreshCw,
  Send,
  Square,
  X,
  Terminal,
  User,
  Wrench,
  XCircle,
} from 'lucide-react';
import { graphRunner } from '../api/graph-runner';
import { fetchProviderModels, operatorCopilotApi, StreamAbortedError, NetworkError, ServerError } from '../api/operator-copilot';
import type { CopilotEvent } from '../api/operator-copilot';
import { parseSlashCommand, getCommandSuggestions } from '../lib/slash-commands';
import type { SlashCommand } from '../lib/slash-commands';
import { useSettingsStore, PROVIDERS } from '../store/settings';
import type { AIProvider } from '../store/settings';
import { useAccountStore } from '../store/accounts';
import { useCopilotStore } from '../store/copilot';
import type { RunState } from '../store/copilot';
import type { Account } from '../types';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { cn } from '../lib/cn';

interface AttachedFile {
  name: string;
  content: string;
  lines: number;
  sizeKb: number;
}

const MAX_FILE_KB = 512;
const ACCEPTED_FILE_TYPES = '.txt,.csv,.json,.jsonl';

const QUICK_SUGGESTIONS = [
  'List all active accounts and their status',
  'Show recent engagement activity for the last 7 days',
  'Recommend hashtags for a travel photography post',
  'Check proxy health and report any issues',
];

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)]">
      <button
        type="button"
        onClick={() => setOpen((c) => !c)}
        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-left text-xs font-medium text-[#9aa7cf] transition-colors hover:text-[#dce6ff]"
      >
        <span className="font-mono">{title}</span>
        {open
          ? <ChevronDown className="h-3.5 w-3.5 text-[#7dcfff]" />
          : <ChevronRight className="h-3.5 w-3.5 text-[#4a5578]" />}
      </button>
      {open && (
        <div className="border-t border-[rgba(162,179,229,0.08)] px-3 py-3">
          {children}
        </div>
      )}
    </div>
  );
}

function EventCard({ event }: { event: CopilotEvent }) {
  switch (event.type) {
    case 'run_start':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <Play className="h-3 w-3 shrink-0 text-[#9ece6a]" />
          <span className="text-xs text-[#4a5a7a]">run started</span>
          {event.thread_id != null && (
            <span className="font-mono text-[11px] text-[#374060]">{String(event.thread_id).slice(0, 12)}…</span>
          )}
        </div>
      );

    case 'node_update':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <ChevronRight className="h-3 w-3 shrink-0 text-[#374060]" />
          <span className="font-mono text-[11px] italic text-[#3e4e6e]">
            {event.node ? String(event.node) : 'node'}
          </span>
        </div>
      );

    case 'plan_ready':
      return (
        <CollapsibleSection title="execution_plan">
          <pre className="code-block text-xs">{JSON.stringify(event.execution_plan ?? event, null, 2)}</pre>
        </CollapsibleSection>
      );

    case 'policy_result': {
      const proposed = event.proposed_calls as unknown[] | undefined;
      const approved = event.approved_calls as unknown[] | undefined;
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <List className="h-3.5 w-3.5 shrink-0 text-[#7aa2f7]" />
            <span className="text-xs font-medium text-[#8e9ac0]">policy_check</span>
            {proposed && <Badge variant="blue">{proposed.length} proposed</Badge>}
            {approved && <Badge variant="green">{approved.length} approved</Badge>}
          </div>
          {(proposed || approved) && (
            <CollapsibleSection title="policy_details">
              <pre className="code-block text-xs">
                {JSON.stringify({ proposed_calls: proposed, approved_calls: approved }, null, 2)}
              </pre>
            </CollapsibleSection>
          )}
        </div>
      );
    }

    case 'tool_result': {
      const toolName = event.tool_name ? String(event.tool_name) : 'tool';
      return (
        <CollapsibleSection title={`tool_result · ${toolName}`}>
          <div className="mb-2 flex items-center gap-2">
            <Wrench className="h-3.5 w-3.5 text-[#e0af68]" />
            <span className="font-mono text-xs text-[#d4b896]">{toolName}</span>
          </div>
          <pre className="code-block text-xs">{JSON.stringify(event.result ?? event, null, 2)}</pre>
        </CollapsibleSection>
      );
    }

    case 'final_response':
      return (
        <div className="flex gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.10)]">
            <Bot className="h-4 w-4 text-[#7dcfff]" />
          </div>
          <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-[rgba(125,207,255,0.12)] bg-[rgba(122,162,247,0.07)] px-4 py-3">
            <p className="whitespace-pre-wrap text-sm leading-6 text-[#eef4ff]">
              {event.text ? String(event.text) : JSON.stringify(event)}
            </p>
          </div>
        </div>
      );

    case 'run_finish':
      return (
        <div className="flex items-center gap-2 py-0.5">
          <Square className="h-3 w-3 shrink-0 text-[#9ece6a]" />
          <span className="text-xs text-[#4a6a4a]">run complete</span>
          <Badge variant="green">done</Badge>
        </div>
      );

    case 'run_error':
      return (
        <div className="rounded-xl border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.07)] px-3 py-2.5 text-sm">
          <div className="flex items-center gap-2 text-[#ffccd7]">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span className="text-xs font-medium">run_error</span>
          </div>
          {event.message != null && (
            <p className="mt-1 font-mono text-xs text-[#f78e9e]">{String(event.message)}</p>
          )}
        </div>
      );

    default:
      return (
        <CollapsibleSection title={`event:${event.type}`}>
          <pre className="code-block text-xs text-[#9fb0d8]">{JSON.stringify(event, null, 2)}</pre>
        </CollapsibleSection>
      );
  }
}

function ApprovalCard({
  payload,
  onDecision,
  loading,
}: {
  payload: Record<string, unknown>;
  onDecision: (result: 'approved' | 'rejected' | 'edited', editedCalls?: Record<string, unknown>[]) => void;
  loading: boolean;
}) {
  const [editMode, setEditMode] = useState(false);
  const [jsonText, setJsonText] = useState(() => {
    const calls = payload.proposed_calls ?? payload.tool_calls ?? [];
    return JSON.stringify(calls, null, 2);
  });
  const [parseError, setParseError] = useState('');

  function handleSubmitEdit() {
    try {
      const parsed = JSON.parse(jsonText) as Record<string, unknown>[];
      onDecision('edited', parsed);
    } catch {
      setParseError('Invalid JSON — fix the payload before submitting.');
    }
  }

  return (
    <div className="rounded-2xl border border-[rgba(224,175,104,0.28)] bg-[rgba(224,175,104,0.06)] p-4 space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-[#e0af68]" />
        <span className="text-sm font-semibold text-[#f0d080]">Approval Required</span>
        <Badge variant="yellow">waiting</Badge>
      </div>

      {editMode ? (
        <div className="space-y-2">
          <textarea
            id="copilot-approval-payload"
            name="copilotApprovalPayload"
            value={jsonText}
            onChange={(e) => { setJsonText(e.target.value); setParseError(''); }}
            rows={8}
            className="glass-textarea font-mono text-xs"
          />
          {parseError && <p className="text-xs text-[#ff9db0]">{parseError}</p>}
        </div>
      ) : (
        <pre className="code-block max-h-64 text-xs overflow-auto">
          {JSON.stringify(payload.proposed_calls ?? payload.tool_calls ?? payload, null, 2)}
        </pre>
      )}

      <div className="flex flex-wrap gap-2">
        {editMode ? (
          <>
            <Button size="sm" onClick={handleSubmitEdit} loading={loading}>
              <CheckCircle className="h-3.5 w-3.5" /> Submit
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditMode(false)} disabled={loading}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" onClick={() => onDecision('approved')} loading={loading}>
              <CheckCircle className="h-3.5 w-3.5" /> Approve
            </Button>
            <Button size="sm" variant="danger" onClick={() => onDecision('rejected')} disabled={loading}>
              <XCircle className="h-3.5 w-3.5" /> Reject
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditMode(true)} disabled={loading}>
              <Edit3 className="h-3.5 w-3.5" /> Edit
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

// ─── State badge ────────────────────────────────────────────────────────────

function StateBadge({ state, isRunning }: { state: RunState; isRunning: boolean }) {
  if (state === 'idle') return null;
  const map: Record<RunState, { variant: 'blue' | 'green' | 'red' | 'yellow'; label: string }> = {
    idle: { variant: 'blue', label: 'idle' },
    running: { variant: 'blue', label: 'running' },
    waiting_approval: { variant: 'yellow', label: 'approval' },
    done: { variant: 'green', label: 'done' },
    error: { variant: 'red', label: 'error' },
  };
  const { variant, label } = map[state];
  return (
    <Badge variant={variant} className="capitalize">
      {isRunning && <Loader className="h-3 w-3 animate-spin" />}
      {label}
    </Badge>
  );
}

// ─── Provider switcher ──────────────────────────────────────────────────────

const OAUTH_PROVIDERS: AIProvider[] = ['openai_codex', 'claude_code'];

function ProviderSwitcher() {
  const provider = useSettingsStore((s) => s.provider);
  const model = useSettingsStore((s) => s.model);
  const apiKeys = useSettingsStore((s) => s.apiKeys);
  const providerBaseUrls = useSettingsStore((s) => s.providerBaseUrls);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const setProvider = useSettingsStore((s) => s.setProvider);
  const setModel = useSettingsStore((s) => s.setModel);
  const [open, setOpen] = useState(false);
  const [fetchedModels, setFetchedModels] = useState<Partial<Record<AIProvider, string[]>>>({});
  const [loadingModels, setLoadingModels] = useState<AIProvider | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [open]);

  const configuredProviders = (Object.keys(PROVIDERS) as AIProvider[]).filter((p) => {
    if (OAUTH_PROVIDERS.includes(p)) return true;
    return (apiKeys[p] ?? '').trim().length > 0;
  });

  if (configuredProviders.length === 0) return null;

  const currentConfig = PROVIDERS[provider];

  async function handleFetchModels(e: React.MouseEvent, p: AIProvider) {
    e.stopPropagation();
    setLoadingModels(p);
    try {
      const models = await fetchProviderModels(
        p,
        apiKeys[p] ?? '',
        providerBaseUrls[p] || undefined,
        backendUrl,
      );
      setFetchedModels((prev) => ({ ...prev, [p]: models }));
      if (p === provider && models.length > 0 && !models.includes(model)) {
        setModel(models[0]);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to fetch models');
    } finally {
      setLoadingModels(null);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((c) => !c)}
        className="flex items-center gap-1.5 rounded-lg border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1.5 text-xs text-[#8e9ac0] transition-colors hover:border-[rgba(125,207,255,0.18)] hover:text-[#c0d8f0]"
      >
        <span className="font-medium">{currentConfig.label}</span>
        <span className="text-[#4a5578]">·</span>
        <span className="font-mono text-[11px]">{model}</span>
        <ChevronDown className={cn('h-3 w-3 text-[#4a5578] transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 min-w-[240px] overflow-hidden rounded-xl border border-[rgba(162,179,229,0.12)] bg-[rgba(9,12,22,0.96)] shadow-[0_16px_40px_rgba(4,8,18,0.5)] backdrop-blur-2xl">
          <div className="border-b border-[rgba(162,179,229,0.08)] px-3 py-2">
            <p className="text-[11px] text-[#4a5578]">Switch AI Provider</p>
          </div>
          {configuredProviders.map((p) => {
            const cfg = PROVIDERS[p];
            const isActive = p === provider;
            const isOAuth = OAUTH_PROVIDERS.includes(p);
            const availableModels = fetchedModels[p] ?? cfg.models;
            const isFetching = loadingModels === p;

            return (
              <div
                key={p}
                className={cn(
                  'border-b border-[rgba(162,179,229,0.06)] last:border-0',
                  isActive && 'bg-[rgba(125,207,255,0.05)]',
                )}
              >
                <div className="flex items-center">
                  <button
                    type="button"
                    onClick={() => {
                      setProvider(p);
                      setOpen(false);
                    }}
                    className={cn(
                      'flex flex-1 items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]',
                      isActive ? 'text-[#7dcfff]' : 'text-[#8e9ac0]',
                    )}
                  >
                    <div>
                      <p className="text-xs font-medium">{cfg.label}</p>
                      <p className="mt-0.5 font-mono text-[11px] text-[#4a5578]">
                        {isActive ? model : cfg.defaultModel}
                      </p>
                    </div>
                    {isActive && <CheckCircle className="h-3.5 w-3.5 shrink-0" />}
                  </button>
                  {!isOAuth && (
                    <button
                      type="button"
                      title="Fetch models from provider"
                      onClick={(e) => void handleFetchModels(e, p)}
                      disabled={isFetching}
                      className="mr-2 shrink-0 rounded-md p-1 text-[#4a5578] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-[#7dcfff] disabled:opacity-40"
                    >
                      <RefreshCw className={cn('h-3 w-3', isFetching && 'animate-spin')} />
                    </button>
                  )}
                </div>
                {isActive && availableModels.length > 1 && (
                  <div className="px-3 pb-2.5">
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full rounded-lg border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.04)] px-2 py-1.5 font-mono text-[11px] text-[#c0d8f0] outline-none"
                    >
                      {availableModels.map((m) => (
                        <option key={m} value={m} className="bg-[#090c16]">
                          {m}
                        </option>
                      ))}
                    </select>
                    {fetchedModels[p] && (
                      <p className="mt-1 text-[10px] text-[#374060]">{fetchedModels[p]!.length} models from provider</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── @ mention helpers ───────────────────────────────────────────────────────

/** Returns the partial username after the last `@` before the cursor, or null. */
function atMentionAtCursor(text: string, cursor: number): string | null {
  const before = text.slice(0, cursor);
  const match = before.match(/@(\w*)$/);
  return match ? match[1] : null;
}

/** Replace the `@partial` at cursor with `@username ` */
function replaceAtMention(text: string, cursor: number, username: string): { text: string; cursor: number } {
  const before = text.slice(0, cursor);
  const after = text.slice(cursor);
  const replaced = before.replace(/@\w*$/, `@${username} `);
  return { text: replaced + after, cursor: replaced.length };
}

const STATUS_DOT: Record<Account['status'], string> = {
  active: 'bg-[#9ece6a]',
  idle: 'bg-[#4a5578]',
  logging_in: 'bg-[#e0af68]',
  error: 'bg-[#f7768e]',
  challenge: 'bg-[#ff9db0]',
  '2fa_required': 'bg-[#e0af68]',
};

// ─── Main page ───────────────────────────────────────────────────────────────

export function OperatorCopilotPage() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const provider = useSettingsStore((s) => s.provider);
  const model = useSettingsStore((s) => s.model);
  const apiKeys = useSettingsStore((s) => s.apiKeys);
  const providerBaseUrls = useSettingsStore((s) => s.providerBaseUrls);
  const accounts = useAccountStore((s) => s.accounts);

  const session = useCopilotStore((s) => s.session);
  const setSession = useCopilotStore((s) => s.setSession);
  const resetSession = useCopilotStore((s) => s.resetSession);
  const [message, setMessage] = useState('');
  const [resumeLoading, setResumeLoading] = useState(false);
  const [activeCommand, setActiveCommand] = useState<SlashCommand | null>(null);
  const [showPalette, setShowPalette] = useState(false);
  const [paletteSuggestions, setPaletteSuggestions] = useState<SlashCommand[]>([]);

  // @ mention picker
  const [mentionQuery, setMentionQuery] = useState<string | null>(null); // null = hidden
  const [mentionIndex, setMentionIndex] = useState(0);

  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom whenever session events change (streaming)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session]);

  // Focus input on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [message]);

  const consumeStream = useCallback(async (stream: ReadableStream<CopilotEvent>) => {
    const reader = stream.getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const event = value;
        setSession((prev) => {
          const turns = [...prev.turns];
          if (turns.length === 0) return prev;
          const last = { ...turns[turns.length - 1], events: [...turns[turns.length - 1].events, event] };
          turns[turns.length - 1] = last;

          let runState: RunState = prev.runState;
          let threadId = prev.threadId;
          let approvalPayload = prev.approvalPayload;

          if (event.type === 'run_start') {
            runState = 'running';
            if (event.thread_id) threadId = String(event.thread_id);
          } else if (event.type === 'approval_required') {
            runState = 'waiting_approval';
            approvalPayload = (event.payload as Record<string, unknown>) ?? event;
          } else if (event.type === 'run_finish') {
            runState = 'done';
          } else if (event.type === 'run_error') {
            runState = 'error';
          }
          return { ...prev, turns, runState, threadId, approvalPayload };
        });
      }
    } catch (error) {
      if (error instanceof StreamAbortedError) {
        // User cancelled — settle quietly to 'done', no toast
        setSession((prev) => ({ ...prev, runState: 'done' }));
        return;
      }
      const message = error instanceof NetworkError
        ? error.message
        : error instanceof ServerError
          ? `Server error ${error.status}: ${error.message}`
          : error instanceof Error ? error.message : 'Stream error';
      toast.error(message, { duration: 5000 });
      setSession((prev) => ({ ...prev, runState: 'error' }));
    } finally {
      reader.releaseLock();
      setSession((prev) => (prev.runState === 'running' ? { ...prev, runState: 'done' } : prev));
    }
  }, []);

  function handleMessageChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    setMessage(value);

    const cursor = e.target.selectionStart ?? value.length;
    const query = atMentionAtCursor(value, cursor);

    if (query !== null) {
      // @ mention active — mutually exclusive with slash palette
      setMentionQuery(query);
      setMentionIndex(0);
      setShowPalette(false);
    } else {
      setMentionQuery(null);
      if (value.startsWith('/') && !value.includes(' ')) {
        const suggestions = getCommandSuggestions(value);
        setPaletteSuggestions(suggestions);
        setShowPalette(suggestions.length > 0);
      } else {
        setShowPalette(false);
      }
    }
  }

  // Filtered account list for mention picker
  const mentionAccounts = mentionQuery === null ? [] : accounts
    .filter((a) =>
      mentionQuery === '' || a.username.toLowerCase().startsWith(mentionQuery.toLowerCase()),
    )
    .slice(0, 8);
  const showMentionPalette = mentionQuery !== null && mentionAccounts.length > 0;

  function pickMention(account: Account) {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart ?? message.length;
    const { text: nextText, cursor: nextCursor } = replaceAtMention(message, cursor, account.username);
    setMessage(nextText);
    setMentionQuery(null);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(nextCursor, nextCursor);
    });
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!fileInputRef.current) return;
    fileInputRef.current.value = '';          // reset so same file can be re-selected
    if (!file) return;

    const sizeKb = file.size / 1024;
    if (sizeKb > MAX_FILE_KB) {
      toast.error(`File too large (${sizeKb.toFixed(0)} KB). Maximum is ${MAX_FILE_KB} KB.`);
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = (ev.target?.result as string) ?? '';
      setAttachedFile({
        name: file.name,
        content,
        lines: content.split('\n').filter(Boolean).length,
        sizeKb,
      });
    };
    reader.onerror = () => toast.error('Failed to read file.');
    reader.readAsText(file);
  }

  function handleStop() {
    abortRef.current?.abort();
    abortRef.current = null;
  }

  async function handleSend() {
    const text = message.trim();
    if (!text || session.runState === 'running') return;

    // Cancel any in-flight request before starting a new one
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const parsed = parseSlashCommand(text);
    setMessage('');
    setShowPalette(false);

    if (parsed) {
      const { command, args } = parsed;
      setActiveCommand(command);
      setSession((prev) => ({
        ...prev,
        threadId: undefined,
        turns: [...prev.turns, { userPrompt: text, events: [] }],
        runState: 'running',
        approvalPayload: undefined,
      }));
      try {
        const payload = {
          ...command.buildPayload(args),
          provider,
          model,
          apiKey: apiKeys[provider] || undefined,
          providerBaseUrl: providerBaseUrls[provider] || undefined,
        };
        const stream = graphRunner.run(command.runEndpoint, payload, backendUrl, controller.signal);
        await consumeStream(stream);
      } catch (error) {
        if (!(error instanceof StreamAbortedError)) {
          toast.error(error instanceof Error ? error.message : 'Failed to start run');
          setSession((prev) => ({ ...prev, runState: 'error' }));
        }
      }
      return;
    }

    const fileSnapshot = attachedFile;
    setAttachedFile(null);

    setActiveCommand(null);
    setSession((prev) => ({
      ...prev,
      turns: [
        ...prev.turns,
        {
          userPrompt: text,
          attachment: fileSnapshot ? { name: fileSnapshot.name, lines: fileSnapshot.lines } : undefined,
          events: [],
        },
      ],
      runState: 'running',
      approvalPayload: undefined,
    }));

    try {
      const stream = operatorCopilotApi.stream(
        {
          message: text,
          threadId: session.threadId,
          provider,
          model,
          apiKey: apiKeys[provider] || undefined,
          providerBaseUrl: providerBaseUrls[provider] || undefined,
          fileName: fileSnapshot?.name,
          fileContent: fileSnapshot?.content,
          signal: controller.signal,
        },
        backendUrl,
      );
      await consumeStream(stream);
    } catch (error) {
      if (!(error instanceof StreamAbortedError)) {
        toast.error(error instanceof Error ? error.message : 'Failed to start run');
        setSession((prev) => ({ ...prev, runState: 'error' }));
      }
    } finally {
      textareaRef.current?.focus();
    }
  }

  async function handleApproval(result: 'approved' | 'rejected' | 'edited', editedCalls?: Record<string, unknown>[]) {
    if (!session.threadId) { toast.error('No active thread'); return; }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResumeLoading(true);
    setSession((prev) => ({ ...prev, runState: 'running', approvalPayload: undefined }));
    try {
      if (activeCommand) {
        const resumePayload = activeCommand.buildResumePayload(session.threadId, result, editedCalls);
        const stream = graphRunner.resume(activeCommand.resumeEndpoint, resumePayload, backendUrl, controller.signal);
        await consumeStream(stream);
      } else {
        const stream = operatorCopilotApi.resume(
          { threadId: session.threadId, approvalResult: result, editedCalls, signal: controller.signal },
          backendUrl,
        );
        await consumeStream(stream);
      }
    } catch (error) {
      if (!(error instanceof StreamAbortedError)) {
        toast.error(error instanceof Error ? error.message : 'Resume failed');
        setSession((prev) => ({ ...prev, runState: 'error' }));
      }
    } finally {
      setResumeLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // @ mention navigation takes priority
    if (showMentionPalette) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((i) => Math.min(i + 1, mentionAccounts.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const acc = mentionAccounts[mentionIndex];
        if (acc) pickMention(acc);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setMentionQuery(null);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  const isRunning = session.runState === 'running';
  const hasSession = session.turns.length > 0;

  function handleNewChat() {
    abortRef.current?.abort();
    abortRef.current = null;
    resetSession();
    setActiveCommand(null);
    setAttachedFile(null);
    setMessage('');
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Top bar ── */}
      <div className="shrink-0 flex items-center justify-between gap-4 border-b border-[rgba(162,179,229,0.10)] px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.10)]">
            <Bot className="h-4 w-4 text-[#7dcfff]" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[#eef4ff] leading-none">Operator Copilot</p>
            <p className="mt-0.5 text-[11px] text-[#4a5578]">streaming AI · tool approvals · <code className="font-mono">@</code> accounts · <code className="font-mono">/</code> commands</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {(session.turns.length > 0 || session.threadId) && (
            <button
              type="button"
              onClick={handleNewChat}
              disabled={isRunning}
              title="New Chat"
              aria-label="New Chat"
              className="flex items-center gap-1.5 rounded-lg border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1.5 text-xs text-[#8e9ac0] transition-colors hover:border-[rgba(125,207,255,0.18)] hover:text-[#c0d8f0] disabled:opacity-30"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              <span>New Chat</span>
            </button>
          )}
          <ProviderSwitcher />
          <StateBadge state={session.runState} isRunning={isRunning} />
          {session.threadId && (
            <span className="flex items-center gap-1.5 rounded-full border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1 font-mono text-[11px] text-[#4a5578]">
              <CircleDot className="h-2.5 w-2.5 text-[#374060]" />
              {session.threadId.slice(0, 8)}
            </span>
          )}
        </div>
      </div>

      {/* ── Thread ── */}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-5">

        {/* Empty state */}
        {!hasSession && (
          <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[rgba(125,207,255,0.14)] bg-[rgba(125,207,255,0.08)]">
              <Bot className="h-8 w-8 text-[#4a7a9a]" />
            </div>
            <div>
              <p className="text-base font-semibold text-[#c0caf5]">Ready</p>
              <p className="mt-1 text-sm text-[#4a5578]">Send a prompt or type <code className="font-mono text-[#7dcfff]">/</code> for commands</p>
            </div>
            <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
              {QUICK_SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => { setMessage(s); textareaRef.current?.focus(); }}
                  className="cursor-pointer rounded-xl border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5 text-left text-xs text-[#8e9ac0] transition-colors duration-150 hover:border-[rgba(125,207,255,0.18)] hover:bg-[rgba(125,207,255,0.06)] hover:text-[#c0d8f0]"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Active thread */}
        {hasSession && (
          <div className="mx-auto max-w-3xl space-y-3">

            {session.turns.map((turn, idx) => (
              <div key={idx} className="space-y-3">
                {/* User message bubble */}
                <div className="flex justify-end gap-3">
                  <div className="max-w-[80%] space-y-1.5">
                    <div className="rounded-2xl rounded-tr-sm border border-[rgba(122,162,247,0.18)] bg-[rgba(122,162,247,0.10)] px-4 py-2.5">
                      <p className="text-sm leading-6 text-[#dce6ff]">{turn.userPrompt}</p>
                    </div>
                    {turn.attachment && (
                      <div className="flex items-center gap-1.5 rounded-lg border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1.5">
                        <Paperclip className="h-3 w-3 shrink-0 text-[#4a6a8a]" />
                        <span className="font-mono text-[11px] text-[#6a8aaa]">{turn.attachment.name}</span>
                        <span className="text-[11px] text-[#374060]">·</span>
                        <span className="text-[11px] text-[#374060]">{turn.attachment.lines} lines</span>
                      </div>
                    )}
                  </div>
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)]">
                    <User className="h-3.5 w-3.5 text-[#6a7aa0]" />
                  </div>
                </div>

                {/* Events for this turn */}
                {turn.events.map((event, i) => (
                  <EventCard key={i} event={event} />
                ))}
              </div>
            ))}

            {/* Approval */}
            {session.runState === 'waiting_approval' && session.approvalPayload && (
              <ApprovalCard payload={session.approvalPayload} onDecision={handleApproval} loading={resumeLoading} />
            )}

            {/* Streaming indicator */}
            {isRunning && (
              <div className="flex items-center gap-2">
                <Loader className="h-3.5 w-3.5 animate-spin text-[#4a5578]" />
                <span className="text-xs text-[#374060]">processing…</span>
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ── */}
      <div className="shrink-0 border-t border-[rgba(162,179,229,0.10)] bg-[rgba(6,8,16,0.86)] px-5 py-3 backdrop-blur-2xl">
        <div className="mx-auto max-w-3xl">

          {/* Attachment chip */}
          {attachedFile && (
            <div className="mb-2 flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-lg border border-[rgba(125,207,255,0.16)] bg-[rgba(125,207,255,0.06)] px-2.5 py-1.5">
                <Paperclip className="h-3 w-3 shrink-0 text-[#7dcfff]" />
                <span className="font-mono text-[11px] text-[#a0c8e8]">{attachedFile.name}</span>
                <span className="text-[11px] text-[#4a6878]">·</span>
                <span className="text-[11px] text-[#4a6878]">{attachedFile.lines} lines</span>
                <span className="text-[11px] text-[#374060]">·</span>
                <span className="text-[11px] text-[#374060]">{attachedFile.sizeKb < 1 ? `${(attachedFile.sizeKb * 1024).toFixed(0)} B` : `${attachedFile.sizeKb.toFixed(1)} KB`}</span>
                <button
                  type="button"
                  onClick={() => setAttachedFile(null)}
                  className="ml-0.5 rounded p-0.5 text-[#4a6878] transition-colors hover:text-[#ff9db0]"
                  aria-label="Remove attachment"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            id="operator-copilot-attachment"
            name="operatorCopilotAttachment"
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            className="hidden"
            onChange={handleFileSelect}
            aria-hidden="true"
          />

          {/* Unified input container */}
          <div className="relative flex items-end gap-2 rounded-2xl border border-[rgba(162,179,229,0.16)] bg-[rgba(10,14,24,0.52)] px-2 py-2 backdrop-blur-xl transition-colors focus-within:border-[rgba(125,207,255,0.44)] focus-within:shadow-[0_0_0_3px_rgba(125,207,255,0.08)]">

            {/* @ mention palette — anchored to container */}
            {showMentionPalette && (
              <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-xl border border-[rgba(125,207,255,0.14)] bg-[rgba(9,12,22,0.97)] shadow-[0_16px_40px_rgba(4,8,18,0.55)] backdrop-blur-2xl">
                <div className="flex items-center gap-2 border-b border-[rgba(162,179,229,0.07)] px-3 py-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-[#4a5578]">Accounts</span>
                  <span className="ml-auto text-[10px] text-[#2e3556]">↑↓ navigasi · Enter pilih · Esc tutup</span>
                </div>
                {mentionAccounts.map((acc, i) => (
                  <button
                    key={acc.id}
                    type="button"
                    onMouseEnter={() => setMentionIndex(i)}
                    onMouseDown={(e) => { e.preventDefault(); pickMention(acc); }}
                    className={cn(
                      'flex w-full cursor-pointer items-center gap-3 px-3 py-2 text-left transition-colors duration-100',
                      i === mentionIndex ? 'bg-[rgba(125,207,255,0.09)]' : 'hover:bg-[rgba(255,255,255,0.03)]',
                    )}
                  >
                    {/* Avatar / initials */}
                    <div className="relative shrink-0">
                      {acc.avatar ? (
                        <img src={acc.avatar} alt={acc.username} className="h-7 w-7 rounded-full object-cover" />
                      ) : (
                        <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.06)] text-[11px] font-semibold uppercase text-[#7aa2f7]">
                          {acc.username.slice(0, 2)}
                        </div>
                      )}
                      <span className={cn('absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-[rgba(9,12,22,1)]', STATUS_DOT[acc.status])} />
                    </div>

                    {/* Username + status */}
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-[#c0caf5]">
                        <span className="text-[#7dcfff]">@</span>{acc.username}
                      </p>
                      <p className="text-[11px] capitalize text-[#4a5578]">{acc.status}</p>
                    </div>

                    {/* Keyboard hint for highlighted item */}
                    {i === mentionIndex && (
                      <span className="shrink-0 text-[10px] text-[#2e3556]">↵</span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {/* Slash command palette — anchored to container */}
            {showPalette && paletteSuggestions.length > 0 && (
              <div className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-xl border border-[rgba(162,179,229,0.12)] bg-[rgba(9,12,22,0.96)] shadow-[0_16px_40px_rgba(4,8,18,0.5)] backdrop-blur-2xl">
                {paletteSuggestions.map((cmd) => (
                  <button
                    key={cmd.name}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setMessage(`/${cmd.name} `);
                      setShowPalette(false);
                      textareaRef.current?.focus();
                    }}
                    className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                  >
                    <Terminal className="h-3.5 w-3.5 shrink-0 text-[#7dcfff]" />
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-xs text-[#d4f1ff]">/{cmd.name}</span>
                      <span className="ml-2 text-[11px] text-[#4a5578]">{cmd.argSchema}</span>
                    </div>
                    <span className="max-w-[14rem] truncate text-[11px] text-[#4a5578]">{cmd.description}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Attach button — LEFT inside container */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isRunning}
              title="Attach file (.txt, .csv, .json)"
              aria-label="Attach file"
              className={cn(
                'mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors disabled:opacity-30',
                attachedFile
                  ? 'text-[#7dcfff]'
                  : 'text-[#4a5578] hover:text-[#7dcfff]',
              )}
            >
              <Paperclip className="h-[1.05rem] w-[1.05rem]" />
            </button>

            {/* Textarea — transparent, no own border */}
            <div className="relative min-w-0 flex-1">
              <textarea
                ref={textareaRef}
                id="operator-copilot-message"
                name="operatorCopilotMessage"
                value={message}
                onChange={handleMessageChange}
                onKeyDown={handleKeyDown}
                placeholder={isRunning ? 'Waiting for response…' : 'Ask anything… (@ for accounts, / for commands)'}
                disabled={isRunning}
                rows={1}
                aria-label="Message to operator copilot"
                className="w-full resize-none bg-transparent py-1.5 text-sm text-[#eef4ff] outline-none placeholder:text-[#3a4460] disabled:opacity-40"
                style={{ maxHeight: '160px' }}
              />
              {activeCommand && session.runState !== 'idle' && (
                <div className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 flex items-center gap-1 rounded-full border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.05)] px-2 py-0.5 text-[10px] text-[#7dcfff]">
                  <Terminal className="h-2.5 w-2.5" />
                  <span className="font-mono">/{activeCommand.name}</span>
                </div>
              )}
            </div>

            {/* Send / Stop — RIGHT inside container */}
            {isRunning ? (
              <button
                type="button"
                onClick={handleStop}
                aria-label="Stop generation"
                title="Stop generation"
                className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[rgba(247,118,142,0.18)] text-[#f7768e] transition-colors hover:bg-[rgba(247,118,142,0.28)]"
              >
                <Square className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!message.trim() && !attachedFile}
                aria-label="Send message"
                className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[rgba(122,162,247,0.90)] text-white transition-colors hover:bg-[rgba(122,162,247,1)] disabled:opacity-30"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <p className="mt-2 text-center text-[11px] text-[#2a3450]">
            {isRunning ? 'Click ■ to stop generation' : 'Enter to send · Shift+Enter for new line'}
          </p>
        </div>
      </div>
    </div>
  );
}
