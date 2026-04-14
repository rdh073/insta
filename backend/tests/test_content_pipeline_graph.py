"""Tests for Content Pipeline LangGraph workflow.

Test strategy:
1. Happy path — caption passes validation, approved → scheduled
2. Revision loop — first validation fails, second passes
3. Max revisions reached → stop_reason=validation_failed (loop guard)
4. Operator approval interrupt with correct payload shape
5. Resume rejected → stop_reason=rejected, no scheduling
6. Resume edited → schedule_draft called with edited caption
"""

from __future__ import annotations

import asyncio
from langgraph.checkpoint.memory import MemorySaver

from ai_copilot.application.use_cases.run_content_pipeline import RunContentPipelineUseCase


# =============================================================================
# Stub ports
# =============================================================================


class StubCaptionGenerator:
    def __init__(self, captions=None):
        # captions: list of captions to return per attempt (cycles)
        self._captions = captions or ["Great post! #instagram #content #brand"]
        self.call_count = 0

    async def generate(self, campaign_brief, media_refs, previous_feedback=None, attempt=1):
        caption = self._captions[min(self.call_count, len(self._captions) - 1)]
        self.call_count += 1
        return caption


class StubCaptionValidator:
    def __init__(self, results=None):
        # results: list of {passed, errors, feedback} per call
        self._results = results or [{"passed": True, "errors": [], "feedback": "Good"}]
        self.call_count = 0

    async def validate(self, caption, campaign_brief):
        result = self._results[min(self.call_count, len(self._results) - 1)]
        self.call_count += 1
        return dict(result)


class StubPostScheduler:
    def __init__(self, result=None):
        self.calls = []
        self._result = result or {"job_id": "job-content-001", "status": "scheduled", "scheduled_at": None}

    async def schedule(self, usernames, caption, media_refs, scheduled_at=None):
        self.calls.append({"usernames": usernames, "caption": caption, "scheduled_at": scheduled_at})
        result = dict(self._result)
        result["scheduled_at"] = scheduled_at
        return result


class StubPostSchedulerRaises(StubPostScheduler):
    def __init__(self, exc: Exception | None = None):
        super().__init__()
        self._exc = exc or RuntimeError("scheduler boom")

    async def schedule(self, usernames, caption, media_refs, scheduled_at=None):
        self.calls.append({"usernames": usernames, "caption": caption, "scheduled_at": scheduled_at})
        raise self._exc


def _make_uc(generator=None, validator=None, scheduler=None, usernames=None):
    gen = generator or StubCaptionGenerator()
    val = validator or StubCaptionValidator()
    sched = scheduler or StubPostScheduler()
    uc = RunContentPipelineUseCase(
        caption_generator=gen,
        caption_validator=val,
        post_scheduler=sched,
        account_usecases=None,
        checkpointer=MemorySaver(),
    )
    return uc, gen, val, sched


async def _collect(gen):
    return [ev async for ev in gen]


# =============================================================================
# Test 1: Happy path — approved and scheduled
# =============================================================================


def test_happy_path_approved_scheduled():
    sched = StubPostScheduler()
    uc, _, _, sched = _make_uc(scheduler=sched)

    # Run up to approval interrupt
    events = asyncio.run(_collect(uc.run(
        campaign_brief="Summer sale campaign",
        thread_id="t-happy",
        target_usernames=["user1"],
    )))
    types = [e["type"] for e in events]
    assert "approval_required" in types

    node_updates = [event for event in events if event["type"] == "node_update"]
    assert node_updates, "expected at least one node_update event"
    assert all("data" in event for event in node_updates)
    assert all("output" not in event for event in node_updates)

    # Resume approved
    async def resume():
        return await _collect(uc.resume(thread_id="t-happy", decision="approved"))

    resume_events = asyncio.run(resume())
    resume_types = [e["type"] for e in resume_events]
    assert "run_finish" in resume_types
    finish = next(e for e in resume_events if e["type"] == "run_finish")
    assert finish["stop_reason"] == "scheduled"
    assert len(sched.calls) == 1


# =============================================================================
# Test 2: Revision loop — first fails, second passes
# =============================================================================


def test_revision_loop_second_attempt_passes():
    validator = StubCaptionValidator(results=[
        {"passed": False, "errors": ["Too short"], "feedback": "Make it longer"},
        {"passed": True, "errors": [], "feedback": "Good"},
    ])
    uc, gen, _, _ = _make_uc(
        generator=StubCaptionGenerator(captions=["Short", "A longer and better caption #brand #instagram"]),
        validator=validator,
    )

    events = asyncio.run(_collect(uc.run(
        campaign_brief="Product launch",
        thread_id="t-revision",
        target_usernames=["user2"],
    )))
    types = [e["type"] for e in events]

    # Should reach approval (validation passed on 2nd attempt)
    assert "approval_required" in types
    # Generator was called twice
    assert gen.call_count == 2


