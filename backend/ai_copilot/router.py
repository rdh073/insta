"""Composed ai_copilot FastAPI router."""

from __future__ import annotations

from fastapi import APIRouter

from ai_copilot.endpoints.account_recovery import router as account_recovery_router
from ai_copilot.endpoints.campaign_monitor import router as campaign_monitor_router
from ai_copilot.endpoints.content_pipeline import router as content_pipeline_router
from ai_copilot.endpoints.operator_copilot import router as operator_copilot_router
from ai_copilot.endpoints.risk_control import router as risk_control_router

router = APIRouter(prefix="/api/ai", tags=["ai-langgraph"])

router.include_router(operator_copilot_router)
router.include_router(campaign_monitor_router)
router.include_router(risk_control_router)
router.include_router(account_recovery_router)
router.include_router(content_pipeline_router)
