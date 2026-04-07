import axios from 'axios';
import { buildApiUrl } from '../lib/api-base';

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

export interface ResumeRequest {
  thread_id: string;
  decision: 'approved' | 'rejected' | 'edited';
  notes?: string;
  content?: string;
}

export const smartEngagementApi = {
  async recommend(
    req: SmartEngagementRequest,
    backendUrl?: string,
  ): Promise<SmartEngagementResponse> {
    const url = buildApiUrl('/ai/smart-engagement/recommend', backendUrl);
    const res = await axios.post<SmartEngagementResponse>(url, req);
    return res.data;
  },

  async resume(
    req: ResumeRequest,
    backendUrl?: string,
  ): Promise<SmartEngagementResponse> {
    const url = buildApiUrl('/ai/smart-engagement/resume', backendUrl);
    const res = await axios.post<SmartEngagementResponse>(url, req);
    return res.data;
  },
};
