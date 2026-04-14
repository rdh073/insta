from __future__ import annotations

import asyncio

import pytest

from ai_copilot.adapters.followup_creator_adapter import FollowupCreatorAdapter
from ai_copilot.adapters.post_job_scheduler_contract import StrictPostJobSchedulerPort
from ai_copilot.adapters.post_scheduler_adapter import PostSchedulerAdapter


class SupportedPostJobUseCases:
    def __init__(self, result: dict | None = None) -> None:
        self.calls: list[dict] = []
        self._result = result or {"jobId": "job-001", "status": "scheduled"}

    def create_scheduled_post_for_usernames(
        self,
        usernames: list[str],
        caption: str,
        scheduled_at: str | None = None,
    ) -> dict:
        self.calls.append({
            "usernames": usernames,
            "caption": caption,
            "scheduled_at": scheduled_at,
        })
        payload = dict(self._result)
        payload.setdefault("scheduled_at", scheduled_at)
        return payload


class UnsupportedPostJobUseCases:
    pass


def test_post_scheduler_adapter_supported_capability_path():
    postjobs = SupportedPostJobUseCases(result={"jobId": "job-abc", "status": "QUEUED"})
    adapter = PostSchedulerAdapter(postjob_usecases=StrictPostJobSchedulerPort(postjobs))

    result = asyncio.run(adapter.schedule(
        usernames=["user1"],
        caption="Caption",
        media_refs=["media.jpg"],
        scheduled_at="2026-04-15T10:00:00Z",
    ))

    assert result == {
        "job_id": "job-abc",
        "status": "queued",
        "scheduled_at": "2026-04-15T10:00:00Z",
    }
    assert postjobs.calls == [{
        "usernames": ["user1"],
        "caption": "Caption",
        "scheduled_at": "2026-04-15T10:00:00Z",
    }]


def test_followup_creator_adapter_supported_capability_path():
    postjobs = SupportedPostJobUseCases(result={"job_id": "job-followup", "status": "pending"})
    adapter = FollowupCreatorAdapter(postjob_usecases=StrictPostJobSchedulerPort(postjobs))

    result = asyncio.run(adapter.create_followup(
        campaign_summary={"completion_rate": 0.55},
        operator_decision={
            "decision": "approve",
            "parameters": {
                "usernames": ["user2"],
                "caption": "Follow up",
                "scheduled_at": "2026-04-16T08:30:00Z",
            },
        },
        original_job_ids=["job-1", "job-2"],
    ))

    assert result == {
        "job_id": "job-followup",
        "status": "pending",
        "scheduled_at": "2026-04-16T08:30:00Z",
    }
    assert postjobs.calls == [{
        "usernames": ["user2"],
        "caption": "Follow up",
        "scheduled_at": "2026-04-16T08:30:00Z",
    }]


def test_post_scheduler_adapter_unsupported_capability_path():
    adapter = PostSchedulerAdapter(
        postjob_usecases=StrictPostJobSchedulerPort(UnsupportedPostJobUseCases())
    )

    with pytest.raises(
        RuntimeError,
        match="Missing required post-job capability: 'create_scheduled_post_for_usernames",
    ):
        asyncio.run(adapter.schedule(
            usernames=["user1"],
            caption="Caption",
            media_refs=["media.jpg"],
            scheduled_at=None,
        ))


def test_followup_creator_adapter_unsupported_capability_path():
    adapter = FollowupCreatorAdapter(
        postjob_usecases=StrictPostJobSchedulerPort(UnsupportedPostJobUseCases())
    )

    with pytest.raises(
        RuntimeError,
        match="Missing required post-job capability: 'create_scheduled_post_for_usernames",
    ):
        asyncio.run(adapter.create_followup(
            campaign_summary={"completion_rate": 0.25},
            operator_decision={"decision": "approve", "parameters": {"usernames": ["u1"]}},
            original_job_ids=["job-old"],
        ))
