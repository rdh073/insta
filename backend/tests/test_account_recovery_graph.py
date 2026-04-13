"""Tests for Account Recovery LangGraph workflow.

Test strategy:
1. Healthy account → no issue, already_healthy stop
2. Session expired → relogin succeeds → recovered
3. 2FA required → interrupt emitted with correct payload
4. Resume provide_2fa → relogin with code called
5. Resume abort → stop_reason=aborted
6. Max attempts loop guard prevents infinite retry
"""

from __future__ import annotations

import asyncio
import time
from langgraph.checkpoint.memory import MemorySaver

from ai_copilot.application.use_cases.run_account_recovery import RunAccountRecoveryUseCase


# =============================================================================
# Stub ports
# =============================================================================


class StubDiagnostics:
    def __init__(self, error_state=None, issue="none", healthy=True):
        self._error_state = error_state or {"has_error": False}
        self._issue = issue
        self._healthy = healthy

    async def read_error_state(self, account_id):
        return dict(self._error_state)

    async def classify_issue(self, error_state):
        return self._issue

    async def verify_account_health(self, account_id):
        return {"healthy": self._healthy, "login_state": "logged_in" if self._healthy else "session_expired", "checked_at": time.time()}


class StubExecutor:
    def __init__(self, relogin_result=None, requires_2fa=False, proxy="1.2.3.4:8080"):
        self._relogin_result = relogin_result or {"success": True, "requires_2fa": False, "error": None}
        self._requires_2fa = requires_2fa
        self._proxy = proxy
        self.relogin_calls = []
        self.swap_calls = []

    async def relogin(self, account_id, two_fa_code=None):
        self.relogin_calls.append({"account_id": account_id, "two_fa_code": two_fa_code})
        if self._requires_2fa and two_fa_code is None:
            return {"success": False, "requires_2fa": True, "error": None}
        return dict(self._relogin_result)

    async def swap_proxy(self, account_id, new_proxy):
        self.swap_calls.append({"account_id": account_id, "proxy": new_proxy})
        return {"success": True, "proxy": new_proxy, "error": None}

    async def get_available_proxy(self, account_id):
        return self._proxy


def _make_uc(diagnostics, executor):
    return RunAccountRecoveryUseCase(
        diagnostics=diagnostics,
        executor=executor,
        checkpointer=MemorySaver(),
    )


async def _collect(gen):
    return [ev async for ev in gen]


# =============================================================================
# Test 1: Healthy account → no issue → already_healthy
# =============================================================================


def test_healthy_account_no_issue():
    uc = _make_uc(
        StubDiagnostics(error_state={"has_error": False}, issue="none", healthy=True),
        StubExecutor(),
    )
    events = asyncio.run(_collect(uc.run(account_id="acc-1", username="user1", thread_id="t-healthy")))
    types = [e["type"] for e in events]

    assert "run_finish" in types
    assert "approval_required" not in types

    node_updates = [event for event in events if event["type"] == "node_update"]
    assert node_updates, "expected at least one node_update event"
    assert all("data" in event for event in node_updates)
    assert all("output" not in event for event in node_updates)

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] in ("no_issue", "completed", "recovered")


# =============================================================================
# Test 2: Session expired → relogin succeeds → recovered
# =============================================================================


def test_session_expired_relogin_success():
    uc = _make_uc(
        StubDiagnostics(
            error_state={"has_error": True, "login_state": "session_expired"},
            issue="session_expired",
            healthy=True,
        ),
        StubExecutor(relogin_result={"success": True, "requires_2fa": False, "error": None}),
    )
    events = asyncio.run(_collect(uc.run(account_id="acc-2", username="user2", thread_id="t-relogin")))
    types = [e["type"] for e in events]

    assert "run_finish" in types
    assert "approval_required" not in types

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] in ("recovered", "completed")


# =============================================================================
# Test 3: 2FA required → interrupt emitted
# =============================================================================


def test_2fa_required_triggers_interrupt():
    uc = _make_uc(
        StubDiagnostics(
            error_state={"has_error": True, "login_state": "needs_2fa"},
            issue="2fa_required",
            healthy=False,
        ),
        StubExecutor(requires_2fa=True),
    )
    events = asyncio.run(_collect(uc.run(account_id="acc-3", username="user3", thread_id="t-2fa")))
    types = [e["type"] for e in events]

    assert "approval_required" in types

    approval = next(e for e in events if e["type"] == "approval_required")
    payload = approval["payload"]

    assert payload["type"] == "account_recovery_approval"
    assert "provide_2fa" in payload["options"]
    assert payload["account_id"] == "acc-3"


# =============================================================================
# Test 4: Resume provide_2fa → relogin called with code
# =============================================================================


def test_resume_provide_2fa():
    stub_exec = StubExecutor(requires_2fa=True)
    uc = _make_uc(
        StubDiagnostics(
            error_state={"has_error": True, "login_state": "needs_2fa"},
            issue="2fa_required",
            healthy=True,  # after relogin with code, account becomes healthy
        ),
        stub_exec,
    )
    thread_id = "t-2fa-resume"

    async def run_both():
        await _collect(uc.run(account_id="acc-4", username="user4", thread_id=thread_id))
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="provide_2fa",
            two_fa_code="123456",
        ))

    events = asyncio.run(run_both())
    types = [e["type"] for e in events]

    assert "run_finish" in types
    # Relogin was called with 2FA code
    calls_with_code = [c for c in stub_exec.relogin_calls if c.get("two_fa_code") == "123456"]
    assert len(calls_with_code) >= 1


# =============================================================================
# Test 5: Resume abort → stop_reason=aborted
# =============================================================================


def test_resume_abort():
    uc = _make_uc(
        StubDiagnostics(
            error_state={"has_error": True, "login_state": "needs_2fa"},
            issue="2fa_required",
            healthy=False,
        ),
        StubExecutor(requires_2fa=True),
    )
    thread_id = "t-abort"

    async def run_both():
        await _collect(uc.run(account_id="acc-5", username="user5", thread_id=thread_id))
        return await _collect(uc.resume(thread_id=thread_id, decision="abort"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "aborted"


# =============================================================================
# Test 6: Loop guard — max_recovery_attempts=1 prevents infinite retry
# =============================================================================


def test_loop_guard_max_attempts():
    """With max_recovery_attempts=1, recovery stops after one failed attempt."""
    uc = _make_uc(
        StubDiagnostics(
            error_state={"has_error": True, "login_state": "session_expired"},
            issue="session_expired",
            healthy=False,  # never becomes healthy → retry loop
        ),
        StubExecutor(relogin_result={"success": False, "requires_2fa": False, "error": "fail"}),
    )
    events = asyncio.run(_collect(uc.run(
        account_id="acc-6",
        username="user6",
        thread_id="t-loop",
        max_recovery_attempts=1,
    )))
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] in ("max_attempts_reached", "failed", "completed")
    # Must not loop forever
    assert len(events) < 50
