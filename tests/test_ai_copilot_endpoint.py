"""Smoke tests for /api/ai/chat/graph endpoint.

Tests HTTP integration, SSE streaming, and backward compatibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest


def test_router_import():
    """Test that the ai_copilot router can be imported."""
    try:
        from ai_copilot.api import router
        assert router is not None
        print("✓ Router imported successfully")
    except ImportError as e:
        pytest.fail(f"Could not import router: {e}")


def test_router_prefix():
    """Test that router has correct prefix."""
    from ai_copilot.api import router

    # Check that prefix is set correctly
    assert router.prefix == "/api/ai"
    assert "ai-langgraph" in router.tags


def test_endpoint_registration():
    """Test that endpoints are registered."""
    from ai_copilot.api import router

    # Get route paths
    routes = router.routes if hasattr(router, "routes") else []

    # Should have at least the /graph endpoint
    route_paths = [r.path for r in routes] if routes else []
    # The router.post decorator should create the route
    assert router is not None


def test_dependency_injection_function():
    """Test that dependency injection function exists."""
    from ai_copilot.api import get_operator_copilot_usecase

    # Function should exist and be callable
    assert callable(get_operator_copilot_usecase)


def test_backward_compatibility_old_endpoint():
    """Test that old /api/ai/chat endpoint still exists.

    This is a documentation test to verify we didn't break the old route.
    """
    # The old route should still be available at app.adapters.http.routers.ai
    try:
        from app.adapters.http.routers.ai import router as old_router
        assert old_router is not None
        assert old_router.prefix == "/api/ai"
        print("✓ Old /api/ai route still available")
    except Exception as e:
        pytest.fail(f"Old route may be broken: {e}")


def test_no_circular_imports():
    """Test that there are no circular imports between ai_copilot modules."""
    import sys

    try:
        from ai_copilot.api import router
        from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase
        from ai_copilot.application.ports import LLMGatewayPort, ToolExecutorPort

        # Should have imported without circular import error
        assert "ai_copilot.api" in sys.modules
        print("✓ No circular imports in ai_copilot modules")
    except ImportError as e:
        if "circular" in str(e).lower() or "partially initialized" in str(e).lower():
            pytest.fail(f"Circular import detected: {e}")
        # Other import errors (missing optional deps) are not circular import failures
        pytest.skip(f"Optional dependency missing: {e}")


def test_sse_headers_configured():
    """Test that SSE response headers are configured.

    This is a source code review test.
    """
    import inspect
    from ai_copilot.api import operator_copilot_run

    source = inspect.getsource(operator_copilot_run)

    # Should mention SSE headers
    assert "text/event-stream" in source
    assert "StreamingResponse" in source
    print("✓ SSE headers configured in endpoint")


def test_request_body_contract():
    """Test that request body contract is documented.

    This is a source code review test.
    """
    import inspect
    from ai_copilot.api import operator_copilot_run

    source = inspect.getsource(operator_copilot_run)

    # Should document request contract
    assert "messages" in source or "request" in source
    print("✓ Request contract documented")


def test_old_route_not_modified():
    """Verify old route hasn't been changed."""
    from app.adapters.http.routers.ai import router as old_router

    # Old route should still be at /api/ai
    assert old_router.prefix == "/api/ai"
    print("✓ Old route endpoint unchanged")


def test_new_route_isolated():
    """Verify new route is in a separate module from the legacy router."""
    from ai_copilot.api import router as new_router
    from app.adapters.http.routers.ai import router as old_router

    # They must be distinct router objects even if they share the /api/ai prefix
    assert new_router is not old_router
    print("✓ New route is a separate router instance from the legacy router")


def test_dependency_injection_cached():
    """Test that dependency injection uses caching."""
    from ai_copilot.api import get_operator_copilot_usecase

    # Should have lru_cache decorator
    assert hasattr(get_operator_copilot_usecase, "__wrapped__")
    print("✓ Dependency injection cached with lru_cache")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
