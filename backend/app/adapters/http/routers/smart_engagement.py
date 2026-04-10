"""Smart engagement HTTP router - todo-5: integration, mode gating, audit.

OWNERSHIP: Thin HTTP adapter. Parse request → validate mode → delegate to use case.
No business logic. Mode gating enforced here AND at adapter level.

Endpoints (todo-5 spec):
  POST /api/ai/smart-engagement/recommend  → recommendation mode only
  POST /api/ai/smart-engagement/resume     → resume after approval interrupt

Separate experimental path from /api/ai/chat (not connected to chat graph).

Mode gating rules:
  - recommendation mode: always available, NoOp executor injected
  - execution mode: requires SMART_ENGAGEMENT_EXECUTION_ENABLED=true env var
  - execution mode cannot be activated by prompt alone (validated request field + config)

UI contract (operator sees):
  - recommended target
  - draft comment/DM
  - risk score and reasoning
  - relevance reasoning
  - status (recommendation vs execution)
  - final decision and brief audit trail
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from app.adapters.http.dependencies import (
    get_approval_adapter,
    get_audit_log_adapter,
    get_smart_engagement_exec,
    get_smart_engagement_execution_enabled,
    get_smart_engagement_rec,
    get_smart_engagement_usecases,
)
from app.adapters.http.utils import format_error
from ai_copilot.application.use_cases.run_smart_engagement import SmartEngagementUseCase
from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

router = APIRouter(prefix="/api/ai/smart-engagement", tags=["smart-engagement"])

_EXECUTION_ENABLED = os.getenv("SMART_ENGAGEMENT_EXECUTION_ENABLED", "true").lower() == "true"


# =============================================================================
# Request / Response models
# =============================================================================

class SmartEngagementRequest(BaseModel):
    """Request payload for smart engagement recommendation."""

    execution_mode: str = "recommendation"
    """'recommendation' (default, safe) or 'execute' (requires feature flag)"""

    goal: str = "engage with relevant accounts"
    """Operator's intent (e.g., 'comment on educational posts')"""

    account_id: str = "default_account"
    """Account that will perform engagement"""

    max_targets: int = 5
    """Maximum targets to discover"""

    max_actions_per_target: int = 3
    """Maximum actions per target"""

    approval_timeout: float = 3600.0
    """Seconds to wait for approval before treating as rejected (default 1 hour)"""

    metadata: Optional[dict[str, Any]] = None
    """Optional metadata. Include thread_id to resume a previous run."""

    @field_validator("execution_mode")
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        if v not in ("recommendation", "execute"):
            raise ValueError("execution_mode must be 'recommendation' or 'execute'")
        return v


class ResumeRequest(BaseModel):
    """Request to resume a workflow paused at the approval interrupt."""

    thread_id: str
    """Thread ID from the interrupted run (returned in interrupt response)"""

    decision: str
    """'approved', 'rejected', or 'edited'"""

    notes: str = ""
    """Decision notes (reason for approval/rejection)"""

    content: Optional[str] = None
    """Edited content (only when decision='edited')"""

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in ("approved", "rejected", "edited"):
            raise ValueError("decision must be 'approved', 'rejected', or 'edited'")
        return v


class RecommendationDetail(BaseModel):
    """Structured recommendation detail for UI rendering."""

    target: Optional[str] = None
    """Target username or post_id"""

    action_type: Optional[str] = None
    """follow, dm, comment, like"""

    draft_content: Optional[str] = None
    """Proposed message content (for dm/comment)"""

    reasoning: Optional[str] = None
    """Why this action is recommended (relevance reason)"""

    expected_outcome: Optional[str] = None
    """What is expected to happen if executed"""


class RiskDetail(BaseModel):
    """Structured risk assessment for UI rendering."""

    level: Optional[str] = None
    """low, medium, high"""

    rule_hits: list[str] = []
    """Which rules triggered"""

    reasoning: Optional[str] = None
    """Why this risk level"""

    requires_approval: bool = False
    """Whether human approval is required"""


class DecisionDetail(BaseModel):
    """Structured approval decision for UI rendering."""

    id: Optional[str] = None
    """Approval request ID"""

    decision: Optional[str] = None
    """approved, rejected, edited, pending"""

    notes: str = ""
    """Approver's notes"""


