"""Anthropic message block filtering."""

from __future__ import annotations


class AnthropicMessageFilter:
    """Filters message blocks to ensure compatibility with Anthropic API.

    Anthropic Messages API supports specific message block types (text, image, tool_result).
    This filter ensures only allowed block types are sent.
    """

    # Allowlisted block types for Anthropic Messages API
    ALLOWED_BLOCK_TYPES = frozenset(
        {
        "text",
        "image",
        "tool_use",
        "tool_result",
        "thinking",
        "redacted_thinking",
        "document",
        }
    )

    def filter_messages(self, messages: list[dict]) -> list[dict]:
        """Filter message blocks to allowlist.

        Args:
            messages: Chat messages with potentially disallowed block types

        Returns:
            Filtered messages with only allowlisted block types

        """
        filtered: list[dict] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if isinstance(content, str):
                filtered.append({"role": role, "content": content})
                continue
            if not isinstance(content, list):
                continue

            next_blocks = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type not in self.ALLOWED_BLOCK_TYPES:
                    continue
                next_blocks.append(block)

            if next_blocks:
                filtered.append({"role": role, "content": next_blocks})
        return filtered
