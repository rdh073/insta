"""SmartEngagementUseCase - orchestrates smart engagement workflow (todo-4).

Ownership: Workflow entry point, state initialization, result formatting, resume handling.
Delegates to graph for orchestration.
No HTTP, no Instagram SDK, no session files - only domain logic.

Todo-4 additions:
- checkpointer passed to graph (required for interrupt/resume)
- resume(thread_id, decision) for continuing after approval interrupt
- initial_state includes new failure-guard fields (discovery_attempted, approval_attempted)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from typing import Any, AsyncIterator

from langgraph.types import Command

logger = logging.getLogger(__name__)

from ai_copilot.application.graphs.smart_engagement import build_smart_engagement_graph
from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    EngagementMemoryPort,
    RiskScoringPort,
)
from ai_copilot.application.smart_engagement.state import SmartEngagementState
from ai_copilot.application.use_cases.langgraph_runtime_adapter import (
    DEFAULT_LANGGRAPH_VERSION_STRATEGY,
    ainvoke_with_contract,
    astream_with_contract,
    first_interrupt_payload,
    interrupt_payloads_from_exception,
    normalize_invoke_result,
)


class SmartEngagementUseCase:
    """Orchestrates smart engagement workflow.

    Entry point for smart engagement. Coordinates:
    - Graph construction with checkpointer (for interrupt/resume)
    - State initialization with thread_id for checkpointing
    - Resume via Command(resume=...) for approval decisions
    - Result formatting and response

    Uses 6 ports:
    1. AccountContextPort - Account health & constraints
    2. EngagementCandidatePort - Goal-based target discovery
    3. RiskScoringPort - Rule-based risk assessment
    4. ApprovalPort - Approval submission & tracking
    5. EngagementExecutorPort - Action execution (mode-guarded)
    6. AuditLogPort - Explicit event logging

    Invariants:
    - Default mode is 'recommendation' (no auto-execute)
    - Write actions require explicit approval (interrupted for human decision)
    - All decisions are auditable (explicit events)
    - Max 1 discovery cycle and 1 approval per run
    """

    def __init__(
        self,
        account_context: AccountContextPort,
        candidate_discovery: EngagementCandidatePort,
        risk_scoring: RiskScoringPort,
        approval: ApprovalPort,
        executor: EngagementExecutorPort,
        audit_log: AuditLogPort,
        engagement_memory: EngagementMemoryPort | None = None,
        checkpointer=None,
        checkpoint_factory=None,
        store=None,
        max_steps: int = 11,
    ):
        """Initialize use case with 7 port dependencies.

        Args:
            account_context: Account health and constraints
            candidate_discovery: Goal-based target discovery
            risk_scoring: Rule-based risk assessment
            approval: Approval submission and tracking
            executor: Engagement action executor
            audit_log: Audit event logging
            engagement_memory: Cross-thread engagement memory (optional)
            checkpointer: Pre-created LangGraph checkpointer.  Use this when a
                MemorySaver (sync-compatible) is appropriate, e.g. in tests.
            checkpoint_factory: Factory with ``create_async()`` and/or
                ``create_checkpointer()``. For factories with ``create_async()``,
                the checkpointer is created lazily on first ``run()`` / ``resume()``
                so bootstrap stays synchronous.
            store: LangGraph Store instance for cross-thread memory.
            max_steps: Max workflow iterations (default 11 for 11-node graph)
        """
        if checkpointer is not None and checkpoint_factory is not None:
            raise ValueError(
                "Invalid smart engagement checkpointer configuration: provide "
                "either 'checkpointer' or 'checkpoint_factory', not both."
            )

        self.account_context = account_context
        self.candidate_discovery = candidate_discovery
        self.risk_scoring = risk_scoring
        self.approval = approval
        self.executor = executor
        self.audit_log = audit_log
        self.engagement_memory = engagement_memory
        self.max_steps = max_steps

        self._nodes = SmartEngagementNodes(
            account_context=account_context,
            candidate_discovery=candidate_discovery,
            risk_scoring=risk_scoring,
            approval=approval,
            executor=executor,
            audit_log=audit_log,
            engagement_memory=engagement_memory,
            max_steps=max_steps,
        )
        self._store = store
        self._checkpoint_factory = checkpoint_factory
        self._checkpointer = None
        self.checkpointer = None
        self._graph_lock = asyncio.Lock()
        self._version_strategy = DEFAULT_LANGGRAPH_VERSION_STRATEGY

        if checkpointer is not None:
            # Eager path: caller supplied a pre-created checkpointer.
            self._checkpointer = self._validate_checkpointer(
                checkpointer,
                source="checkpointer",
            )
            self.graph = build_smart_engagement_graph(
                self._nodes,
                checkpointer=self._checkpointer,
                store=store,
            )
        elif checkpoint_factory is None:
            # Deterministic fallback for alternate wiring/tests.
            from langgraph.checkpoint.memory import MemorySaver

            self._checkpointer = self._validate_checkpointer(
                MemorySaver(),
                source="default MemorySaver fallback",
            )
            self.graph = build_smart_engagement_graph(
                self._nodes,
                checkpointer=self._checkpointer,
                store=store,
            )
        else:
            has_async, _has_sync = self._validate_checkpoint_factory(checkpoint_factory)
            if has_async:
                # Lazy path: async checkpointer created on first run()/resume() call.
                self.graph = None
            else:
                # Sync-only factory path for tests/alternate wiring.
                self._checkpointer = self._validate_checkpointer(
                    checkpoint_factory.create_checkpointer(),
                    source="checkpoint_factory.create_checkpointer()",
                )
                self.graph = build_smart_engagement_graph(
                    self._nodes,
                    checkpointer=self._checkpointer,
                    store=store,
                )

        self.checkpointer = self._checkpointer

    @staticmethod
    def _validate_checkpoint_factory(checkpoint_factory) -> tuple[bool, bool]:
        """Validate checkpoint factory contract and return available creation modes."""
        has_async = callable(getattr(checkpoint_factory, "create_async", None))
        has_sync = callable(getattr(checkpoint_factory, "create_checkpointer", None))
        if not has_async and not has_sync:
            raise ValueError(
                "Invalid smart engagement checkpoint_factory: expected "
                "create_async() and/or create_checkpointer()."
            )
        return has_async, has_sync

    @staticmethod
    def _validate_checkpointer(checkpointer, *, source: str):
        """Validate checkpointer shape for predictable interrupt/resume semantics."""
        if checkpointer is None:
            raise ValueError(
                f"Invalid smart engagement checkpointer from {source}: got None."
            )

        has_sync_contract = (
            all(
                callable(getattr(checkpointer, name, None))
                for name in ("get_tuple", "put", "put_writes")
            )
            or all(
                callable(getattr(checkpointer, name, None))
                for name in ("get", "put", "list")
            )
        )
        has_async_contract = (
            all(
                callable(getattr(checkpointer, name, None))
                for name in ("aget_tuple", "aput", "aput_writes")
            )
            or all(
                callable(getattr(checkpointer, name, None))
                for name in ("aget", "aput", "alist")
            )
        )

        if not has_sync_contract and not has_async_contract:
            raise ValueError(
                f"Invalid smart engagement checkpointer from {source}: expected "
                "LangGraph saver methods for sync (get_tuple/put/put_writes or "
                "get/put/list) or async (aget_tuple/aput/aput_writes or "
                "aget/aput/alist) operation."
            )
        return checkpointer

    async def _ensure_graph(self) -> None:
        """Lazily build the compiled graph with an async checkpointer.

        Called at the start of every ``run()`` and ``resume()`` when
        ``checkpoint_factory.create_async()`` is used for checkpointer resolution.
        A lock prevents duplicate initialisation under concurrent requests.
        """
        if self.graph is not None:
            return

        if self._checkpoint_factory is None:
            raise RuntimeError(
                "Smart engagement graph is uninitialized and no checkpoint_factory "
                "is available to create a checkpointer."
            )

        async with self._graph_lock:
            if self.graph is not None:
                return
            create_async = getattr(self._checkpoint_factory, "create_async", None)
            if not callable(create_async):
                raise RuntimeError(
                    "Smart engagement lazy graph initialization requires "
                    "checkpoint_factory.create_async()."
                )
            checkpointer = create_async()
            if inspect.isawaitable(checkpointer):
                checkpointer = await checkpointer
            self._checkpointer = self._validate_checkpointer(
                checkpointer,
                source="checkpoint_factory.create_async()",
            )
            self.checkpointer = self._checkpointer
            self.graph = build_smart_engagement_graph(
                self._nodes,
                checkpointer=self._checkpointer,
                store=self._store,
            )

    async def run(
        self,
        execution_mode: str = "recommendation",
        goal: str = "engage with relevant accounts",
        account_id: str = "default_account",
        max_targets: int = 5,
        max_actions_per_target: int = 3,
        approval_timeout: float = 3600.0,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Start a new smart engagement workflow run.

        Args:
            execution_mode: 'recommendation' (default) or 'execute'
            goal: Operator's intent (e.g., "comment on educational posts")
            account_id: Account that will perform engagement
            max_targets: Maximum targets to discover
            max_actions_per_target: Maximum actions per target
            approval_timeout: Seconds before approval times out (default 3600)
            metadata: Optional dict; may include 'thread_id' for resumption

        Returns:
            Dict with:
            - mode: Execution mode used
            - status: stop_reason (recommendation_only, interrupted, completed, error, ...)
            - interrupted: True if workflow is paused at approval interrupt
            - interrupt_payload: Self-contained approval request (if interrupted)
            - thread_id: Use this to resume after interrupt
            - recommendation: Proposed action (if recommendation mode)
            - risk_assessment: Risk evaluation
            - execution: Execution result (if executed)
            - audit_trail: Decision history
            - outcome_reason: Human-readable reason for workflow end
        """
        await self._ensure_graph()
        thread_id = (metadata or {}).get("thread_id") or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = self._build_initial_state(
            thread_id=thread_id,
            execution_mode=execution_mode,
            goal=goal,
            account_id=account_id,
            max_targets=max_targets,
            max_actions_per_target=max_actions_per_target,
            approval_timeout=approval_timeout,
        )

        try:
            raw_result = await ainvoke_with_contract(
                self.graph,
                initial_state,
                config=config,
                strategy=self._version_strategy,
            )
        except Exception as e:
            interrupt_payload = first_interrupt_payload(interrupt_payloads_from_exception(e))
            if interrupt_payload is not None:
                state = await self._recover_graph_state(config)
                trail = state.get("audit_trail", []) if isinstance(state, dict) else []
                if not trail:
                    trail = await self._recover_audit_trail(thread_id)
                return self._format_interrupted_response(
                    mode=execution_mode,
                    thread_id=thread_id,
                    interrupt_payload=interrupt_payload,
                    state=state if isinstance(state, dict) else {},
                    audit_trail=trail,
                )
            logger.exception("Smart engagement run failed thread=%s goal=%r", thread_id, goal)
            trail = await self._recover_audit_trail(thread_id)
            return {
                "mode": execution_mode,
                "status": "error",
                "error": str(e),
                "thread_id": thread_id,
                "audit_trail": trail,
            }

        result = normalize_invoke_result(raw_result)
        payload = first_interrupt_payload(result.interrupt_payloads)
        if payload is not None:
            value = result.value if isinstance(result.value, dict) else {}
            return self._format_interrupted_response(
                mode=execution_mode,
                thread_id=thread_id,
                interrupt_payload=payload,
                state=value,
                audit_trail=value.get("audit_trail", []),
            )

        return self._format_response(result.value, execution_mode, thread_id)

    async def run_stream(
        self,
        execution_mode: str = "recommendation",
        goal: str = "engage with relevant accounts",
        account_id: str = "default_account",
        max_targets: int = 5,
        max_actions_per_target: int = 3,
        approval_timeout: float = 3600.0,
        metadata: dict | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Start a new run and stream node-level LangGraph updates incrementally."""
        await self._ensure_graph()
        thread_id = (metadata or {}).get("thread_id") or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = self._build_initial_state(
            thread_id=thread_id,
            execution_mode=execution_mode,
            goal=goal,
            account_id=account_id,
            max_targets=max_targets,
            max_actions_per_target=max_actions_per_target,
            approval_timeout=approval_timeout,
        )

        async for event in self._stream_graph(
            initial_state,
            config=config,
            thread_id=thread_id,
            fallback_mode=execution_mode,
        ):
            yield event

    async def resume(
        self,
        thread_id: str,
        decision: dict,
    ) -> dict[str, Any]:
        """Resume workflow after approval interrupt.

        Args:
            thread_id: The thread_id from the interrupted run
            decision: Approval decision dict:
                {
                    "decision": "approved" | "rejected" | "edited",
                    "notes": "Optional notes",
                    "content": "Edited content (if decision=edited)"
                }

        Returns:
            Same format as run() - final workflow state
        """
        await self._ensure_graph()
        config = {"configurable": {"thread_id": thread_id}}

        try:
            raw_result = await ainvoke_with_contract(
                self.graph,
                Command(resume=decision),
                config=config,
                strategy=self._version_strategy,
            )
        except Exception as e:
            interrupt_payload = first_interrupt_payload(interrupt_payloads_from_exception(e))
            if interrupt_payload is not None:
                state = await self._recover_graph_state(config)
                trail = state.get("audit_trail", []) if isinstance(state, dict) else []
                if not trail:
                    trail = await self._recover_audit_trail(thread_id)
                mode = state.get("mode", "execute") if isinstance(state, dict) else "execute"
                return self._format_interrupted_response(
                    mode=mode,
                    thread_id=thread_id,
                    interrupt_payload=interrupt_payload,
                    state=state if isinstance(state, dict) else {},
                    audit_trail=trail,
                )
            logger.exception("Smart engagement resume failed thread=%s", thread_id)
            trail = await self._recover_audit_trail(thread_id)
            return {
                "mode": "execute",
                "status": "error",
                "error": str(e),
                "thread_id": thread_id,
                "audit_trail": trail,
            }

        result = normalize_invoke_result(raw_result)
        payload = first_interrupt_payload(result.interrupt_payloads)
        if payload is not None:
            value = result.value if isinstance(result.value, dict) else {}
            mode = value.get("mode", "execute")
            return self._format_interrupted_response(
                mode=mode,
                thread_id=thread_id,
                interrupt_payload=payload,
                state=value,
                audit_trail=value.get("audit_trail", []),
            )

        mode = result.value.get("mode", "execute") if isinstance(result.value, dict) else "execute"
        return self._format_response(result.value, mode, thread_id)

    async def resume_stream(
        self,
        thread_id: str,
        decision: dict,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resume a suspended run and stream incremental LangGraph updates."""
        await self._ensure_graph()
        config = {"configurable": {"thread_id": thread_id}}
        async for event in self._stream_graph(
            Command(resume=decision),
            config=config,
            thread_id=thread_id,
            fallback_mode="execute",
            resumed=True,
        ):
            yield event

    async def _stream_graph(
        self,
        graph_input: Any,
        *,
        config: dict[str, Any],
        thread_id: str,
        fallback_mode: str,
        resumed: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Drive graph.astream() and emit incremental SSE-ready events."""
        run_start = {"type": "run_start", "run_id": thread_id, "thread_id": thread_id}
        if resumed:
            run_start["resumed"] = True
        yield run_start

        try:
            async for chunk in astream_with_contract(
                self.graph,
                graph_input,
                config=config,
                stream_mode="updates",
                strategy=self._version_strategy,
            ):
                for entry in chunk.entries:
                    if entry.kind == "interrupt":
                        yield {
                            "type": "approval_required",
                            "thread_id": thread_id,
                            "payload": entry.payload if isinstance(entry.payload, dict) else {},
                        }
                        return

                    node_name = entry.node_name or ""
                    yield {
                        "type": "node_update",
                        "node": node_name,
                        "data": self._safe(entry.payload),
                    }

            final_state = await self._recover_graph_state(config)
            mode = (
                final_state.get("mode", fallback_mode)
                if isinstance(final_state, dict)
                else fallback_mode
            )
            final_result = self._format_response(final_state, mode, thread_id)
            stop_reason = final_result.get("status") or "completed"
            if stop_reason == "unknown":
                stop_reason = "completed"

            yield {
                "type": "final_response",
                "thread_id": thread_id,
                "stop_reason": stop_reason,
                "text": final_result.get("outcome_reason") or "Smart engagement completed.",
                "result": final_result,
            }
            yield {"type": "run_finish", "run_id": thread_id, "stop_reason": stop_reason}

        except Exception as exc:
            interrupt_payload = first_interrupt_payload(interrupt_payloads_from_exception(exc))
            if interrupt_payload is not None:
                yield {
                    "type": "approval_required",
                    "thread_id": thread_id,
                    "payload": interrupt_payload if isinstance(interrupt_payload, dict) else {},
                }
                return
            logger.exception(
                "Smart engagement stream failed thread=%s resumed=%s",
                thread_id,
                resumed,
            )
            yield {
                "type": "run_error",
                "run_id": thread_id,
                "thread_id": thread_id,
                "message": "Smart engagement failed.",
            }

    async def _recover_graph_state(self, config: dict[str, Any]) -> SmartEngagementState:
        """Best-effort recovery of latest graph state after streaming completes."""
        try:
            snapshot = await self.graph.aget_state(config)
            if snapshot:
                values = snapshot.values or {}
                if isinstance(values, dict):
                    return values
        except Exception:
            logger.debug(
                "Could not recover smart engagement graph state thread=%s",
                config.get("configurable", {}).get("thread_id"),
            )
        return {}

    def _build_initial_state(
        self,
        *,
        thread_id: str,
        execution_mode: str,
        goal: str,
        account_id: str,
        max_targets: int,
        max_actions_per_target: int,
        approval_timeout: float,
    ) -> SmartEngagementState:
        """Construct initial SmartEngagementState for run() and run_stream()."""
        return {
            # Base state
            "messages": [],
            "current_tool_calls": None,
            "tool_results": {},
            "stop_reason": None,
            "step_count": 0,
            # Resumable execution
            "thread_id": thread_id,
            # Execution control
            "mode": execution_mode,
            "goal": goal,
            # Goal parsing (populated by ingest_goal node)
            "structured_goal": None,
            # Account context
            "account_id": account_id,
            "account_health": None,
            # Target selection
            "candidate_targets": [],
            "selected_target": None,
            # Action selection
            "proposed_action": None,
            "draft_payload": None,
            # Risk assessment
            "risk_assessment": None,
            # Approval
            "approval_request": None,
            "approval_result": None,
            # Execution
            "execution_result": None,
            # Audit trail
            "audit_trail": [],
            # Failure guards (todo-4)
            "discovery_attempted": False,
            "approval_attempted": False,
            # Outcome
            "outcome_reason": None,
            # Approval timeout
            "approval_timeout": approval_timeout,
            # Loop control
            "max_targets": max_targets,
            "max_actions_per_target": max_actions_per_target,
        }

    async def _recover_audit_trail(self, thread_id: str) -> list:
        """Best-effort recovery of audit trail from the audit log port."""
        try:
            return await self.audit_log.get_audit_trail(thread_id)
        except Exception:
            logger.debug("Could not recover audit trail for thread=%s", thread_id)
            return []

    def _safe(self, value: Any) -> Any:
        """Convert LangGraph node payloads into JSON-safe values for SSE."""
        if isinstance(value, dict):
            return {k: self._safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._safe(item) for item in value]
        if isinstance(value, tuple):
            return [self._safe(item) for item in value]
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        return str(value)

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_string(value: Any) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return None

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _recommendation_from_interrupt_payload(
        self,
        interrupt_payload: Any,
    ) -> dict[str, Any] | None:
        payload = self._as_dict(interrupt_payload)
        if not payload:
            return None

        draft_action = self._as_dict(payload.get("draft_action"))
        draft_payload = self._as_dict(payload.get("draft_payload"))
        recommendation = {
            "target": (
                self._as_string(payload.get("target"))
                or self._as_string(draft_action.get("target_id"))
            ),
            "action_type": self._as_string(draft_action.get("action_type")),
            "content": (
                self._as_string(draft_action.get("content"))
                or self._as_string(payload.get("draft_content"))
                or self._as_string(draft_payload.get("content"))
            ),
            "reasoning": self._as_string(payload.get("relevance_reason")),
            "expected_outcome": None,
        }
        if not any(value is not None for value in recommendation.values()):
            return None
        return recommendation

    def _risk_assessment_from_interrupt_payload(
        self,
        interrupt_payload: Any,
    ) -> dict[str, Any] | None:
        payload = self._as_dict(interrupt_payload)
        if not payload:
            return None

        level = self._as_string(payload.get("risk_level"))
        reasoning = self._as_string(payload.get("risk_reason"))
        rule_hits = self._as_string_list(payload.get("rule_hits"))
        if level is None and reasoning is None and len(rule_hits) == 0:
            return None

        requires_approval_raw = payload.get("requires_approval")
        requires_approval = (
            requires_approval_raw
            if isinstance(requires_approval_raw, bool)
            else True
        )
        return {
            "level": level,
            "rule_hits": rule_hits,
            "reasoning": reasoning,
            "requires_approval": requires_approval,
        }

    def _format_interrupted_response(
        self,
        *,
        mode: str,
        thread_id: str,
        interrupt_payload: Any,
        state: SmartEngagementState | dict[str, Any] | None,
        audit_trail: list | None,
    ) -> dict[str, Any]:
        state_dict = state if isinstance(state, dict) else {}
        response = self._format_response(state_dict, mode, thread_id)
        response["status"] = "interrupted"
        response["interrupted"] = True
        response["interrupt_payload"] = interrupt_payload
        response["thread_id"] = thread_id
        response["audit_trail"] = audit_trail or state_dict.get("audit_trail", [])

        if "recommendation" not in response:
            recommendation = self._recommendation_from_interrupt_payload(interrupt_payload)
            if recommendation is not None:
                response["recommendation"] = recommendation

        if "risk_assessment" not in response:
            risk_assessment = self._risk_assessment_from_interrupt_payload(interrupt_payload)
            if risk_assessment is not None:
                response["risk_assessment"] = risk_assessment

        return response

    def _format_response(
        self,
        state: SmartEngagementState,
        mode: str,
        thread_id: str | None = None,
    ) -> dict:
        """Format final workflow state into response dict."""
        response: dict[str, Any] = {
            "mode": mode,
            "status": state.get("stop_reason", "unknown"),
            "thread_id": thread_id or state.get("thread_id"),
            "outcome_reason": state.get("outcome_reason"),
            "audit_trail": state.get("audit_trail", []),
            "interrupted": False,
        }

        # Add recommendation (proposed_action from state)
        action = state.get("proposed_action")
        if action:
            response["recommendation"] = {
                "target": action.get("target_id"),
                "action_type": action.get("action_type"),
                "content": action.get("content"),
                "reasoning": action.get("reasoning"),
                "expected_outcome": action.get("expected_outcome"),
            }

        # Add risk assessment
        risk = state.get("risk_assessment")
        if risk:
            response["risk_assessment"] = {
                "level": risk.get("risk_level"),
                "rule_hits": risk.get("rule_hits", []),
                "reasoning": risk.get("reasoning"),
                "requires_approval": risk.get("requires_approval"),
            }

        # Add approval status
        approval_req = state.get("approval_request")
        approval_res = state.get("approval_result")
        if approval_req:
            response["approval"] = {
                "id": approval_req.get("approval_id"),
                "decision": approval_res.get("decision") if approval_res else "pending",
                "notes": approval_res.get("approver_notes", "") if approval_res else "",
            }

        # Add execution result
        result = state.get("execution_result")
        if result:
            response["execution"] = result

        return response
