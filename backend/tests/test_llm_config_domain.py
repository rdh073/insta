"""Tests for LLM configuration domain entity and use cases.

Deliberately avoids importing from app.adapters.persistence to stay
independent of SQLAlchemy/database dependencies in the test environment.
Uses a minimal in-process stub for the repository.
"""

from __future__ import annotations

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import replace
from typing import Optional
from uuid import UUID

from app.domain.llm_config import (
    LLMConfig,
    LLMProvider,
    InvalidLLMConfig,
    NoActiveLLMConfigError,
)
from app.application.use_cases.llm_config import LLMConfigUseCases


# ---------------------------------------------------------------------------
# Stub repository (avoids SQLAlchemy / persistence package dependency)
# ---------------------------------------------------------------------------

class StubLLMConfigRepository:
    """Minimal in-memory repo for test isolation."""

    def __init__(self):
        self._configs: dict[str, LLMConfig] = {}

    def save(self, config):
        self._configs[str(config.id)] = config
        return config

    def find_by_id(self, config_id):
        return self._configs.get(str(config_id))

    def find_all(self):
        return sorted(self._configs.values(), key=lambda c: c.created_at, reverse=True)

    def find_active(self):
        for c in self._configs.values():
            if c.is_active:
                return c
        return None

    def delete(self, config_id):
        self._configs.pop(str(config_id), None)

    def set_active(self, config_id):
        key = str(config_id)
        if key not in self._configs:
            raise KeyError(f"Config {config_id!r} not found")
        now = datetime.now(timezone.utc)
        for cid, config in list(self._configs.items()):
            updated = replace(config, is_active=(cid == key), updated_at=now)
            self._configs[cid] = updated


# ---------------------------------------------------------------------------
# Domain entity tests
# ---------------------------------------------------------------------------


class TestLLMProvider:
    def test_valid_providers(self):
        assert LLMProvider.from_string("openai") == LLMProvider.OPENAI
        assert LLMProvider.from_string("GEMINI") == LLMProvider.GEMINI
        assert LLMProvider.from_string("deepseek") == LLMProvider.DEEPSEEK
        assert LLMProvider.from_string("antigravity") == LLMProvider.ANTIGRAVITY
        assert LLMProvider.from_string("openai_codex") == LLMProvider.OPENAI_CODEX
        assert LLMProvider.from_string("claude_code") == LLMProvider.CLAUDE_CODE

    def test_invalid_provider_raises(self):
        with pytest.raises(InvalidLLMConfig, match="not valid"):
            LLMProvider.from_string("claude")

    def test_empty_provider_raises(self):
        with pytest.raises(InvalidLLMConfig):
            LLMProvider.from_string("")


class TestLLMConfig:
    def test_create_valid(self):
        config = LLMConfig.create(
            label="My ChatGPT",
            provider="openai",
            api_key="sk-test12345",
            model="gpt-4o-mini",
        )
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4o-mini"
        assert config.is_active is False
        assert config.id is not None

    def test_empty_api_key_rejected(self):
        with pytest.raises(InvalidLLMConfig, match="api_key"):
            LLMConfig.create(label="test", provider="openai", api_key="", model="gpt-4o")

    def test_whitespace_api_key_rejected(self):
        with pytest.raises(InvalidLLMConfig, match="api_key"):
            LLMConfig.create(label="test", provider="openai", api_key="   ", model="gpt-4o")

    def test_empty_model_rejected(self):
        with pytest.raises(InvalidLLMConfig, match="model"):
            LLMConfig.create(label="test", provider="openai", api_key="sk-123", model="")

    def test_empty_label_rejected(self):
        with pytest.raises(InvalidLLMConfig, match="label"):
            LLMConfig.create(label="", provider="openai", api_key="sk-123", model="gpt-4o")

    def test_invalid_provider_rejected(self):
        with pytest.raises(InvalidLLMConfig, match="not valid"):
            LLMConfig.create(label="test", provider="chatgpt", api_key="sk-123", model="gpt-4o")

    def test_masked_api_key(self):
        config = LLMConfig.create(
            label="test", provider="openai", api_key="sk-abc12345xyz", model="gpt-4o"
        )
        masked = config.masked_api_key()
        assert masked.endswith("xyz")  # Last 4 chars visible
        assert not masked.startswith("sk-abc")  # Full key not in mask

    def test_masked_api_key_short(self):
        config = LLMConfig.create(
            label="test", provider="openai", api_key="ab", model="gpt-4o"
        )
        assert config.masked_api_key() == "***"

    def test_str_representation(self):
        config = LLMConfig.create(
            label="My Key", provider="openai", api_key="sk-123", model="gpt-4o"
        )
        s = str(config)
        assert "openai" in s
        assert "My Key" in s
        assert "inactive" in s


# ---------------------------------------------------------------------------
# In-memory repository tests
# ---------------------------------------------------------------------------


