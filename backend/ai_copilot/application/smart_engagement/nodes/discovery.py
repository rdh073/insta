"""Smart engagement node stage: candidate discovery and ranking."""

from __future__ import annotations

import logging
import time

from ai_copilot.application.smart_engagement.scoring import _score_candidate
from ai_copilot.application.smart_engagement.state import AuditEvent, SmartEngagementState

logger = logging.getLogger(__name__)


class DiscoveryNodesMixin:
    # =========================================================================
    # Node 3: discover_candidates
    # =========================================================================

    async def discover_candidates_node(self, state: SmartEngagementState) -> dict:
        """Discover engagement candidates based on operator goal.

        Bounded: max 1 discovery per run (discovery_attempted flag).
        Fail-fast: no candidates → outcome_reason set.
        Routing: route_after_discovery() → 'rank_candidates' or 'log_outcome'
        """
        # Failure rule: max 1 discovery per run
        if state.get("discovery_attempted"):
            return {
                "outcome_reason": "Discovery already attempted this run",
                "stop_reason": "discovery_limit_reached",
            }

        account_id = state.get("account_id", "")
        goal = state.get("goal", "")
        max_targets = state.get("max_targets", 5)

        try:
            candidates = await self.candidate_discovery.discover_candidates(
                account_id=account_id,
                goal=goal,
                filters={"max_results": max_targets},
            )

            # Filter out recently engaged and rejected targets via memory
            excluded_ids: set[str] = set()
            if self.engagement_memory is not None and candidates:
                try:
                    recent = await self.engagement_memory.recall_recent_engagements(
                        account_id, limit=50
                    )
                    excluded_ids.update(r["target_id"] for r in recent)
                    rejected = await self.engagement_memory.recall_rejected_targets(account_id)
                    excluded_ids.update(rejected)
                except Exception:
                    logger.warning(
                        "Memory recall failed for account=%s, proceeding without filter",
                        account_id,
                    )

            if excluded_ids:
                before = len(candidates)
                candidates = [c for c in candidates if c.get("target_id") not in excluded_ids]
                filtered_count = before - len(candidates)
                if filtered_count > 0:
                    logger.info(
                        "Filtered %d recently-engaged/rejected targets for account=%s",
                        filtered_count,
                        account_id,
                    )

            if not candidates:
                reason = f"No candidates found for goal: {goal!r}"
                event = await self._emit(
                    state,
                    AuditEvent(
                        event_type="action_skipped",
                        node_name="discover_candidates",
                        event_data={
                            "reason": reason,
                            "goal": goal,
                            "excluded_count": len(excluded_ids),
                        },
                        timestamp=time.time(),
                    ),
                )
                return {
                    "candidate_targets": [],
                    "discovery_attempted": True,
                    "outcome_reason": reason,
                    "stop_reason": "no_candidates",
                    "audit_trail": [event],
                }

            event = await self._emit(
                state,
                AuditEvent(
                    event_type="candidates_discovered",
                    node_name="discover_candidates",
                    event_data={
                        "count": len(candidates),
                        "goal": goal,
                        "excluded_count": len(excluded_ids),
                    },
                    timestamp=time.time(),
                ),
            )

            return {
                "candidate_targets": candidates,
                "discovery_attempted": True,
                "audit_trail": [event],
            }

        except Exception as e:
            reason = f"Discovery error: {str(e)[:80]}"
            logger.exception(
                "discover_candidates failed for account=%s goal=%r", account_id, goal
            )
            event = await self._emit(
                state,
                AuditEvent(
                    event_type="node_error",
                    node_name="discover_candidates",
                    event_data={"error": reason, "account_id": account_id, "goal": goal},
                    timestamp=time.time(),
                ),
            )
            return {
                "candidate_targets": [],
                "discovery_attempted": True,
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [event],
            }

    def route_after_discovery(self, state: SmartEngagementState) -> str:
        """Route: candidates found → rank_candidates, else → log_outcome."""
        stop = state.get("stop_reason")
        candidates = state.get("candidate_targets", [])
        if stop or not candidates:
            return "log_outcome"
        return "rank_candidates"

    # =========================================================================
    # Node 4: rank_candidates
    # =========================================================================

    async def rank_candidates_node(self, state: SmartEngagementState) -> dict:
        """Rank and select the best candidate target.

        Scores by: engagement_rate (primary), follower_count (secondary).
        Selects top-ranked candidate as selected_target.
        """
        candidates = state.get("candidate_targets", [])
        structured_goal = state.get("structured_goal") or {}

        if not candidates:
            return {"selected_target": None}

        # Score candidates by relevance and engagement
        scored = sorted(
            candidates,
            key=lambda c: _score_candidate(c, structured_goal),
            reverse=True,
        )

        selected = scored[0]

        event = await self._emit(
            state,
            AuditEvent(
                event_type="target_selected",
                node_name="rank_candidates",
                event_data={
                    "target_id": selected.get("target_id"),
                    "total_candidates": len(candidates),
                    "reason": "Top-ranked by engagement_rate and goal fit",
                },
                timestamp=time.time(),
            )
        )

        return {"selected_target": selected, "audit_trail": [event]}
