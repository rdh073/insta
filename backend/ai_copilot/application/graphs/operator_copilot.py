"""Full operator copilot graph — 9-node topology with approval gating.

Topology (todo-4 spec):

  START
    → ingest_request
    → classify_goal
      [blocked intent]         → summarize_result → finish → END
    → plan_actions
      [no valid tool calls]    → summarize_result → finish → END
    → review_tool_policy
      [all read_only]          → execute_tools
      [write_sensitive]        → request_approval_if_needed
        [approved]             → execute_tools
        [edited]               → review_tool_policy   (re-validate)
        [rejected/timeout]     → summarize_result → finish → END
    → execute_tools
    → review_results
    → summarize_result
    → finish
    → END

Routing invariants (from todo-4):
- Blocked intent routes immediately to summarize_result (no planning).
- No valid tool calls from planner routes to summarize_result.
- All-read-only calls skip approval entirely.
- Write-sensitive calls MUST go through request_approval_if_needed.
- Only "approved" or "edited+re-validated" calls reach execute_tools.
- "edited" calls re-enter review_tool_policy before execution.
- Rejection closes the run; no automatic replanning.
- review_results always leads to summarize_result (with optional warning flag).
- Loop is bounded: one planning pass and one execution pass per run.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

logger = logging.getLogger(__name__)

from ai_copilot.application.state import OperatorCopilotState
from ai_copilot.application.ports import (
    CopilotMemoryPort,
    LLMGatewayPort,
    ToolExecutorPort,
    ApprovalPort,
    AuditLogPort,
    validate_approval_payload,
)
from ai_copilot.application.operator_copilot_policy import (
    ToolPolicy,
    ToolPolicyRegistry,
)

if TYPE_CHECKING:
    pass

# ── Constants ──────────────────────────────────────────────────────────────────

_BLOCKED_CATEGORIES = {
    "spam",
    "mass_action",
    "account_deletion",
    "tos_violation",
    "scraping",
}

_CLASSIFY_SYSTEM_PROMPT = """\
You are the intent classifier for an Instagram multi-account management copilot.
Operators manage many Instagram accounts simultaneously from a single dashboard.
They may write in any language (English, Bahasa Indonesia, etc.) — always parse intent regardless of language.

## @mention convention
Operators use @username to reference accounts. Extract every @mention in the request.
If no @mention is present but the request implies an account, leave mentions empty — do NOT guess.

## Output
Produce a JSON object with these fields:
  - normalized_goal: one sentence restating the operator's intent in English, including any @mentions verbatim
  - category: one of:
      "account_management"  — login, logout, proxy, session, account info
      "content_read"        — view posts, media, stories, highlights, collections
      "content_write"       — publish, schedule, delete posts/stories/highlights
      "engagement_read"     — view followers, following, likes, comments, insights
      "engagement_write"    — follow, unfollow, like, unlike, comment, DM
      "discovery"           — hashtag search, location search, explore
      "analytics"           — insights, metrics, engagement stats
      "conversational"      — greeting, thanks, help question, chit-chat
  - mentions: list of @usernames found in the request (e.g. ["user1", "user2"]), empty list if none
  - conversational: true ONLY when the message needs zero Instagram tool execution.
    Examples: "hi", "thanks", "what can you do?", "explain how scheduling works".
    Counter-examples (NOT conversational): "how many followers does @x have?" — this requires a tool.
  - direct_response: if conversational is true, a short helpful reply in the SAME language as the request; otherwise null
  - blocked: true if the request involves any of:
      spam, mass follow/unfollow, bulk DM, account deletion, credential harvesting,
      impersonation, phishing, ToS violations, bulk scraping, automated engagement farming
  - block_reason: explanation if blocked; null otherwise

Respond with ONLY the JSON object. No markdown fences."""

_PLAN_SYSTEM_PROMPT = """\
You are the execution planner for an Instagram multi-account management copilot.

## Runtime payload you receive
- goal: normalized operator goal
- mentioned_accounts: raw @mentions extracted from the request
- managed_accounts: dashboard accounts currently available to act as `username` \
  (includes status, followers, following counts when available)
- available_tools: tool schemas with policy hints and parameter guidance
- recent_interactions (optional): summaries of past copilot runs — use these to \
  avoid repeating failed actions or to reference prior results
- context_error (optional): if present, account data could not be loaded — \
  suggest list_accounts as the first step

