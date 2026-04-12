"""Tool Registry Bridge — bridges app ToolRegistry to ToolExecutorPort.

This adapter is the explicit mapping layer required by todo-5:
  "Adapter boleh menjembatani tool lama dari backend/ai_tools.py, tetapi
   harus ada lapisan pemetaan: nama tool, schema argumen, klasifikasi policy,
   apakah read-only atau write-sensitive, apakah perlu approval"

Responsibilities:
1. get_schemas() — return only non-BLOCKED tool schemas; annotate each schema
   with its policy classification so the LLM planner sees risk in the tool
   description and can include it in the execution plan.

2. execute() — second-line defense: reject BLOCKED tools even if the graph's
   review_tool_policy_node somehow passes one through.

3. Name mapping — ToolPolicyRegistry uses the same names as the app's
   ToolRegistry (both indexed by the handler name, e.g. "list_accounts").
   If a tool in the registry is not in ToolPolicyRegistry, it is treated as
   BLOCKED (deny-unknown principle).

Contrast with PolicyAwareToolExecutor (generic bridge, can be instantiated
anywhere). ToolRegistryBridgeAdapter is the operator-copilot-specific bridge
that annotates schemas with approval hints for the LLM planner.
"""

from __future__ import annotations

import copy
import logging
from typing import Any
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from ai_copilot.application.ports import ToolExecutorPort
from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry

if TYPE_CHECKING:
    from app.adapters.ai.tool_registry import ToolRegistry


# Policy annotation appended to tool descriptions for LLM awareness
_POLICY_SUFFIXES: dict[str, str] = {
    ToolPolicy.READ_ONLY.value: " [read-only: no approval needed]",
    ToolPolicy.WRITE_SENSITIVE.value: " [write-sensitive: requires operator approval]",
    ToolPolicy.BLOCKED.value: " [BLOCKED: not available]",
}


