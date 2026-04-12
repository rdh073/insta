"""Ports (abstract interfaces) for smart engagement workflow.

OWNERSHIP: Define contracts between graph/nodes and adapters.
No HTTP, no Instagram SDK, no session files - only abstract method signatures.

Port Contracts:
- RiskScoringPort returns reasoning, not just scores
- ApprovalPort receives self-contained approval_request (no state lookups)
- EngagementExecutorPort never called in recommendation mode (graph enforces)
- AuditLogPort receives explicit events (target_selected, scored, approval_requested, etc.)

Ports define capabilities needed by the graph without importing concrete implementations.
Adapters provide the actual implementations.

Usage:
- Graph/nodes depend on ports (abstract)
- Adapters implement ports (concrete)
- HTTP layer injects adapters through use case
- Policy/logic stays in graph, not adapters
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .state import (
    AccountHealth,
    ApprovalRequest,
    ApprovalResult,
    AuditEvent,
    DraftPayload,
    EngagementMemoryRecord,
    EngagementTarget,
    ExecutionResult,
    ProposedAction,
    RiskAssessment,
)


# === New Ports (Todo-3) ===

SMART_ENGAGEMENT_AUDIT_EVENT_TYPES: frozenset[str] = frozenset({
    "goal_ingested",
    "session_refresh_attempted",
    "session_refresh_result",
    "account_loaded",
    "candidates_discovered",
    "target_selected",
    "action_drafted",
    "scored",
    "approval_requested",
    "approval_decided",
    "action_executed",
    "action_skipped",
    "execution_error",
    "node_error",
    "workflow_completed",
})
"""Canonical smart-engagement audit event_type values emitted by nodes."""


class AccountContextPort(ABC):
    """Port for fetching account context and health."""

    @abstractmethod
    async def get_account_context(self, account_id: str) -> AccountHealth:
        """Fetch account health and status.

        Args:
            account_id: Account ID

        Returns:
            AccountHealth with status, cooldown, proxy, login_state

        Raises:
            ValueError: If account not found
            Exception: If fetch fails
        """

    @abstractmethod
    async def validate_account_ready(self, account_id: str) -> bool:
        """Check if account is ready for engagement.

        Args:
            account_id: Account ID

        Returns:
            True if account is active and not in cooldown
        """

    async def try_refresh_session(self, account_id: str) -> bool:
        """Attempt to restore an expired or missing Instagram session.

        Called automatically by load_account_context_node when login_state is
        not 'logged_in'.  Subclasses that can re-authenticate override this;
        the default implementation is a safe no-op that returns False so that
        existing test stubs and adapters without relogin capability continue to
        work without changes.

        Args:
            account_id: Account whose session needs refreshing

        Returns:
            True if the session is now loaded and ready, False otherwise
        """
        return False


class EngagementCandidatePort(ABC):
    """Port for discovering engagement targets based on intent."""

    @abstractmethod
    async def discover_candidates(
        self,
        account_id: str,
        goal: str,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        """Discover candidates matching operator's goal.

        Args:
            account_id: Account that will engage
            goal: Operator's intent (e.g., 'find targets for educational comments')
            filters: Optional filters (min_followers, engagement_rate, etc.)

        Returns:
            List of EngagementTarget dicts

        Raises:
            Exception: If discovery fails
        """

    @abstractmethod
    async def get_target_metadata(self, target_id: str) -> dict:
        """Get detailed metadata for a single target.

        Args:
            target_id: Username or post ID

        Returns:
            Dict with engagement stats, activity, etc.
        """


class RiskScoringPort(ABC):
    """Port for risk assessment with explicit reasoning.

    Port Contract:
    - MUST return reasoning string (not just score)
    - MUST return rule_hits list (which rules were triggered)
    - MUST determine requires_approval based on risk_level and action type
    """

    @abstractmethod
    async def assess_risk(
        self,
        action: ProposedAction,
        target: EngagementTarget,
        account_health: AccountHealth,
    ) -> RiskAssessment:
        """Assess risk of engagement action.

        Args:
            action: Proposed action (follow, dm, comment, like)
            target: Target account/post
            account_health: Current account status

        Returns:
            RiskAssessment with:
            - risk_level: low, medium, high
            - rule_hits: list of triggered rules
            - reasoning: WHY this risk (not just score)
            - requires_approval: bool (True for high risk or write actions)

        Raises:
            Exception: If assessment fails
        """


class ApprovalPort(ABC):
    """Port for approval gate.

    Port Contract:
    - approval_request MUST be self-contained (UI reads it without state lookup)
    - Approval submission returns approval_id (for tracking)
    - get_approval_status returns full ApprovalResult
    """

    @abstractmethod
    async def submit_for_approval(
        self,
        approval_request: ApprovalRequest,
    ) -> str:
        """Submit action for human approval.

        Args:
            approval_request: Self-contained payload with everything UI needs

        Returns:
            Approval request ID (for tracking)

        Raises:
            Exception: If submission fails
        """

    @abstractmethod
    async def get_approval_status(self, approval_id: str) -> ApprovalResult:
        """Get approval decision.

        Args:
            approval_id: ID from submit_for_approval()

        Returns:
            ApprovalResult with decision (approved/rejected/edited/timeout)

        Raises:
            ValueError: If approval_id not found
        """


class EngagementExecutorPort(ABC):
    """Port for executing engagement actions.

    Port Contract:
    - NEVER call execute methods when mode='recommendation'
    - Graph MUST enforce mode before calling executor
    - Execute methods should fail fast if approval not granted
    """

    @abstractmethod
    async def execute_follow(self, target_id: str, account_id: str) -> ExecutionResult:
        """Follow a user account.

        Args:
            target_id: Username to follow
            account_id: Account performing action

        Returns:
            ExecutionResult with success, action_id, timestamp
        """

    @abstractmethod
    async def execute_dm(
        self,
        target_id: str,
        account_id: str,
        message: str,
    ) -> ExecutionResult:
        """Send direct message.

        Args:
            target_id: Username to message
            account_id: Account sending message
            message: Message content

        Returns:
            ExecutionResult with success, action_id, timestamp
        """

    @abstractmethod
    async def execute_comment(
        self,
        post_id: str,
        account_id: str,
        comment_text: str,
    ) -> ExecutionResult:
        """Post comment on a post.

        Args:
            post_id: Post ID
            account_id: Account posting comment
            comment_text: Comment content

        Returns:
            ExecutionResult with success, action_id, timestamp
        """

    @abstractmethod
    async def execute_like(
        self,
        post_id: str,
        account_id: str,
    ) -> ExecutionResult:
        """Like a post.

        Args:
            post_id: Post ID
            account_id: Account liking post

        Returns:
            ExecutionResult with success, timestamp
        """

    @abstractmethod
    def is_write_action(self, action_type: str) -> bool:
        """Check if action type modifies Instagram state.

        Args:
            action_type: follow, dm, comment, like, skip

        Returns:
            True if action requires approval
        """


class EngagementMemoryPort(ABC):
    """Port for cross-thread engagement memory.

    Stores and retrieves past engagement outcomes so the workflow can:
    - Avoid re-engaging recently contacted targets
    - Skip targets whose engagement was rejected by the operator
    - Learn from past success/failure patterns

    Port Contract:
    - Namespace isolation per account_id (accounts don't see each other's memory)
    - Recent engagements return newest-first
    - Rejected targets are a subset of recent engagements with outcome='rejected'
    """

    @abstractmethod
    async def recall_recent_engagements(
        self,
        account_id: str,
        limit: int = 20,
    ) -> list[EngagementMemoryRecord]:
        """Recall recent engagement outcomes for an account.

        Args:
            account_id: Account that performed engagements
            limit: Max records to return (newest first)

        Returns:
            List of EngagementMemoryRecord, newest first
        """

    @abstractmethod
    async def store_engagement_outcome(
        self,
        account_id: str,
        target_id: str,
        action_type: str,
        outcome: str,
    ) -> None:
        """Store an engagement outcome for future recall.

        Args:
            account_id: Account that performed the action
            target_id: Who/what was engaged
            action_type: follow, dm, comment, like
            outcome: success, failed, rejected, skipped
        """

    @abstractmethod
    async def recall_rejected_targets(
        self,
        account_id: str,
        limit: int = 50,
    ) -> set[str]:
        """Recall target_ids whose engagement was rejected by the operator.

        Args:
            account_id: Account
            limit: Max records to scan

        Returns:
            Set of target_ids that were rejected
        """


class AuditLogPort(ABC):
    """Port for audit trail logging.

    Port Contract:
    - Receive explicit events per node decision (not implicit state changes)
    - event_type in SMART_ENGAGEMENT_AUDIT_EVENT_TYPES
    - event_data varies by event_type (encapsulate all context)
    """

    @abstractmethod
    async def log_event(
        self,
        event: AuditEvent,
    ) -> None:
        """Log an explicit workflow event.

        Args:
            event: AuditEvent with:
                - event_type: value from SMART_ENGAGEMENT_AUDIT_EVENT_TYPES
                - node_name: which node emitted this
                - event_data: event-specific data (includes all context)
                - timestamp: when event occurred

        Raises:
            Exception: If logging fails
        """

    @abstractmethod
    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        """Get audit trail for a thread.

        Args:
            thread_id: Execution thread ID

        Returns:
            List of AuditEvent in chronological order
        """
