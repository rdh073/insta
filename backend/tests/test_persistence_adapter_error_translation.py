"""Adapter-level tests for persistence failure catalog translation."""

from __future__ import annotations

from contextlib import contextmanager
import sys
import types

import pytest
from sqlalchemy.exc import SQLAlchemyError

# Minimal shim for backend/state.py import dependency via app.adapters.persistence package.
if "instagrapi" not in sys.modules:
    instagrapi_module = types.ModuleType("instagrapi")
    exceptions_module = types.ModuleType("instagrapi.exceptions")

    class _StubClient:  # pragma: no cover - shim class
        pass

    class _StubException(Exception):  # pragma: no cover - shim class
        pass

    instagrapi_module.Client = _StubClient
    exceptions_module.LoginRequired = _StubException
    exceptions_module.BadPassword = _StubException
    exceptions_module.ReloginAttemptExceeded = _StubException
    exceptions_module.TwoFactorRequired = _StubException
    instagrapi_module.exceptions = exceptions_module
    sys.modules["instagrapi"] = instagrapi_module
    sys.modules["instagrapi.exceptions"] = exceptions_module

from app.adapters.persistence.errors import PersistenceInfrastructureError
from app.adapters.persistence.failure_catalog import build_persistence_failure_message
from app.adapters.persistence.sql_repositories import SqlAccountRepository
from app.adapters.persistence.sql_uow import SqlAlchemyPersistenceUoW


class _BrokenStore:
    def __init__(self, raw_message: str):
        self.raw_message = raw_message

    @contextmanager
    def session_scope(self):
        raise SQLAlchemyError(self.raw_message)
        yield  # pragma: no cover

    def get_active_session(self):
        return None


class _SessionWithFailMode:
    def __init__(self, mode: str, raw_message: str):
        self._mode = mode
        self._raw_message = raw_message

    def begin(self):
        if self._mode == "begin":
            raise SQLAlchemyError(self._raw_message)

    def commit(self):
        if self._mode == "commit":
            raise SQLAlchemyError(self._raw_message)

    def rollback(self):
        if self._mode == "rollback":
            raise SQLAlchemyError(self._raw_message)

    def close(self):
        return None


class _StoreForUow:
    def __init__(self, mode: str, raw_message: str):
        self._mode = mode
        self._raw_message = raw_message
        self._active = None

    def session_factory(self):
        return _SessionWithFailMode(self._mode, self._raw_message)

    def set_active_session(self, session):
        self._active = session
        return "token"

    def reset_active_session(self, token):
        self._active = None


def test_sql_repository_raises_catalog_message_not_raw_vendor_string():
    raw_vendor_error = "sqlite3.OperationalError: database is locked"
    repo = SqlAccountRepository(_BrokenStore(raw_vendor_error))

    with pytest.raises(PersistenceInfrastructureError) as err:
        repo.get("acc-1")

    assert str(err.value) == build_persistence_failure_message("get")
    assert raw_vendor_error not in str(err.value)


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        ("begin", "uow_begin"),
        ("commit", "uow_commit"),
        ("rollback", "uow_rollback"),
    ],
)
def test_sql_uow_raises_catalog_message_not_raw_vendor_string(mode: str, operation: str):
    raw_vendor_error = "psycopg.OperationalError: timeout while acquiring connection"
    uow = SqlAlchemyPersistenceUoW(_StoreForUow(mode=mode, raw_message=raw_vendor_error))

    if mode == "begin":
        with pytest.raises(PersistenceInfrastructureError) as err:
            uow.begin()
    elif mode == "commit":
        uow.begin()
        with pytest.raises(PersistenceInfrastructureError) as err:
            uow.commit()
    else:
        uow.begin()
        with pytest.raises(PersistenceInfrastructureError) as err:
            uow.rollback()

    assert str(err.value) == build_persistence_failure_message(operation)
    assert raw_vendor_error not in str(err.value)
