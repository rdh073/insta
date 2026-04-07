"""Tests for Risk Control LangGraph workflow.

Test strategy:
1. Low risk → short-circuit to recheck, no interrupt
2. High risk → cooldown applied, no interrupt
3. Critical risk → escalation interrupt triggered with correct payload
4. Resume abort → stop_reason=aborted, no policy applied
5. Resume override_policy → apply_operator_override called, recheck runs
6. Port contract satisfied by stub adapters
"""

from __future__ import annotations

import asyncio
import time
import pytest
from langgraph.checkpoint.memory import MemorySaver

from ai_copilot.application.use_cases.run_risk_control import RunRiskControlUseCase


# =============================================================================
# Stub ports
# =============================================================================


class StubAccountSignal:
    def __init__(self, status=None, events=None):
        self._status = status or {"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": []}
        self._events = events or []

    async def get_account_status(self, account_id):
        return dict(self._status)

    async def get_recent_events(self, account_id, limit=20):
        return list(self._events)


class StubPolicyDecision:
    def __init__(self, decision="continue"):
        self._decision = decision
        self.cooldown_calls = []

    async def evaluate(self, account_id, risk_level, risk_factors, recent_events):
        return self._decision

    async def apply_cooldown(self, account_id, duration_seconds):
        until = time.time() + duration_seconds
        self.cooldown_calls.append({"account_id": account_id, "duration": duration_seconds, "until": until})
        return until


class StubProxyRotation:
    def __init__(self, candidate=None):
        self._candidate = candidate
        self.apply_calls = []

    async def get_candidate_proxy(self, account_id):
        return self._candidate

    async def apply_proxy(self, account_id, proxy):
        self.apply_calls.append({"account_id": account_id, "proxy": proxy})
        return {"success": True, "proxy": proxy, "applied_at": time.time()}


def _make_use_case(status=None, events=None, policy_decision="continue", proxy_candidate=None):
    stub_signal = StubAccountSignal(status=status, events=events)
    stub_policy = StubPolicyDecision(decision=policy_decision)
    stub_proxy = StubProxyRotation(candidate=proxy_candidate)
    checkpointer = MemorySaver()
    uc = RunRiskControlUseCase(
        account_signal=stub_signal,
        policy_decision=stub_policy,
        proxy_rotation=stub_proxy,
        checkpointer=checkpointer,
    )
    return uc, stub_signal, stub_policy, stub_proxy


async def _collect(gen):
    events = []
    async for ev in gen:
        events.append(ev)
    return events


# =============================================================================
# Test 1: Low risk → short-circuit to recheck, no interrupt
# =============================================================================


def test_low_risk_no_interrupt():
    """Healthy account produces low risk and completes without interrupting."""
    uc, _, _, _ = _make_use_case(
        status={"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": []},
        events=[],
        policy_decision="continue",
    )

    events = asyncio.run(_collect(uc.run(account_id="acc-1", thread_id="t-low")))
    types = [e["type"] for e in events]

    assert "run_start" in types
    assert "run_finish" in types
    assert "approval_required" not in types

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] in ("completed",)


# =============================================================================
# Test 2: High risk → cooldown applied, no interrupt
# =============================================================================


def test_high_risk_cooldown_applied():
    """High error burst triggers cooldown policy without needing escalation."""
    # 4 error events → error_burst:4 → high risk
    error_events = [{"event_type": "login_error", "timestamp": time.time(), "detail": ""}] * 4
    uc, _, stub_policy, _ = _make_use_case(
        status={"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": []},
        events=error_events,
        policy_decision="cooldown",
    )

    events = asyncio.run(_collect(uc.run(account_id="acc-2", thread_id="t-high")))
    types = [e["type"] for e in events]

    assert "run_finish" in types
    assert "approval_required" not in types

    # Cooldown was applied
    assert len(stub_policy.cooldown_calls) == 1


# =============================================================================
# Test 3: Critical risk → escalation interrupt triggered
# =============================================================================


def test_critical_risk_triggers_interrupt():
    """Account with challenge flag produces critical risk and pauses for operator."""
    uc, _, _, _ = _make_use_case(
        status={"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": ["challenge"]},
        policy_decision="escalate",
    )

    events = asyncio.run(_collect(uc.run(account_id="acc-3", thread_id="t-critical")))
    types = [e["type"] for e in events]

    assert "approval_required" in types

    approval = next(e for e in events if e["type"] == "approval_required")
    payload = approval["payload"]

    assert payload["type"] == "risk_control_escalation"
    assert payload["account_id"] == "acc-3"
    assert "risk_level" in payload
    assert set(payload["options"]) == {"approve_policy", "override_policy", "abort"}


# =============================================================================
# Test 4: Resume abort → stop_reason=aborted
# =============================================================================


def test_resume_abort():
    """After escalation interrupt, decision=abort → stop_reason=aborted."""
    uc, _, _, _ = _make_use_case(
        status={"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": ["challenge"]},
        policy_decision="escalate",
    )
    thread_id = "t-abort"

    async def run_both():
        await _collect(uc.run(account_id="acc-4", thread_id=thread_id))
        return await _collect(uc.resume(thread_id=thread_id, decision="abort", notes="Not now"))

    events = asyncio.run(run_both())
    types = [e["type"] for e in events]

    assert "run_finish" in types
    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] == "aborted"


# =============================================================================
# Test 5: Resume override_policy → override applied, recheck runs
# =============================================================================


def test_resume_override_policy():
    """After escalation, override_policy=cooldown applies cooldown and rechecks."""
    uc, _, stub_policy, _ = _make_use_case(
        status={"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "error_flags": ["challenge"]},
        policy_decision="escalate",
    )
    thread_id = "t-override"

    async def run_both():
        await _collect(uc.run(account_id="acc-5", thread_id=thread_id))
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="override_policy",
            override_policy="cooldown",
        ))

    events = asyncio.run(run_both())
    types = [e["type"] for e in events]

    assert "run_finish" in types
    assert "approval_required" not in types

    # Cooldown was applied during override
    assert len(stub_policy.cooldown_calls) >= 1


# =============================================================================
# Test 6: Port contract satisfied by stubs
# =============================================================================


def test_stub_ports_satisfy_interface():
    """Verify stub adapters return expected shapes."""
    async def run():
        signal = StubAccountSignal()
        policy = StubPolicyDecision()
        proxy = StubProxyRotation(candidate="1.2.3.4:8080")

        status = await signal.get_account_status("acc-x")
        assert isinstance(status, dict)
        assert "status" in status

        events = await signal.get_recent_events("acc-x")
        assert isinstance(events, list)

        decision = await policy.evaluate("acc-x", "high", ["error_burst:3"], [])
        assert decision in ("continue", "cooldown", "rotate_proxy", "escalate")

        cooldown_until = await policy.apply_cooldown("acc-x", 3600.0)
        assert isinstance(cooldown_until, float)

        candidate = await proxy.get_candidate_proxy("acc-x")
        assert candidate == "1.2.3.4:8080"

        result = await proxy.apply_proxy("acc-x", "1.2.3.4:8080")
        assert result["success"] is True

    asyncio.run(run())
