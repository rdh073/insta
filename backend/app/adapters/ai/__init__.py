"""AI adapter layer public exports.

Do not re-export deprecated ``app.adapters.ai.tools`` bridges here.
Package import must stay compatible even after the tombstone module is removed.
"""

from .openai_gateway import AIGateway, AIResponse
from .tool_registry import ToolRegistry, create_tool_registry

__all__ = [
    "AIGateway",
    "AIResponse",
    "ToolRegistry",
    "create_tool_registry",
]
