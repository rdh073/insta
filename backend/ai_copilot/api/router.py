from __future__ import annotations

from fastapi import APIRouter

from .endpoints.account_recovery import router as account_recovery_router
from .endpoints.campaign_monitor import router as campaign_monitor_router
from .endpoints.content_pipeline import router as content_pipeline_router
from .endpoints.operator_copilot import router as operator_copilot_router
from .endpoints.risk_control import router as risk_control_router


router = APIRouter(prefix="/api/ai", tags=["ai-langgraph"])
router.include_router(operator_copilot_router)
router.include_router(campaign_monitor_router)
router.include_router(risk_control_router)
router.include_router(account_recovery_router)
router.include_router(content_pipeline_router)
