"""LangGraph operator copilot - stateful AI with read-only tools.

Clean architecture module for LangGraph-based workflows.

Module structure:
- application/: Core business logic (state, graphs, use cases)
  - ports.py: Abstract interfaces (LLMGatewayPort, ToolExecutorPort)
  - state.py: Typed graph state
  - graphs/: Graph definitions
  - use_cases/: Workflow orchestration
- adapters/: Implementations of ports
  - llm_gateway.py: LLM interaction (wraps app's AIGateway)
  - tool_executor.py: Tool execution with read-only access control
  - checkpoint.py: State persistence
- api/: HTTP transport layer package (FastAPI router + endpoint modules)

Dependency direction: api → use_cases → graphs → ports ← adapters

Note: This module is kept minimal to avoid namespace conflicts with the
installed langgraph library. Use relative imports within submodules.
"""

# Empty init - submodules handle their own imports to avoid namespace conflicts
# with the installed langgraph library
