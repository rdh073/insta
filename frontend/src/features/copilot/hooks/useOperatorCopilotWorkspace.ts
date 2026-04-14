import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import toast from 'react-hot-toast';
import { graphRunner } from '../../../api/graph-runner';
import { commandJsonRunner } from '../../../api/command-json-runner';
import { operatorCopilotApi, StreamAbortedError, NetworkError, ServerError } from '../../../api/operator-copilot';
import type { CopilotEvent } from '../../../api/operator-copilot';
import { parseSlashCommand, getCommandSuggestions } from '../../../lib/slash-commands';
import type { SlashCommand } from '../../../lib/slash-commands';
import { useSettingsStore } from '../../../store/settings';
import { useAccountStore } from '../../../store/accounts';
import { useCopilotStore } from '../../../store/copilot';
import type { RunState } from '../../../store/copilot';
import type { Account } from '../../../types';
import {
  atMentionAtCursor,
  replaceAtMention,
  MAX_FILE_KB,
} from '../components/copilot-helpers';
import type { AttachedFile } from '../components/copilot-helpers';

export function useOperatorCopilotWorkspace() {
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

  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);

  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [message]);

  const appendRunError = useCallback((errorMessage: string) => {
    setSession((prev) => {
      const turns = [...prev.turns];
      if (turns.length > 0) {
        const lastIdx = turns.length - 1;
        const lastTurn = turns[lastIdx];
        turns[lastIdx] = {
          ...lastTurn,
          events: [...lastTurn.events, { type: 'run_error', message: errorMessage }],
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
      const errorMessage = error instanceof NetworkError
        ? error.message
        : error instanceof ServerError
          ? `Server error ${error.status}: ${error.message}`
          : error instanceof Error ? error.message : 'Stream error';
      toast.error(errorMessage, { duration: 5000 });
      appendRunError(errorMessage);
    } finally {
      reader.releaseLock();
      setSession((prev) => (prev.runState === 'running' ? { ...prev, runState: 'done' } : prev));
    }
  }, [appendRunError, setSession]);

  function handleMessageChange(e: ChangeEvent<HTMLTextAreaElement>) {
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

  const mentionAccounts = useMemo(
    () => mentionQuery === null
      ? []
      : accounts
        .filter((a) => mentionQuery === '' || a.username.toLowerCase().startsWith(mentionQuery.toLowerCase()))
        .slice(0, 8),
    [accounts, mentionQuery],
  );

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

  function handleFileSelect(e: ChangeEvent<HTMLInputElement>) {
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
    if (!session.threadId) {
      toast.error('No active thread');
      return;
    }
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
        const errorMessage = error instanceof Error ? error.message : 'Invalid edited resume payload.';
        toast.error(errorMessage);
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

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
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

  function handleSuggestionClick(suggestion: string) {
    setMessage(suggestion);
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function handleCommandPick(nextMessage: string) {
    setMessage(nextMessage);
    setShowPalette(false);
  }

  return {
    backendUrl,
    backendApiKey,
    session,
    message,
    resumeLoading,
    activeCommand,
    showPalette,
    paletteSuggestions,
    mentionAccounts,
    mentionIndex,
    showMentionPalette,
    attachedFile,
    textareaRef,
    scrollRef,
    bottomRef,
    fileInputRef,
    isRunning,
    hasSession,
    setMentionIndex,
    handleNewChat,
    handleSuggestionClick,
    handleApproval,
    handleFileSelect,
    handleStop,
    handleMessageChange,
    handleKeyDown,
    handleSend,
    pickMention,
    handleCommandPick,
    clearAttachedFile: () => setAttachedFile(null),
    openFilePicker: () => fileInputRef.current?.click(),
  };
}
