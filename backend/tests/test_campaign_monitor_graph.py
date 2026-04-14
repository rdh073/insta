"""Tests for Campaign Monitor LangGraph workflow.

Test strategy:
1. Happy path (request_decision=False) — no interrupt, recommendation_only
2. Interrupt triggered when request_decision=True
3. Resume approved → create_followup_task called
4. Resume skip → workflow finishes without followup
5. No-data path — no jobs → stop_reason=no_data (fail-fast)
6. Port contract satisfied by stub adapter

All tests use duck-typed stub ports (no ABC import) and MemorySaver checkpointer.
"""

from __future__ import annotations

import asyncio
import pytest
from langgraph.checkpoint.memory import MemorySaver

from ai_copilot.application.campaign_monitor.nodes import CampaignMonitorNodes
from ai_copilot.application.graphs.campaign_monitor import build_campaign_monitor_graph
from ai_copilot.application.use_cases.run_campaign_monitor import RunCampaignMonitorUseCase


# =============================================================================
# Stub ports
# =============================================================================


class StubJobMonitor:
    """Minimal duck-typed JobMonitorPort stub."""

    def __init__(self, jobs=None, health=None, insights=None):
        self._jobs = jobs if jobs is not None else _sample_jobs()
        self._health = health if health is not None else {}
        self._insights = insights

    async def load_recent_jobs(self, lookback_days, job_ids):
        if job_ids:
            return [j for j in self._jobs if j["id"] in job_ids]
        return list(self._jobs)

    async def get_account_health_bulk(self, account_ids):
        return {
            aid: self._health.get(
                aid,
                {"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None},
            )
            for aid in account_ids
        }

    async def get_post_insights(self, account_id, job_id):
        return self._insights


class StubFollowupCreator:
    """Minimal duck-typed FollowupCreatorPort stub."""

    def __init__(self, result=None):
        self.calls = []
        self._result = result or {"job_id": "followup-001", "status": "scheduled", "scheduled_at": None}

    async def create_followup(self, campaign_summary, operator_decision, original_job_ids):
        self.calls.append({
            "campaign_summary": campaign_summary,
            "operator_decision": operator_decision,
            "original_job_ids": original_job_ids,
        })
        return dict(self._result)


def _sample_jobs():
    return [
        {
            "id": "job-1",
            "account_id": "acc-1",
            "status": "completed",
            "campaign_tag": "spring_promo",
            "username": "user1",
            "created_at": "2025-01-01T10:00:00Z",
        },
        {
            "id": "job-2",
            "account_id": "acc-1",
            "status": "completed",
            "campaign_tag": "spring_promo",
            "username": "user1",
            "created_at": "2025-01-02T10:00:00Z",
        },
        {
            "id": "job-3",
            "account_id": "acc-2",
            "status": "failed",
            "campaign_tag": "spring_promo",
            "username": "user2",
            "created_at": "2025-01-03T10:00:00Z",
        },
    ]


def _make_use_case(jobs=None, health=None, insights=None, followup_result=None):
    stub_monitor = StubJobMonitor(jobs=jobs, health=health, insights=insights)
    stub_followup = StubFollowupCreator(result=followup_result)
    checkpointer = MemorySaver()
    uc = RunCampaignMonitorUseCase(
        job_monitor=stub_monitor,
        followup_creator=stub_followup,
        checkpointer=checkpointer,
    )
    return uc, stub_followup


async def _collect(gen) -> list[dict]:
    events = []
    async for ev in gen:
        events.append(ev)
    return events


# =============================================================================
# Test 1: Happy path — recommendation only (no interrupt)
# =============================================================================


def test_happy_path_recommendation_only():
    """With request_decision=False, workflow completes without interrupting."""
    uc, stub_followup = _make_use_case()

    events = asyncio.run(_collect(uc.run(
        thread_id="t-happy",
        request_decision=False,
        lookback_days=7,
    )))

    types = [e["type"] for e in events]
    assert "run_start" in types
    assert "run_finish" in types
    assert "approval_required" not in types

    node_updates = [event for event in events if event["type"] == "node_update"]
    assert node_updates, "expected at least one node_update event"
    assert all("data" in event for event in node_updates)
    assert all("output" not in event for event in node_updates)

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] in (
        "recommendation_only", "no_action", "followup", "boost", "pause", "reschedule", "completed"
    )

    # No followup created in recommendation-only mode
    assert len(stub_followup.calls) == 0


# =============================================================================
# Test 2: Interrupt triggered when request_decision=True
# =============================================================================


