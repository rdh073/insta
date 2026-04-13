"""RunRiskControlUseCase — entry point for the Risk Control workflow."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from langgraph.types import Command

from ai_copilot.application.risk_control.nodes import RiskControlNodes
from ai_copilot.application.risk_control.ports import (
    AccountSignalPort,
    PolicyDecisionPort,
    ProxyRotationPort,
)
from ai_copilot.application.risk_control.state import make_initial_state
from ai_copilot.application.graphs.risk_control import build_risk_control_graph
from ai_copilot.application.use_cases.stream_event_contract import emit_node_update


class RunRiskControlUseCase:
    def __init__(
        self,
        account_signal: AccountSignalPort,
        policy_decision: PolicyDecisionPort,
        proxy_rotation: ProxyRotationPort,
        checkpointer=None,
    ):
        self.checkpointer = checkpointer
        nodes = RiskControlNodes(
            account_signal=account_signal,
            policy_decision=policy_decision,
            proxy_rotation=proxy_rotation,
        )
        self.graph = build_risk_control_graph(nodes, checkpointer=checkpointer)

    async def run(
        self,
        *,
        account_id: str,
        thread_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = make_initial_state(thread_id=thread_id, account_id=account_id)

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id}

        async for event in _stream_graph(self.graph, initial_state, config, thread_id):
            yield event

    async def resume(
        self,
        *,
        thread_id: str,
        decision: str,
        override_policy: str | None = None,
        notes: str | None = None,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        config = {"configurable": {"thread_id": thread_id}}
        resume_payload = {
            "decision": decision,
            "override_policy": override_policy,
            "notes": notes or "",
            **kwargs,
        }

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id, "resumed": True}

        async for event in _stream_graph(self.graph, Command(resume=resume_payload), config, thread_id):
            yield event


async def _stream_graph(graph, input_or_command, config, thread_id) -> AsyncIterator[dict]:
    try:
        async for chunk in graph.astream(input_or_command, config=config, stream_mode="updates"):
            for node_name, updates in chunk.items():
                if node_name == "__interrupt__":
                    payload = _extract_interrupt_payload(updates)
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
        final_policy = final_state.get("final_policy")
        recheck_risk = final_state.get("recheck_risk_level")

        parts = []
        if outcome_reason:
            parts.append(outcome_reason)
        if final_policy:
            parts.append(f"Policy: {final_policy}")
        if recheck_risk:
            parts.append(f"Post-check risk: {recheck_risk}")

        yield {
            "type": "final_response",
            "text": " | ".join(parts) or "Risk control run complete.",
            "thread_id": thread_id,
            "stop_reason": stop_reason,
            "final_policy": final_policy,
            "recheck_risk_level": recheck_risk,
        }
        yield {"type": "run_finish", "run_id": thread_id, "stop_reason": stop_reason}

    except Exception as exc:
        exc_type = type(exc).__name__
        if "GraphInterrupt" in exc_type or "Interrupt" in exc_type:
            payload = _extract_interrupt_payload(getattr(exc, "args", (exc,)))
            yield {"type": "approval_required", "thread_id": thread_id, "payload": payload}
            return
        yield {"type": "run_error", "run_id": thread_id, "message": str(exc)}


def _extract_interrupt_payload(data) -> dict:
    if isinstance(data, (list, tuple)) and data:
        item = data[0]
        return item.value if hasattr(item, "value") else item
    return data if isinstance(data, dict) else {}
