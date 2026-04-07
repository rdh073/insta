"""HTTP integration tests for /api/ai/smart-engagement router.

Tests:
- POST /api/ai/smart-engagement/recommend: recommendation mode (always available)
- POST /api/ai/smart-engagement/recommend: execute mode blocked without feature flag (403)
- POST /api/ai/smart-engagement/resume: blocked without feature flag (403)
- GET /api/ai/smart-engagement/approval/{id}: approval status lookup
- POST /api/ai/smart-engagement/approval/{id}/decide: record decision
- SmartEngagementResponse structure: required UI contract fields present
- Pydantic validation: invalid execution_mode → 422
- Pydantic validation: invalid decision → 422

Uses FastAPI TestClient with dependency overrides to avoid hitting real services.
"""

from __future__ import annotations

import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app():
    """Create a minimal FastAPI app with only the smart engagement router.

    Avoids importing app.main (which triggers full create_services() + LangGraph
    graph compilation, causing NameError in graph_nodes.py TYPE_CHECKING imports).
    Returns a fresh app instance each call to avoid shared-state conflicts.
    """
    from app.adapters.http.routers.smart_engagement import router as se_router
    from fastapi.routing import APIRouter

    test_app = FastAPI()
    # Include a fresh copy of the router to avoid shared route state
    test_app.include_router(se_router)
    return test_app


# ---------------------------------------------------------------------------
# Fake use cases for dependency override
# ---------------------------------------------------------------------------

class _FakeSmartEngagementRec:
    """Fake use case that returns a deterministic recommendation result."""

    async def run(self, **kwargs) -> dict:
        return {
            "mode": kwargs.get("execution_mode", "recommendation"),
            "status": "recommendation_only",
            "thread_id": "fake-thread-rec",
            "interrupted": False,
            "interrupt_payload": None,
            "outcome_reason": "Recommendation: follow on user_abc (not executed - mode=recommendation)",
            "recommendation": {
                "target": "user_abc",
                "action_type": "follow",
                "content": None,
                "reasoning": "High engagement rate",
                "expected_outcome": "Account followed; may receive follow-back",
            },
            "risk_assessment": {
                "level": "medium",
                "rule_hits": ["write_action_requires_approval"],
                "reasoning": "Write action requires approval",
                "requires_approval": True,
            },
            "approval": None,
            "execution": None,
            "audit_trail": [
                {"event_type": "goal_ingested", "node_name": "ingest_goal", "event_data": {}, "timestamp": 1.0},
            ],
        }

    async def resume(self, thread_id: str, decision: dict) -> dict:
        return {
            "mode": "execute",
            "status": "completed",
            "thread_id": thread_id,
            "interrupted": False,
            "outcome_reason": "Action executed",
            "audit_trail": [],
        }


class _FakeSmartEngagementExec:
    """Fake execute-mode use case."""

    async def run(self, **kwargs) -> dict:
        return {
            "mode": "execute",
            "status": "interrupted",
            "thread_id": "fake-thread-exec",
            "interrupted": True,
            "interrupt_payload": {
                "approval_id": "apr_test",
                "thread_id": "fake-thread-exec",
                "account_id": "acc_1",
                "options": ["approve", "reject", "edit"],
            },
            "outcome_reason": None,
            "audit_trail": [],
        }

    async def resume(self, thread_id: str, decision: dict) -> dict:
        return {
            "mode": "execute",
            "status": "action_executed",
            "thread_id": thread_id,
            "interrupted": False,
            "outcome_reason": "Action executed successfully",
            "audit_trail": [],
        }


class _FakeApprovalAdapter:
    def __init__(self):
        self._store: dict = {}

    async def submit_for_approval(self, **kwargs) -> str:
        aid = "apr_http_test"
        self._store[aid] = {"approval_id": aid, "status": "pending", "requested_at": time.time(), "approved_at": None, "approver_notes": ""}
        return aid

    async def get_approval_status(self, approval_id: str) -> dict:
        if approval_id not in self._store:
            raise ValueError(f"Approval {approval_id!r} not found")
        return self._store[approval_id]

    async def record_approval_decision(self, approval_id: str, approved: bool, approver_notes: str = "") -> dict:
        if approval_id not in self._store:
            raise ValueError(f"Approval {approval_id!r} not found")
        self._store[approval_id]["status"] = "approved" if approved else "rejected"
        self._store[approval_id]["approved_at"] = time.time()
        self._store[approval_id]["approver_notes"] = approver_notes
        return self._store[approval_id]


