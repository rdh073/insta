"""Node functions for Campaign Monitor workflow.

OWNERSHIP: Business logic via ports. No HTTP, no SDK, no LLM.

Topology:
  load_recent_jobs
    [no jobs] → finish(no_data)
  → group_by_campaign
  → evaluate_outcome
  → suggest_next_action
  → request_operator_decision  ← CONDITIONAL interrupt (only if request_decision==True)
      [skip / request_decision==False] → finish(recommendation_only)
      [approve / modify]              → create_followup_task → finish
  → finish

Failure rules:
- No jobs loaded → stop_reason=no_data
- No valid campaign groups → stop_reason=no_campaigns
- Decision interrupt only fires once (guarded by stop_reason check)
"""

from __future__ import annotations

import time
from collections import defaultdict

from langgraph.types import interrupt

from ai_copilot.application.campaign_monitor.ports import (
    ALLOWED_FOLLOWUP_RESULT_STATUSES,
    FollowupCreatorPort,
    JobMonitorPort,
)
from ai_copilot.application.campaign_monitor.state import CampaignMonitorState


class CampaignMonitorNodes:
    """Nodes for the Campaign Monitor workflow."""

    def __init__(
        self,
        job_monitor: JobMonitorPort,
        followup_creator: FollowupCreatorPort,
    ):
        self.job_monitor = job_monitor
        self.followup_creator = followup_creator

    def _event(self, event_type: str, node_name: str, data: dict) -> dict:
        return {
            "event_type": event_type,
            "node_name": node_name,
            "event_data": data,
            "timestamp": time.time(),
        }

    @staticmethod
    def _normalize_status(value: object) -> str:
        return str(value or "").strip().lower()

    def _validate_followup_result(self, result: dict) -> tuple[str, str] | None:
        job_id = str(result.get("job_id", "") or "").strip()
        status = self._normalize_status(result.get("status"))
        if not job_id or status not in ALLOWED_FOLLOWUP_RESULT_STATUSES:
            return None
        return job_id, status

    # =========================================================================
    # Node 1: load_recent_jobs
    # =========================================================================

    async def load_recent_jobs_node(self, state: CampaignMonitorState) -> dict:
        """Load job statuses and account health from ports.

        Fail-fast: no jobs → stop_reason=no_data.
        """
        lookback_days = state.get("lookback_days", 7)
        job_ids = state.get("job_ids", [])

        try:
            jobs = await self.job_monitor.load_recent_jobs(lookback_days, job_ids)
        except Exception as exc:
            reason = f"Failed to load jobs: {str(exc)[:120]}"
            return {
                "job_statuses": [],
                "outcome_reason": reason,
                "stop_reason": "error",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("load_failed", "load_recent_jobs", {"error": reason})],
            }

        if not jobs:
            reason = "No recent jobs found"
            return {
                "job_statuses": [],
                "outcome_reason": reason,
                "stop_reason": "no_data",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("no_data", "load_recent_jobs", {"lookback_days": lookback_days})],
            }

        # Load account health in bulk
        account_ids = list({j.get("account_id", "") for j in jobs if j.get("account_id")})
        try:
            account_health = await self.job_monitor.get_account_health_bulk(account_ids)
        except Exception:
            account_health = {}

        return {
            "job_statuses": jobs,
            "account_health": account_health,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("jobs_loaded", "load_recent_jobs", {
                "count": len(jobs),
                "account_count": len(account_ids),
            })],
        }

    def route_after_load(self, state: CampaignMonitorState) -> str:
        """Route: jobs found → group_by_campaign, else → finish."""
        if state.get("stop_reason"):
            return "finish"
        return "group_by_campaign"

    # =========================================================================
    # Node 2: group_by_campaign
    # =========================================================================

    async def group_by_campaign_node(self, state: CampaignMonitorState) -> dict:
        """Group job statuses by campaign_tag.

        Jobs without a campaign_tag are grouped under '_ungrouped'.
        """
        jobs = state.get("job_statuses", [])

        by_tag: dict[str, list] = defaultdict(list)
        for job in jobs:
            tag = job.get("campaign_tag") or "_ungrouped"
            by_tag[tag].append(job)

        campaign_groups = []
        for tag, tag_jobs in by_tag.items():
            account_ids = list({j.get("account_id", "") for j in tag_jobs if j.get("account_id")})
            campaign_groups.append({
                "campaign_tag": tag,
                "job_ids": [j.get("id") or j.get("job_id", "") for j in tag_jobs],
                "account_ids": account_ids,
                "jobs": tag_jobs,
            })

        if not campaign_groups:
            return {
                "campaign_groups": [],
                "outcome_reason": "No campaign groups formed",
                "stop_reason": "no_campaigns",
                "audit_trail": [self._event("no_campaigns", "group_by_campaign", {})],
            }

        return {
            "campaign_groups": campaign_groups,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("campaigns_grouped", "group_by_campaign", {
                "campaign_count": len(campaign_groups),
                "tags": [g["campaign_tag"] for g in campaign_groups],
            })],
        }

    def route_after_grouping(self, state: CampaignMonitorState) -> str:
        if state.get("stop_reason"):
            return "finish"
        return "evaluate_outcome"

    # =========================================================================
    # Node 3: evaluate_outcome
    # =========================================================================

    async def evaluate_outcome_node(self, state: CampaignMonitorState) -> dict:
        """Aggregate performance metrics across campaigns.

        Optionally enriches with post insights if available.
        Produces campaign_summary with aggregate metrics.
        """
        campaign_groups = state.get("campaign_groups", [])
        account_health = state.get("account_health", {})

        total_jobs = 0
        completed = 0
        failed = 0
        pending = 0
        total_insights: dict = {"likes": 0, "comments": 0, "reach": 0, "saves": 0}
        has_insights = False

        for group in campaign_groups:
            for job in group.get("jobs", []):
                total_jobs += 1
                status = job.get("status", "unknown")
                if status in ("completed", "published", "success"):
                    completed += 1
                elif status in ("failed", "error"):
                    failed += 1
                else:
                    pending += 1

                # Try to enrich with insights
                account_id = job.get("account_id", "")
                job_id = job.get("id") or job.get("job_id", "")
                if account_id and job_id:
                    try:
                        insight = await self.job_monitor.get_post_insights(account_id, job_id)
                        if insight:
                            has_insights = True
                            for key in total_insights:
                                total_insights[key] += insight.get(key, 0)
                    except Exception:
                        pass

        # Health summary
        healthy_accounts = sum(
            1 for h in account_health.values()
            if h.get("status") == "active" and h.get("login_state") == "logged_in"
        )

        campaign_summary = {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "completion_rate": round(completed / total_jobs, 2) if total_jobs else 0.0,
            "failure_rate": round(failed / total_jobs, 2) if total_jobs else 0.0,
            "healthy_accounts": healthy_accounts,
            "total_accounts": len(account_health),
            "insights": total_insights if has_insights else None,
        }

        return {
            "campaign_summary": campaign_summary,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("outcome_evaluated", "evaluate_outcome", {
                "total_jobs": total_jobs,
                "completion_rate": campaign_summary["completion_rate"],
                "failure_rate": campaign_summary["failure_rate"],
            })],
        }

    # =========================================================================
    # Node 4: suggest_next_action
    # =========================================================================

    async def suggest_next_action_node(self, state: CampaignMonitorState) -> dict:
        """Rule-based engine to recommend next action.

        Rules (applied in priority order):
        1. failure_rate > 0.4 → pause
        2. pending > 0 and failure_rate < 0.1 → reschedule
        3. completion_rate >= 0.8 and insights.reach > 0 → boost
        4. completion_rate >= 0.6 → followup
        5. default → no_action
        """
        summary = state.get("campaign_summary") or {}
        failure_rate = summary.get("failure_rate", 0.0)
        completion_rate = summary.get("completion_rate", 0.0)
        pending = summary.get("pending", 0)
        insights = summary.get("insights") or {}

        if failure_rate > 0.4:
            action = "pause"
            reasoning = (
                f"High failure rate ({failure_rate:.0%}) — pause campaign and investigate "
                f"account health or content issues."
            )
            details = {"failure_rate": failure_rate, "threshold": 0.4}
        elif pending > 0 and failure_rate < 0.1:
            action = "reschedule"
            reasoning = (
                f"{pending} jobs still pending with low failure rate ({failure_rate:.0%}) "
                f"— reschedule for optimal delivery window."
            )
            details = {"pending_jobs": pending}
        elif completion_rate >= 0.8 and insights.get("reach", 0) > 0:
            action = "boost"
            reasoning = (
                f"Strong performance: {completion_rate:.0%} completion, "
                f"{insights.get('reach', 0)} reach — boost to extend audience."
            )
            details = {"completion_rate": completion_rate, "reach": insights.get("reach", 0)}
        elif completion_rate >= 0.6:
            action = "followup"
            reasoning = (
                f"Good completion rate ({completion_rate:.0%}) — schedule followup "
                f"content to maintain engagement momentum."
            )
            details = {"completion_rate": completion_rate}
        else:
            action = "no_action"
            reasoning = "Campaign metrics are within normal range — no action required."
            details = {}

        return {
            "recommended_action": action,
            "action_reasoning": reasoning,
            "action_details": details,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("action_suggested", "suggest_next_action", {
                "action": action,
                "reasoning": reasoning,
            })],
        }

    # =========================================================================
    # Node 5: request_operator_decision  (CONDITIONAL INTERRUPT)
    # =========================================================================

    async def request_operator_decision_node(self, state: CampaignMonitorState) -> dict:
        """Ask the operator to approve or skip the recommended action.

        Only fires if request_decision==True in the initial state.
        Uses LangGraph interrupt() to pause execution.

        Interrupt payload (self-contained, UI reads without state lookup):
        {
            thread_id, campaign_summary, recommended_action,
            action_reasoning, action_details, campaign_groups,
            options: ["approve", "skip", "modify"]
        }

        On resume: operator_decision = {decision: "approve"|"skip"|"modify", parameters: {...}}
        """
        # Build self-contained interrupt payload
        interrupt_payload = {
            "type": "campaign_monitor_decision",
            "thread_id": state.get("thread_id"),
            "campaign_summary": state.get("campaign_summary"),
            "recommended_action": state.get("recommended_action"),
            "action_reasoning": state.get("action_reasoning"),
            "action_details": state.get("action_details"),
            "campaign_groups": [
                {
                    "campaign_tag": g.get("campaign_tag"),
                    "job_count": len(g.get("job_ids", [])),
                    "account_ids": g.get("account_ids", []),
                }
                for g in state.get("campaign_groups", [])
            ],
            "options": ["approve", "skip", "modify"],
            "requested_at": time.time(),
        }

        # INTERRUPT: pause here and wait for operator decision
        operator_decision = interrupt(interrupt_payload)

        # --- Resumed here ---
        if not operator_decision:
            operator_decision = {"decision": "skip", "parameters": {}}

        decision_value = operator_decision.get("decision", "skip")

        audit = self._event("decision_received", "request_operator_decision", {
            "decision": decision_value,
        })

        if decision_value == "skip":
            return {
                "operator_decision": operator_decision,
                "outcome_reason": "Operator chose to skip followup action",
                "stop_reason": "skipped_by_operator",
                "audit_trail": [audit],
            }

        return {
            "operator_decision": operator_decision,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [audit],
        }

    def route_after_decision(self, state: CampaignMonitorState) -> str:
        """Route: skipped/no decision → finish, approved/modify → create_followup."""
        if state.get("stop_reason"):
            return "finish"
        decision = (state.get("operator_decision") or {}).get("decision", "skip")
        if decision in ("approve", "modify"):
            return "create_followup_task"
        return "finish"

    def route_for_decision_gate(self, state: CampaignMonitorState) -> str:
        """Decide whether to interrupt or go straight to finish.

        Called as the conditional edge after suggest_next_action.
        - request_decision==True  → request_operator_decision (will interrupt)
        - request_decision==False → finish
        """
        if state.get("request_decision"):
            return "request_operator_decision"
        return "finish"

    # =========================================================================
    # Node 6: create_followup_task
    # =========================================================================

    async def create_followup_task_node(self, state: CampaignMonitorState) -> dict:
        """Create a scheduled followup job based on operator decision."""
        campaign_summary = state.get("campaign_summary") or {}
        operator_decision = state.get("operator_decision") or {}
        original_job_ids = [
            jid
            for group in state.get("campaign_groups", [])
            for jid in group.get("job_ids", [])
        ]

        try:
            result = await self.followup_creator.create_followup(
                campaign_summary=campaign_summary,
                operator_decision=operator_decision,
                original_job_ids=original_job_ids,
            )
            if not isinstance(result, dict):
                reason = f"Failed to create followup: invalid followup result type={type(result).__name__}"
                return {
                    "outcome_reason": reason,
                    "stop_reason": "error",
                    "audit_trail": [self._event("followup_invalid_result", "create_followup_task", {
                        "reason": reason,
                    })],
                }

            validated = self._validate_followup_result(result)
            if not validated:
                followup_job_id = str(result.get("job_id", "") or "").strip()
                status = self._normalize_status(result.get("status"))
                problems = []
                if not followup_job_id:
                    problems.append("missing job_id")
                if status not in ALLOWED_FOLLOWUP_RESULT_STATUSES:
                    if status:
                        problems.append(f"unsupported status '{status}'")
                    else:
                        problems.append("missing status")

                reason = f"Failed to create followup: invalid followup result ({', '.join(problems)})"
                return {
                    "followup_payload": result,
                    "outcome_reason": reason,
                    "stop_reason": "error",
                    "audit_trail": [self._event("followup_invalid_result", "create_followup_task", {
                        "job_id_present": bool(followup_job_id),
                        "status": status or None,
                        "allowed_statuses": sorted(ALLOWED_FOLLOWUP_RESULT_STATUSES),
                    })],
                }

            followup_job_id, status = validated
            outcome_reason = f"Followup task created: job_id={followup_job_id}"
            return {
                "followup_payload": result,
                "followup_job_id": followup_job_id,
                "outcome_reason": outcome_reason,
                "stop_reason": "followup_created",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("followup_created", "create_followup_task", {
                    "job_id": followup_job_id,
                    "status": status,
                })],
            }
        except Exception as exc:
            reason = f"Failed to create followup: {str(exc)[:120]}"
            return {
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [self._event("followup_failed", "create_followup_task", {"error": reason})],
            }

    # =========================================================================
    # Node 7: finish
    # =========================================================================

    async def finish_node(self, state: CampaignMonitorState) -> dict:
        """Final terminal node. Ensures stop_reason and outcome_reason are set."""
        stop_reason = state.get("stop_reason")
        outcome_reason = state.get("outcome_reason")

        if not stop_reason:
            stop_reason = "recommendation_only"

        if not outcome_reason:
            action = state.get("recommended_action", "no_action")
            if stop_reason == "recommendation_only":
                outcome_reason = f"Recommendation: {action} (operator decision not requested)"
            elif stop_reason == "no_data":
                outcome_reason = "No jobs found to monitor"
            elif stop_reason == "no_campaigns":
                outcome_reason = "No campaign groups formed"
            elif stop_reason == "followup_created":
                outcome_reason = f"Followup created for action: {action}"
            else:
                outcome_reason = f"Workflow ended: {stop_reason}"

        return {
            "stop_reason": stop_reason,
            "outcome_reason": outcome_reason,
        }