# =============================================================================
# Test 3: Max revisions reached → validation_failed (loop guard)
# =============================================================================


def test_max_revisions_loop_guard():
    validator = StubCaptionValidator(results=[
        {"passed": False, "errors": ["Bad"], "feedback": "Try again"},
    ] * 5)
    uc, gen, _, _ = _make_uc(validator=validator)

    events = asyncio.run(_collect(uc.run(
        campaign_brief="Brief",
        thread_id="t-maxrev",
        target_usernames=["user3"],
        max_revisions=2,
    )))
    types = [e["type"] for e in events]

    assert "run_finish" in types
    assert "approval_required" not in types

    finish = next(e for e in events if e["type"] == "run_finish")
    assert finish["stop_reason"] == "validation_failed"

    # Generator called at most max_revisions times
    assert gen.call_count <= 2


# =============================================================================
# Test 4: Approval interrupt payload shape
# =============================================================================


def test_approval_interrupt_payload_shape():
    uc, _, _, _ = _make_uc()
    events = asyncio.run(_collect(uc.run(
        campaign_brief="Test campaign",
        thread_id="t-payload",
        target_usernames=["user4"],
        media_refs=["img1.jpg"],
    )))

    approval = next((e for e in events if e["type"] == "approval_required"), None)
    assert approval is not None

    payload = approval["payload"]
    assert payload["type"] == "content_pipeline_approval"
    assert payload["thread_id"] == "t-payload"
    assert "caption" in payload
    assert "campaign_brief" in payload
    assert set(payload["options"]) == {"approved", "rejected", "edited"}


# =============================================================================
# Test 5: Resume rejected → no scheduling
# =============================================================================


def test_resume_rejected_no_schedule():
    sched = StubPostScheduler()
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-rejected"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(thread_id=thread_id, decision="rejected", reason="Not good enough"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "rejected"
    assert len(sched.calls) == 0


# =============================================================================
# Test 6: Resume edited → schedule with edited caption
# =============================================================================


def test_resume_edited_schedules_with_edited_caption():
    sched = StubPostScheduler()
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-edited"
    edited_caption = "My custom edited caption #custom #brand"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(
            thread_id=thread_id,
            decision="edited",
            edited_caption=edited_caption,
        ))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "scheduled"
    assert len(sched.calls) == 1
    assert sched.calls[0]["caption"] == edited_caption


# =============================================================================
# Test 7: Invalid scheduler status → explicit error path
# =============================================================================


def test_resume_approved_invalid_schedule_status_routes_to_error():
    sched = StubPostScheduler(result={"job_id": "job-content-002", "status": "stub", "scheduled_at": None})
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-invalid-status"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(thread_id=thread_id, decision="approved"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(sched.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "unsupported status" in final_response.get("text", "")


# =============================================================================
# Test 8: Missing job_id → explicit error path
# =============================================================================


def test_resume_approved_missing_job_id_routes_to_error():
    sched = StubPostScheduler(result={"status": "scheduled", "scheduled_at": None})
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-missing-jobid"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(thread_id=thread_id, decision="approved"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(sched.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "missing job_id" in final_response.get("text", "")


# =============================================================================
# Test 9: Blank job_id → explicit error path
# =============================================================================


def test_resume_approved_blank_job_id_routes_to_error():
    sched = StubPostScheduler(result={"job_id": "   ", "status": "scheduled", "scheduled_at": None})
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-blank-jobid"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(thread_id=thread_id, decision="approved"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(sched.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "missing job_id" in final_response.get("text", "")


# =============================================================================
# Test 10: Scheduler exception → explicit error path
# =============================================================================


def test_resume_approved_scheduler_exception_routes_to_error():
    sched = StubPostSchedulerRaises(exc=RuntimeError("scheduler crashed"))
    uc, _, _, _ = _make_uc(scheduler=sched)
    thread_id = "t-scheduler-exc"

    async def run_both():
        await _collect(uc.run(campaign_brief="Brief", thread_id=thread_id, target_usernames=["u1"]))
        return await _collect(uc.resume(thread_id=thread_id, decision="approved"))

    events = asyncio.run(run_both())
    finish = next((e for e in events if e["type"] == "run_finish"), None)
    assert finish is not None
    assert finish["stop_reason"] == "error"
    assert len(sched.calls) == 1

    final_response = next((e for e in events if e["type"] == "final_response"), {})
    assert "Scheduling failed: scheduler crashed" in final_response.get("text", "")
