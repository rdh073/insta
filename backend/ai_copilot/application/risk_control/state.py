"""Risk Control workflow state."""

from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list, new: list) -> list:
    if not isinstance(new, list):
        return existing
    return existing + new


class RiskControlState(TypedDict):
    thread_id: str
    account_id: str

    recent_events: list[dict]
    account_status: dict | None

    risk_level: str | None           # "low"|"medium"|"high"|"critical"
    risk_factors: list[str]
    risk_reasoning: str | None

    policy_decision: str | None      # "continue"|"cooldown"|"rotate_proxy"|"escalate"
    cooldown_until: float | None
    proxy_candidate: str | None
    proxy_rotation_result: dict | None

    recheck_status: dict | None
    recheck_risk_level: str | None

    operator_override: dict | None
    final_policy: str | None

    outcome_reason: str | None
    stop_reason: str | None
    step_count: int
    audit_trail: Annotated[list[dict], _append]


def make_initial_state(thread_id: str, account_id: str) -> RiskControlState:
    return RiskControlState(
        thread_id=thread_id,
        account_id=account_id,
        recent_events=[],
        account_status=None,
        risk_level=None,
        risk_factors=[],
        risk_reasoning=None,
        policy_decision=None,
        cooldown_until=None,
        proxy_candidate=None,
        proxy_rotation_result=None,
        recheck_status=None,
        recheck_risk_level=None,
        operator_override=None,
        final_policy=None,
        outcome_reason=None,
        stop_reason=None,
        step_count=0,
        audit_trail=[],
    )
