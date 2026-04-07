"""OpenAI Codex OAuth gateway adapter.

Calls the Codex Responses API at chatgpt.com/backend-api/codex/responses
using an OAuth Bearer token and chatgpt-account-id header.

Reference: openai_codex_provider.py (nanobot project)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import TYPE_CHECKING, Any, AsyncGenerator

from .llm_failure_catalog import (
    LLMFailure,
    LLMFailureFamily,
    translate_failure,
)

if TYPE_CHECKING:
    from .codex_oauth_client import CodexOAuthClient
    from .codex_wham import CodexWHAMClient, CodexRateLimitInfo

_CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
_ORIGINATOR = "insta-manager"


class CodexOAuthGateway:
    """OpenAI Codex gateway using the Responses API with OAuth authentication."""

    def __init__(
        self,
        oauth_client: CodexOAuthClient,
        wham_client: CodexWHAMClient | None = None,
    ):
        self.oauth_client = oauth_client
        self.wham_client = wham_client
        self._rate_limit_info: CodexRateLimitInfo | None = None

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai_codex",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        if provider != "openai_codex":
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=f"CodexOAuthGateway only handles openai_codex, got {provider!r}",
                provider=provider,
            )

        model = model or "gpt-5.3-codex"

        try:
            access_token = await self.oauth_client.get_access_token()
        except Exception as e:
            raise translate_failure(
                e,
                LLMFailureFamily.AUTH,
                provider,
                f"Failed to obtain Codex access token: {e}",
            )

        account_id: str | None = None
        get_account_id = getattr(self.oauth_client, "get_account_id", None)
        if callable(get_account_id):
            account_id = get_account_id()

        if self.wham_client is not None:
            try:
                self._rate_limit_info = await self.wham_client.fetch_usage(
                    access_token, account_id=account_id
                )
            except Exception:
                self._rate_limit_info = None

        try:
            response = await self._call_codex_api(
                messages=messages,
                model=model,
                access_token=access_token,
                account_id=account_id,
            )
        except Exception as e:
            family = _classify_error(e)
            raise translate_failure(
                e,
                family,
                provider,
                f"Codex request failed: {e}",
            )

        return {
            "content": response.get("content", ""),
            "finish_reason": response.get("finish_reason", "stop"),
            "tool_calls": response.get("tool_calls", []),
        }

    async def _call_codex_api(
        self,
        messages: list[dict],
        model: str,
        access_token: str,
        account_id: str | None = None,
    ) -> dict:
        system_prompt, input_items = _convert_messages(messages)
        headers = _build_headers(access_token, account_id)

        body: dict[str, Any] = {
            "model": _strip_model_prefix(model),
            "store": False,
            "stream": True,
            "instructions": system_prompt,
            "input": input_items,
            "text": {"verbosity": "medium"},
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": _prompt_cache_key(messages),
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }

        url = os.getenv("OPENAI_CODEX_RESPONSES_URL", _CODEX_RESPONSES_URL).strip()

        try:
            content, tool_calls, finish_reason = await _request_codex(url, headers, body, verify=True)
        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" not in str(e):
                raise
            content, tool_calls, finish_reason = await _request_codex(url, headers, body, verify=False)

        # Normalise tool_calls to OpenAI dict format expected by the rest of the stack
        normalised_tool_calls = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)
                    if isinstance(tc.get("arguments"), dict)
                    else tc.get("arguments", "{}"),
                },
            }
            for tc in tool_calls
        ]

        return {
            "content": content,
            "finish_reason": finish_reason,
            "tool_calls": normalised_tool_calls,
        }

    def get_default_model(self, provider: str) -> str:
        if provider != "openai_codex":
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=f"CodexOAuthGateway only handles openai_codex, got {provider!r}",
                provider=provider,
            )
        return "gpt-5.3-codex"


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------

def _build_headers(access_token: str, account_id: str | None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "OpenAI-Beta": "responses=experimental",
        "originator": _ORIGINATOR,
        "User-Agent": "insta-manager (python)",
        "accept": "text/event-stream",
        "content-type": "application/json",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def _strip_model_prefix(model: str) -> str:
    """Remove openai-codex/ or openai_codex/ prefix if present."""
    if model.startswith(("openai-codex/", "openai_codex/")):
        return model.split("/", 1)[1]
    return model


def _prompt_cache_key(messages: list[dict]) -> str:
    raw = json.dumps(messages, ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _request_codex(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    verify: bool,
) -> tuple[str, list[dict], str]:
    import httpx

    timeout = float(os.getenv("OPENAI_CODEX_API_TIMEOUT_SECONDS", "60"))
    async with httpx.AsyncClient(timeout=timeout, verify=verify) as client:
        async with client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code != 200:
                text = await response.aread()
                raise RuntimeError(_friendly_error(response.status_code, text.decode("utf-8", "ignore")))
            return await _consume_sse(response)


def _friendly_error(status_code: int, raw: str) -> str:
    if status_code == 429:
        return "ChatGPT usage quota exceeded or rate limit triggered."
    if status_code == 401:
        return f"Codex auth failed (401). Re-authenticate via OAuth. {raw[:120]}"
    return f"HTTP {status_code}: {raw[:240]}"


def _classify_error(error: Exception) -> LLMFailureFamily:
    msg = str(error).lower()
    if "401" in msg or "auth" in msg or "token" in msg:
        return LLMFailureFamily.AUTH
    if "429" in msg or "quota" in msg or "rate" in msg:
        return LLMFailureFamily.RATE_LIMIT
    if "500" in msg or "503" in msg or "timeout" in msg:
        return LLMFailureFamily.PROVIDER_UNAVAILABLE
    if "400" in msg or "invalid" in msg:
        return LLMFailureFamily.INVALID_REQUEST
    return LLMFailureFamily.PROVIDER_UNAVAILABLE


# ---------------------------------------------------------------------------
# Message conversion: OpenAI chat format → Codex Responses API input items
# ---------------------------------------------------------------------------

def _convert_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Extract system prompt and convert messages to Codex input items."""
    system_prompt = ""
    input_items: list[dict[str, Any]] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            system_prompt = content if isinstance(content, str) else ""
            continue

        if role == "user":
            input_items.append(_convert_user_message(content))
            continue

        if role == "assistant":
            if isinstance(content, str) and content:
                input_items.append({
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": content}],
                    "status": "completed",
                    "id": f"msg_{idx}",
                })
            for tool_call in msg.get("tool_calls", []) or []:
                fn = tool_call.get("function") or {}
                call_id, item_id = _split_tool_call_id(tool_call.get("id"))
                call_id = call_id or f"call_{idx}"
                item_id = item_id or f"fc_{idx}"
                input_items.append({
                    "type": "function_call",
                    "id": item_id,
                    "call_id": call_id,
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments") or "{}",
                })
            continue

        if role == "tool":
            call_id, _ = _split_tool_call_id(msg.get("tool_call_id"))
            output_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            input_items.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": output_text,
            })
            continue

    return system_prompt, input_items


