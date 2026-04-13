"""RunCampaignMonitorUseCase — entry point for the Campaign Monitor workflow.

Owns: state initialization, thread_id generation, interrupt detection, result formatting.
Delegates all business logic to the graph.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from langgraph.types import Command

from ai_copilot.application.campaign_monitor.nodes import CampaignMonitorNodes
from ai_copilot.application.campaign_monitor.ports import (
    FollowupCreatorPort,
    JobMonitorPort,
)
from ai_copilot.application.campaign_monitor.state import make_initial_state
from ai_copilot.application.graphs.campaign_monitor import build_campaign_monitor_graph
from ai_copilot.application.use_cases.stream_event_contract import emit_node_update


class RunCampaignMonitorUseCase:
    """Orchestrates the Campaign Monitor LangGraph workflow.

    Exposes run() and resume() that yield SSE-compatible event dicts.
    """

    def __init__(
        self,
        job_monitor: JobMonitorPort,
        followup_creator: FollowupCreatorPort,
        checkpointer=None,
    ):
        self.job_monitor = job_monitor
        self.followup_creator = followup_creator
        self.checkpointer = checkpointer

        nodes = CampaignMonitorNodes(
            job_monitor=job_monitor,
            followup_creator=followup_creator,
        )
        self.graph = build_campaign_monitor_graph(nodes, checkpointer=checkpointer)

    async def run(
        self,
        *,
        thread_id: str | None = None,
        job_ids: list[str] | None = None,
        lookback_days: int = 7,
        request_decision: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Start a new campaign monitor run.

        Yields SSE event dicts:
          run_start, node_update, approval_required, final_response, run_finish, run_error
        """
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = make_initial_state(
            thread_id=thread_id,
            job_ids=job_ids,
            lookback_days=lookback_days,
            request_decision=request_decision,
        )

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id}

        async for event in self._stream_graph(self.graph, initial_state, config, thread_id):
            yield event

    async def resume(
        self,
        *,
        thread_id: str,
        decision: str,
        parameters: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resume a workflow suspended at the operator decision interrupt.

        Args:
            thread_id: Thread ID of the suspended run.
            decision: "approve" | "skip" | "modify"
            parameters: Optional extra parameters for "modify" decision.
        """
        config = {"configurable": {"thread_id": thread_id}}
        resume_payload = {"decision": decision, "parameters": parameters or {}}

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id, "resumed": True}

        async for event in self._stream_graph(
            self.graph,
            Command(resume=resume_payload),
            config,
            thread_id,
        ):
            yield event

    @staticmethod
    async def _stream_graph(
        graph,
        input_or_command,
        config: dict,
        thread_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream graph events, detecting interrupts and formatting SSE events."""
        try:
            async for chunk in graph.astream(input_or_command, config=config, stream_mode="updates"):
                # Each chunk is {node_name: state_updates}
                for node_name, updates in chunk.items():
                    if node_name == "__interrupt__":
                        # Interrupt: emit approval_required and stop
                        interrupt_data = updates
                        payload = (
                            interrupt_data[0].value
                            if isinstance(interrupt_data, (list, tuple)) and interrupt_data
                            else interrupt_data
                        )
                        yield {
                            "type": "approval_required",
                            "thread_id": thread_id,
                            "payload": payload,
                        }
                        return

                    yield emit_node_update(node_name, updates)

            # Graph completed normally — emit final response
            # Read final state from checkpointer if available
            final_state = {}
            try:
                final_state_snapshot = await graph.aget_state(config)
                if final_state_snapshot:
                    final_state = final_state_snapshot.values or {}
            except Exception:
                pass

            stop_reason = final_state.get("stop_reason", "completed")
            outcome_reason = final_state.get("outcome_reason", "")
            recommended_action = final_state.get("recommended_action")
            campaign_summary = final_state.get("campaign_summary")
            followup_job_id = final_state.get("followup_job_id")

            response_parts = []
            if outcome_reason:
                response_parts.append(outcome_reason)
            if recommended_action and stop_reason not in ("followup_created",):
                response_parts.append(f"Recommended action: {recommended_action}")
            if followup_job_id:
                response_parts.append(f"Followup job created: {followup_job_id}")

            yield {
                "type": "final_response",
                "text": " | ".join(response_parts) if response_parts else "Campaign monitor run complete.",
                "thread_id": thread_id,
                "stop_reason": stop_reason,
                "recommended_action": recommended_action,
                "campaign_summary": campaign_summary,
                "followup_job_id": followup_job_id,
            }
            yield {
                "type": "run_finish",
                "run_id": thread_id,
                "stop_reason": stop_reason,
            }

        except Exception as exc:
            # Check for GraphInterrupt raised by older LangGraph versions
            exc_type = type(exc).__name__
            if "GraphInterrupt" in exc_type or "Interrupt" in exc_type:
                args = getattr(exc, "args", ())
                payload = {}
                if args:
                    first = args[0]
                    if isinstance(first, (list, tuple)) and first:
                        item = first[0]
                        payload = item.value if hasattr(item, "value") else item
                    else:
                        payload = first
                yield {
                    "type": "approval_required",
                    "thread_id": thread_id,
                    "payload": payload,
                }
                return

            yield {
                "type": "run_error",
                "run_id": thread_id,
                "message": str(exc),
            }
