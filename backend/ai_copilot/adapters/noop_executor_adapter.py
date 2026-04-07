"""NoOp executor adapter - rejects all write actions for recommendation mode.

PURPOSE: Enforce the no-write invariant at the adapter level, not just the graph level.
When injected instead of the real EngagementExecutorAdapter, write operations
physically cannot succeed even if there is a bug in the graph routing.

Used when:
- mode='recommendation' (default safe mode)
- execution feature flag is disabled

This is a safety net - the graph should already prevent execution in
recommendation mode via gate_by_mode, but this adapter makes it impossible
at the infrastructure level.
"""

from __future__ import annotations

import time

from ai_copilot.application.smart_engagement.ports import EngagementExecutorPort
from ai_copilot.application.smart_engagement.state import ExecutionResult

_REASON = "Write action blocked: recommendation mode (NoOpExecutorAdapter injected)"
_REASON_CODE = "recommendation_only"


class NoOpExecutorAdapter(EngagementExecutorPort):
    """Executor that rejects all write actions.

    Injected when mode='recommendation' or execution feature flag is off.
    Returns ExecutionResult(success=False) for every action.

    This is NOT an error - it is correct behavior for recommendation mode.
    """

    async def execute_follow(self, target_id: str, account_id: str) -> ExecutionResult:
        """Reject follow action in recommendation mode."""
        return ExecutionResult(
            success=False,
            action_id=None,
            reason=_REASON,
            reason_code=_REASON_CODE,
            timestamp=time.time(),
        )

    async def execute_dm(
        self,
        target_id: str,
        account_id: str,
        message: str,
    ) -> ExecutionResult:
        """Reject DM action in recommendation mode."""
        return ExecutionResult(
            success=False,
            action_id=None,
            reason=_REASON,
            reason_code=_REASON_CODE,
            timestamp=time.time(),
        )

    async def execute_comment(
        self,
        post_id: str,
        account_id: str,
        comment_text: str,
    ) -> ExecutionResult:
        """Reject comment action in recommendation mode."""
        return ExecutionResult(
            success=False,
            action_id=None,
            reason=_REASON,
            reason_code=_REASON_CODE,
            timestamp=time.time(),
        )

    async def execute_like(self, post_id: str, account_id: str) -> ExecutionResult:
        """Reject like action in recommendation mode."""
        return ExecutionResult(
            success=False,
            action_id=None,
            reason=_REASON,
            reason_code=_REASON_CODE,
            timestamp=time.time(),
        )

    def is_write_action(self, action_type: str) -> bool:
        """All actions are considered write actions in NoOp mode."""
        return True