## Account model — critical
Most tools require a `username` parameter. This is the ACTING managed account — \
the logged-in dashboard account that will perform the API call. It is NOT the target \
user being looked up or acted on.
- Only choose `username` values from `managed_accounts`. Never invent acting accounts.
- `target_username` / `recipient_username` refer to external Instagram users.
- When the operator says "check followers of @alice using @bob", @bob is the acting \
  account (`username`) and @alice is the target.
- When multiple @mentions appear and only one of them exists in `managed_accounts`, \
  that managed account is the acting `username`; the other mentions are targets.
- When a read request mentions exactly one @username and it is also a managed account, \
  it can be both acting account and target.
- When no managed account can be resolved for a tool that requires `username`, do NOT guess. \
  Prefer a single `list_accounts` call if that can clarify the next step; otherwise return empty tool calls.

## Output
Produce a JSON object with:
  - execution_plan: list of steps, each {step, tool, reason, risk_level}
  - proposed_tool_calls: list of calls, each {id, name, arguments}

## Rules
1. Use ONLY tools listed in the provided schemas. Match parameter names exactly.
2. Assign unique ids: "c1", "c2", etc.
3. risk_level: "low" (read-only), "medium" (writes affecting own account), "high" (writes affecting others).
4. Every required argument MUST come from the operator's request or from known context — \
   never fabricate values.
5. NEVER use placeholder references: no PLACEHOLDER_*, result_of_c1, <list_of_ids>, \
   account_id_from_list, or any synthetic forward-reference.
6. **Stop-and-resolve rule**: If step B depends on step A's output (e.g., you need a \
   user_id, thread_id, or media_pk that is not yet known), emit ONLY step A. \
   Do NOT emit step B — the system will re-plan after A completes. \
   This is the single most important rule. Violating it causes execution failures.
7. For identifier parameters such as user_id, media_pk, media_id, thread_id, message_id, \
   highlight_pk, and story_ids, only use exact values that are explicitly known. \
   If unknown, stop at the discovery step; do not jump ahead to a write.
8. Prefer the smallest set of tools that answers the request.
9. When the operator asks about "all accounts" or "every account", emit a single \
   list_accounts call first — do not expand into per-account calls.
10. If the request includes attached raw text and a tool accepts a free-form `text` field \
    such as `import_proxies.text`, pass the attached text exactly instead of paraphrasing it.
11. Follow the tool-level parameter guidance in `available_tools`. If a note says a field is \
    the acting managed account or requires a prior lookup, obey it.
12. If the goal cannot be achieved with known arguments, return empty lists and do NOT \
    generate speculative calls.
13. If `recent_interactions` shows that a similar goal recently failed, adjust your approach \
    (e.g., try a different tool or suggest a prerequisite step). Do not blindly repeat \
    a plan that already failed.

Respond with ONLY the JSON object. No markdown fences."""

_REVIEW_SYSTEM_PROMPT = """\
You are the result reviewer for an Instagram multi-account management copilot.
Given the operator's intent, the execution plan, and tool results, assess whether \
the results actually satisfy the request.

## Checks to perform
1. **Error detection**: if any result contains an "error" key, flag it.
2. **Completeness**: did every planned tool return data? Flag missing results.
3. **Empty results**: if a tool returned empty data (0 posts, 0 followers, etc.) where \
   results were expected, that is a warning, not a success.
4. **Partial success**: if some tools succeeded and others failed, report both.
5. **Intent match**: do the returned data fields actually answer what the operator asked? \
   e.g., they asked for followers but got media — that is a mismatch.
6. **Data staleness**: if results contain timestamps far in the past relative to a \
   time-sensitive request, flag it.

## Output
Produce a JSON object with:
  - matched_intent: true if at least one result meaningfully addresses the request; false otherwise
  - warnings: list of specific concern strings (empty list if none). Be concrete: \
    "get_user_medias returned 0 posts" not "results may be incomplete".
  - recommendation: "proceed_to_summary" or "summarize_with_warning"

Respond with ONLY the JSON object. No markdown fences."""

_SUMMARIZE_SYSTEM_PROMPT = """\
You are the response writer for an Instagram multi-account management copilot.
The operator manages many Instagram accounts from a single dashboard.

## Response rules
1. **Language**: reply in the SAME language the operator used. If they wrote in Bahasa \
   Indonesia, reply in Bahasa Indonesia. If English, reply in English.
