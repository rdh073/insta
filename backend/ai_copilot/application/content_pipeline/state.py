"""Content Pipeline workflow state."""

from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list, new: list) -> list:
    if not isinstance(new, list):
        return existing
    return existing + new


class ContentPipelineState(TypedDict):
    thread_id: str
    campaign_brief: str
    media_refs: list[str]

    caption: str | None
    caption_feedback: str | None
    revision_count: int
    max_revisions: int              # loop guard, default 3

    validation_passed: bool
    validation_errors: list[str]

    target_usernames: list[str]
    resolved_account_ids: list[str]

    approval_status: str | None     # "pending"|"approved"|"rejected"|"edited"
    operator_edit: str | None

    scheduled_at: str | None
    job_id: str | None
    schedule_result: dict | None

    outcome_reason: str | None
    stop_reason: str | None
    step_count: int
    audit_trail: Annotated[list[dict], _append]


def make_initial_state(
    thread_id: str,
    campaign_brief: str,
    *,
    media_refs: list[str] | None = None,
    target_usernames: list[str] | None = None,
    scheduled_at: str | None = None,
    max_revisions: int = 3,
) -> ContentPipelineState:
    return ContentPipelineState(
        thread_id=thread_id,
        campaign_brief=campaign_brief,
        media_refs=media_refs or [],
        caption=None,
        caption_feedback=None,
        revision_count=0,
        max_revisions=max_revisions,
        validation_passed=False,
        validation_errors=[],
        target_usernames=target_usernames or [],
        resolved_account_ids=[],
        approval_status=None,
        operator_edit=None,
        scheduled_at=scheduled_at,
        job_id=None,
        schedule_result=None,
        outcome_reason=None,
        stop_reason=None,
        step_count=0,
        audit_trail=[],
    )
