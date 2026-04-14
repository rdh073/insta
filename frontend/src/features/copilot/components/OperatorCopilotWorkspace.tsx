import { Bot, CircleDot, Loader, Paperclip, PlusCircle, Send, Square, Terminal, User, X } from 'lucide-react';
import { cn } from '../../../lib/cn';
import { useOperatorCopilotWorkspace } from '../hooks/useOperatorCopilotWorkspace';
import { ApprovalCard } from './ApprovalCard';
import { CommandPalette } from './CommandPalette';
import { CopilotEmptyState } from './CopilotEmptyState';
import { EventCard } from './EventCard';
import { MentionPalette } from './MentionPalette';
import { ProviderSwitcher } from './ProviderSwitcher';
import { StateBadge } from './StateBadge';
import { ACCEPTED_FILE_TYPES } from './copilot-helpers';

export function OperatorCopilotWorkspace() {
  const controller = useOperatorCopilotWorkspace();

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 flex items-center justify-between gap-4 border-b border-[rgba(162,179,229,0.10)] px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-[rgba(125,207,255,0.18)] bg-[rgba(125,207,255,0.10)]">
            <Bot className="h-4 w-4 text-[#7dcfff]" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-none text-[#eef4ff]">Operator Copilot</p>
            <p className="mt-0.5 text-[11px] text-[#4a5578]">
              streaming AI · tool approvals · <code className="font-mono">@</code> accounts · <code className="font-mono">/</code> commands
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {(controller.session.turns.length > 0 || controller.session.threadId) && (
            <button
              type="button"
              onClick={controller.handleNewChat}
              disabled={controller.isRunning}
              title="New Chat"
              aria-label="New Chat"
              className="flex items-center gap-1.5 rounded-lg border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-2.5 py-1.5 text-xs text-[#8e9ac0] transition-colors hover:border-[rgba(125,207,255,0.18)] hover:text-[#c0d8f0] disabled:opacity-30"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              <span>New Chat</span>
            </button>
          )}
          <ProviderSwitcher />
          <StateBadge state={controller.session.runState} isRunning={controller.isRunning} />
          {controller.session.threadId && (
            <span className="flex items-center gap-1.5 rounded-full border border-[rgba(162,179,229,0.10)] bg-[rgba(255,255,255,0.03)] px-2.5 py-1 font-mono text-[11px] text-[#4a5578]">
              <CircleDot className="h-2.5 w-2.5 text-[#374060]" />
              {controller.session.threadId.slice(0, 8)}
            </span>
          )}
        </div>
      </div>

      <div ref={controller.scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-5">
        {!controller.hasSession && <CopilotEmptyState onSuggestionClick={controller.handleSuggestionClick} />}

        {controller.hasSession && (
          <div className="mx-auto max-w-3xl space-y-3">
            {controller.session.turns.map((turn, idx) => (
              <div key={idx} className="space-y-3">
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

            {controller.session.runState === 'waiting_approval' && controller.session.approvalPayload && (
              <ApprovalCard
                payload={controller.session.approvalPayload}
                onDecision={controller.handleApproval}
                loading={controller.resumeLoading}
              />
            )}

            {controller.isRunning && (
              <div className="flex items-center gap-2">
                <Loader className="h-3.5 w-3.5 animate-spin text-[#4a5578]" />
                <span className="text-xs text-[#374060]">processing…</span>
              </div>
            )}
          </div>
        )}
        <div ref={controller.bottomRef} />
      </div>

      <div className="shrink-0 border-t border-[rgba(162,179,229,0.10)] bg-[rgba(6,8,16,0.86)] px-5 py-3 backdrop-blur-2xl">
        <div className="mx-auto max-w-3xl">
          {controller.attachedFile && (
            <div className="mb-2 flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-lg border border-[rgba(125,207,255,0.16)] bg-[rgba(125,207,255,0.06)] px-2.5 py-1.5">
                <Paperclip className="h-3 w-3 shrink-0 text-[#7dcfff]" />
                <span className="font-mono text-[11px] text-[#a0c8e8]">{controller.attachedFile.name}</span>
                <span className="text-[11px] text-[#4a6878]">·</span>
                <span className="text-[11px] text-[#4a6878]">{controller.attachedFile.lines} lines</span>
                <span className="text-[11px] text-[#374060]">·</span>
                <span className="text-[11px] text-[#374060]">
                  {controller.attachedFile.sizeKb < 1
                    ? `${(controller.attachedFile.sizeKb * 1024).toFixed(0)} B`
                    : `${controller.attachedFile.sizeKb.toFixed(1)} KB`}
                </span>
                <button
                  type="button"
                  onClick={controller.clearAttachedFile}
                  className="ml-0.5 rounded p-0.5 text-[#4a6878] transition-colors hover:text-[#ff9db0]"
                  aria-label="Remove attachment"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}

          <input
            ref={controller.fileInputRef}
            id="operator-copilot-attachment"
            name="operatorCopilotAttachment"
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            className="hidden"
            onChange={controller.handleFileSelect}
            aria-hidden="true"
          />

          <div className="relative flex items-end gap-2 rounded-2xl border border-[rgba(162,179,229,0.16)] bg-[rgba(10,14,24,0.52)] px-2 py-2 backdrop-blur-xl transition-colors focus-within:border-[rgba(125,207,255,0.44)] focus-within:shadow-[0_0_0_3px_rgba(125,207,255,0.08)]">
            {controller.showMentionPalette && (
              <MentionPalette
                accounts={controller.mentionAccounts}
                activeIndex={controller.mentionIndex}
                onHover={controller.setMentionIndex}
                onPick={controller.pickMention}
                backendUrl={controller.backendUrl}
                backendApiKey={controller.backendApiKey}
              />
            )}

            {controller.showPalette && controller.paletteSuggestions.length > 0 && (
              <CommandPalette
                suggestions={controller.paletteSuggestions}
                onPick={controller.handleCommandPick}
                textareaRef={controller.textareaRef}
              />
            )}

            <button
              type="button"
              onClick={controller.openFilePicker}
              disabled={controller.isRunning}
              title="Attach file (.txt, .csv, .json)"
              aria-label="Attach file"
              className={cn(
                'mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors disabled:opacity-30',
                controller.attachedFile ? 'text-[#7dcfff]' : 'text-[#4a5578] hover:text-[#7dcfff]',
              )}
            >
              <Paperclip className="h-[1.05rem] w-[1.05rem]" />
            </button>

            <div className="relative min-w-0 flex-1">
              <textarea
                ref={controller.textareaRef}
                id="operator-copilot-message"
                name="operatorCopilotMessage"
                value={controller.message}
                onChange={controller.handleMessageChange}
                onKeyDown={controller.handleKeyDown}
                placeholder={controller.isRunning ? 'Waiting for response…' : 'Ask anything… (@ for accounts, / for commands)'}
                disabled={controller.isRunning}
                rows={1}
                aria-label="Message to operator copilot"
                className="w-full resize-none bg-transparent py-1.5 text-sm text-[#eef4ff] outline-none placeholder:text-[#3a4460] disabled:opacity-40"
                style={{ maxHeight: '160px' }}
              />
              {controller.activeCommand && controller.session.runState !== 'idle' && (
                <div className="pointer-events-none absolute right-0 top-1/2 flex -translate-y-1/2 items-center gap-1 rounded-full border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.05)] px-2 py-0.5 text-[10px] text-[#7dcfff]">
                  <Terminal className="h-2.5 w-2.5" />
                  <span className="font-mono">/{controller.activeCommand.name}</span>
                </div>
              )}
            </div>

            {controller.isRunning ? (
              <button
                type="button"
                onClick={controller.handleStop}
                aria-label="Stop generation"
                title="Stop generation"
                className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[rgba(247,118,142,0.18)] text-[#f7768e] transition-colors hover:bg-[rgba(247,118,142,0.28)]"
              >
                <Square className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void controller.handleSend()}
                disabled={!controller.message.trim() && !controller.attachedFile}
                aria-label="Send message"
                className="mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[rgba(122,162,247,0.90)] text-white transition-colors hover:bg-[rgba(122,162,247,1)] disabled:opacity-30"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <p className="mt-2 text-center text-[11px] text-[#2a3450]">
            {controller.isRunning ? 'Click ■ to stop generation' : 'Enter to send · Shift+Enter for new line'}
          </p>
        </div>
      </div>
    </div>
  );
}
