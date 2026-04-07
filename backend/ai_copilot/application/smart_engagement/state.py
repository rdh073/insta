"""Smart engagement workflow state - extends OperatorCopilotState with engagement-specific fields.

State Contract:
- Minimal explicit fields for checkpointing, resumption, and UI rendering
- Self-contained payloads (approval_request has everything UI needs)
- Explicit events for audit trail (not implicit state transitions)
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph import add_messages

# Import base state
from ai_copilot.application.state import OperatorCopilotState


def _append_audit_events(existing: list, new: list) -> list:
    """Reducer: accumulate audit events (simple append, no deduplication)."""
    if not isinstance(new, list):
        return existing
    return existing + new


# === Engagement Target ===

class EngagementTarget(TypedDict):
    """Single engagement target (account or post)."""

    target_id: str
    """Unique identifier (username or post_id)"""

    target_type: str
    """Type: account, post, hashtag"""

    metadata: dict
    """Raw metadata: follower_count, engagement_rate, etc."""


# === Account Context ===

class AccountHealth(TypedDict):
    """Account status and constraints."""

    status: str
    """active, cooldown, suspicious, needs_relogin"""

    cooldown_until: float | None
    """Timestamp when account can engage again (None if no cooldown)"""

    proxy: str | None
    """Proxy in use (if any)"""

    login_state: str
    """logged_in, needs_2fa, session_expired"""

    recent_actions: int
    """Number of actions in last hour (for rate limiting)"""


# === Action and Risk ===

class ProposedAction(TypedDict):
    """Single engagement action proposal."""

    action_type: str
    """Action type: follow, dm, comment, like, skip"""

    target_id: str
    """Target username/post_id"""

    content: str | None
    """Message content (for DM/comment, None for follow/like)"""

    reasoning: str
    """Why this action is recommended"""

    expected_outcome: str
    """Expected result of action"""


class RiskAssessment(TypedDict):
    """Risk evaluation for proposed action."""

    risk_level: str
    """low, medium, high"""

    rule_hits: list[str]
    """Which rules triggered (e.g., ['follow_daily_limit', 'comment_frequency'])"""

    reasoning: str
    """Detailed reason why this risk level"""

    requires_approval: bool
    """True if risk_level is high or action is write operation"""


class DraftPayload(TypedDict):
    """Draft content and reasoning (for DM/comment)."""

    content: str | None
    """Proposed message content (None for follow/like)"""

    reasoning: str
    """Why this specific content is recommended"""

    tone: str
    """Tone/style (conversational, professional, educational, etc.)"""


# === Approval ===

class ApprovalRequest(TypedDict):
    """Self-contained approval payload for UI (no state lookup needed)."""

    approval_id: str
    """Unique approval request ID"""

    thread_id: str
    """Resumable execution thread"""

    account_id: str
    """Which account will act"""

    target_id: str
    """Target username/post_id"""

    action_type: str
    """follow, dm, comment, like"""

    draft_payload: DraftPayload
    """Draft content with reasoning"""

    risk_level: str
    """low, medium, high"""

    risk_reasoning: str
    """Why this risk"""

    operator_intent: str
    """Original goal (e.g., 'comment on educational posts')"""

    requested_at: float
    """Timestamp"""


class ApprovalResult(TypedDict):
    """Approval decision outcome."""

    approval_id: str
    """Which approval was decided"""

    decision: str
    """approved, rejected, edited, timeout"""

    approver_notes: str
    """Human decision notes"""

    edited_content: str | None
    """Modified content (if decision=edited)"""

    decided_at: float
    """Timestamp of decision"""


# === Execution ===

class ExecutionResult(TypedDict):
    """Result of executing an action."""

    success: bool
    """True if action executed successfully"""

    action_id: str | None
    """Result ID (post_id, dm_id, etc.) if successful"""

    reason: str
    """Success message or error reason"""

    reason_code: str
    """Stable machine-readable reason code."""

    timestamp: float
    """When execution occurred"""


# === Audit Event ===

class EngagementMemoryRecord(TypedDict):
    """Single past engagement outcome stored in cross-thread memory."""

    target_id: str
    """Who/what was engaged"""

    action_type: str
    """follow, dm, comment, like"""

    outcome: str
    """success, failed, rejected, skipped"""

    account_id: str
    """Which account performed the action"""

    timestamp: float
    """When the engagement happened"""


class AuditEvent(TypedDict):
    """Explicit audit event per workflow decision."""

    event_type: str
    """target_selected, scored, approval_requested, action_skipped, action_executed"""

    node_name: str
    """Which node emitted this event"""

    event_data: dict
    """Event-specific data (varies by type)"""

    timestamp: float
    """When event occurred"""


# === Main State ===

class SmartEngagementState(OperatorCopilotState):
    """Smart engagement workflow state.

    Minimum explicit fields for:
    - Checkpointing and resumption (thread_id)
    - Execution control (mode, goal, account context)
    - Workflow progress (target selection, action drafting, risk assessment, approval)
    - Audit trail (explicit events per node decision)

    Invariants:
    - mode='recommendation' is default (no auto-execute)
    - approval_request is self-contained (UI reads it without accessing other state)
    - audit_trail captures explicit events (not implicit transitions)
    - executor never called when mode='recommendation'
    """

    # === Resumable Execution ===

    thread_id: str
    """Unique identifier for this execution thread (used for checkpointing and resumption)"""

    # === Execution Control ===

    mode: str
    """'recommendation' (default, no execution) or 'execute'"""

    goal: str
    """Operator's intent (e.g., 'find targets for educational comments')"""

    # === Account Context ===

    account_id: str
    """Account ID that will perform engagement"""

    account_health: AccountHealth | None
    """Account status and constraints (cooldown, proxy, login state)"""

    # === Target Selection ===

    candidate_targets: list[EngagementTarget]
    """Discovered targets for potential engagement"""

    selected_target: EngagementTarget | None
    """Target chosen for this engagement"""

    # === Action Selection ===

    proposed_action: ProposedAction | None
    """Action proposed for selected target"""

    draft_payload: DraftPayload | None
    """Draft content and reasoning (for DM/comment)"""

    # === Risk Assessment ===

    risk_assessment: RiskAssessment | None
    """Risk evaluation of proposed action"""

    # === Approval ===

    approval_request: ApprovalRequest | None
    """Self-contained approval payload (sent to UI)"""

    approval_result: ApprovalResult | None
    """Approval decision outcome"""

    # === Execution ===

    execution_result: ExecutionResult | None
    """Result of executed action (if executed)"""

    # === Audit Trail ===

    audit_trail: Annotated[list[AuditEvent], _append_audit_events]
    """Explicit events emitted per node (target_selected, scored, approval_requested, etc.)"""

    # === Goal Parsing ===

    structured_goal: dict | None
    """Parsed goal from ingest_goal: {intent, target_type, action_type, constraints}"""

    # === Failure Guards ===

    discovery_attempted: bool
    """True after first candidate discovery (prevents re-discovery loops)"""

    approval_attempted: bool
    """True after first approval request (prevents retry-on-rejection)"""

    # === Outcome ===

    outcome_reason: str | None
    """Human-readable reason why workflow ended (set at log_outcome)"""

    # === Approval Timeout ===

    approval_timeout: float
    """Seconds to wait for approval before treating as rejected (default 3600)"""

    # === Loop Control ===

    max_targets: int
    """Maximum candidate targets to consider (default 5)"""

    max_actions_per_target: int
    """Maximum actions to propose per target (default 3)"""
