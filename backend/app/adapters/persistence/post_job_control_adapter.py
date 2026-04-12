"""Adapter for PostJobControlPort backed by state gateway + optional persistence."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional, Protocol

from app.application.ports.persistence_models import JobRecord
from app.application.ports.persistence_uow import PersistenceUnitOfWork

from .state_gateway import StateGateway, default_state_gateway


class _JobRepository(Protocol):
    def get(self, job_id: str) -> Optional[JobRecord]:
        ...

    def set(self, job_id: str, job: JobRecord | dict) -> None:
        ...


class PostJobControlAdapter:
    """Implements PostJobControlPort with runtime + durable status synchronization."""

    def __init__(
        self,
        gateway: StateGateway | None = None,
        job_repo: _JobRepository | None = None,
        uow: PersistenceUnitOfWork | None = None,
    ) -> None:
        self._gw = gateway or default_state_gateway
        self._job_repo = job_repo
        self._uow = uow

    def _uow_scope(self):
        if self._uow is None:
            return nullcontext()
        return self._uow

    def get_job(self, job_id: str) -> dict:
        return self._gw.get_job(job_id)

    def set_job_status(self, job_id: str, status: str) -> None:
        # Durable backends must persist control transitions so restart restore
        # uses the latest truth (e.g., stopped jobs are not resurrected).
        if self._job_repo is not None:
            with self._uow_scope():
                record = self._job_repo.get(job_id)
                if record is None:
                    raise KeyError(job_id)
                record.status = status
                self._job_repo.set(job_id, record)
            return
        self._gw.set_job_status(job_id, status)

    def request_stop(self, job_id: str) -> None:
        self._gw.request_job_stop(job_id)

    def request_pause(self, job_id: str) -> None:
        self._gw.request_job_pause(job_id)

    def request_resume(self, job_id: str) -> None:
        self._gw.request_job_resume(job_id)

    def clear_control(self, job_id: str) -> None:
        self._gw.clear_job_control(job_id)
