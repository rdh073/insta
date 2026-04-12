import type { CopilotEvent } from '../api/operator-copilot';

type ApprovalResult = 'approved' | 'rejected' | 'edited';

export interface SlashCommand {
  name: string;
  description: string;
  argSchema: string;
  transport: 'sse' | 'json';
  runEndpoint: string;
  resumeEndpoint: string;
  buildPayload: (args: string, threadId?: string) => Record<string, unknown>;
  buildResumePayload: (
    threadId: string,
    result: ApprovalResult,
    editedCalls?: Record<string, unknown>[],
    approvalPayload?: Record<string, unknown>,
  ) => Record<string, unknown>;
}

// Re-export so consumers don't need a separate import
export type { CopilotEvent };

function extractMentions(args: string): { usernames: string[]; remaining: string } {
  const parts = args.trim().split(/\s+/);
  const usernames: string[] = [];
  const rest: string[] = [];
  for (const part of parts) {
    if (part.startsWith('@')) {
      usernames.push(part.slice(1));
    } else {
      rest.push(part);
    }
  }
  return { usernames, remaining: rest.join(' ') };
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined;
  return value as Record<string, unknown>;
}

function mergeEditedRecords(
  editedCalls?: Record<string, unknown>[],
): Record<string, unknown> | undefined {
  if (!editedCalls || editedCalls.length === 0) return undefined;
  const merged: Record<string, unknown> = {};
  for (const call of editedCalls) {
    for (const [key, value] of Object.entries(call)) {
      merged[key] = value;
    }
  }
  return Object.keys(merged).length > 0 ? merged : undefined;
}

