"""RunContentPipelineUseCase — entry point for the Content Pipeline workflow."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from langgraph.types import Command

from ai_copilot.application.content_pipeline.nodes import ContentPipelineNodes
from ai_copilot.application.content_pipeline.ports import (
    CaptionGeneratorPort,
    CaptionValidatorPort,
    PostSchedulerPort,
)
from ai_copilot.application.content_pipeline.state import make_initial_state
from ai_copilot.application.graphs.content_pipeline import build_content_pipeline_graph
from ai_copilot.application.use_cases.stream_event_contract import emit_node_update


class RunContentPipelineUseCase:
    def __init__(
        self,
        caption_generator: CaptionGeneratorPort,
        caption_validator: CaptionValidatorPort,
        post_scheduler: PostSchedulerPort,
        account_usecases=None,
        checkpointer=None,
    ):
        nodes = ContentPipelineNodes(
            caption_generator=caption_generator,
            caption_validator=caption_validator,
            post_scheduler=post_scheduler,
            account_usecases=account_usecases,
        )
        self.graph = build_content_pipeline_graph(nodes, checkpointer=checkpointer)

    async def run(
        self,
        *,
        campaign_brief: str,
        thread_id: str | None = None,
        media_refs: list[str] | None = None,
        target_usernames: list[str] | None = None,
        scheduled_at: str | None = None,
        max_revisions: int = 3,
    ) -> AsyncIterator[dict[str, Any]]:
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = make_initial_state(
            thread_id=thread_id,
            campaign_brief=campaign_brief,
            media_refs=media_refs,
            target_usernames=target_usernames,
            scheduled_at=scheduled_at,
            max_revisions=max_revisions,
        )

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id}
        async for event in _stream_graph(self.graph, initial_state, config, thread_id):
            yield event

    async def resume(
        self,
        *,
        thread_id: str,
        decision: str,
        edited_caption: str | None = None,
        reason: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        config = {"configurable": {"thread_id": thread_id}}
        resume_payload = {
            "decision": decision,
            "edited_caption": edited_caption,
            "reason": reason or "",
        }

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id, "resumed": True}
        async for event in _stream_graph(self.graph, Command(resume=resume_payload), config, thread_id):
            yield event


async def _stream_graph(graph, input_or_command, config, thread_id) -> AsyncIterator[dict]:
    try:
        async for chunk in graph.astream(input_or_command, config=config, stream_mode="updates"):
            for node_name, updates in chunk.items():
                if node_name == "__interrupt__":
                    payload = _extract_interrupt(updates)
                    yield {"type": "approval_required", "thread_id": thread_id, "payload": payload}
                    return
                yield emit_node_update(node_name, updates)

        final_state = {}
        try:
            snap = await graph.aget_state(config)
            if snap:
                final_state = snap.values or {}
        except Exception:
            pass

        stop_reason = final_state.get("stop_reason", "completed")
        outcome_reason = final_state.get("outcome_reason", "")
        job_id = final_state.get("job_id")

        yield {
            "type": "final_response",
            "text": outcome_reason or "Content pipeline complete.",
            "thread_id": thread_id,
            "stop_reason": stop_reason,
            "job_id": job_id,
            "caption": final_state.get("caption"),
        }
        yield {"type": "run_finish", "run_id": thread_id, "stop_reason": stop_reason}

    except Exception as exc:
        exc_type = type(exc).__name__
        if "GraphInterrupt" in exc_type or "Interrupt" in exc_type:
            payload = _extract_interrupt(getattr(exc, "args", (exc,)))
            yield {"type": "approval_required", "thread_id": thread_id, "payload": payload}
            return
        yield {"type": "run_error", "run_id": thread_id, "message": str(exc)}


def _extract_interrupt(data) -> dict:
    if isinstance(data, (list, tuple)) and data:
        item = data[0]
        return item.value if hasattr(item, "value") else item
    return data if isinstance(data, dict) else {}
