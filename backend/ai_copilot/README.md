# LangGraph Operator Copilot Module

Clean architecture module for stateful AI orchestration with LangGraph.

**Status**: Architectural skeleton complete - ready for integration testing

## Module Overview

```
langgraph/
├── application/          (Core business logic - NO framework imports)
│   ├── ports.py         (Abstract interfaces: LLMGatewayPort, ToolExecutorPort, CheckpointFactoryPort)
│   ├── state.py         (Typed state: OperatorCopilotState)
│   ├── graphs/          (Graph definitions)
│   │   └── operator_copilot.py (State graph builder and nodes)
│   └── use_cases/       (Workflow orchestration)
│       └── run_operator_copilot.py (Graph execution entrypoint - invoke or stream)
├── adapters/            (Port implementations - CAN import frameworks)
│   ├── llm_gateway.py   (Wraps app's AIGateway)
│   ├── tool_executor.py (Read-only tool whitelist enforcement)
│   └── checkpoint.py    (MemorySaver-based persistence)
├── api.py              (HTTP transport layer - FastAPI router)
└── README.md           (This file)
```

## Architecture Principles

### 1. Dependency Inversion

```
HTTP API (api.py)
    ↓
Use Cases (run_operator_copilot.py)
    ↓
Graphs (operator_copilot.py)
    ↓
Ports (ports.py) ← Adapters (llm_gateway.py, tool_executor.py, checkpoint.py)
```

**Key Rule**: Application layer depends on ports, NOT on concrete implementations.

### 2. Layer Isolation