def _convert_user_message(content: Any) -> dict[str, Any]:
    if isinstance(content, str):
        return {"role": "user", "content": [{"type": "input_text", "text": content}]}
    if isinstance(content, list):
        converted: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                converted.append({"type": "input_text", "text": item.get("text", "")})
            elif item.get("type") == "image_url":
                url = (item.get("image_url") or {}).get("url")
                if url:
                    converted.append({"type": "input_image", "image_url": url, "detail": "auto"})
        if converted:
            return {"role": "user", "content": converted}
    return {"role": "user", "content": [{"type": "input_text", "text": ""}]}


def _split_tool_call_id(tool_call_id: Any) -> tuple[str, str | None]:
    if isinstance(tool_call_id, str) and tool_call_id:
        if "|" in tool_call_id:
            call_id, item_id = tool_call_id.split("|", 1)
            return call_id, item_id or None
        return tool_call_id, None
    return "call_0", None


# ---------------------------------------------------------------------------
# SSE streaming parser
# ---------------------------------------------------------------------------

async def _iter_sse(response: Any) -> AsyncGenerator[dict[str, Any], None]:
    buffer: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if buffer:
                data_lines = [ln[5:].strip() for ln in buffer if ln.startswith("data:")]
                buffer = []
                if not data_lines:
                    continue
                data = "\n".join(data_lines).strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    yield json.loads(data)
                except Exception:
                    continue
            continue
        buffer.append(line)


async def _consume_sse(response: Any) -> tuple[str, list[dict], str]:
    content = ""
    tool_calls: list[dict] = []
    tool_call_buffers: dict[str, dict[str, Any]] = {}
    finish_reason = "stop"

    async for event in _iter_sse(response):
        event_type = event.get("type")

        if event_type == "response.output_item.added":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                call_id = item.get("call_id")
                if call_id:
                    tool_call_buffers[call_id] = {
                        "id": item.get("id") or "fc_0",
                        "name": item.get("name"),
                        "arguments": item.get("arguments") or "",
                    }

        elif event_type == "response.output_text.delta":
            content += event.get("delta") or ""

        elif event_type == "response.function_call_arguments.delta":
            call_id = event.get("call_id")
            if call_id and call_id in tool_call_buffers:
                tool_call_buffers[call_id]["arguments"] += event.get("delta") or ""

        elif event_type == "response.function_call_arguments.done":
            call_id = event.get("call_id")
            if call_id and call_id in tool_call_buffers:
                tool_call_buffers[call_id]["arguments"] = event.get("arguments") or ""

        elif event_type == "response.output_item.done":
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                call_id = item.get("call_id")
                if call_id:
                    buf = tool_call_buffers.get(call_id) or {}
                    args_raw = buf.get("arguments") or item.get("arguments") or "{}"
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {"raw": args_raw}
                    tool_calls.append({
                        "id": f"{call_id}|{buf.get('id') or item.get('id') or 'fc_0'}",
                        "name": buf.get("name") or item.get("name"),
                        "arguments": args,
                    })

        elif event_type == "response.completed":
            status = (event.get("response") or {}).get("status")
            finish_reason = _map_finish_reason(status)

        elif event_type in {"error", "response.failed"}:
            raise RuntimeError("Codex response failed")

    return content, tool_calls, finish_reason


_FINISH_REASON_MAP = {
    "completed": "stop",
    "incomplete": "length",
    "failed": "error",
    "cancelled": "error",
}


def _map_finish_reason(status: str | None) -> str:
    return _FINISH_REASON_MAP.get(status or "completed", "stop")