function readFirstString(
  obj: Record<string, unknown> | undefined,
  keys: string[],
): string | undefined {
  if (!obj) return undefined;
  for (const key of keys) {
    const value = obj[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return undefined;
}

function readFirstStringArray(
  obj: Record<string, unknown> | undefined,
  keys: string[],
): string[] | undefined {
  if (!obj) return undefined;
  for (const key of keys) {
    const value = obj[key];
    if (!Array.isArray(value)) continue;
    const normalized = value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean);
    if (normalized.length > 0) return normalized;
  }
  return undefined;
}

function readPositiveDecisionOption(
  approvalPayload?: Record<string, unknown>,
): string | undefined {
  const options = approvalPayload?.options;
  if (!Array.isArray(options)) return undefined;
  return options.find((item): item is string => typeof item === 'string' && item !== 'abort');
}

function isRecoverDecision(value: string | undefined): value is 'provide_2fa' | 'approve_proxy_swap' | 'abort' {
  return value === 'provide_2fa' || value === 'approve_proxy_swap' || value === 'abort';
}

function extractMonitorParameters(
  edited: Record<string, unknown> | undefined,
): Record<string, unknown> | undefined {
  if (!edited) return undefined;

  const nestedParameters = asRecord(edited.parameters);
  const base: Record<string, unknown> = {
    ...(nestedParameters ?? edited),
  };

  const usernames = readFirstStringArray(
    { ...base, ...edited },
    ['usernames', 'target_usernames', 'targetUsernames'],
  );
  if (usernames && usernames.length > 0) {
    base.usernames = usernames;
  }

  const caption = readFirstString({ ...base, ...edited }, ['caption']);
  if (caption) {
    base.caption = caption;
  }

  const scheduledAt = readFirstString(
    { ...base, ...edited },
    ['scheduled_at', 'scheduledAt'],
  );
  if (scheduledAt) {
    base.scheduled_at = scheduledAt;
  }

  const mediaPaths = readFirstStringArray(
    { ...base, ...edited },
    ['media_paths', 'mediaPaths', 'media_refs', 'mediaRefs'],
  );
  if (mediaPaths && mediaPaths.length > 0) {
    base.media_paths = mediaPaths;
  }

  return Object.keys(base).length > 0 ? base : undefined;
}

function ensureEditedValue(
  commandName: string,
  fieldName: string,
  value: unknown,
): void {
  if (typeof value === 'string' && value.trim()) return;
  throw new Error(`/${commandName} edited resume requires ${fieldName}.`);
}

function ensureEditedParameters(
  commandName: string,
  parameters: Record<string, unknown> | undefined,
): void {
  if (parameters && Object.keys(parameters).length > 0) return;
  throw new Error(`/${commandName} edited resume requires non-empty parameters.`);
}

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'engage',
    description: 'Run smart engagement for an account with a goal',
    argSchema: '@username <engagement goal>',
    transport: 'sse',
    runEndpoint: '/ai/smart-engagement/recommend/stream',
    resumeEndpoint: '/ai/smart-engagement/resume/stream',
    buildPayload(args, threadId) {
      const { usernames, remaining } = extractMentions(args);
      return {
        threadId,
        execution_mode: 'recommendation',
        goal: remaining || 'engage with relevant posts in niche',
        account_id: usernames[0] ?? 'default_account',
        max_targets: 5,
        max_actions_per_target: 3,
      };
    },
    buildResumePayload(threadId, result, editedCalls) {
      const edited = mergeEditedRecords(editedCalls);
      const content =
        result === 'edited'
          ? readFirstString(edited, ['content', 'draft_content', 'edited_content', 'text', 'message'])
          : undefined;
      return {
        thread_id: threadId,
        decision: result,
        ...(content ? { content } : {}),
      };
    },
  },
  {
    name: 'monitor',
    description: 'Evaluate recent campaigns and suggest next actions',
    argSchema: '[lookback_days=7]',
    transport: 'sse',
    runEndpoint: '/ai/campaign-monitor/run',
    resumeEndpoint: '/ai/campaign-monitor/resume',
    buildPayload(args, threadId) {
      const days = parseInt(args.trim(), 10);
      return {
        threadId,
        jobIds: [],
        lookbackDays: Number.isFinite(days) ? days : 7,
        requestDecision: true,
      };
    },
    buildResumePayload(threadId, result, editedCalls) {
      const decision =
        result === 'approved' ? 'approve' : result === 'edited' ? 'modify' : 'skip';
      const edited = mergeEditedRecords(editedCalls);
      const parameters = result === 'edited' ? extractMonitorParameters(edited) : undefined;
      if (result === 'edited') {
        ensureEditedParameters('monitor', parameters);
      }
      return {
        threadId,
        decision,
        ...(result === 'edited' ? { parameters } : {}),
      };
    },
  },
  {
    name: 'risk',
    description: 'Evaluate account risk and apply control policy',
    argSchema: '@username',
    transport: 'sse',
    runEndpoint: '/ai/risk-control/run',
    resumeEndpoint: '/ai/risk-control/resume',
    buildPayload(args, threadId) {
      const { usernames, remaining } = extractMentions(args);
      const accountId = usernames[0] ?? remaining.trim();
      return { threadId, accountId };
    },
    buildResumePayload(threadId, result, editedCalls) {
      const decision =
        result === 'approved'
          ? 'approve_policy'
          : result === 'edited'
          ? 'override_policy'
          : 'abort';
      const edited = mergeEditedRecords(editedCalls);
      const overridePolicy =
        result === 'edited'
          ? readFirstString(edited, ['override_policy', 'overridePolicy', 'policy', 'policy_decision'])
          : undefined;
      const notes =
        result === 'edited'
          ? readFirstString(edited, ['notes', 'reason'])
          : undefined;
      if (result === 'edited') {
        ensureEditedValue('risk', 'overridePolicy', overridePolicy);
      }
      return {
        threadId,
        decision,
        ...(overridePolicy ? { overridePolicy } : {}),
        ...(notes ? { notes } : {}),
      };
    },
  },
  {
    name: 'recover',
    description: 'Diagnose and recover a broken account session',
    argSchema: '@username',
    transport: 'sse',
    runEndpoint: '/ai/account-recovery/run',
    resumeEndpoint: '/ai/account-recovery/resume',
    buildPayload(args, threadId) {
      const { usernames, remaining } = extractMentions(args);
      const username = usernames[0] ?? remaining.trim();
      return { threadId, accountId: username, username };
    },
    buildResumePayload(threadId, result, editedCalls, approvalPayload) {
      const edited = mergeEditedRecords(editedCalls);
      const suggestedDecision = readPositiveDecisionOption(approvalPayload);
      const twoFaCode =
        result === 'edited'
          ? readFirstString(edited, ['two_fa_code', 'twoFaCode', 'code', 'otp'])
          : undefined;
      const proxy =
        result === 'edited'
          ? readFirstString(edited, ['proxy', 'proxy_candidate'])
          : undefined;
      const explicitDecision =
        result === 'edited'
          ? readFirstString(edited, ['decision'])
          : undefined;
      const normalizedExplicitDecision = isRecoverDecision(explicitDecision) ? explicitDecision : undefined;
      const normalizedSuggestedDecision = isRecoverDecision(suggestedDecision) ? suggestedDecision : undefined;

      const fallbackEditedDecision = twoFaCode ? 'provide_2fa' : 'approve_proxy_swap';
      const decision =
        result === 'rejected'
          ? 'abort'
          : normalizedExplicitDecision && normalizedExplicitDecision !== 'abort'
          ? normalizedExplicitDecision
          : normalizedSuggestedDecision && normalizedSuggestedDecision !== 'abort'
          ? normalizedSuggestedDecision
          : result === 'edited'
          ? fallbackEditedDecision
          : 'approve_proxy_swap';

      if (result === 'edited' && !twoFaCode && !proxy) {
        throw new Error('/recover edited resume requires twoFaCode or proxy.');
      }

      return {
        threadId,
        decision,
        ...(twoFaCode ? { twoFaCode } : {}),
        ...(proxy ? { proxy } : {}),
      };
    },
  },
  {
    name: 'pipeline',
    description: 'Generate, validate, and schedule an Instagram caption',
    argSchema: '@username1 ... <campaign brief>',
    transport: 'sse',
    runEndpoint: '/ai/content-pipeline/run',
    resumeEndpoint: '/ai/content-pipeline/resume',
    buildPayload(args, threadId) {
      const { usernames, remaining } = extractMentions(args);
      return {
        threadId,
        targetUsernames: usernames,
        campaignBrief: remaining,
        mediaRefs: [],
        scheduledAt: null,
      };
    },
    buildResumePayload(threadId, result, editedCalls) {
      const edited = mergeEditedRecords(editedCalls);
      const editedCaption =
        result === 'edited'
          ? readFirstString(edited, ['edited_caption', 'editedCaption', 'caption', 'content', 'text'])
          : undefined;
      const reason =
        result === 'edited'
          ? readFirstString(edited, ['reason', 'notes'])
          : undefined;
      if (result === 'edited') {
        ensureEditedValue('pipeline', 'editedCaption', editedCaption);
      }
      return {
        threadId,
        decision: result,
        ...(editedCaption ? { editedCaption } : {}),
        ...(reason ? { reason } : {}),
      };
    },
  },
];

export function parseSlashCommand(
  text: string,
): { command: SlashCommand; args: string } | null {
  const trimmed = text.trimStart();
  if (!trimmed.startsWith('/')) return null;
  const withoutSlash = trimmed.slice(1);
  const spaceIdx = withoutSlash.indexOf(' ');
  const name = spaceIdx === -1 ? withoutSlash : withoutSlash.slice(0, spaceIdx);
  const args = spaceIdx === -1 ? '' : withoutSlash.slice(spaceIdx + 1);
  const command = SLASH_COMMANDS.find((c) => c.name === name.toLowerCase());
  if (!command) return null;
  return { command, args };
}

export function getCommandSuggestions(prefix: string): SlashCommand[] {
  const lower = prefix.toLowerCase().replace(/^\//, '');
  if (!lower) return SLASH_COMMANDS;
  return SLASH_COMMANDS.filter((c) => c.name.startsWith(lower));
}