| Layer | Allowed Imports | Forbidden |
|-------|-----------------|-----------|
| **application/** | langgraph, typing, abc | fastapi, openai, vendor SDKs |
| **adapters/** | application.ports, vendor SDK | fastapi, other adapters |
| **api.py** | fastapi, adapters, use_cases | - |

### 3. Read-Only Access Control

Tool access is enforced at the adapter level:

```python
# In adapters/tool_executor.py
ALLOWED_TOOLS = {
    "list_accounts",
    "get_account_info", 
    "get_post_jobs",
}

# Any attempt to call other tools raises ValueError with "Access denied"
```

## How It Works

### Graph Execution Flow

```
User Request
    ↓
api.py → POST /operator-copilot
    ↓
RunOperatorCopilotUseCase.stream()
    ↓
build_read_only_operator_graph()
    ↓
LangGraph Workflow:
    START
    ↓
  agent_node ──(LLMGatewayPort.request_completion)──→ Get AI response
    ↓
  should_continue (routing)
    ├─ [tool_calls?] → tool_executor_node ──(ToolExecutorPort.execute)──→ Run tools
    │                                                    ↓
    │                                          should_continue_loop
    │                                                    ↓
    │                                          [max_steps?] → END or back to agent
    │
    └─ [text] → respond_node
                 ↓
               END
    ↓
Yield SSE events (tool calls, results, text response)
```

### State Management

```python
OperatorCopilotState:
  - messages: list[dict]  # Conversation history (managed by LangGraph reducer)
  - current_tool_calls: dict[str, dict] | None  # In-flight tool calls
  - tool_results: dict[str, dict]  # Completed tool results
  - stop_reason: str | None  # Why workflow stopped
  - step_count: int  # Iteration counter
```

**Note**: `add_messages` reducer prevents message duplication automatically.

## Integration Guide

### 1. Wire Adapters into App Bootstrap

In `app/bootstrap/container.py`:

```python
from langgraph import (
    LLMGatewayAdapter,
    ReadOnlyToolExecutor,
    MemoryCheckpointFactory,
    RunOperatorCopilotUseCase,
)

def create_services():
    # ... existing code ...
    
    # Create LangGraph adapters
    llm_adapter = LLMGatewayAdapter(ai_gateway)
    tool_executor = ReadOnlyToolExecutor(tool_registry)
    checkpoint_factory = MemoryCheckpointFactory()
    
    # Create use case
    operator_copilot_usecase = RunOperatorCopilotUseCase(
        llm_gateway=llm_adapter,
        tool_executor=tool_executor,
        max_steps=6,
    )
    
    return {
        # ... existing services ...
        "langgraph_run": operator_copilot_usecase,
    }
```

### 2. Add HTTP Endpoint

In `app/adapters/http/routers/ai.py` or new `langgraph_router.py`:

```python
from fastapi import APIRouter, Depends
from langgraph.api import router as langgraph_router

# Include router
app.include_router(langgraph_router)
```

Or manually add endpoint:

```python
@router.post("/operator-copilot")
async def operator_copilot(
    request: dict,
    run_graph: RunOperatorCopilotUseCase = Depends(get_operator_copilot_usecase),
):
    async def generate():
        async for event in run_graph.stream(request["messages"], request.get("threadId")):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"x-vercel-ai-ui-message-stream": "v1"},
    )
```

### 3. Add Dependency

```python
# app/adapters/http/dependencies.py

def get_operator_copilot_usecase():
    services = get_services()
    return services["langgraph_run"]
```

## Testing

### Unit Tests (Application Layer)

Application code can be tested without FastAPI or OpenAI:

```python
# Create mock ports
class MockLLMGateway(LLMGatewayPort):
    async def request_completion(self, messages, **kwargs):
        return {
            "content": "Hello",
            "finish_reason": "stop",
            "tool_calls": [],
        }

class MockToolExecutor(ToolExecutorPort):
    async def execute(self, tool_name, args):
        return {"status": "ok"}

# Test graph
graph, _ = build_read_only_operator_graph(MockLLMGateway(), MockToolExecutor())
# Invoke and verify
```

### Integration Tests

Test with real adapters but mocked underlying services:

```python
# Use LLMGatewayAdapter + mock AIGateway
# Use ReadOnlyToolExecutor + mock ToolRegistry
# Run full graph and verify SSE events
```

## Design Patterns Used

### 1. Ports & Adapters (Hexagonal Architecture)

- **Ports**: Abstract interfaces (LLMGatewayPort, ToolExecutorPort)
- **Adapters**: Concrete implementations (LLMGatewayAdapter, ReadOnlyToolExecutor)
- **Benefit**: Application logic independent of infrastructure

### 2. Dependency Injection

All dependencies injected at use case initialization:

```python
run_graph = RunOperatorCopilotUseCase(
    llm_gateway=llm_adapter,
    tool_executor=tool_executor,
)
```

**Benefit**: Easy to swap implementations (e.g., for testing)

### 3. Stateful Workflow

LangGraph manages state persistence and checkpointing:

```python
config = {"configurable": {"thread_id": "..."}}
for output in graph.stream(initial_state, config):
    # State automatically checkpointed
```

**Benefit**: Resumable workflows, multi-turn conversations

## Constraints & Limitations (Intentional)

✅ **What works**:
- Read-only operations (list accounts, get info, check jobs)
- Stateful multi-turn conversations
- Tool access control
- SSE streaming

❌ **What's blocked**:
- Write operations (relogin, schedule posts, set proxy)
- Multi-agent workflows (single agent only)
- Human approval gates (todo: Phase 7)
- External persistence (in-memory only, can extend)

## Extending the Module

### Add a New Workflow Graph

1. Create `application/graphs/new_workflow.py`
2. Define nodes and routing
3. Call `StateGraph.compile()` with ports
4. Create use case wrapper

### Add a New Tool Executor

1. Create adapter implementing `ToolExecutorPort`
2. Enforce access control in `execute()`
3. Inject into `RunOperatorCopilotUseCase`

### Migrate to Database Persistence

1. Create new adapter implementing `CheckpointFactoryPort`
2. Return SQLite/PostgreSQL checkpointer
3. Inject into graph builder
4. No changes to application code needed

## Dependencies

```
langgraph>=0.1.0
```

That's it. No FastAPI, OpenAI, or other vendor code in `application/`.

## Next Steps

- [ ] Integration testing with app bootstrap
- [ ] Add to app HTTP routers
- [ ] Smoke test graph execution
- [ ] Performance baseline measurement
- [ ] Phase 7: Add write-operation graphs with approval gates

---

**Module Status**: ✅ Ready for integration  
**Last Updated**: 2026-04-01  
**Architecture Validation**: Ports & adapters ✓ Dependency inversion ✓ Framework isolation ✓
