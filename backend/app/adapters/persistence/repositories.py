"""In-memory repository implementations."""

from __future__ import annotations

from typing import Optional
from app.application.ports.persistence_models import AccountRecord, JobRecord
from app.domain.proxy import Proxy
from .state_gateway import default_state_gateway


class InMemoryAccountRepository:
    """In-memory account repository backed by state.py."""

    def __init__(self, gateway=default_state_gateway):
        self.gateway = gateway

    def get(self, account_id: str) -> Optional[AccountRecord]:
        raw = self.gateway.get_account(account_id)
        if raw is None:
            return None
        return AccountRecord.from_dict(raw)

    def exists(self, account_id: str) -> bool:
        return self.gateway.has_account(account_id)

    def set(self, account_id: str, data: AccountRecord | dict) -> None:
        if isinstance(data, AccountRecord):
            self.gateway.set_account(account_id, data.to_dict())
        else:
            self.gateway.set_account(account_id, AccountRecord.from_dict(data).to_dict())

    def update(self, account_id: str, **kwargs) -> None:
        self.gateway.update_account(account_id, **kwargs)

    def remove(self, account_id: str) -> None:
        self.gateway.pop_account(account_id)

    def find_by_username(self, username: str) -> Optional[str]:
        return self.gateway.find_account_id_by_username(username)

    def list_all_ids(self) -> list[str]:
        return self.gateway.account_ids()

    def iter_all(self) -> list[tuple[str, AccountRecord]]:
        return [
            (account_id, AccountRecord.from_dict(data))
            for account_id, data in self.gateway.iter_account_items()
        ]


class InMemoryClientRepository:
    """In-memory client repository backed by state.py."""

    def __init__(self, gateway=default_state_gateway):
        self.gateway = gateway

    def get(self, account_id: str):
        return self.gateway.get_client(account_id)

    def set(self, account_id: str, client) -> None:
        self.gateway.set_client(account_id, client)

    def remove(self, account_id: str):
        return self.gateway.pop_client(account_id)

    def exists(self, account_id: str) -> bool:
        return self.gateway.has_client(account_id)

    def list_active_ids(self) -> list[str]:
        return self.gateway.active_client_ids()


class InMemoryStatusRepository:
    """In-memory status repository backed by state.py."""

    def __init__(self, gateway=default_state_gateway):
        self.gateway = gateway

    def get(self, account_id: str, default: Optional[str] = None) -> Optional[str]:
        return self.gateway.get_account_status_value(account_id, default or "idle")

    def set(self, account_id: str, status: str) -> None:
        self.gateway.set_account_status(account_id, status)

    def clear(self, account_id: str) -> None:
        self.gateway.clear_account_status(account_id)


class InMemoryJobRepository:
    """In-memory job repository backed by state.py."""

    def __init__(self, gateway=default_state_gateway):
        self.gateway = gateway

    def get(self, job_id: str) -> Optional[JobRecord]:
        raw = self.gateway.get_job(job_id)
        if raw is None:
            return None
        return JobRecord.from_dict(raw)

    def set(self, job_id: str, job: JobRecord | dict) -> None:
        if isinstance(job, JobRecord):
            self.gateway.set_job(job_id, job.to_dict())
        else:
            self.gateway.set_job(job_id, JobRecord.from_dict(job).to_dict())

    def list_all(self) -> list[JobRecord]:
        return [JobRecord.from_dict(job) for job in self.gateway.iter_jobs_values()]


class InMemoryProxyRepository:
    """In-memory proxy repository (used for tests and non-persistent mode)."""

    def __init__(self):
        self._store: dict[tuple[str, int], Proxy] = {}

    def save(self, proxy: Proxy) -> None:
        self._store[(proxy.host, proxy.port)] = proxy

    def list_all(self) -> list[Proxy]:
        return sorted(self._store.values(), key=lambda p: p.latency_ms)

    def delete(self, host: str, port: int) -> None:
        self._store.pop((host, port), None)

    def exists(self, host: str, port: int) -> bool:
        return (host, port) in self._store