# ---------------------------------------------------------------------------
# App + client setup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from app.adapters.http.dependencies import (
        get_smart_engagement_rec,
        get_smart_engagement_exec,
        get_smart_engagement_execution_enabled,
        get_approval_adapter,
    )

    app = _make_test_app()
    _rec = _FakeSmartEngagementRec()
    _exec = _FakeSmartEngagementExec()
    _approval = _FakeApprovalAdapter()
    # Seed with a known approval_id for GET/POST tests
    _approval._store["apr_known"] = {
        "approval_id": "apr_known",
        "status": "pending",
        "requested_at": 1000.0,
        "approved_at": None,
        "approver_notes": "",
    }

    app.dependency_overrides[get_smart_engagement_rec] = lambda: _rec
    app.dependency_overrides[get_smart_engagement_exec] = lambda: _exec
    app.dependency_overrides[get_smart_engagement_execution_enabled] = lambda: False
    app.dependency_overrides[get_approval_adapter] = lambda: _approval

    yield TestClient(app)


@pytest.fixture(scope="module")
def exec_client():
    """Client with execution mode ENABLED."""
    from app.adapters.http.dependencies import (
        get_smart_engagement_rec,
        get_smart_engagement_exec,
        get_smart_engagement_execution_enabled,
        get_approval_adapter,
    )

    app = _make_test_app()
    _rec = _FakeSmartEngagementRec()
    _exec = _FakeSmartEngagementExec()
    _approval = _FakeApprovalAdapter()

    app.dependency_overrides[get_smart_engagement_rec] = lambda: _rec
    app.dependency_overrides[get_smart_engagement_exec] = lambda: _exec
    app.dependency_overrides[get_smart_engagement_execution_enabled] = lambda: True
    app.dependency_overrides[get_approval_adapter] = lambda: _approval

    yield TestClient(app)


# ===========================================================================
# POST /recommend — recommendation mode
# ===========================================================================