2. **No fabrication**: only report data present in the tool results. If data is missing, \
   say so — do not invent numbers.
3. **Account references**: always prefix usernames with @ (e.g., @alice).
4. **Numbers**: format large numbers readably (e.g., 12.4K, 1.2M). Include exact \
   numbers in parentheses for important metrics (e.g., 12.4K (12,389) followers).
5. **Errors**: if any tool failed, explain the failure clearly and suggest what the \
   operator can try (e.g., "check if the account is still logged in").
6. **Warnings**: if the reviewer flagged warnings, incorporate them naturally — \
   don't hide issues from the operator.
7. **Structure**: for list data (followers, posts, etc.) use a clean format. \
   For single-value answers, be brief. For analytics, highlight key takeaways first.
8. **Actionable insight**: when data suggests something notable (engagement drop, \
   unusual metrics, proxy issues), mention it concisely.
9. **Length**: be concise. 2-5 sentences for simple queries. Use bullet points for \
   lists exceeding 3 items. Never exceed 500 words."""


def _planner_visible_tool_schemas(tool_schemas: list[dict]) -> list[dict]:
    """Return compact schema details that help the planner choose valid arguments."""
    visible: list[dict] = []

    for schema in tool_schemas:
        function = schema.get("function", {})
        parameters = function.get("parameters", {})
        properties = parameters.get("properties", {}) or {}
        description = function.get("description", "")

        visible.append({
            "name": function.get("name"),
            "description": description,
            "policy": _extract_policy_hint(description),
            "required": list(parameters.get("required", []) or []),
            "parameters": {
                key: {
                    "type": value.get("type"),
                    "description": value.get("description", ""),
                    "enum": value.get("enum"),
                    "items_type": (value.get("items") or {}).get("type"),
                }
                for key, value in properties.items()
            },
            "parameter_notes": {
                key: note
                for key, value in properties.items()
                if (note := _parameter_planning_note(key, value))
            },
            "planning_hints": _tool_planning_hints(function.get("name", ""), properties),
        })

    return visible


def _extract_policy_hint(description: str) -> str | None:
    """Extract the policy suffix injected by ToolRegistryBridgeAdapter."""
    normalized = description.lower()
    if "[read-only:" in normalized:
        return "read_only"
    if "[write-sensitive:" in normalized:
        return "write_sensitive"
    if "[blocked:" in normalized:
        return "blocked"
    return None


def _parameter_planning_note(key: str, value: dict) -> str | None:
    """Provide deterministic planning guidance for ambiguous argument names."""
    notes = {
        "username": "Acting managed account username. Must come from managed_accounts.",
        "target_username": "External Instagram target username. Do not use as acting username unless it is also in managed_accounts.",
        "recipient_username": "External Instagram recipient username.",
        "usernames": "List of managed account usernames that should act on the request.",
        "participant_usernames": "External participants for a DM thread. Do not include the acting account unless the operator explicitly wants that.",
        "user_id": "Numeric Instagram user ID. Never infer from @username without a prior lookup.",
        "media_pk": "Numeric post ID. Never invent or derive it from memory.",
        "media_id": "Instagram media ID string. Only use an explicitly known value.",
        "thread_id": "Direct message thread ID. Requires a prior lookup unless explicitly provided.",
        "message_id": "Direct message ID. Requires a prior lookup unless explicitly provided.",
        "highlight_pk": "Numeric highlight ID. Requires a prior lookup unless explicitly provided.",
        "story_ids": "List of existing story IDs. Requires a prior lookup unless explicitly provided.",
        "proxy_url": "Exact proxy URL from the request, attached text, or a prior proxy-pool lookup.",
        "text": "Use the operator-provided or attached text exactly when importing or sending content.",
    }
    note = notes.get(key)
    if not note:
        return None

    enum_values = value.get("enum")
    if enum_values:
        return f"{note} Allowed values: {enum_values}."
    return note


def _tool_planning_hints(tool_name: str, properties: dict[str, dict]) -> list[str]:
    """Add compact tool-specific hints that reduce common planner mistakes."""
    hints: list[str] = []

    if tool_name == "list_accounts":
        hints.append("Use first when the acting managed account is ambiguous or the operator asks about all accounts.")
    if tool_name == "import_proxies":
        hints.append("Best fit for pasted or attached newline-separated proxy lists.")
    if tool_name in {"follow_user", "unfollow_user", "send_direct_message"}:
        hints.append("This is a write action; choose it only when the target is explicit.")
    if tool_name in {"get_direct_thread", "list_direct_messages", "send_message_to_thread", "delete_direct_message"}:
        hints.append("Requires a known thread_id before execution.")
    if any(key in properties for key in ("user_id", "media_pk", "media_id", "thread_id", "message_id", "highlight_pk", "story_ids")):
        hints.append("Do not supply unresolved identifiers; stop at the discovery step if needed.")

    return hints


def _is_missing_required_argument(value: Any) -> bool:
    """Return True when a required argument is absent or effectively empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _contains_placeholder_reference(value: Any) -> bool:
    """Detect planner placeholders that cannot be resolved at execution time."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return False
        return (
            "placeholder" in normalized
            or normalized.startswith("result_of_")
            or "_from_list" in normalized
            or (normalized.startswith("<") and normalized.endswith(">"))
        )
    if isinstance(value, list):
        return any(_contains_placeholder_reference(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder_reference(item) for item in value.values())
    return False


def _sanitize_proposed_tool_calls(
    proposed_tool_calls: list[dict],
    tool_schemas: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Drop tool calls with unsupported keys, missing required args, or placeholders."""
    schema_by_name = {
        schema.get("function", {}).get("name"): schema
        for schema in tool_schemas
        if schema.get("function", {}).get("name")
    }

    accepted: list[dict] = []
    dropped: list[dict] = []

    for call in proposed_tool_calls:
        name = call.get("name")
        schema = schema_by_name.get(name)
        if not schema:
            dropped.append({
                "id": call.get("id"),
                "name": name,
                "reason": "unknown_tool",
            })
            continue

        raw_args = call.get("arguments", {})
        if not isinstance(raw_args, dict):
            dropped.append({
                "id": call.get("id"),
                "name": name,
                "reason": "arguments_must_be_object",
            })
            continue

        parameters = schema.get("function", {}).get("parameters", {})
        properties = parameters.get("properties", {}) or {}
        allowed_keys = set(properties.keys())
        required_keys = list(parameters.get("required", []) or [])

        sanitized_args = raw_args
        unknown_keys: list[str] = []
        if allowed_keys:
            unknown_keys = sorted(set(raw_args.keys()) - allowed_keys)
            sanitized_args = {key: value for key, value in raw_args.items() if key in allowed_keys}

        missing_required = [
            key for key in required_keys
            if _is_missing_required_argument(sanitized_args.get(key))
        ]

        if missing_required:
            dropped.append({
                "id": call.get("id"),
                "name": name,
                "reason": "missing_required_arguments",
                "missing": missing_required,
            })
            continue

        if unknown_keys and not sanitized_args:
            dropped.append({
                "id": call.get("id"),
                "name": name,
                "reason": "unsupported_argument_keys",
                "unknown_keys": unknown_keys,
            })
            continue

        if _contains_placeholder_reference(sanitized_args):
            dropped.append({
                "id": call.get("id"),
                "name": name,
                "reason": "placeholder_arguments",
            })
            continue

        accepted_call = dict(call)
        accepted_call["arguments"] = sanitized_args
        accepted.append(accepted_call)

    return accepted, dropped


