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
import logging
import uuid
from typing import Any

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
            checkpoint_factory: Factory with ``create_async()`` method.  Preferred
                over ``checkpointer`` for production — the async checkpointer is
                created lazily on the first ``run()`` / ``resume()`` call so that
                bootstrap stays synchronous while the graph still uses an async-
                compatible SQLite saver (AsyncSqliteSaver) at runtime.
            store: LangGraph Store instance for cross-thread memory.
            max_steps: Max workflow iterations (default 11 for 11-node graph)
        """
        self.account_context = account_context
        self.candidate_discovery = candidate_discovery
        self.risk_scoring = risk_scoring
        self.approval = approval
        self.executor = executor
        self.audit_log = audit_log
        self.engagement_memory = engagement_memory
        self.checkpointer = checkpointer
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
        self._graph_lock = asyncio.Lock()

        if checkpoint_factory is None:
            # Eager path: caller supplied a pre-created checkpointer (tests, MemorySaver)
            self.graph = build_smart_engagement_graph(
                self._nodes, checkpointer=checkpointer, store=store,
            )
        else:
            # Lazy path: async checkpointer created on first run()/resume() call
            self.graph = None

    async def _ensure_graph(self) -> None:
        """Lazily build the compiled graph with an async checkpointer.

        Called at the start of every ``run()`` and ``resume()`` when
        ``checkpoint_factory`` was supplied instead of a pre-built checkpointer.
        A lock prevents duplicate initialisation under concurrent requests.
        """
        if self.graph is not None:
            return
        async with self._graph_lock:
            if self.graph is not None:
                return
            checkpointer = await self._checkpoint_factory.create_async()
            self.graph = build_smart_engagement_graph(
                self._nodes, checkpointer=checkpointer, store=self._store,
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

        initial_state: SmartEngagementState = {
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

        try:
            result = await self.graph.ainvoke(initial_state, config=config)
        except Exception as e:
            # Check if this is an interrupt (LangGraph raises GraphInterrupt)
            interrupt_payload = _extract_interrupt_payload(e)
            if interrupt_payload is not None:
                trail = await self._recover_audit_trail(thread_id)
                return {
                    "mode": execution_mode,
                    "status": "interrupted",
                    "interrupted": True,
                    "interrupt_payload": interrupt_payload,
                    "thread_id": thread_id,
                    "audit_trail": trail,
                }
            logger.exception("Smart engagement run failed thread=%s goal=%r", thread_id, goal)
            trail = await self._recover_audit_trail(thread_id)
            return {
                "mode": execution_mode,
                "status": "error",
                "error": str(e),
                "thread_id": thread_id,
                "audit_trail": trail,
            }

        # Check if graph paused at interrupt (returned state with __interrupt__ key)
        if isinstance(result, dict) and "__interrupt__" in result:
            interrupt_data = result["__interrupt__"]
            payload = interrupt_data[0].value if interrupt_data else {}
            return {
                "mode": execution_mode,
                "status": "interrupted",
                "interrupted": True,
                "interrupt_payload": payload,
                "thread_id": thread_id,
                "audit_trail": result.get("audit_trail", []),
            }

        return self._format_response(result, execution_mode, thread_id)

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
            result = await self.graph.ainvoke(
                Command(resume=decision),
                config=config,
            )
        except Exception as e:
            interrupt_payload = _extract_interrupt_payload(e)
            if interrupt_payload is not None:
                trail = await self._recover_audit_trail(thread_id)
                return {
                    "mode": "execute",
                    "status": "interrupted",
                    "interrupted": True,
                    "interrupt_payload": interrupt_payload,
                    "thread_id": thread_id,
                    "audit_trail": trail,
                }
            logger.exception("Smart engagement resume failed thread=%s", thread_id)
            trail = await self._recover_audit_trail(thread_id)
            return {
                "mode": "execute",
                "status": "error",
                "error": str(e),
                "thread_id": thread_id,
                "audit_trail": trail,
            }

        mode = result.get("mode", "execute") if isinstance(result, dict) else "execute"
        return self._format_response(result, mode, thread_id)

    async def _recover_audit_trail(self, thread_id: str) -> list:
        """Best-effort recovery of audit trail from the audit log port."""
        try:
            return await self.audit_log.get_audit_trail(thread_id)
        except Exception:
            logger.debug("Could not recover audit trail for thread=%s", thread_id)
            return []

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


def _extract_interrupt_payload(exc: Exception) -> dict | None:
    """Extract interrupt payload from LangGraph GraphInterrupt exception.

    Returns the interrupt value if exc is a GraphInterrupt, else None.
    """
    # LangGraph raises GraphInterrupt when interrupt() is called
    exc_type = type(exc).__name__
    if "GraphInterrupt" in exc_type or "Interrupt" in exc_type:
        # The interrupt value is typically stored in exc.args or exc.value
        args = getattr(exc, "args", ())
        if args:
            first = args[0]
            # LangGraph wraps interrupt payload in a list of Interrupt objects
            if isinstance(first, (list, tuple)) and first:
                item = first[0]
                if hasattr(item, "value"):
                    return item.value
                return item
            return first
    return None
