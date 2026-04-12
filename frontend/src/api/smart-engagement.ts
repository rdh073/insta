import { api } from './client';

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

export const smartEngagementApi = {
  async recommend(req: SmartEngagementRequest): Promise<SmartEngagementResponse> {
    const res = await api.post<SmartEngagementResponse>('/ai/smart-engagement/recommend', req);
    return res.data;
  },

  async resume(req: ResumeRequest): Promise<SmartEngagementResponse> {
    const res = await api.post<SmartEngagementResponse>('/ai/smart-engagement/resume', {
      ...req,
      decision: DECISION_TO_CANONICAL[req.decision],
    });
    return res.data;
  },
};