# ── Nodes ──────────────────────────────────────────────────────────────────────


class OperatorCopilotNodes:
    """Node functions for the full operator copilot graph.

    Depends on ports only — no concrete framework or vendor imports.
    Every decision point logs to AuditLogPort before acting.
    """

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
        """Build provider overrides for LLM calls from persisted thread state."""
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

    async def _planner_runtime_context(self) -> dict:
        """Load optional runtime context for the planner without widening the port contract."""
        context_getter = getattr(self.tool_executor, "get_planner_context", None)
        if not callable(context_getter):
            return {}

        try:
            context = await context_getter()
        except Exception as exc:
            await self.audit_log.log("planner_decision", {
                "stage": "plan_actions_context",
                "context_available": False,
                "error": str(exc),
            })
            return {}

        if not isinstance(context, dict):
            return {}
        return context

    # ── Node: ingest_request ──────────────────────────────────────────────────

    async def ingest_request_node(self, state: OperatorCopilotState) -> dict:
        """Receive and record the raw operator request.

        Increments step_count and logs the initial operator_request audit event.
        Does NOT call LLM — pure state normalization.
        """
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
            "approval_attempted": False,   # reset loop-bound flag for fresh run
        }

    # ── Node: classify_goal ───────────────────────────────────────────────────

    async def classify_goal_node(self, state: OperatorCopilotState) -> dict:
        """Classify the operator request: normalize goal and detect blocked intent.

        LLM call. Result determines whether planning proceeds or is skipped.
        """
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
            # Strip markdown code fences that some providers (e.g. Gemini) add
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

    # ── Node: plan_actions ────────────────────────────────────────────────────

    async def plan_actions_node(self, state: OperatorCopilotState) -> dict:
        """Produce an execution plan and proposed tool calls.

        LLM call. Passes tool schemas so the model can only reference real tools.
        """
        normalized_goal = state.get("normalized_goal") or state.get("operator_request", "")
        mentions = state.get("mentions") or []
        tool_schemas = self.tool_executor.get_schemas()
        runtime_context = await self._planner_runtime_context()

        user_payload: dict = {
            "goal": normalized_goal,
            "available_tools": _planner_visible_tool_schemas(tool_schemas),
        }
        if mentions:
            user_payload["mentioned_accounts"] = mentions
        if runtime_context:
            user_payload.update(runtime_context)

        # Inject recent interaction history from cross-thread memory
        if self.copilot_memory is not None:
            try:
                memory_ns = state.get("thread_id", "default")[:36]  # use thread prefix as namespace
                recent = await self.copilot_memory.recall_recent_interactions(memory_ns, limit=5)
                if recent:
                    user_payload["recent_interactions"] = [
                        {"goal": r.get("goal", ""), "tools_used": r.get("tools_used", []), "outcome": r.get("outcome", "")}
                        for r in recent
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
            "execution_plan": execution_plan,
            "proposed_tool_calls": proposed_tool_calls,
            "dropped_tool_calls": dropped_tool_calls,
            "runtime_context_keys": sorted(runtime_context.keys()),
        })

        return {
            "execution_plan": execution_plan,
            "proposed_tool_calls": proposed_tool_calls,
        }

    # ── Node: review_tool_policy ──────────────────────────────────────────────

    async def review_tool_policy_node(self, state: OperatorCopilotState) -> dict:
        """Classify each proposed tool call and compute aggregate risk.

        No LLM call — pure registry lookup. Populates tool_policy_flags and
        risk_assessment. Blocked calls are stripped from proposed_tool_calls.
        """
        proposed = state.get("proposed_tool_calls", [])

        # Strip blocked calls before further routing
        executable = self.policy_registry.filter_executable(proposed)
        blocked_names = [
            c["name"] for c in proposed
            if self.policy_registry.classify(c["name"]).policy == ToolPolicy.BLOCKED
        ]

        flags = self.policy_registry.classify_calls(executable)

        risk_reasons = []
        if blocked_names:
            risk_reasons.append(f"blocked tools stripped: {blocked_names}")

        write_sensitive = [
            c["name"] for c in executable
            if flags.get(c["id"]) == ToolPolicy.WRITE_SENSITIVE.value
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
            "proposed_count": len(proposed),
            "blocked_names": blocked_names,
            "executable_count": len(executable),
            "flags": flags,
            "risk_assessment": risk_assessment,
        })

        return {
            "proposed_tool_calls": executable,
            # Pre-populate approved_tool_calls with all executable calls.
            # For the read_only path these are final (no approval needed).
            # For the write_sensitive path, request_approval_if_needed_node
            # will confirm or replace them based on operator decision.
            "approved_tool_calls": executable,
            "tool_policy_flags": flags,
            "risk_assessment": risk_assessment,
        }

    # ── Node: request_approval_if_needed ─────────────────────────────────────

    async def request_approval_if_needed_node(self, state: OperatorCopilotState) -> dict:
        """Interrupt execution to request operator approval for write-sensitive calls.

        Builds self-contained approval payload, logs it, then calls interrupt().
        The graph resumes when the caller provides Command(resume=...).

        Loop-bound invariant: approval is attempted at most once per run.
        If already attempted (e.g. after an edited → re-validate cycle brought
        us back here), close the run rather than looping infinitely.
        """
        # Loop-bound: max 1 approval attempt per run
        if state.get("approval_attempted"):
            await self.audit_log.log("stop_reason", {
                "stop_reason": "approval_limit_reached",
                "thread_id": state.get("thread_id"),
                "reason": "Approval already attempted this run. Rejection is final.",
            })
            return {
                "stop_reason": "rejected",
                "final_response": (
                    "Cannot process: approval already attempted this run. "
                    "Rejection is final. Please start a new session."
                ),
                "approval_attempted": True,
            }

        proposed = state.get("proposed_tool_calls", [])
        flags = state.get("tool_policy_flags", {})
        risk = state.get("risk_assessment") or {}
        execution_plan = state.get("execution_plan") or []

        # Build reasons map from execution_plan
        plan_by_tool: dict[str, str] = {}
        for step in execution_plan:
            name = step.get("tool", "")
            reason = step.get("reason", "")
            if name and reason:
                plan_by_tool[name] = reason

        tool_reasons = {
            call["id"]: plan_by_tool.get(call["name"], "no reason provided")
            for call in proposed
        }

        approval_request = {
            "operator_intent": state.get("normalized_goal") or state.get("operator_request", ""),
            "proposed_tool_calls": proposed,
            "tool_reasons": tool_reasons,
            "risk_assessment": risk,
            "options": ["approve", "reject", "edit"],
        }

        # Contract enforcement: payload must satisfy ApprovalPort contract before interrupt
        validate_approval_payload(approval_request)

        await self.audit_log.log("approval_submitted", {
            "approval_request": approval_request,
            "thread_id": state.get("thread_id"),
        })

        # Interrupt: pause graph here; resume with operator decision
        decision = interrupt(approval_request)

        # After resume: decision is {"result": "approved"|"rejected"|"edited",
        # "edited_calls": [...]}  (edited_calls present only when result=="edited")
        approval_result = decision.get("result", "rejected") if isinstance(decision, dict) else str(decision)
        edited_calls = decision.get("edited_calls") if isinstance(decision, dict) else None

        await self.audit_log.log("approval_result", {
            "approval_result": approval_result,
            "thread_id": state.get("thread_id"),
        })

        updates: dict = {
            "approval_result": approval_result,
            "approval_request": approval_request,
            "approval_attempted": True,   # loop-bound: no second approval attempt this run
        }

        if approval_result == "approved":
            # Confirm the pre-populated approved_tool_calls (no change needed,
            # but log is already captured above)
            pass

        elif approval_result == "edited" and edited_calls:
            # Re-run sanitization on the operator-supplied edits so that malformed,
            # placeholder, or retargeted arguments cannot reach execution.
            tool_schemas = self.tool_executor.get_schemas()
            sanitized, dropped = _sanitize_proposed_tool_calls(edited_calls, tool_schemas)
            if dropped:
                await self.audit_log.log("edited_calls_sanitized", {
                    "dropped": dropped,
                    "thread_id": state.get("thread_id"),
                })
            updates["proposed_tool_calls"] = sanitized
            updates["approved_tool_calls"] = []  # cleared until review_tool_policy re-approves

        elif approval_result in ("rejected", "timeout"):
            updates["stop_reason"] = "rejected"
            updates["approved_tool_calls"] = []  # clear; nothing should execute
            updates["final_response"] = "Action cancelled by operator."

        return updates

    # ── Node: execute_tools ───────────────────────────────────────────────────

    async def execute_tools_node(self, state: OperatorCopilotState) -> dict:
        """Execute approved tool calls via ToolExecutorPort.

        Only calls in approved_tool_calls are executed. The executor enforces
        its own access control as a second line of defense.
        """
        approved = state.get("approved_tool_calls", [])
        results: dict[str, dict] = {}
        tool_names: dict[str, str] = {}  # call_id → tool_name for stream identity

        for call in approved:
            call_id = call.get("id", "")
            tool_name = call.get("name", "")
            tool_names[call_id] = tool_name
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (TypeError, json.JSONDecodeError):
                    results[call_id] = {"error": f"malformed_arguments: could not parse string arguments for {tool_name!r}"}
                    await self.audit_log.log("execution_skipped", {
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "reason": "malformed_string_arguments",
                    })
                    continue

            try:
                result = await self.tool_executor.execute(tool_name, args)
                results[call_id] = result
                await self.audit_log.log("tool_execution", {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "args": args,
                    "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                })
            except Exception as exc:
                error_result = {"error": str(exc)}
                results[call_id] = error_result
                await self.audit_log.log("execution_failure", {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "error": str(exc),
                })

        return {"tool_results": results, "tool_call_names": tool_names}

    # ── Node: review_results ──────────────────────────────────────────────────

    async def review_results_node(self, state: OperatorCopilotState) -> dict:
        """Review tool results against original intent.

        LLM call. Findings are passed to summarize_result for context.
        Never routes to retry or replanning — mismatch produces a warning only.
        """
        tool_results = state.get("tool_results", {})
        execution_plan = state.get("execution_plan") or []
        intent = state.get("normalized_goal") or state.get("operator_request", "")

        messages = [
            {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "operator_intent": intent,
                    "execution_plan": execution_plan,
                    "tool_results": tool_results,
                }),
            },
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
            findings = json.loads(raw)
        except Exception as exc:
            # Fail closed: a broken or unparseable reviewer must not silently pass
            # results as successful. Mark matched_intent=False so the summarizer
            # knows review did not validate the outcome.
            findings = {
                "matched_intent": False,
                "warnings": [f"reviewer_parse_error: {exc}"],
                "recommendation": "proceed_to_summary",
                "_parse_error": str(exc),
            }

        await self.audit_log.log("review_finding", {
            "matched_intent": findings.get("matched_intent"),
            "warnings": findings.get("warnings", []),
            "recommendation": findings.get("recommendation"),
        })

        return {"review_findings": findings}

    # ── Node: summarize_result ────────────────────────────────────────────────

    async def summarize_result_node(self, state: OperatorCopilotState) -> dict:
        """Produce the final response for the operator.

        LLM call. Uses tool results, plan, and review findings. If stop_reason
        is already set (e.g. "blocked" or "rejected"), returns existing
        final_response without an additional LLM call.
        """
        # If a response was already set by an earlier gate, don't call LLM again.
        # Return the existing final_response so the stream emitter can emit it.
        existing = state.get("final_response")
        stop_reason = state.get("stop_reason")
        if existing and stop_reason in ("blocked", "rejected", "responded"):
            return {"final_response": existing}

        tool_results = state.get("tool_results", {})
        execution_plan = state.get("execution_plan") or []
        review_findings = state.get("review_findings") or {}
        intent = state.get("normalized_goal") or state.get("operator_request", "")
        warnings = review_findings.get("warnings", [])

        messages = [
            {"role": "system", "content": _SUMMARIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "operator_request": intent,
                    "execution_plan": execution_plan,
                    "tool_results": tool_results,
                    "warnings": warnings,
                }),
            },
        ]

        try:
            response = await self.llm_gateway.request_completion(
                messages=messages,
                **self._llm_request_kwargs(state),
            )
            final_response = response.get("content", "")
        except Exception as exc:
            final_response = f"Summary unavailable: {exc}"

        return {"final_response": final_response}

    # ── Node: finish ──────────────────────────────────────────────────────────

    async def finish_node(self, state: OperatorCopilotState) -> dict:
        """Mark run as complete, log stop_reason, and persist interaction to memory."""
        stop_reason = state.get("stop_reason") or "done"
        final_stop = stop_reason if stop_reason != "responded" else "done"

        await self.audit_log.log("stop_reason", {
            "stop_reason": final_stop,
            "thread_id": state.get("thread_id"),
        })

        # Store interaction summary to cross-thread memory
        if self.copilot_memory is not None:
            goal = state.get("normalized_goal") or state.get("operator_request", "")
            tools_used = [c.get("name", "") for c in state.get("approved_tool_calls", [])]
            outcome = "success" if final_stop == "done" and tools_used else final_stop
            try:
                memory_ns = state.get("thread_id", "default")[:36]
                await self.copilot_memory.store_interaction_summary(memory_ns, {
                    "goal": goal,
                    "tools_used": tools_used,
                    "outcome": outcome,
                    "stop_reason": final_stop,
                })
            except Exception:
                logger.warning("Failed to store copilot interaction to memory")

        return {"stop_reason": final_stop}

    # ── Routers ───────────────────────────────────────────────────────────────

    def route_after_classify(self, state: OperatorCopilotState) -> str:
        """After classify_goal: blocked/conversational → summarize_result, else → plan_actions."""
        stop_reason = state.get("stop_reason")
        if stop_reason in ("blocked", "responded"):
            return "summarize_result"
        return "plan_actions"

    def route_after_plan(self, state: OperatorCopilotState) -> str:
        """After plan_actions: no valid calls → summarize_result, else → review_tool_policy."""
        proposed = state.get("proposed_tool_calls", [])
        if not proposed:
            return "summarize_result"
        return "review_tool_policy"

    def route_after_policy(self, state: OperatorCopilotState) -> str:
        """After review_tool_policy:
        - no executable calls → summarize_result
        - all read_only → execute_tools
        - write_sensitive + approval_attempted → execute_tools
          (operator already approved/edited once; no second approval gate)
        - write_sensitive + not yet attempted → request_approval_if_needed

        Loop-bound: if approval was already attempted this run, route
        write_sensitive calls to execute_tools directly. The operator's
        edit decision is treated as implicit approval for the edited calls.
        """
        proposed = state.get("proposed_tool_calls", [])
        if not proposed:
            return "summarize_result"
        if self.policy_registry.all_read_only(proposed):
            return "execute_tools"
        # write_sensitive path
        if state.get("approval_attempted"):
            # Loop-bound: approval already happened; treat edited calls as approved
            return "execute_tools"
        return "request_approval_if_needed"

    def route_after_approval(self, state: OperatorCopilotState) -> str:
        """After request_approval_if_needed:
        - approved → execute_tools
        - edited → review_tool_policy (re-validate modified calls)
        - rejected/timeout/missing → summarize_result
        """
        result = state.get("approval_result")
        if result == "approved":
            return "execute_tools"
        if result == "edited":
            return "review_tool_policy"
        return "summarize_result"


