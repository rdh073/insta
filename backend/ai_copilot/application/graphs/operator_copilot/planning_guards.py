"""Planner visibility and sanitization guards for proposed tool calls."""

from __future__ import annotations

from typing import Any


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
