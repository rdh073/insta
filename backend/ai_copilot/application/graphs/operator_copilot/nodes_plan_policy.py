"""Plan and policy-stage node implementations for operator copilot graph."""

from __future__ import annotations

import hashlib
import json
import logging

from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry
from ai_copilot.application.ports import (
    ApprovalPort,
    AuditLogPort,
    CopilotMemoryPort,
    LLMGatewayPort,
    ToolExecutorPort,
)
from ai_copilot.application.state import OperatorCopilotState

from .planning_guards import _planner_visible_tool_schemas, _sanitize_proposed_tool_calls
from .prompts import (
    _CLASSIFY_SYSTEM_PROMPT,
    _PLAN_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class OperatorCopilotPlanPolicyNodes:
    """Node mix for ingest/classify/plan/policy stages."""

    def __init__(
        self,
        llm_gateway: LLMGatewayPort,
        tool_executor: ToolExecutorPort,
        approval_port: ApprovalPort,
        audit_log: AuditLogPort,
        policy_registry: ToolPolicyRegistry | None = None,
        copilot_memory: CopilotMemoryPort | None = None,
        max_steps: int = 1,
    ):
        self.llm_gateway = llm_gateway
        self.tool_executor = tool_executor
        self.approval_port = approval_port
        self.audit_log = audit_log
        self.policy_registry = policy_registry or ToolPolicyRegistry()
        self.copilot_memory = copilot_memory
        self.max_steps = max_steps

    @staticmethod
    def _llm_request_kwargs(state: OperatorCopilotState) -> dict:
        """Build provider overrides for LLM calls from persisted thread state.

        State is the authoritative source for provider routing — every LLM
        call in the operator copilot graph (classify, plan, review, summarize)
        MUST resolve its provider/model/api_key/base_url through this helper,
        never via a node-local default. The ``"openai"`` fallback only kicks
        in when ``state.provider`` is falsy (legacy threads seeded without
        a provider).
        """
        provider = state.get("provider") or "openai"
        model = state.get("model") or None
        api_key = state.get("api_key") or None
        provider_base_url = state.get("provider_base_url") or None
        return {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "provider_base_url": provider_base_url,
        }

    async def _planner_runtime_context(self, thread_id: str | None = None) -> dict:
        """Load optional runtime context for the planner without widening the port contract."""
        context_getter = getattr(self.tool_executor, "get_planner_context", None)
        if not callable(context_getter):
            return {}

        try:
            context = await context_getter()
        except Exception as exc:
            await self.audit_log.log("planner_decision", {
                "stage": "plan_actions_context",
                "thread_id": thread_id,
                "context_available": False,
                "error": str(exc),
            })
            return {}

        if not isinstance(context, dict):
            return {}
        return context

    @staticmethod
    def _normalize_namespace_token(value: str) -> str:
        """Normalize free-form ids/usernames into a stable namespace-safe token."""
        token = value.strip().lower().lstrip("@")
        if not token:
            return ""
        allowed = []
        for ch in token:
            if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch in ("_", "-", ".", ":"):
                allowed.append(ch)
            else:
                allowed.append("_")
        normalized = "".join(allowed).strip("._-:")
        return normalized[:96]

    @classmethod
    def _managed_account_tokens(cls, runtime_context: dict | None) -> list[str]:
        """Return normalized managed account usernames from planner runtime context."""
        if not isinstance(runtime_context, dict):
            return []
        managed = runtime_context.get("managed_accounts")
        if not isinstance(managed, list):
            return []

        tokens: list[str] = []
        for entry in managed:
            if not isinstance(entry, dict):
                continue
            username = entry.get("username")
            if not isinstance(username, str):
                continue
            normalized = cls._normalize_namespace_token(username)
            if normalized:
                tokens.append(normalized)
        return tokens

    @classmethod
    def _extract_account_tokens_from_calls(cls, calls: list[dict]) -> list[str]:
        """Extract account-like identifiers from tool call arguments."""
        keys = (
            "username",
            "account_username",
            "account",
            "source_account",
            "account_id",
            "accountId",
        )
        tokens: list[str] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    continue
            if not isinstance(args, dict):
                continue
            for key in keys:
                raw = args.get(key)
                if not isinstance(raw, str):
                    continue
                normalized = cls._normalize_namespace_token(raw)
                if normalized:
                    tokens.append(normalized)
        return tokens

    @classmethod
    def _resolve_account_scope(
        cls,
        state: OperatorCopilotState,
        runtime_context: dict | None = None,
    ) -> str:
        """Resolve account scope for memory namespace, preferring acting account signals."""
        mentions = [
            cls._normalize_namespace_token(raw)
            for raw in (state.get("mentions") or [])
            if isinstance(raw, str)
        ]
        mentions = [m for m in mentions if m]
        managed_tokens = set(cls._managed_account_tokens(runtime_context))

        if managed_tokens:
            for mention in mentions:
                if mention in managed_tokens:
                    return mention

        if mentions:
            return mentions[0]

        for key in ("approved_tool_calls", "proposed_tool_calls"):
            calls = state.get(key) or []
            if not isinstance(calls, list):
                continue
            call_tokens = cls._extract_account_tokens_from_calls(calls)
            if managed_tokens:
                for token in call_tokens:
                    if token in managed_tokens:
                        return token
            if call_tokens:
                return call_tokens[0]

        return "global"

    @classmethod
    def _resolve_operator_scope(
        cls,
        state: OperatorCopilotState,
        runtime_context: dict | None = None,
    ) -> str:
        """Resolve stable operator scope for memory namespace."""
        explicit_scope = state.get("operator_id") or state.get("operator_scope")
        if isinstance(explicit_scope, str):
            normalized = cls._normalize_namespace_token(explicit_scope)
            if normalized:
                return f"operator:{normalized}"

        managed_tokens = sorted(set(cls._managed_account_tokens(runtime_context)))
        if managed_tokens:
            digest = hashlib.sha1(",".join(managed_tokens).encode("utf-8")).hexdigest()[:16]
            return f"managed:{digest}"

        api_key = state.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            digest = hashlib.sha1(api_key.strip().encode("utf-8")).hexdigest()[:16]
            return f"apikey:{digest}"

        thread_id = state.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip():
            normalized = cls._normalize_namespace_token(thread_id)
            if normalized:
                return f"thread:{normalized}"

        return "operator:default"

    @classmethod
    def _build_copilot_memory_namespace(
        cls,
        state: OperatorCopilotState,
        runtime_context: dict | None = None,
    ) -> str:
        """Build deterministic memory namespace shared by planner recall and finish write."""
        operator_scope = cls._resolve_operator_scope(state, runtime_context=runtime_context)
        account_scope = cls._resolve_account_scope(state, runtime_context=runtime_context)
        return f"copilot:{operator_scope}:account:{account_scope}"[:180]

    async def _resolve_copilot_memory_namespace(
        self,
        state: OperatorCopilotState,
        runtime_context: dict | None = None,
    ) -> str:
        """Resolve namespace, reusing persisted state value when available."""
        existing = state.get("copilot_memory_namespace")
        if isinstance(existing, str) and existing.strip():
            return existing

        context = runtime_context
        if context is None:
            context = await self._planner_runtime_context(thread_id=state.get("thread_id"))
        return self._build_copilot_memory_namespace(state, runtime_context=context)

    async def ingest_request_node(self, state: OperatorCopilotState) -> dict:
        """Receive and record the raw operator request."""
        operator_request = state.get("operator_request", "")
        step_count = state.get("step_count", 0) + 1

        await self.audit_log.log("operator_request", {
            "operator_request": operator_request,
            "thread_id": state.get("thread_id"),
            "step": step_count,
        })

        return {
            "step_count": step_count,
            "proposed_tool_calls": [],
            "approved_tool_calls": [],
            "tool_policy_flags": {},
            "approval_attempted": False,
        }

    async def classify_goal_node(self, state: OperatorCopilotState) -> dict:
        """Classify the operator request: normalize goal and detect blocked intent."""
        operator_request = state.get("operator_request", "")

        messages = [
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": operator_request},
        ]

        try:
            response = await self.llm_gateway.request_completion(
                messages=messages,
                **self._llm_request_kwargs(state),
            )
            raw = response.get("content", "{}")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0].strip()
            classification = json.loads(raw)
        except Exception as exc:
            classification = {
                "normalized_goal": operator_request,
                "blocked": False,
                "block_reason": None,
                "_parse_error": str(exc),
            }

        normalized_goal = classification.get("normalized_goal", operator_request)
        is_blocked = bool(classification.get("blocked", False))
        block_reason = classification.get("block_reason")
        is_conversational = bool(classification.get("conversational", False))
        direct_response = classification.get("direct_response")
        mentions = classification.get("mentions") or []

        await self.audit_log.log("planner_decision", {
            "stage": "classify_goal",
            "thread_id": state.get("thread_id"),
            "normalized_goal": normalized_goal,
            "blocked": is_blocked,
            "block_reason": block_reason,
            "conversational": is_conversational,
            "mentions": mentions,
        })

        updates: dict = {"normalized_goal": normalized_goal, "mentions": mentions}

        if is_blocked:
            updates["stop_reason"] = "blocked"
            updates["final_response"] = (
                f"I cannot process this request: {block_reason or 'policy violation.'}"
            )
            updates["risk_assessment"] = {
                "level": "high",
                "reasons": [block_reason or "intent blocked by policy"],
                "blocking": True,
            }
        elif is_conversational:
            updates["stop_reason"] = "responded"
            updates["final_response"] = direct_response or "Hello! How can I help you manage your Instagram accounts?"

        return updates

    async def plan_actions_node(self, state: OperatorCopilotState) -> dict:
        """Produce an execution plan and proposed tool calls."""
        normalized_goal = state.get("normalized_goal") or state.get("operator_request", "")
        mentions = state.get("mentions") or []
        tool_schemas = self.tool_executor.get_schemas()
        runtime_context = await self._planner_runtime_context(thread_id=state.get("thread_id"))
        memory_ns = await self._resolve_copilot_memory_namespace(
            state,
            runtime_context=runtime_context,
        )

        user_payload: dict = {
            "goal": normalized_goal,
            "available_tools": _planner_visible_tool_schemas(tool_schemas),
        }
        if mentions:
            user_payload["mentioned_accounts"] = mentions
        if runtime_context:
            user_payload.update(runtime_context)

        if self.copilot_memory is not None:
            try:
                recent = await self.copilot_memory.recall_recent_interactions(memory_ns, limit=5)
                if recent:
                    user_payload["recent_interactions"] = [
                        {
                            "goal": record.get("goal", ""),
                            "tools_used": record.get("tools_used", []),
                            "outcome": record.get("outcome", ""),
                        }
                        for record in recent
                    ]
            except Exception:
                logger.warning("Failed to recall copilot memory, proceeding without context")

        messages = [
            {"role": "system", "content": _PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ]

        try:
            response = await self.llm_gateway.request_completion(
                messages=messages,
                **self._llm_request_kwargs(state),
            )
            raw = response.get("content", "{}")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0].strip()
            plan_data = json.loads(raw)
        except Exception as exc:
            plan_data = {
                "execution_plan": [],
                "proposed_tool_calls": [],
                "_parse_error": str(exc),
            }

        execution_plan = plan_data.get("execution_plan", [])
        proposed_tool_calls = plan_data.get("proposed_tool_calls", [])

        proposed_tool_calls, dropped_tool_calls = _sanitize_proposed_tool_calls(
            proposed_tool_calls,
            tool_schemas,
        )

        await self.audit_log.log("planner_decision", {
            "stage": "plan_actions",
            "thread_id": state.get("thread_id"),
            "execution_plan": execution_plan,
            "proposed_tool_calls": proposed_tool_calls,
            "dropped_tool_calls": dropped_tool_calls,
            "runtime_context_keys": sorted(runtime_context.keys()),
            "copilot_memory_namespace": memory_ns,
        })

        return {
            "execution_plan": execution_plan,
            "proposed_tool_calls": proposed_tool_calls,
            "copilot_memory_namespace": memory_ns,
        }

    async def review_tool_policy_node(self, state: OperatorCopilotState) -> dict:
        """Classify each proposed tool call and compute aggregate risk."""
        proposed = state.get("proposed_tool_calls", [])

        executable = self.policy_registry.filter_executable(proposed)
        blocked_names = [
            call["name"] for call in proposed
            if self.policy_registry.classify(call["name"]).policy == ToolPolicy.BLOCKED
        ]

        flags = self.policy_registry.classify_calls(executable)

        risk_reasons = []
        if blocked_names:
            risk_reasons.append(f"blocked tools stripped: {blocked_names}")

        write_sensitive = [
            call["name"] for call in executable
            if flags.get(call["id"]) == ToolPolicy.WRITE_SENSITIVE.value
        ]
        if write_sensitive:
            risk_reasons.append(f"write-sensitive tools require approval: {write_sensitive}")

        risk_level = (
            "high" if blocked_names
            else "medium" if write_sensitive
            else "low"
        )

        risk_assessment = {
            "level": risk_level,
            "reasons": risk_reasons,
            "blocking": bool(blocked_names and not executable),
        }

        await self.audit_log.log("policy_gate", {
            "thread_id": state.get("thread_id"),
            "proposed_count": len(proposed),
            "blocked_names": blocked_names,
            "executable_count": len(executable),
            "flags": flags,
            "risk_assessment": risk_assessment,
        })

        return {
            "proposed_tool_calls": executable,
            "approved_tool_calls": executable,
            "tool_policy_flags": flags,
            "risk_assessment": risk_assessment,
        }


__all__ = ["OperatorCopilotPlanPolicyNodes"]
