"""RunAccountRecoveryUseCase — entry point for the Account Recovery workflow."""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from langgraph.types import Command

from ai_copilot.application.account_recovery.nodes import AccountRecoveryNodes
from ai_copilot.application.account_recovery.ports import (
    AccountDiagnosticsPort,
    RecoveryExecutorPort,
)
from ai_copilot.application.account_recovery.state import make_initial_state
from ai_copilot.application.graphs.account_recovery import build_account_recovery_graph
from ai_copilot.application.use_cases.stream_event_contract import emit_node_update


class RunAccountRecoveryUseCase:
    def __init__(
        self,
        diagnostics: AccountDiagnosticsPort,
        executor: RecoveryExecutorPort,
        checkpointer=None,
    ):
        nodes = AccountRecoveryNodes(diagnostics=diagnostics, executor=executor)
        self.graph = build_account_recovery_graph(nodes, checkpointer=checkpointer)

    async def run(
        self,
        *,
        account_id: str,
        username: str,
        thread_id: str | None = None,
        max_recovery_attempts: int = 3,
    ) -> AsyncIterator[dict[str, Any]]:
        thread_id = thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = make_initial_state(
            thread_id=thread_id,
            account_id=account_id,
            username=username,
            max_recovery_attempts=max_recovery_attempts,
        )

        yield {"type": "run_start", "run_id": thread_id, "thread_id": thread_id}
        async for event in _stream_graph(self.graph, initial_state, config, thread_id):
            yield event

    async def resume(
        self,
        *,
        thread_id: str,
        decision: str,
        two_fa_code: str | None = None,
        proxy: str | None = None,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        config = {"configurable": {"thread_id": thread_id}}
        resume_payload = {
            "decision": decision,
            "two_fa_code": two_fa_code,
            "proxy": proxy,
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
        result = final_state.get("result")

        yield {
            "type": "final_response",
            "text": outcome_reason or "Account recovery complete.",
            "thread_id": thread_id,
            "stop_reason": stop_reason,
            "result": result,
            "recovery_successful": final_state.get("recovery_successful", False),
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
