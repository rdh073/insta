"""Adapter for PostJobControlPort backed by the in-memory state gateway."""

from __future__ import annotations

from .state_gateway import StateGateway, default_state_gateway


class PostJobControlAdapter:
    """Implements PostJobControlPort by delegating to StateGateway + job_store."""

    def __init__(self, gateway: StateGateway | None = None) -> None:
        self._gw = gateway or default_state_gateway

    def get_job(self, job_id: str) -> dict:
        return self._gw.get_job(job_id)

    def set_job_status(self, job_id: str, status: str) -> None:
        self._gw.set_job_status(job_id, status)

    def request_stop(self, job_id: str) -> None:
        self._gw.request_job_stop(job_id)

    def request_pause(self, job_id: str) -> None:
        self._gw.request_job_pause(job_id)

    def request_resume(self, job_id: str) -> None:
        self._gw.request_job_resume(job_id)
