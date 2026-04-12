"""Smart engagement node stage: goal ingestion and account context loading."""

from __future__ import annotations

import logging
import time

from ai_copilot.application.smart_engagement.goal_parser import (
    _account_not_healthy_reason,
    _parse_goal,
)
from ai_copilot.application.smart_engagement.state import AuditEvent, SmartEngagementState

logger = logging.getLogger(__name__)


class ContextNodesMixin:
    # =========================================================================
    # Node 1: ingest_goal
    # =========================================================================

    async def ingest_goal_node(self, state: SmartEngagementState) -> dict:
        """Parse operator goal into structured form.

        Pure parsing - no external calls. Extracts:
        - intent: what action type (comment, follow, like, dm)
        - target_type: account/post/hashtag
        - action_type: follow/comment/like/dm
        - constraints: content filters, audience criteria
        """
        goal = state.get("goal", "")

        structured_goal = _parse_goal(goal)

        event = await self._emit(
            AuditEvent(
                event_type="goal_ingested",
                node_name="ingest_goal",
                event_data={
                    "goal": goal,
                    "structured_goal": structured_goal,
                    "thread_id": state.get("thread_id"),
                },
                timestamp=time.time(),
            )
        )

        return {
            "structured_goal": structured_goal,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [event],
        }

    # =========================================================================
    # Node 2: load_account_context
    # =========================================================================

    async def load_account_context_node(self, state: SmartEngagementState) -> dict:
        """Fetch account health and constraints.

        If the account's session is missing/expired the node attempts one
        automatic relogin via AccountContextPort.try_refresh_session() before
        giving up.  This lets smart engagement recover from stale sessions
        (e.g. after a server restart) without operator intervention.

        Fail-fast: if account still not healthy after refresh attempt →
        outcome_reason set for log_outcome.
        Routing: route_after_account_context() → 'discover_candidates' or 'log_outcome'
        """
        account_id = state.get("account_id", "")

        try:
            health = await self.account_context.get_account_context(account_id)

            is_healthy = (
                health.get("status") == "active"
                and health.get("login_state") == "logged_in"
                and health.get("cooldown_until") is None
            )

            # Session not ready — try one automatic relogin before giving up.
            # try_refresh_session() returns False by default (no-op for adapters
            # that don't support it) so this is always safe to call.
            if not is_healthy and health.get("login_state") != "logged_in":
                refresh_event = await self._emit(
                    AuditEvent(
                        event_type="session_refresh_attempted",
                        node_name="load_account_context",
                        event_data={"account_id": account_id, "reason": "session_not_loaded"},
                        timestamp=time.time(),
                    )
                )
                refreshed = await self.account_context.try_refresh_session(account_id)
                if refreshed:
                    # Re-fetch health after successful refresh
                    health = await self.account_context.get_account_context(account_id)
                    is_healthy = (
                        health.get("status") == "active"
                        and health.get("login_state") == "logged_in"
                        and health.get("cooldown_until") is None
                    )
                    refresh_status = "success" if is_healthy else "partial"
                else:
                    refresh_status = "failed"

                refresh_done_event = await self._emit(
                    AuditEvent(
                        event_type="session_refresh_result",
                        node_name="load_account_context",
                        event_data={
                            "account_id": account_id,
                            "result": refresh_status,
                            "now_healthy": is_healthy,
                        },
                        timestamp=time.time(),
                    )
                )

                if not is_healthy:
                    reason = _account_not_healthy_reason(health)
                    skip_event = await self._emit(
                        AuditEvent(
                            event_type="action_skipped",
                            node_name="load_account_context",
                            event_data={"reason": reason},
                            timestamp=time.time(),
                        )
                    )
                    return {
                        "account_health": health,
                        "outcome_reason": reason,
                        "stop_reason": "account_not_ready",
                        "audit_trail": [refresh_event, refresh_done_event, skip_event],
                    }

                return {
                    "account_health": health,
                    "audit_trail": [
                        refresh_event,
                        refresh_done_event,
                        await self._emit(
                            AuditEvent(
                                event_type="account_loaded",
                                node_name="load_account_context",
                                event_data={
                                    "account_id": account_id,
                                    "status": health.get("status"),
                                    "login_state": health.get("login_state"),
                                    "session_refreshed": True,
                                },
                                timestamp=time.time(),
                            )
                        ),
                    ],
                }

            if not is_healthy:
                reason = _account_not_healthy_reason(health)
                event = await self._emit(
                    AuditEvent(
                        event_type="action_skipped",
                        node_name="load_account_context",
                        event_data={"reason": reason},
                        timestamp=time.time(),
                    )
                )
                return {
                    "account_health": health,
                    "outcome_reason": reason,
                    "stop_reason": "account_not_ready",
                    "audit_trail": [event],
                }

            event = await self._emit(
                AuditEvent(
                    event_type="account_loaded",
                    node_name="load_account_context",
                    event_data={
                        "account_id": account_id,
                        "status": health.get("status"),
                        "login_state": health.get("login_state"),
                    },
                    timestamp=time.time(),
                )
            )

            return {"account_health": health, "audit_trail": [event]}

        except Exception as e:
            reason = f"Account context error: {str(e)[:80]}"
            logger.exception("load_account_context failed for account=%s", account_id)
            event = await self._emit(
                AuditEvent(
                    event_type="node_error",
                    node_name="load_account_context",
                    event_data={"error": reason, "account_id": account_id},
                    timestamp=time.time(),
                )
            )
            return {
                "account_health": None,
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [event],
            }

    def route_after_account_context(self, state: SmartEngagementState) -> str:
        """Route: healthy account → discover_candidates, else → log_outcome."""
        health = state.get("account_health")
        stop = state.get("stop_reason")
        if stop or not health or health.get("status") != "active":
            return "log_outcome"
        return "discover_candidates"
