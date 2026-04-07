"""Risk scoring adapter - implements RiskScoringPort with rule-based assessment.

Uses configurable rules to assess engagement risk.
Returns: risk_level + rule_hits + reasoning (PORT CONTRACT).
"""

from __future__ import annotations

import logging

from ai_copilot.application.smart_engagement.ports import RiskScoringPort

logger = logging.getLogger(__name__)
from ai_copilot.application.smart_engagement.state import (
    AccountHealth,
    EngagementTarget,
    ProposedAction,
    RiskAssessment,
)


class RiskScoringAdapter(RiskScoringPort):
    """Rule-based risk assessment for engagement actions.

    Evaluates risk based on:
    - Account health (cooldown, login state, recent actions)
    - Action type (follow/dm/comment/like are write operations)
    - Target characteristics
    """

    def __init__(self):
        """Initialize with default rule set."""
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> dict:
        """Initialize risk scoring rules.

        Returns:
            Dict mapping rule names to (trigger_fn, risk_impact)
        """
        return {
            # Account constraints
            "account_in_cooldown": (
                lambda action, target, health: health.get("cooldown_until") is not None,
                ("high", "Account in cooldown period"),
            ),
            "account_not_logged_in": (
                lambda action, target, health: health.get("login_state") != "logged_in",
                ("high", "Account not logged in"),
            ),
            # Action frequency
            "too_many_actions_today": (
                lambda action, target, health: health.get("recent_actions", 0) > 10,
                ("high", "Too many actions in recent period"),
            ),
            # Write operation check
            "write_action_requires_approval": (
                lambda action, target, health: action.get("action_type")
                in ["follow", "dm", "comment", "like"],
                ("medium", "Write action requires approval"),
            ),
        }

    async def assess_risk(
        self,
        action: ProposedAction,
        target: EngagementTarget,
        account_health: AccountHealth,
    ) -> RiskAssessment:
        """Assess risk of engagement action using rules.

        Args:
            action: Proposed action
            target: Target account/post
            account_health: Current account status

        Returns:
            RiskAssessment with:
            - risk_level: low, medium, high
            - rule_hits: list of triggered rules
            - reasoning: WHY this risk (REQUIRED by contract)
            - requires_approval: bool
        """
        rule_hits = []
        max_risk_level = "low"
        reasons = []

        # Check each rule
        for rule_name, (trigger_fn, (impact_level, explanation)) in self.rules.items():
            try:
                if trigger_fn(action, target, account_health):
                    rule_hits.append(rule_name)
                    reasons.append(explanation)

                    # Update max risk level
                    if impact_level == "high":
                        max_risk_level = "high"
                    elif impact_level == "medium" and max_risk_level != "high":
                        max_risk_level = "medium"

            except Exception:
                logger.exception("Risk rule %r failed, skipping", rule_name)
                continue

        # Build reasoning
        if rule_hits:
            reasoning = f"Triggered {len(rule_hits)} rule(s): {', '.join(rule_hits)}"
            if reasons:
                reasoning += f". {'; '.join(reasons)}"
        else:
            reasoning = "No risk rules triggered"

        # Determine if approval is required
        requires_approval = (
            max_risk_level == "high"
            or action.get("action_type") in ["follow", "dm", "comment", "like"]
        )

        return RiskAssessment(
            risk_level=max_risk_level,
            rule_hits=rule_hits,
            reasoning=reasoning,
            requires_approval=requires_approval,
        )