class SmartEngagementResponse(BaseModel):
    """Response from smart engagement workflow.

    UI contract: operator must see all required fields per todo-5.
    """

    mode: str
    """Execution mode used"""

    status: str
    """Workflow stop_reason"""

    thread_id: Optional[str] = None
    """Thread ID for resumption (stable across interrupt/resume)"""

    interrupted: bool = False
    """True if workflow is paused at approval interrupt - use /resume to continue"""

    interrupt_payload: Optional[dict] = None
    """Self-contained approval request (only when interrupted=True)"""

    outcome_reason: Optional[str] = None
    """Human-readable reason why workflow ended"""

    # ── UI contract fields ──────────────────────────────────────────────────

    recommendation: Optional[RecommendationDetail] = None
    """Structured recommendation: target, draft, relevance reason"""

    risk: Optional[RiskDetail] = None
    """Structured risk: score, reasoning, rule hits"""

    decision: Optional[DecisionDetail] = None
    """Structured approval decision: who approved/rejected"""

    execution: Optional[dict] = None
    """Execution result (if action was executed)"""

    brief_audit: list[dict] = []
    """Last 5 audit events for UI display"""

    # Full audit trail for external consumers
    audit_trail: list[dict] = []


class ApprovalStatusResponse(BaseModel):
    """Approval status response."""

    approval_id: str
    status: str
    requested_at: float
    approved_at: Optional[float] = None
    approver_notes: str = ""


# =============================================================================
# Helpers
# =============================================================================

def _format_response(result: dict) -> SmartEngagementResponse:
    """Convert use case result dict to SmartEngagementResponse with UI contract fields."""
    # Build structured recommendation
    rec_dict = result.get("recommendation")
    recommendation = None
    if rec_dict:
        recommendation = RecommendationDetail(
            target=rec_dict.get("target"),
            action_type=rec_dict.get("action_type"),
            draft_content=rec_dict.get("content"),
            reasoning=rec_dict.get("reasoning"),
            expected_outcome=rec_dict.get("expected_outcome"),
        )

    # Build structured risk
    risk_dict = result.get("risk_assessment")
    risk = None
    if risk_dict:
        risk = RiskDetail(
            level=risk_dict.get("level"),
            rule_hits=risk_dict.get("rule_hits", []),
            reasoning=risk_dict.get("reasoning"),
            requires_approval=risk_dict.get("requires_approval", False),
        )

    # Build structured decision
    approval_dict = result.get("approval")
    decision = None
    if approval_dict:
        decision = DecisionDetail(
            id=approval_dict.get("id"),
            decision=approval_dict.get("decision"),
            notes=approval_dict.get("notes", ""),
        )

    # Brief audit: last 5 events for UI summary
    full_audit = result.get("audit_trail", [])
    brief_audit = full_audit[-5:] if full_audit else []

    return SmartEngagementResponse(
        mode=result.get("mode", "recommendation"),
        status=result.get("status", "unknown"),
        thread_id=result.get("thread_id"),
        interrupted=result.get("interrupted", False),
        interrupt_payload=result.get("interrupt_payload"),
        outcome_reason=result.get("outcome_reason"),
        recommendation=recommendation,
        risk=risk,
        decision=decision,
        execution=result.get("execution"),
        brief_audit=brief_audit,
        audit_trail=full_audit,
    )


def _get_use_case_for_mode(
    mode: str,
    rec_use_case: SmartEngagementUseCase,
    exec_use_case: SmartEngagementUseCase | None,
    execution_enabled: bool,
) -> SmartEngagementUseCase:
    """Select the appropriate use case based on mode and feature flag.

    Raises HTTPException 403 if execute mode requested but not enabled.
    """
    if mode == "execute":
        if not execution_enabled or exec_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Execution mode is not enabled. "
                    "Set SMART_ENGAGEMENT_EXECUTION_ENABLED=true in server config. "
                    "Execution mode cannot be activated by request alone."
                ),
            )
        return exec_use_case

    # recommendation mode: always use the NoOp-executor instance
    return rec_use_case


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/recommend",
    response_model=SmartEngagementResponse,
    status_code=status.HTTP_200_OK,
)
async def recommend(
    request: SmartEngagementRequest,
    rec_use_case: SmartEngagementUseCase = Depends(get_smart_engagement_rec),
    exec_use_case=Depends(get_smart_engagement_exec),
    execution_enabled: bool = Depends(get_smart_engagement_execution_enabled),
) -> SmartEngagementResponse:
    """Run smart engagement workflow.

    Recommendation mode (default, safe):
    - Discovers targets, drafts action, assesses risk
    - Returns recommendation with target, draft, risk score, relevance reason
    - Never executes write actions (NoOp executor injected)

    Execution mode (requires SMART_ENGAGEMENT_EXECUTION_ENABLED=true config):
    - Same as recommendation, but proceeds to approval interrupt
    - After resume with 'approved', executes the action
    - Requires explicit feature flag; cannot be activated by prompt alone

    Returns:
        SmartEngagementResponse with UI-ready fields.
        If interrupted=True, call POST /resume with thread_id to continue.
    """
    use_case = _get_use_case_for_mode(
        request.execution_mode, rec_use_case, exec_use_case, execution_enabled
    )

    try:
        result = await use_case.run(
            execution_mode=request.execution_mode,
            goal=request.goal,
            account_id=request.account_id,
            max_targets=request.max_targets,
            max_actions_per_target=request.max_actions_per_target,
            approval_timeout=request.approval_timeout,
            metadata=request.metadata,
        )
        return _format_response(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Smart engagement /recommend failed account=%s goal=%r", request.account_id, request.goal)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error(e, "Smart engagement error"),
        )


