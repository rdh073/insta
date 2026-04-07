"""Concrete LLMGatewayPort backed by AIGateway (OpenAI-compatible).

All vendor-to-state mapping lives here.  Nodes never import this file directly;
they receive an LLMGatewayPort at construction time.
"""

from __future__ import annotations

import json
import re

from app.adapters.ai.openai_gateway import AIGateway, ProviderConfig


class LLMGatewayAdapter:
    """LLMGatewayPort implementation that wraps AIGateway.

    Translates structured node requests into LLM API calls and maps
    raw vendor responses back to plain Python types.
    """

    def __init__(
        self,
        ai_gateway: AIGateway,
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> None:
        self._gateway = ai_gateway
        self._provider = provider
        self._model = model or ProviderConfig.get_default_model(provider)
        self._api_key = api_key
        self._provider_base_url = provider_base_url

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _complete(self, messages: list[dict]) -> str:
        """Single completion call, returns plain text."""
        response = await self._gateway.request_completion(
            messages=messages,
            provider=self._provider,
            model=self._model,
            api_key=self._api_key,
            provider_base_url=self._provider_base_url,
        )
        return (response.content or "").strip()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract the first JSON object found in *text*."""
        # Try to find JSON block (possibly wrapped in markdown fences)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON object found in LLM response: {text!r}")

    # ── LLMGatewayPort ───────────────────────────────────────────────────────

    async def classify_request(
        self,
        user_request: str,
        messages: list[dict],
    ) -> str:
        """Return 'direct_answer' or 'tool_lookup'."""
        classify_prompt = {
            "role": "user",
            "content": (
                "Classify the following operator request.\n"
                "Reply with EXACTLY one of: direct_answer  tool_lookup\n"
                "- direct_answer: you can answer from memory/context alone.\n"
                "- tool_lookup: a backend tool must be called to get real data.\n\n"
                f"Request: {user_request}"
            ),
        }
        raw = await self._complete(messages + [classify_prompt])
        if "tool_lookup" in raw.lower():
            return "tool_lookup"
        return "direct_answer"

    async def plan_read_only_action(
        self,
        user_request: str,
        allowed_tools: list[str],
        messages: list[dict],
    ) -> tuple[str, dict]:
        """Return (tool_name, tool_args) for one backend tool call."""
        plan_prompt = {
            "role": "user",
            "content": (
                f"Pick exactly ONE tool from this list: {allowed_tools}\n"
                f"to answer: {user_request!r}\n\n"
                "Respond with ONLY a JSON object, no prose:\n"
                '{"tool": "<tool_name>", "args": {<key>: <value>}}'
            ),
        }
        raw = await self._complete(messages + [plan_prompt])
        try:
            parsed = self._extract_json(raw)
            tool_name = str(parsed.get("tool", ""))
            tool_args = dict(parsed.get("args", {}))
        except (ValueError, KeyError, TypeError):
            # Fallback: use first allowed tool with empty args
            tool_name = allowed_tools[0] if allowed_tools else ""
            tool_args = {}
        return tool_name, tool_args

    async def summarize_result(
        self,
        user_request: str,
        tool_results: list[dict],
        messages: list[dict],
    ) -> str:
        """Return a human-readable answer from tool results."""
        results_text = json.dumps(tool_results, ensure_ascii=False, indent=2)
        summarize_prompt = {
            "role": "user",
            "content": (
                f"The operator asked: {user_request!r}\n\n"
                f"Tool results:\n{results_text}\n\n"
                "Write a concise, natural-language answer for the operator."
            ),
        }
        return await self._complete(messages + [summarize_prompt])
