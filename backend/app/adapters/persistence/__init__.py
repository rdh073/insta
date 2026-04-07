"""Persistence adapter layer - in-memory repositories and file storage."""

from .repositories import (
    InMemoryAccountRepository,
    InMemoryClientRepository,
    InMemoryStatusRepository,
    InMemoryJobRepository,
)
from .activity_log import ActivityLogWriter
from .session_store import SessionStore as SessionStoreImpl
from .uow import InMemoryPersistenceUoW
from .sql_store import SqlitePersistenceStore
from .sql_repositories import SqlAccountRepository, SqlStatusRepository, SqlJobRepository
from .sql_uow import SqlAlchemyPersistenceUoW
from .factory import build_persistence_adapters
from .state_gateway import StateGateway, default_state_gateway
from .errors import PersistenceInfrastructureError
from .failure_catalog import SPEC_PERSISTENCE_INFRA_ERROR, build_persistence_failure_message

# Export with interface name for clarity
SessionStore = SessionStoreImpl

__all__ = [
    "InMemoryAccountRepository",
    "InMemoryClientRepository",
    "InMemoryStatusRepository",
    "InMemoryJobRepository",
    "ActivityLogWriter",
    "SessionStore",
    "InMemoryPersistenceUoW",
    "SqlitePersistenceStore",
    "SqlAccountRepository",
    "SqlStatusRepository",
    "SqlJobRepository",
    "SqlAlchemyPersistenceUoW",
    "build_persistence_adapters",
    "StateGateway",
    "default_state_gateway",
    "PersistenceInfrastructureError",
    "SPEC_PERSISTENCE_INFRA_ERROR",
    "build_persistence_failure_message",
]