class TestStubLLMConfigRepository:
    def _make_config(self, label="test", is_active=False):
        config = LLMConfig.create(
            label=label, provider="openai", api_key="sk-123", model="gpt-4o"
        )
        return replace(config, is_active=is_active)

    def test_save_and_find_by_id(self):
        repo = StubLLMConfigRepository()
        config = self._make_config()
        repo.save(config)
        found = repo.find_by_id(config.id)
        assert found is not None
        assert found.id == config.id

    def test_find_by_id_missing(self):
        repo = StubLLMConfigRepository()
        assert repo.find_by_id(uuid4()) is None

    def test_find_all_returns_newest_first(self):
        repo = StubLLMConfigRepository()
        c1 = LLMConfig.create(label="c1", provider="openai", api_key="sk-1", model="gpt-4")
        c2 = replace(
            LLMConfig.create(label="c2", provider="openai", api_key="sk-2", model="gpt-4"),
            created_at=c1.created_at + timedelta(seconds=1),
        )
        repo.save(c1)
        repo.save(c2)
        all_configs = repo.find_all()
        assert all_configs[0].label == "c2"  # Newest first
        assert all_configs[1].label == "c1"

    def test_find_active_none_when_empty(self):
        repo = StubLLMConfigRepository()
        assert repo.find_active() is None

    def test_set_active(self):
        repo = StubLLMConfigRepository()
        c1 = self._make_config("c1")
        c2 = self._make_config("c2")
        repo.save(c1)
        repo.save(c2)
        repo.set_active(c1.id)
        assert repo.find_active().id == c1.id
        repo.set_active(c2.id)
        assert repo.find_active().id == c2.id
        # c1 must be deactivated
        assert repo.find_by_id(c1.id).is_active is False

    def test_delete(self):
        repo = StubLLMConfigRepository()
        c = self._make_config()
        repo.save(c)
        repo.delete(c.id)
        assert repo.find_by_id(c.id) is None


# ---------------------------------------------------------------------------
# Use case tests
# ---------------------------------------------------------------------------


class TestLLMConfigUseCases:
    def _make_uc(self):
        return LLMConfigUseCases(repo=StubLLMConfigRepository())

    def test_create_config(self):
        uc = self._make_uc()
        config = uc.create(
            label="My ChatGPT", provider="openai", api_key="sk-123", model="gpt-4o-mini"
        )
        assert config.label == "My ChatGPT"
        assert config.provider == LLMProvider.OPENAI

    def test_create_invalid_raises_value_error(self):
        uc = self._make_uc()
        with pytest.raises(ValueError, match="api_key"):
            uc.create(label="x", provider="openai", api_key="", model="gpt-4o")

    def test_create_and_activate(self):
        uc = self._make_uc()
        config = uc.create(
            label="Main", provider="openai", api_key="sk-123", model="gpt-4o", activate=True
        )
        active = uc.get_active()
        assert active.id == config.id
        assert active.is_active is True

    def test_get_active_raises_when_none(self):
        uc = self._make_uc()
        with pytest.raises(NoActiveLLMConfigError):
            uc.get_active()

    def test_get_active_or_none_returns_none(self):
        uc = self._make_uc()
        assert uc.get_active_or_none() is None

    def test_activate_switches_active(self):
        uc = self._make_uc()
        c1 = uc.create(label="c1", provider="openai", api_key="sk-1", model="gpt-4", activate=True)
        c2 = uc.create(label="c2", provider="gemini", api_key="gl-2", model="gemini-flash")
        uc.activate(c2.id)
        assert uc.get_active().id == c2.id

    def test_activate_unknown_raises_key_error(self):
        uc = self._make_uc()
        with pytest.raises(KeyError):
            uc.activate(uuid4())

    def test_list_all(self):
        uc = self._make_uc()
        uc.create(label="a", provider="openai", api_key="sk-a", model="gpt-4")
        uc.create(label="b", provider="gemini", api_key="gl-b", model="flash")
        all_configs = uc.list_all()
        assert len(all_configs) == 2

    def test_update_fields(self):
        uc = self._make_uc()
        c = uc.create(label="original", provider="openai", api_key="sk-old", model="gpt-4")
        updated = uc.update(c.id, label="updated", model="gpt-4o")
        assert updated.label == "updated"
        assert updated.model == "gpt-4o"
        assert updated.api_key == "sk-old"  # Unchanged

    def test_update_unknown_raises_key_error(self):
        uc = self._make_uc()
        with pytest.raises(KeyError):
            uc.update(uuid4(), label="x")

    def test_delete_config(self):
        uc = self._make_uc()
        c = uc.create(label="to_delete", provider="openai", api_key="sk-123", model="gpt-4")
        uc.delete(c.id)
        assert len(uc.list_all()) == 0

    def test_delete_unknown_raises_key_error(self):
        uc = self._make_uc()
        with pytest.raises(KeyError):
            uc.delete(uuid4())