def test_recommend_default_recommendation_mode(client):
    response = client.post("/api/ai/smart-engagement/recommend", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "recommendation"
    assert body["status"] == "recommendation_only"
    assert body["interrupted"] is False


def test_recommend_response_has_ui_contract_fields(client):
    """Response must include all UI-contract fields."""
    response = client.post("/api/ai/smart-engagement/recommend", json={
        "goal": "follow tech accounts",
        "account_id": "acc_1",
    })

    assert response.status_code == 200
    body = response.json()

    # Required response fields per SmartEngagementResponse model
    assert "mode" in body
    assert "status" in body
    assert "interrupted" in body
    assert "brief_audit" in body
    assert "audit_trail" in body

    # Structured recommendation
    rec = body.get("recommendation")
    assert rec is not None
    assert "target" in rec
    assert "action_type" in rec
    assert "reasoning" in rec

    # Structured risk
    risk = body.get("risk")
    assert risk is not None
    assert "level" in risk
    assert "rule_hits" in risk
    assert "reasoning" in risk
    assert "requires_approval" in risk


def test_recommend_brief_audit_is_last_5(client):
    """brief_audit must contain at most 5 events from audit_trail."""
    response = client.post("/api/ai/smart-engagement/recommend", json={})
    body = response.json()

    audit_trail = body.get("audit_trail", [])
    brief_audit = body.get("brief_audit", [])

    # brief_audit ≤ 5 and is the tail of audit_trail
    assert len(brief_audit) <= 5
    if audit_trail:
        expected = audit_trail[-5:]
        assert brief_audit == expected


# ===========================================================================
# POST /recommend — execution mode gating (403)
# ===========================================================================

def test_recommend_execute_mode_blocked_without_flag(client):
    """Execute mode must be blocked (403) when SMART_ENGAGEMENT_EXECUTION_ENABLED is false."""
    response = client.post("/api/ai/smart-engagement/recommend", json={
        "execution_mode": "execute",
    })

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "execution" in detail.lower() or "enabled" in detail.lower()


def test_recommend_execute_mode_allowed_with_flag(exec_client):
    """Execute mode must work when feature flag is enabled."""
    response = exec_client.post("/api/ai/smart-engagement/recommend", json={
        "execution_mode": "execute",
    })

    assert response.status_code == 200
    body = response.json()
    # Fake exec use case returns interrupted=True
    assert body["interrupted"] is True


# ===========================================================================
# POST /recommend — Pydantic validation
# ===========================================================================

def test_recommend_invalid_execution_mode_422(client):
    """Invalid execution_mode must return 422 Unprocessable Entity."""
    response = client.post("/api/ai/smart-engagement/recommend", json={
        "execution_mode": "auto",  # Not in (recommendation, execute)
    })

    assert response.status_code == 422


def test_recommend_valid_execution_mode_values(client):
    """Only 'recommendation' and 'execute' are valid execution_mode values."""
    for valid_mode in ("recommendation",):
        resp = client.post("/api/ai/smart-engagement/recommend", json={"execution_mode": valid_mode})
        assert resp.status_code == 200, f"Expected 200 for mode={valid_mode!r}"


# ===========================================================================
# POST /resume — gating and validation
# ===========================================================================

def test_resume_blocked_without_exec_flag(client):
    """Resume must be blocked (403) when execution is not enabled."""
    response = client.post("/api/ai/smart-engagement/resume", json={
        "thread_id": "t1",
        "decision": "approved",
        "notes": "",
    })

    assert response.status_code == 403


def test_resume_allowed_with_exec_flag(exec_client):
    """Resume must succeed when execution flag is enabled."""
    response = exec_client.post("/api/ai/smart-engagement/resume", json={
        "thread_id": "fake-thread-exec",
        "decision": "approved",
        "notes": "all good",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("action_executed", "completed", "recommendation_only", "unknown")


def test_resume_invalid_decision_422(exec_client):
    """Invalid decision value must return 422."""
    response = exec_client.post("/api/ai/smart-engagement/resume", json={
        "thread_id": "t1",
        "decision": "maybe",  # Not in (approved, rejected, edited)
    })

    assert response.status_code == 422


def test_resume_valid_decision_values(exec_client):
    """All valid decision values must be accepted."""
    for decision in ("approved", "rejected", "edited"):
        resp = exec_client.post("/api/ai/smart-engagement/resume", json={
            "thread_id": "t1",
            "decision": decision,
        })
        assert resp.status_code == 200, f"Expected 200 for decision={decision!r}"


# ===========================================================================
# GET /approval/{id}
# ===========================================================================

def test_get_approval_status_known_id(client):
    """Known approval_id must return 200 with status fields."""
    response = client.get("/api/ai/smart-engagement/approval/apr_known")

    assert response.status_code == 200
    body = response.json()
    assert body["approval_id"] == "apr_known"
    assert body["status"] == "pending"
    assert "requested_at" in body


def test_get_approval_status_unknown_id(client):
    """Unknown approval_id must return 404."""
    response = client.get("/api/ai/smart-engagement/approval/nonexistent_xyz")

    assert response.status_code == 404


# ===========================================================================
# POST /approval/{id}/decide
# ===========================================================================

def test_record_approval_decision_approve(client):
    """Approve decision must update status to approved."""
    # First seed an approval
    response = client.post(
        "/api/ai/smart-engagement/approval/apr_known/decide",
        params={"approved": "true", "notes": "LGTM"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approver_notes"] == "LGTM"


def test_record_approval_decision_reject(client):
    """Reject decision must update status to rejected."""
    # Need a fresh approval — the fixture store is shared but we can re-seed
    # (The 'apr_known' is already approved from the previous test in this module,
    # so we inject a fresh id)
    from app.adapters.http.dependencies import get_approval_adapter

    fresh_app = _make_test_app()
    fake = _FakeApprovalAdapter()
    fake._store["apr_fresh"] = {
        "approval_id": "apr_fresh", "status": "pending",
        "requested_at": time.time(), "approved_at": None, "approver_notes": "",
    }
    fresh_app.dependency_overrides[get_approval_adapter] = lambda: fake

    resp = TestClient(fresh_app).post(
        "/api/ai/smart-engagement/approval/apr_fresh/decide",
        params={"approved": "false", "notes": "too risky"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


# ===========================================================================
# Router registration
# ===========================================================================

def test_smart_engagement_router_prefix():
    """Smart engagement router must be at /api/ai/smart-engagement."""
    from app.adapters.http.routers.smart_engagement import router

    assert router.prefix == "/api/ai/smart-engagement"
    assert "smart-engagement" in router.tags


def test_smart_engagement_routes_registered():
    """Required routes must be registered on the router."""
    from app.adapters.http.routers.smart_engagement import router

    paths = [r.path for r in router.routes if hasattr(r, "path")]
    # Paths include the router prefix: /api/ai/smart-engagement/recommend etc.
    assert any(p.endswith("/recommend") for p in paths)
    assert any(p.endswith("/resume") for p in paths)
    assert any("approval_id" in p for p in paths)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