def test_interrupt_triggered_when_request_decision():
    """With request_decision=True and jobs present, workflow emits approval_required."""
    uc, _ = _make_use_case()

    events = asyncio.run(_collect(uc.run(
        thread_id="t-interrupt",
        request_decision=True,
        lookback_days=7,
    )))

    types = [e["type"] for e in events]
    assert "approval_required" in types

    approval_event = next(e for e in events if e["type"] == "approval_required")
    payload = approval_event["payload"]

    # Self-contained payload checks
    assert payload["type"] == "campaign_monitor_decision"
    assert payload["thread_id"] == "t-interrupt"
    assert "recommended_action" in payload
    assert "campaign_summary" in payload
    assert "options" in payload
    assert set(payload["options"]) == {"approve", "skip", "modify"}


# =============================================================================
# Test 3: Resume approved → create_followup_task called
# =============================================================================


def test_resume_approve_creates_followup():
    """After interrupt, resuming with decision=approve triggers create_followup_task."""
    uc, stub_followup = _make_use_case()
    thread_id = "t-resume-approve"

    async def run_both():
        # First: start and get interrupted
        await _collect(uc.run(
            thread_id=thread_id,
            request_decision=True,
        ))
        # Resume with approve
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="approve",
            parameters={"usernames": ["user1"], "caption": "Follow-up post!"},
        ))

    events = asyncio.run(run_both())

    types = [e["type"] for e in events]
    assert "run_finish" in types

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] in ("followup_created", "completed")

    # FollowupCreatorPort was called
    assert len(stub_followup.calls) == 1
    call = stub_followup.calls[0]
    assert call["operator_decision"]["decision"] == "approve"


# =============================================================================
# Test 4: Resume skip → no followup
# =============================================================================


def test_resume_skip_no_followup():
    """After interrupt, resuming with decision=skip finishes without followup."""
    uc, stub_followup = _make_use_case()
    thread_id = "t-resume-skip"

    async def run_both():
        await _collect(uc.run(thread_id=thread_id, request_decision=True))
        return await _collect(uc.resume(thread_id=thread_id, decision="skip"))

    events = asyncio.run(run_both())

    types = [e["type"] for e in events]
    assert "run_finish" in types
    assert "approval_required" not in types
    assert len(stub_followup.calls) == 0


# =============================================================================
# Test 5: No jobs → stop_reason=no_data (fail-fast)
# =============================================================================


def test_no_jobs_stops_with_no_data():
    """When no jobs are found, workflow stops immediately with stop_reason=no_data."""
    uc, stub_followup = _make_use_case(jobs=[])

    events = asyncio.run(_collect(uc.run(thread_id="t-nodata", request_decision=True)))

    types = [e["type"] for e in events]
    assert "approval_required" not in types
    assert "run_finish" in types

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] == "no_data"

    assert len(stub_followup.calls) == 0


# =============================================================================
# Test 6: Port contract — stub satisfies interface
# =============================================================================


def test_stub_ports_satisfy_interface():
    """Verify stub adapters are callable and return the expected shapes."""
    monitor = StubJobMonitor()
    followup = StubFollowupCreator()

    async def run():
        jobs = await monitor.load_recent_jobs(lookback_days=7, job_ids=[])
        assert isinstance(jobs, list)
        assert all(isinstance(j, dict) for j in jobs)

        health = await monitor.get_account_health_bulk(["acc-1"])
        assert isinstance(health, dict)
        assert "acc-1" in health

        insight = await monitor.get_post_insights("acc-1", "job-1")
        assert insight is None  # default stub returns None

        result = await followup.create_followup(
            campaign_summary={"completion_rate": 0.8},
            operator_decision={"decision": "approve", "parameters": {}},
            original_job_ids=["job-1"],
        )
        assert "job_id" in result
        assert result["status"] == "scheduled"

    asyncio.run(run())


# =============================================================================
# Test 7: Invalid followup status → explicit error path
# =============================================================================


def test_resume_approve_invalid_followup_status_routes_to_error():
    uc, stub_followup = _make_use_case(followup_result={
        "job_id": "followup-002",
        "status": "stub",
        "scheduled_at": None,
    })
    thread_id = "t-resume-invalid-status"

    async def run_both():
        await _collect(uc.run(thread_id=thread_id, request_decision=True))
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="approve",
            parameters={"usernames": ["user1"], "caption": "Follow-up"},
        ))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(stub_followup.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "unsupported status" in final_response.get("text", "")


# =============================================================================
# Test 8: Missing followup job_id → explicit error path
# =============================================================================


def test_resume_approve_missing_followup_job_id_routes_to_error():
    uc, stub_followup = _make_use_case(followup_result={
        "status": "scheduled",
        "scheduled_at": None,
    })
    thread_id = "t-resume-missing-jobid"

    async def run_both():
        await _collect(uc.run(thread_id=thread_id, request_decision=True))
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="approve",
            parameters={"usernames": ["user1"], "caption": "Follow-up"},
        ))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(stub_followup.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "missing job_id" in final_response.get("text", "")
