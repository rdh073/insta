import { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Bot,
  CircleDot,
  Loader,
  Paperclip,
  PlusCircle,
  Send,
  Square,
  Terminal,
  User,
  X,
} from 'lucide-react';
import { graphRunner } from '../api/graph-runner';
import { commandJsonRunner } from '../api/command-json-runner';
import { operatorCopilotApi, StreamAbortedError, NetworkError, ServerError } from '../api/operator-copilot';
import type { CopilotEvent } from '../api/operator-copilot';
import { parseSlashCommand, getCommandSuggestions } from '../lib/slash-commands';
import type { SlashCommand } from '../lib/slash-commands';
import { useSettingsStore } from '../store/settings';
import { useAccountStore } from '../store/accounts';
import { useCopilotStore } from '../store/copilot';
import type { RunState } from '../store/copilot';
import type { Account } from '../types';
import { cn } from '../lib/cn';

import {
  EventCard,
  ApprovalCard,
  StateBadge,
  ProviderSwitcher,
  MentionPalette,
  CommandPalette,
  CopilotEmptyState,
  atMentionAtCursor,
  replaceAtMention,
  MAX_FILE_KB,
  ACCEPTED_FILE_TYPES,
} from '../features/copilot/components';
import type { AttachedFile } from '../features/copilot/components';

// ─── Main page ───────────────────────────────────────────────────────────────

export function OperatorCopilotPage() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
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
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);

  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom whenever session events change
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

  // ── Stream consumer ──

  const appendRunError = useCallback((message: string) => {
    setSession((prev) => {
      const turns = [...prev.turns];
      if (turns.length > 0) {
        const lastIdx = turns.length - 1;
        const lastTurn = turns[lastIdx];
        turns[lastIdx] = {
          ...lastTurn,
          events: [...lastTurn.events, { type: 'run_error', message }],
        };
      }
      return { ...prev, turns, runState: 'error' };
    });
  }, [setSession]);

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
        setSession((prev) => ({ ...prev, runState: 'done' }));
        return;
      }
      const message = error instanceof NetworkError
        ? error.message
        : error instanceof ServerError
          ? `Server error ${error.status}: ${error.message}`
          : error instanceof Error ? error.message : 'Stream error';
      toast.error(message, { duration: 5000 });
      appendRunError(message);
    } finally {
      reader.releaseLock();
      setSession((prev) => (prev.runState === 'running' ? { ...prev, runState: 'done' } : prev));
    }
  }, [appendRunError, setSession]);

  // ── Handlers ──

  function handleMessageChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    setMessage(value);

    const cursor = e.target.selectionStart ?? value.length;
    const query = atMentionAtCursor(value, cursor);

    if (query !== null) {
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
    fileInputRef.current.value = '';
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
        const rawPayload = command.buildPayload(args);
        for (const key of ['account_id', 'accountId'] as const) {
          const val = rawPayload[key];
          if (typeof val === 'string') {
            const match = accounts.find((a) => a.username === val);
            if (match) rawPayload[key] = match.id;
          }
        }
        const payload = {
          ...rawPayload,
        };
        const stream = command.transport === 'json'
          ? commandJsonRunner.run(command.runEndpoint, payload, backendUrl, controller.signal)
          : graphRunner.run(
            command.runEndpoint,
            {
              ...payload,
              provider,
              model,
              apiKey: apiKeys[provider] || undefined,
              providerBaseUrl: providerBaseUrls[provider] || undefined,
            },
            backendUrl,
            controller.signal,
          );
        await consumeStream(stream);
      } catch (error) {
        if (!(error instanceof StreamAbortedError)) {
          const errMessage = error instanceof Error ? error.message : 'Failed to start run';
          toast.error(errMessage);
          appendRunError(errMessage);
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
        const errMessage = error instanceof Error ? error.message : 'Failed to start run';
        toast.error(errMessage);
        appendRunError(errMessage);
      }
    } finally {
      textareaRef.current?.focus();
    }
  }

  async function handleApproval(result: 'approved' | 'rejected' | 'edited', editedCalls?: Record<string, unknown>[]) {
    if (!session.threadId) { toast.error('No active thread'); return; }
    if (result === 'edited' && (!editedCalls || editedCalls.length === 0)) {
      toast.error('Edited approval requires at least one edited call.');
      return;
    }

    let resumePayload: Record<string, unknown> | undefined;
    if (activeCommand) {
      try {
        resumePayload = activeCommand.buildResumePayload(
          session.threadId,
          result,
          editedCalls,
          session.approvalPayload,
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Invalid edited resume payload.';
        toast.error(message);
        return;
      }
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setResumeLoading(true);
    setSession((prev) => ({ ...prev, runState: 'running', approvalPayload: undefined }));
    try {
      if (activeCommand) {
        if (!resumePayload) {
          throw new Error('Resume payload missing for slash command.');
        }
        const stream = activeCommand.transport === 'json'
          ? commandJsonRunner.resume(activeCommand.resumeEndpoint, resumePayload, backendUrl, controller.signal)
          : graphRunner.resume(activeCommand.resumeEndpoint, resumePayload, backendUrl, controller.signal);
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
        const errMessage = error instanceof Error ? error.message : 'Resume failed';
        toast.error(errMessage);
        appendRunError(errMessage);
      }
    } finally {
      setResumeLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
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

  // ── Render ──

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

        {!hasSession && (
          <CopilotEmptyState onSuggestionClick={(s) => { setMessage(s); textareaRef.current?.focus(); }} />
        )}

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

                {turn.events.map((event, i) => (
                  <EventCard key={i} event={event} />
                ))}
              </div>
            ))}

            {session.runState === 'waiting_approval' && session.approvalPayload && (
              <ApprovalCard payload={session.approvalPayload} onDecision={handleApproval} loading={resumeLoading} />
            )}

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

            {showMentionPalette && (
              <MentionPalette
                accounts={mentionAccounts}
                activeIndex={mentionIndex}
                onHover={setMentionIndex}
                onPick={pickMention}
                backendUrl={backendUrl}
                backendApiKey={backendApiKey}
              />
            )}

            {showPalette && paletteSuggestions.length > 0 && (
              <CommandPalette
                suggestions={paletteSuggestions}
                onPick={(msg) => { setMessage(msg); setShowPalette(false); }}
                textareaRef={textareaRef}
              />
            )}

            {/* Attach button */}
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

            {/* Textarea */}
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

            {/* Send / Stop */}
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
