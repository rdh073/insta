"""Helper module to import the installed langgraph library.

This avoids namespace conflicts between the installed langgraph library
and this backend/langgraph module by explicitly loading from site-packages.
"""

import sys
import importlib.util

# Find the installed langgraph library in site-packages
_installed_lg = None
for path in sys.path:
    if 'site-packages' in path:
        spec = importlib.util.find_spec('langgraph', [path])
        if spec and spec.origin:
            _installed_lg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_installed_lg)
            break

if not _installed_lg:
    raise ImportError("Could not find installed langgraph library in site-packages")

# Re-export commonly used imports
try:
    from ai_copilot.graph import StateGraph, START, END
    from ai_copilot.checkpoint.memory import MemorySaver
    from ai_copilot.graph.message import add_messages
except ImportError as e:
    # If standard imports work, good
    add_messages = None
    StateGraph = None
    START = None
    END = None
    MemorySaver = None
