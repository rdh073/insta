"""Run operator copilot use case — entrypoint for run and resume.

Owns:
- State initialisation for new runs
- graph.stream() / graph.astream() invocation with correct thread config
- Interrupt detection and suspension payload extraction
- Resume with operator approval decision
- SSE event formatting for HTTP transport

Does NOT own:
- Policy classification (ToolPolicyRegistry)
- Approval logic (ApprovalPort)
- LLM interaction (LLMGatewayPort)
- Tool execution (ToolExecutorPort)
- Audit (AuditLogPort)

Dependency direction: api → this use case → graph → ports ← adapters
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

from langgraph.types import Command

from ai_copilot.application.state import OperatorCopilotState, make_initial_state
from ai_copilot.application.graphs.operator_copilot import (
    OperatorCopilotNodes,
    build_operator_copilot_graph,
)
from ai_copilot.application.ports import (
    CopilotMemoryPort,
    LLMGatewayPort,
    ToolExecutorPort,
    ApprovalPort,
    AuditLogPort,
    CheckpointFactoryPort,
)
from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry

# ── Sentinel node name where the graph suspends for approval ──────────────────
_APPROVAL_NODE = "request_approval_if_needed"


class RunOperatorCopilotUseCase:
    """Orchestrates a full operator copilot run or resume.

    One instance per application lifetime (graph is compiled once).
    Thread-safe: all mutable state lives in the checkpointer, keyed by thread_id.

    Usage::

        use_case = RunOperatorCopilotUseCase(
            llm_gateway=...,
            tool_executor=...,
            approval_port=...,
            audit_log=...,
            checkpoint_factory=...,
        )

        # New run
        async for event in use_case.run("Show my last 5 posts", thread_id="t-123"):
            print(event)

        # Resume after operator approves
        async for event in use_case.resume("t-123", approval_result="approved"):
            print(event)
    """

    def __init__(
        self,
        llm_gateway: LLMGatewayPort,
        tool_executor: ToolExecutorPort,
        approval_port: ApprovalPort,
        audit_log: AuditLogPort,
        checkpoint_factory: CheckpointFactoryPort | None = None,
        checkpointer=None,
        policy_registry: ToolPolicyRegistry | None = None,
        copilot_memory: CopilotMemoryPort | None = None,
        store=None,
        max_steps: int = 1,
    ):
        """Compile the graph once during initialisation.

        Args:
            llm_gateway: LLM interaction port.
            tool_executor: Tool execution port (enforces its own access control).
            approval_port: Approval submission port (not used directly by graph;
                           the graph uses LangGraph interrupt instead).
            audit_log: Audit logging port.
            checkpointer: Pre-created LangGraph checkpointer (takes precedence over
                          checkpoint_factory). Use when the checkpointer requires
                          async initialisation (e.g. AsyncSqliteSaver).
            checkpoint_factory: If provided and checkpointer is None, calls
                                 create_checkpointer() synchronously.
                                 If both are None, MemorySaver is used.
            policy_registry: Tool classification registry.
                             Defaults to ToolPolicyRegistry() if not supplied.
            copilot_memory: Cross-thread copilot memory (optional).
            store: LangGraph Store instance for cross-thread memory.
            max_steps: Max planning iterations (currently 1 per todo-4 spec).
        """
        self.llm_gateway = llm_gateway
        self.tool_executor = tool_executor
        self.approval_port = approval_port
        self.audit_log = audit_log

        if checkpointer is not None:
            self._checkpointer = checkpointer
        elif checkpoint_factory is not None:
            self._checkpointer = checkpoint_factory.create_checkpointer()
        else:
            from langgraph.checkpoint.memory import MemorySaver
            self._checkpointer = MemorySaver()

        nodes = OperatorCopilotNodes(
            llm_gateway=llm_gateway,
            tool_executor=tool_executor,
            approval_port=approval_port,
            audit_log=audit_log,
            policy_registry=policy_registry or ToolPolicyRegistry(),
            copilot_memory=copilot_memory,
            max_steps=max_steps,
        )

        self._graph = build_operator_copilot_graph(
            nodes=nodes,
            checkpointer=self._checkpointer,
            store=store,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    async def run(
        self,
        operator_request: str,
        thread_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> AsyncIterator[dict]:
        """Start a new operator copilot run.

        Streams structured event dicts. If the graph suspends at
        request_approval_if_needed, emits an "approval_required" event
        containing the approval payload and stops. The caller must call
        resume() with the operator's decision.

        Args:
            operator_request: Raw natural language request from operator.
            thread_id: Durable session id. Auto-generated if not supplied.

        Yields:
            Structured event dicts (see _emit_* helpers).
        """
        initial_state = make_initial_state(
            operator_request=operator_request,
            thread_id=thread_id,
            provider=provider,
            model=model,
            api_key=api_key,
            provider_base_url=provider_base_url,
        )
        thread_id = initial_state["thread_id"]  # use generated id if none provided
        config = {"configurable": {"thread_id": thread_id}}

        async for event in self._stream_graph(initial_state, config, thread_id):
            yield event

    async def resume(
        self,
        thread_id: str,
        approval_result: str,
        edited_calls: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Resume a suspended run with an operator approval decision.

        The graph must be suspended at request_approval_if_needed for this to
        have any effect. If the thread is not suspended, yields an error event.

        Args:
            thread_id: Thread id of the suspended run.
            approval_result: One of "approved", "rejected", "edited".
            edited_calls: Required when approval_result == "edited". List of
                          modified tool call dicts [{id, name, arguments}, ...].

        Yields:
            Structured event dicts.
        """
        decision = {"result": approval_result}
        if approval_result == "edited" and edited_calls:
            decision["edited_calls"] = edited_calls

        config = {"configurable": {"thread_id": thread_id}}
        resume_input = Command(resume=decision)

        async for event in self._stream_graph(resume_input, config, thread_id):
            yield event

    # ── Internal streaming ─────────────────────────────────────────────────────

    async def _stream_graph(
        self,
        graph_input,
        config: dict,
        thread_id: str,
    ) -> AsyncIterator[dict]:
        """Drive graph.astream() and translate outputs to structured events."""
        run_id = str(uuid.uuid4())
        yield _emit_start(run_id, thread_id)

        try:
            async for chunk in self._graph.astream(graph_input, config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    if node_name == "__interrupt__":
                        # Graph suspended for approval.
                        # LangGraph returns node_output as a tuple of Interrupt objects,
                        # each with a .value attribute holding the interrupt payload.
                        interrupt_items = (
                            node_output
                            if isinstance(node_output, (list, tuple))
                            else [node_output]
                        )
                        for item in interrupt_items:
                            value = getattr(item, "value", item)
                            yield _emit_approval_required(thread_id, value)
                        return

                    yield _emit_node_update(node_name, node_output)

                    # ── Typed UI contract events ─────────────────────────────
                    # These let the frontend render structured state without
                    # parsing raw node_update output.
                    if not isinstance(node_output, dict):
                        continue

                    if node_name == "plan_actions":
                        plan = node_output.get("execution_plan")
                        calls = node_output.get("proposed_tool_calls")
                        if plan is not None or calls is not None:
                            yield _emit_plan_ready(plan or [], calls or [])

                    elif node_name == "review_tool_policy":
                        flags = node_output.get("tool_policy_flags", {})
                        risk = node_output.get("risk_assessment") or {}
                        if flags or risk:
                            yield _emit_policy_result(flags, risk)

                    elif node_name == "execute_tools":
                        results = node_output.get("tool_results", {})
                        names = node_output.get("tool_call_names", {})
                        for call_id, result in results.items():
                            yield _emit_tool_result(call_id, names.get(call_id, ""), result)

                    elif node_name == "summarize_result":
                        final_resp = node_output.get("final_response")
                        if final_resp:
                            yield _emit_final_response(final_resp)

            yield _emit_finish(run_id, "done")

        except Exception as exc:
            yield _emit_error(run_id, str(exc))


# ── SSE event helpers ──────────────────────────────────────────────────────────


def _emit_start(run_id: str, thread_id: str) -> dict:
    return {"type": "run_start", "run_id": run_id, "thread_id": thread_id}


def _emit_node_update(node_name: str, output: dict) -> dict:
    return {"type": "node_update", "node": node_name, "output": output}


def _emit_approval_required(thread_id: str, payload: dict) -> dict:
    """Emitted when graph suspends at request_approval_if_needed.

    The payload matches the UI contract from todo-5:
    - operator_intent
    - proposed_tool_calls
    - tool_reasons
    - risk_assessment
    - options
    """
    return {
        "type": "approval_required",
        "thread_id": thread_id,
        "payload": payload,
    }


def _emit_plan_ready(execution_plan: list, proposed_tool_calls: list) -> dict:
    """Emitted when plan_actions completes with a non-empty plan.

    Frontend can render a plan card showing:
    - What steps will be taken
    - Which tools are selected
    - Why each tool was chosen
    """
    return {
        "type": "plan_ready",
        "execution_plan": execution_plan,
        "proposed_tool_calls": proposed_tool_calls,
        "tool_count": len(proposed_tool_calls),
    }


def _emit_policy_result(
    flags: dict[str, str],
    risk_assessment: dict,
) -> dict:
    """Emitted when review_tool_policy classifies the proposed tool calls.

    Frontend can render a risk indicator and show which tools need approval.
    """
    needs_approval = any(v == "write_sensitive" for v in flags.values())
    return {
        "type": "policy_result",
        "flags": flags,
        "risk_level": risk_assessment.get("level", "low"),
        "risk_reasons": risk_assessment.get("reasons", []),
        "needs_approval": needs_approval,
    }


def _emit_tool_result(call_id: str, tool_name: str, result: dict) -> dict:
    """Emitted once per tool execution after execute_tools completes.

    Frontend can render individual tool result cards with tool identity.
    """
    success = "error" not in result
    return {
        "type": "tool_result",
        "call_id": call_id,
        "tool_name": tool_name,
        "success": success,
        "result": result,
    }


def _emit_final_response(text: str) -> dict:
    return {"type": "final_response", "text": text}


def _emit_finish(run_id: str, stop_reason: str) -> dict:
    return {"type": "run_finish", "run_id": run_id, "stop_reason": stop_reason}


def _emit_error(run_id: str, message: str) -> dict:
    return {"type": "run_error", "run_id": run_id, "message": message[:200]}
