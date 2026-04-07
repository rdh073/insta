"""Engagement executor adapter - app-owned execution bridge for smart engagement."""

from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

from ai_copilot.application.smart_engagement.ports import EngagementExecutorPort
from ai_copilot.application.smart_engagement.state import ExecutionResult


@runtime_checkable
class DirectUseCasesPort(Protocol):
    def send_to_username(self, account_id: str, username: str, text: str):
        pass

    def send_to_users(self, account_id: str, user_ids: list[int], text: str):
        pass


@runtime_checkable
class CommentUseCasesPort(Protocol):
    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: int | None = None,
    ):
        pass


@runtime_checkable
class IdentityUseCasesPort(Protocol):
    def get_public_user_by_id(self, account_id: str, user_id: int):
        pass


class EngagementExecutorAdapter(EngagementExecutorPort):
    """Executes supported engagement actions via application use cases only."""

    def __init__(
        self,
        account_id: str = "",
        direct_use_cases: DirectUseCasesPort | None = None,
        comment_use_cases: CommentUseCasesPort | None = None,
        identity_use_cases: IdentityUseCasesPort | None = None,
    ):
        self.account_id = account_id
        self.direct_use_cases = direct_use_cases
        self.comment_use_cases = comment_use_cases
        self.identity_use_cases = identity_use_cases

    async def execute_follow(self, target_id: str, account_id: str) -> ExecutionResult:
        return self._result(
            success=False,
            action_id=None,
            reason="Follow action is not supported yet",
            reason_code="unsupported_action",
        )

    async def execute_dm(
        self,
        target_id: str,
        account_id: str,
        message: str,
    ) -> ExecutionResult:
        if self.direct_use_cases is None:
            return self._result(
                success=False,
                action_id=None,
                reason="Direct use case is not configured",
                reason_code="adapter_not_configured",
            )
        resolved_account_id = account_id or self.account_id
        if not resolved_account_id:
            return self._result(
                success=False,
                action_id=None,
                reason="Account ID is required for DM execution",
                reason_code="invalid_input",
            )
        try:
            if target_id.isdigit():
                numeric_id = int(target_id)
                if self.identity_use_cases is not None:
                    # Validate the target user exists and is resolvable.
                    self.identity_use_cases.get_public_user_by_id(resolved_account_id, numeric_id)
                sent_message = self.direct_use_cases.send_to_users(
                    account_id=resolved_account_id,
                    user_ids=[numeric_id],
                    text=message,
                )
            else:
                sent_message = self.direct_use_cases.send_to_username(
                    account_id=resolved_account_id,
                    username=target_id,
                    text=message,
                )
            return self._result(
                success=True,
                action_id=str(sent_message.direct_message_id),
                reason=f"DM sent to {target_id}",
                reason_code="ok",
            )
        except ValueError as exc:
            return self._result(
                success=False,
                action_id=None,
                reason=str(exc),
                reason_code="validation_error",
            )
        except Exception:
            logger.exception("DM execution failed for account=%s target=%s", resolved_account_id, target_id)
            return self._result(
                success=False,
                action_id=None,
                reason="DM execution failed",
                reason_code="execution_failed",
            )

    async def execute_comment(
        self,
        post_id: str,
        account_id: str,
        comment_text: str,
    ) -> ExecutionResult:
        if self.comment_use_cases is None:
            return self._result(
                success=False,
                action_id=None,
                reason="Comment use case is not configured",
                reason_code="adapter_not_configured",
            )
        resolved_account_id = account_id or self.account_id
        if not resolved_account_id:
            return self._result(
                success=False,
                action_id=None,
                reason="Account ID is required for comment execution",
                reason_code="invalid_input",
            )
        try:
            comment = self.comment_use_cases.create_comment(
                account_id=resolved_account_id,
                media_id=post_id,
                text=comment_text,
                reply_to_comment_id=None,
            )
            return self._result(
                success=True,
                action_id=str(comment.pk),
                reason="Comment created",
                reason_code="ok",
            )
        except ValueError as exc:
            return self._result(
                success=False,
                action_id=None,
                reason=str(exc),
                reason_code="validation_error",
            )
        except Exception:
            logger.exception("Comment execution failed for account=%s post=%s", resolved_account_id, post_id)
            return self._result(
                success=False,
                action_id=None,
                reason="Comment execution failed",
                reason_code="execution_failed",
            )

    async def execute_like(self, post_id: str, account_id: str) -> ExecutionResult:
        return self._result(
            success=False,
            action_id=None,
            reason="Like action is not supported yet",
            reason_code="unsupported_action",
        )

    def is_write_action(self, action_type: str) -> bool:
        write_actions = {"follow", "dm", "comment", "like"}
        return action_type.lower() in write_actions

    def _result(
        self,
        *,
        success: bool,
        action_id: str | None,
        reason: str,
        reason_code: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            success=success,
            action_id=action_id,
            reason=reason,
            reason_code=reason_code,
            timestamp=time.time(),
        )