class ToolRegistryBridgeAdapter(ToolExecutorPort):
    """Bridges app ToolRegistry to ToolExecutorPort for operator copilot.

    Key properties:
    - Only non-BLOCKED tools are exposed to the LLM via get_schemas().
    - Schemas are annotated with policy hints so the planner can reason about
      which tools need approval vs. which are safe to call immediately.
    - execute() enforces policy as a second-line defense.
    - Unknown tools (not in ToolPolicyRegistry) are treated as BLOCKED.

    Args:
        tool_registry: App's ToolRegistry (provides execute() + get_schemas()).
        policy_registry: Tool classification registry.
                         Defaults to ToolPolicyRegistry() if not supplied.
        annotate_schemas: If True (default), append policy suffixes to tool
                          descriptions. Set False in tests to keep descriptions clean.
    """

    def __init__(
        self,
        tool_registry: "ToolRegistry",
        policy_registry: ToolPolicyRegistry | None = None,
        annotate_schemas: bool = True,
    ) -> None:
        self._tool_registry = tool_registry
        self._policy_registry = policy_registry or ToolPolicyRegistry()
        self._annotate = annotate_schemas
        # Cache computed schemas (tool registry is static after startup)
        self._cached_schemas: list[dict] | None = None

    # ── ToolExecutorPort interface ─────────────────────────────────────────────

    async def execute(self, tool_name: str, args: dict) -> dict:
        """Execute a tool after second-line policy check.

        Args:
            tool_name: Tool identifier.
            args: Tool arguments dict.

        Returns:
            Tool result dict.

        Raises:
            ValueError: If tool is BLOCKED or unknown.
        """
        classification = self._policy_registry.classify(tool_name)

        if classification.policy == ToolPolicy.BLOCKED:
            raise ValueError(
                f"Execution blocked: '{tool_name}' is classified as BLOCKED "
                f"({classification.reason}). "
                "This call should have been filtered by review_tool_policy_node."
            )

        return await self._tool_registry.execute(tool_name, args)

    async def get_planner_context(self) -> dict[str, Any]:
        """Return compact runtime context that helps the planner stay grounded.

        The planner needs to know which managed accounts exist, their status,
        and basic metrics so it can select the right acting account and avoid
        inventing usernames or guessing IDs.

        If account retrieval fails, returns a diagnostic hint so the planner
        can suggest list_accounts as a first step.
        """
        if self._policy_registry.classify("list_accounts").policy == ToolPolicy.BLOCKED:
            return {}

        try:
            summary = await self._tool_registry.execute("list_accounts", {})
        except Exception:
            logger.exception("get_planner_context: list_accounts failed")
            return {
                "managed_accounts": [],
                "managed_account_count": 0,
                "context_error": "Could not load managed accounts. Consider calling list_accounts as the first step.",
            }

        if not isinstance(summary, dict):
            return {}

        accounts = summary.get("accounts")
        if not isinstance(accounts, list):
            return {}

        compact_accounts: list[dict[str, Any]] = []
        for raw_account in accounts[:25]:
            if not isinstance(raw_account, dict):
                continue
            username = str(raw_account.get("username") or "").strip().lstrip("@")
            if not username:
                continue
            proxy = str(raw_account.get("proxy") or "").strip()
            followers = raw_account.get("followers")
            following = raw_account.get("following")
            entry: dict[str, Any] = {
                "username": f"@{username}",
                "status": raw_account.get("status") or "unknown",
                "proxy": "configured" if proxy and proxy.lower() != "none" else "none",
            }
            if isinstance(followers, int):
                entry["followers"] = followers
            if isinstance(following, int):
                entry["following"] = following
            compact_accounts.append(entry)

        total = summary.get("total")
        active = summary.get("active")
        return {
            "managed_accounts": compact_accounts,
            "managed_account_count": int(total) if isinstance(total, int) else len(compact_accounts),
            "active_account_count": int(active) if isinstance(active, int) else None,
        }

    def get_schemas(self) -> list[dict]:
        """Return non-BLOCKED tool schemas with optional policy annotations.

        Filters out BLOCKED tools (including unknown tools). Annotates each
        remaining schema's description with the policy classification so the
        LLM planner can incorporate approval requirements into its plan.

        Returns:
            List of OpenAI function-calling format schema dicts.
        """
        if self._cached_schemas is not None:
            return self._cached_schemas

        raw_schemas = self._tool_registry.get_schemas()
        result = []

        for schema in raw_schemas:
            name = _extract_name(schema)
            if not name:
                continue

            classification = self._policy_registry.classify(name)
            if classification.policy == ToolPolicy.BLOCKED:
                continue  # never expose blocked tools to LLM

            if self._annotate:
                schema = _annotate_schema(schema, classification.policy)

            result.append(schema)

        self._cached_schemas = result
        return result

    # ── Introspection helpers ──────────────────────────────────────────────────

    def get_policy_summary(self) -> dict[str, str]:
        """Return a mapping of tool_name → policy value for all registered tools.

        Useful for debugging and for the API's /info endpoint.
        """
        return {
            _extract_name(s): self._policy_registry.classify(_extract_name(s)).policy.value
            for s in self._tool_registry.get_schemas()
            if _extract_name(s)
        }

    def get_policy_coverage_report(self) -> dict[str, object]:
        """Return machine-readable policy/registry parity coverage report."""
        registered_names = {
            _extract_name(schema)
            for schema in self._tool_registry.get_schemas()
            if _extract_name(schema)
        }
        return self._policy_registry.build_parity_report(registered_names)

    def invalidate_schema_cache(self) -> None:
        """Force recomputation of schemas on next get_schemas() call."""
        self._cached_schemas = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_name(schema: dict) -> str:
    """Extract tool name from OpenAI function-calling schema or flat schema."""
    return (
        schema.get("function", {}).get("name")
        or schema.get("name")
        or ""
    )


def _annotate_schema(schema: dict, policy: ToolPolicy) -> dict:
    """Return a shallow-copied schema with policy suffix in the description.

    Appends the policy classification to the tool's description string so the
    LLM planner can factor approval requirements into its execution plan.

    Never mutates the original schema.
    """
    suffix = _POLICY_SUFFIXES.get(policy.value, "")
    if not suffix:
        return schema

    schema = copy.deepcopy(schema)

    if "function" in schema:
        fn = schema["function"]
        fn["description"] = fn.get("description", "") + suffix
    elif "description" in schema:
        schema["description"] = schema["description"] + suffix

    return schema
