import type { CopilotEvent } from '../api/operator-copilot';

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
    result: 'approved' | 'rejected' | 'edited',
    editedCalls?: Record<string, unknown>[],
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

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'engage',
    description: 'Run smart engagement for an account with a goal',
    argSchema: '@username <engagement goal>',
    transport: 'json',
    runEndpoint: '/ai/smart-engagement/recommend',
    resumeEndpoint: '/ai/smart-engagement/resume',
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
    buildResumePayload(threadId, result) {
      return {
        thread_id: threadId,
        decision: result,
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
    buildResumePayload(threadId, result) {
      const decision =
        result === 'approved' ? 'approve' : result === 'edited' ? 'modify' : 'skip';
      return { threadId, decision };
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
    buildResumePayload(threadId, result) {
      const decision =
        result === 'approved'
          ? 'approve_policy'
          : result === 'edited'
          ? 'override_policy'
          : 'abort';
      return { threadId, decision };
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
    buildResumePayload(threadId, result, editedCalls) {
      const decision =
        result === 'approved'
          ? 'approve_proxy_swap'
          : result === 'edited'
          ? 'provide_2fa'
          : 'abort';
      const twoFaCode =
        result === 'edited' && editedCalls?.[0]
          ? String(Object.values(editedCalls[0])[0] ?? '')
          : undefined;
      return { threadId, decision, twoFaCode };
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
    buildResumePayload(threadId, result) {
      return { threadId, decision: result };
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
