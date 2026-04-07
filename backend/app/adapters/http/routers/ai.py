"""DEPRECATED: AI chat router has been removed in Phase D (LangGraph-Only Migration).

PHASE D MIGRATION: Legacy non-graph AI assistant removed.

Routing Summary:
  ❌ /api/ai/chat                  REMOVED (legacy AIChartUseCases tool-loop)
  ✅ /api/ai/chat/graph            ACTIVE (ai_copilot/api.py, RunOperatorCopilotUseCase)

All AI requests should use the new LangGraph operator copilot at:
  - POST /api/ai/chat/graph        Start new graph execution
  - POST /api/ai/chat/graph/resume Resume checkpoint (with approval)

The AI router is now deprecated and will be removed in a future cleanup.
This file is kept as documentation only.
"""

from fastapi import APIRouter

# PHASE D MIGRATION: All handlers removed - see ai_copilot/api.py for active graph endpoints
router = APIRouter(prefix="/api/ai", tags=["ai-deprecated"])
