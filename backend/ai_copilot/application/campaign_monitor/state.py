"""Campaign Monitor workflow state.

Tracks job monitoring, campaign grouping, outcome evaluation, and followup scheduling.
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list, new: list) -> list:
    if not isinstance(new, list):
        return existing
    return existing + new


class CampaignMonitorState(TypedDict):
    thread_id: str
    """Unique execution thread for checkpointing and resumption."""

    job_ids: list[str]
    """Explicit job IDs to load. Empty = load all recent."""

    lookback_days: int
    """How many days back to scan for jobs (default 7)."""

    job_statuses: list[dict]
    """Raw job status dicts loaded from PostJobUseCases."""

    campaign_groups: list[dict]
    """Jobs grouped by campaign tag: [{campaign_tag, job_ids, account_ids}]."""

    account_health: dict
    """Health summary per account_id: {account_id: health_summary}."""

    campaign_summary: dict | None
    """Aggregated outcome summary across all campaigns."""

    recommended_action: str | None
    """One of: 'boost'|'pause'|'reschedule'|'followup'|'no_action'."""

    action_reasoning: str | None
    """Human-readable justification for the recommended action."""

    action_details: dict | None
    """Additional structured data for the recommended action."""

    request_decision: bool
    """True = interrupt and ask operator; False = recommendation only."""

    operator_decision: dict | None
    """Decision returned after interrupt: {decision, parameters}."""

    followup_payload: dict | None
    """Constructed followup job payload (before scheduling)."""

    followup_job_id: str | None
    """Job ID of the created followup task (after scheduling)."""

    outcome_reason: str | None
    """Human-readable explanation of why the workflow ended."""

    stop_reason: str | None
    """Machine-readable terminal state code."""

    step_count: int
    """Step counter for debugging."""

    audit_trail: Annotated[list[dict], _append]
    """Chronological list of audit events emitted by nodes."""


def make_initial_state(
    thread_id: str,
    *,
    job_ids: list[str] | None = None,
    lookback_days: int = 7,
    request_decision: bool = False,
) -> CampaignMonitorState:
    return CampaignMonitorState(
        thread_id=thread_id,
        job_ids=job_ids or [],
        lookback_days=lookback_days,
        job_statuses=[],
        campaign_groups=[],
        account_health={},
        campaign_summary=None,
        recommended_action=None,
        action_reasoning=None,
        action_details=None,
        request_decision=request_decision,
        operator_decision=None,
        followup_payload=None,
        followup_job_id=None,
        outcome_reason=None,
        stop_reason=None,
        step_count=0,
        audit_trail=[],
    )
