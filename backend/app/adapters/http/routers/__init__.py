"""HTTP routers organized by domain."""

from .accounts import router as accounts_router
from .posts import router as posts_router
from .logs import router as logs_router
from .dashboard import router as dashboard_router
from .ai import router as ai_router
from .instagram import router as instagram_router

__all__ = [
    "accounts_router",
    "posts_router",
    "logs_router",
    "dashboard_router",
    "ai_router",
    "instagram_router",
]
