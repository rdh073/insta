import { api } from './client';

// Smart engagement runs a 9-stage LangGraph pipeline with up to 3 LLM
// round-trips (classify_goal, draft_action, score_risk) plus Instagram
// fetches (user_info, user_medias, hashtag_medias). At typical cloud LLM
// latency (~5-10s/call) this exceeds the 20s axios default comfortably.
// 90s leaves headroom for slower providers (Ollama remote, reasoning models).
const SMART_ENGAGEMENT_TIMEOUT_MS = 90_000;

export interface SmartEngagementRequest {
  execution_mode: 'recommendation' | 'execute';
  goal: string;
  account_id: string;
  max_targets: number;
  max_actions_per_target: number;
  approval_timeout?: number;
  metadata?: Record<string, unknown>;
}

export interface RecommendationDetail {
  target?: string;
  action_type?: string;
  draft_content?: string;
  reasoning?: string;
  expected_outcome?: string;
}

export interface RiskDetail {
  level?: string;
  rule_hits: string[];
  reasoning?: string;
  requires_approval: boolean;
}

export interface DecisionDetail {
  id?: string;
  decision?: string;
  notes: string;
}

export interface SmartEngagementResponse {
  mode: string;
  status: string;
  thread_id?: string;
  interrupted: boolean;
  interrupt_payload?: Record<string, unknown>;
  outcome_reason?: string;
  recommendation?: RecommendationDetail;
  risk?: RiskDetail;
  decision?: DecisionDetail;
  execution?: Record<string, unknown>;
  brief_audit: Record<string, unknown>[];
  audit_trail: Record<string, unknown>[];
}

export type SmartEngagementDecision =
  | 'approve'
  | 'reject'
  | 'edit'
  | 'approved'
  | 'rejected'
  | 'edited';

type CanonicalSmartEngagementDecision = 'approved' | 'rejected' | 'edited';

const DECISION_TO_CANONICAL: Record<SmartEngagementDecision, CanonicalSmartEngagementDecision> = {
  approve: 'approved',
  approved: 'approved',
  reject: 'rejected',
  rejected: 'rejected',
  edit: 'edited',
  edited: 'edited',
};

export interface ResumeRequest {
  thread_id: string;
  decision: SmartEngagementDecision;
  notes?: string;
  content?: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

function hasRecommendationValue(value: RecommendationDetail): boolean {
  return Boolean(value.target || value.action_type || value.draft_content || value.reasoning || value.expected_outcome);
}

function hasRiskValue(value: RiskDetail): boolean {
  return Boolean(value.level || value.reasoning || value.rule_hits.length > 0);
}

function normalizeInterruptFallback(response: SmartEngagementResponse): SmartEngagementResponse {
  const payload = asRecord(response.interrupt_payload);
  if (!payload) return response;

  const draftAction = asRecord(payload.draft_action);
  const draftPayload = asRecord(payload.draft_payload);

  const recommendation =
    response.recommendation ??
    (() => {
      const fallback: RecommendationDetail = {
        target: asString(payload.target) ?? asString(draftAction?.target_id),
        action_type: asString(draftAction?.action_type),
        draft_content: asString(draftAction?.content) ?? asString(payload.draft_content) ?? asString(draftPayload?.content),
        reasoning: asString(payload.relevance_reason),
        expected_outcome: undefined,
      };
      return hasRecommendationValue(fallback) ? fallback : undefined;
    })();

  const risk =
    response.risk ??
    (() => {
      const requiresApprovalRaw = payload.requires_approval;
      const fallback: RiskDetail = {
        level: asString(payload.risk_level),
        rule_hits: asStringArray(payload.rule_hits),
        reasoning: asString(payload.risk_reason),
        requires_approval: typeof requiresApprovalRaw === 'boolean' ? requiresApprovalRaw : true,
      };
      return hasRiskValue(fallback) ? fallback : undefined;
    })();

  if (!recommendation && !risk) return response;
  return {
    ...response,
    recommendation,
    risk,
  };
}

export const smartEngagementApi = {
  async recommend(req: SmartEngagementRequest): Promise<SmartEngagementResponse> {
    const res = await api.post<SmartEngagementResponse>('/ai/smart-engagement/recommend', req, {
      timeout: SMART_ENGAGEMENT_TIMEOUT_MS,
    });
    return normalizeInterruptFallback(res.data);
  },

  async resume(req: ResumeRequest): Promise<SmartEngagementResponse> {
    const res = await api.post<SmartEngagementResponse>(
      '/ai/smart-engagement/resume',
      {
        ...req,
        decision: DECISION_TO_CANONICAL[req.decision],
      },
      { timeout: SMART_ENGAGEMENT_TIMEOUT_MS },
    );
    return normalizeInterruptFallback(res.data);
  },
};