@router.post(
    "/resume",
    response_model=SmartEngagementResponse,
    status_code=status.HTTP_200_OK,
)
async def resume(
    request: ResumeRequest,
    exec_use_case=Depends(get_smart_engagement_exec),
    execution_enabled: bool = Depends(get_smart_engagement_execution_enabled),
) -> SmartEngagementResponse:
    """Resume a workflow paused at the approval interrupt.

    When a previous /recommend call returned interrupted=True, call this
    endpoint to continue execution with the approval decision.

    Request Body:
        thread_id: From the interrupted run's response
        decision: 'approved', 'rejected', or 'edited'
        notes: Optional decision reason
        content: Edited content (if decision='edited')

    Returns:
        Final workflow state after resumption.
    """
    # Resume requires execution mode (only execute workflows interrupt)
    if not execution_enabled or exec_use_case is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resume requires execution mode. Set SMART_ENGAGEMENT_EXECUTION_ENABLED=true.",
        )

    try:
        result = await exec_use_case.resume(
            thread_id=request.thread_id,
            decision={
                "decision": request.decision,
                "notes": request.notes,
                "content": request.content,
            },
        )
        return _format_response(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Smart engagement /resume failed thread=%s", request.thread_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error(e, "Resume error"),
        )


@router.get(
    "/approval/{approval_id}",
    response_model=ApprovalStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_approval_status(
    approval_id: str,
    approval_adapter: InMemoryApprovalAdapter = Depends(get_approval_adapter),
) -> ApprovalStatusResponse:
    """Check approval status.

    Path Parameters:
        approval_id: Approval request ID

    Returns:
        Approval record with status (pending/approved/rejected)
    """
    try:
        approval = await approval_adapter.get_approval_status(approval_id)
        return ApprovalStatusResponse(
            approval_id=approval["approval_id"],
            status=approval["status"],
            requested_at=approval["requested_at"],
            approved_at=approval["approved_at"],
            approver_notes=approval.get("approver_notes", ""),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=format_error(e, "Approval not found"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error(e, "Error checking approval"),
        )


@router.post(
    "/approval/{approval_id}/decide",
    response_model=ApprovalStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def record_approval_decision(
    approval_id: str,
    approved: bool = Query(..., description="True to approve, False to reject"),
    notes: str = Query("", description="Decision notes"),
    approval_adapter: InMemoryApprovalAdapter = Depends(get_approval_adapter),
) -> ApprovalStatusResponse:
    """Record human approval decision (legacy endpoint).

    Prefer POST /resume for interrupt-based workflows.

    Path Parameters:
        approval_id: Approval request ID

    Query Parameters:
        approved: True to approve, False to reject
        notes: Decision notes

    Returns:
        Updated approval record
    """
    try:
        approval = await approval_adapter.record_approval_decision(
            approval_id=approval_id,
            approved=approved,
            approver_notes=notes,
        )
        return ApprovalStatusResponse(
            approval_id=approval["approval_id"],
            status=approval["status"],
            requested_at=approval["requested_at"],
            approved_at=approval["approved_at"],
            approver_notes=approval.get("approver_notes", ""),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=format_error(e, "Approval not found"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error(e, "Error recording decision"),
        )
