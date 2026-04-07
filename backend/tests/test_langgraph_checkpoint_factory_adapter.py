"""Tests for configurable LangGraph checkpoint factory adapter."""

from __future__ import annotations

from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory


def test_checkpoint_factory_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("LANGGRAPH_CHECKPOINTER_BACKEND", raising=False)
    monkeypatch.delenv("LANGGRAPH_CHECKPOINTER_SQLITE_PATH", raising=False)

    factory = ConfigurableCheckpointFactory.from_env()

    checkpointer = factory.create()
    assert checkpointer.__class__.__name__ == "InMemorySaver"


def test_checkpoint_factory_rejects_unknown_backend():
    factory = ConfigurableCheckpointFactory(backend="unknown")

    try:
        factory.create()
        assert False, "Expected RuntimeError for unknown backend"
    except RuntimeError as exc:
        assert "LANGGRAPH_CHECKPOINTER_BACKEND" in str(exc)


def test_checkpoint_factory_sqlite_backend_routes_to_sqlite_creator(monkeypatch):
    factory = ConfigurableCheckpointFactory(
        backend="sqlite", sqlite_path="/tmp/test-checkpoints.sqlite3"
    )
    sentinel = object()
    monkeypatch.setattr(factory, "_create_sqlite", lambda: sentinel)

    result = factory.create()

    assert result is sentinel

