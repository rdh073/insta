"""Account Recovery workflow state."""

from __future__ import annotations

from typing import Annotated, TypedDict


def _append(existing: list, new: list) -> list:
    if not isinstance(new, list):
        return existing
    return existing + new


class AccountRecoveryState(TypedDict):
    thread_id: str
    account_id: str
    username: str

    error_type: str | None       # "challenge"|"blocked"|"session_expired"|"2fa_required"|"unknown"
    current_proxy: str | None
    error_details: dict | None

    recovery_path: str | None    # "relogin"|"swap_proxy"|"relogin_with_new_proxy"|"unrecoverable"
    recovery_attempts: int
    max_recovery_attempts: int   # loop guard

    requires_2fa: bool
    two_fa_code: str | None

    operator_decision: str | None  # "provide_2fa"|"approve_proxy_swap"|"abort"
    operator_payload: dict | None  # full resume payload

    relogin_result: dict | None
    proxy_swap_result: dict | None
    health_check_result: dict | None

    recovery_successful: bool
    result: str | None           # "recovered"|"failed"|"aborted"

    outcome_reason: str | None
    stop_reason: str | None
    step_count: int
    audit_trail: Annotated[list[dict], _append]


def make_initial_state(
    thread_id: str,
    account_id: str,
    username: str,
    max_recovery_attempts: int = 3,
) -> AccountRecoveryState:
    return AccountRecoveryState(
        thread_id=thread_id,
        account_id=account_id,
        username=username,
        error_type=None,
        current_proxy=None,
        error_details=None,
        recovery_path=None,
        recovery_attempts=0,
        max_recovery_attempts=max_recovery_attempts,
        requires_2fa=False,
        two_fa_code=None,
        operator_decision=None,
        operator_payload=None,
        relogin_result=None,
        proxy_swap_result=None,
        health_check_result=None,
        recovery_successful=False,
        result=None,
        outcome_reason=None,
        stop_reason=None,
        step_count=0,
        audit_trail=[],
    )