# ── Graph builder ──────────────────────────────────────────────────────────────


def build_operator_copilot_graph(
    nodes: OperatorCopilotNodes,
    checkpointer=None,
    store=None,
):
    """Build and compile the full operator copilot graph (9 nodes).

    Args:
        nodes: OperatorCopilotNodes instance (carries all port dependencies).
        checkpointer: LangGraph checkpointer (required for interrupt/resume).
                      If None, interrupt() will not persist state between calls.
        store: LangGraph Store for cross-thread memory (optional).

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(OperatorCopilotState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("ingest_request",            nodes.ingest_request_node)
    graph.add_node("classify_goal",             nodes.classify_goal_node)
    graph.add_node("plan_actions",              nodes.plan_actions_node)
    graph.add_node("review_tool_policy",        nodes.review_tool_policy_node)
    graph.add_node("request_approval_if_needed", nodes.request_approval_if_needed_node)
    graph.add_node("execute_tools",             nodes.execute_tools_node)
    graph.add_node("review_results",            nodes.review_results_node)
    graph.add_node("summarize_result",          nodes.summarize_result_node)
    graph.add_node("finish",                    nodes.finish_node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    graph.add_edge(START, "ingest_request")
    graph.add_edge("ingest_request", "classify_goal")

    # ── After classify: blocked or plan ──────────────────────────────────────
    graph.add_conditional_edges(
        "classify_goal",
        nodes.route_after_classify,
        {
            "plan_actions":     "plan_actions",
            "summarize_result": "summarize_result",
        },
    )

    # ── After plan: no calls or policy review ─────────────────────────────────
    graph.add_conditional_edges(
        "plan_actions",
        nodes.route_after_plan,
        {
            "review_tool_policy": "review_tool_policy",
            "summarize_result":   "summarize_result",
        },
    )

    # ── After policy: direct execute or approval gate ─────────────────────────
    graph.add_conditional_edges(
        "review_tool_policy",
        nodes.route_after_policy,
        {
            "execute_tools":              "execute_tools",
            "request_approval_if_needed": "request_approval_if_needed",
            "summarize_result":           "summarize_result",
        },
    )

    # ── After approval: execute, re-validate, or close ────────────────────────
    graph.add_conditional_edges(
        "request_approval_if_needed",
        nodes.route_after_approval,
        {
            "execute_tools":      "execute_tools",
            "review_tool_policy": "review_tool_policy",
            "summarize_result":   "summarize_result",
        },
    )

    # ── Linear: execute → review → summarize → finish → END ───────────────────
    graph.add_edge("execute_tools",  "review_results")
    graph.add_edge("review_results", "summarize_result")
    graph.add_edge("summarize_result", "finish")
    graph.add_edge("finish", END)

    # ── Compile ───────────────────────────────────────────────────────────────
    compile_kwargs: dict = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if store is not None:
        compile_kwargs["store"] = store

    return graph.compile(**compile_kwargs)
