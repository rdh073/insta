"""Phase 1 schema-governance tests for Alembic migrations."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path("/home/xtrzy/Workspace/insta")
BACKEND_ROOT = REPO_ROOT / "backend"
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_scaffold_exists():
    assert ALEMBIC_INI.exists()
    assert (ALEMBIC_DIR / "env.py").exists()
    assert (ALEMBIC_DIR / "versions").exists()
    assert (ALEMBIC_DIR / "versions" / "001_baseline_schema.py").exists()


def test_alembic_upgrade_head_creates_core_persistence_schema(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'alembic-governance.sqlite3'}"
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", db_url)
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")

    engine = create_engine(db_url, future=True)
    try:
        table_names = set(inspect(engine).get_table_names())
        assert {"accounts", "account_status", "jobs", "alembic_version"}.issubset(
            table_names
        )

        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert current == head
    finally:
        engine.dispose()


def test_alembic_upgrade_downgrade_upgrade_cycle_is_controlled(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'alembic-cycle.sqlite3'}"
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", db_url)
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")

    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    engine = create_engine(db_url, future=True)
    try:
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert current == head

        command.downgrade(cfg, "base")

        table_names_after_downgrade = set(inspect(engine).get_table_names())
        assert "accounts" not in table_names_after_downgrade
        assert "account_status" not in table_names_after_downgrade
        assert "jobs" not in table_names_after_downgrade
        assert "alembic_version" in table_names_after_downgrade
        with engine.connect() as conn:
            version_rows = conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        assert version_rows == []

        command.upgrade(cfg, "head")

        table_names_after_reupgrade = set(inspect(engine).get_table_names())
        assert {"accounts", "account_status", "jobs", "alembic_version"}.issubset(
            table_names_after_reupgrade
        )
        with engine.connect() as conn:
            current_after_reupgrade = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        assert current_after_reupgrade == head
    finally:
        engine.dispose()
