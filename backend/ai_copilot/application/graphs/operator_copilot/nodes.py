"""Node composition surface for the operator copilot graph."""

from __future__ import annotations

from ai_copilot.application.state import OperatorCopilotState

from .nodes_approval_execution import OperatorCopilotApprovalExecutionNodes
from .nodes_plan_policy import OperatorCopilotPlanPolicyNodes
from .routing import (
    route_after_approval,
    route_after_classify,
    route_after_plan,
    route_after_policy,
)


class OperatorCopilotNodes(OperatorCopilotApprovalExecutionNodes):
    """Public node surface for builder wiring and tests."""

    def route_after_classify(self, state: OperatorCopilotState) -> str:
        return route_after_classify(state)

    def route_after_plan(self, state: OperatorCopilotState) -> str:
        return route_after_plan(state)

    def route_after_policy(self, state: OperatorCopilotState) -> str:
        return route_after_policy(state, self.policy_registry)

    def route_after_approval(self, state: OperatorCopilotState) -> str:
        return route_after_approval(state)


__all__ = [
    "OperatorCopilotNodes",
    "OperatorCopilotPlanPolicyNodes",
    "OperatorCopilotApprovalExecutionNodes",
]
