"""Single gateway for backend/state.py access.

All persistence adapters must access global in-memory state via this gateway.
"""

from __future__ import annotations

import state as state_module


class StateGateway:
    """Thin wrapper around backend/state.py functions/constants."""

    @property
    def sessions_dir(self):
        return state_module.SESSIONS_DIR

    def get_account(self, account_id: str):
        return state_module.get_account(account_id)

    def has_account(self, account_id: str) -> bool:
        return state_module.has_account(account_id)

    def set_account(self, account_id: str, data: dict) -> None:
        state_module.set_account(account_id, data)

    def update_account(self, account_id: str, **kwargs) -> None:
        state_module.update_account(account_id, **kwargs)

    def pop_account(self, account_id: str):
        return state_module.pop_account(account_id)

    def find_account_id_by_username(self, username: str):
        return state_module.find_account_id_by_username(username)

    def account_ids(self):
        return state_module.account_ids()

    def iter_account_items(self):
        return state_module.iter_account_items()

    def get_client(self, account_id: str):
        return state_module.get_client(account_id)

    def set_client(self, account_id: str, client) -> None:
        state_module.set_client(account_id, client)

    def pop_client(self, account_id: str):
        return state_module.pop_client(account_id)

    def has_client(self, account_id: str) -> bool:
        return state_module.has_client(account_id)

    def active_client_ids(self):
        return state_module.active_client_ids()

    def get_account_status_value(self, account_id: str, default: str = "idle"):
        return state_module.get_account_status_value(account_id, default)

    def set_account_status(self, account_id: str, status: str) -> None:
        state_module.set_account_status(account_id, status)

    def clear_account_status(self, account_id: str) -> None:
        state_module.clear_account_status(account_id)

    def get_job(self, job_id: str):
        return state_module.get_job(job_id)

    def set_job(self, job_id: str, job: dict) -> None:
        state_module.set_job(job_id, job)

    def delete_job(self, job_id: str) -> bool:
        return state_module.delete_job(job_id)

    def iter_jobs_values(self):
        return state_module.iter_jobs_values()

    # ── job lifecycle control ─────────────────────────────────────────────

    def set_job_status(self, job_id: str, status: str) -> None:
        state_module.job_store.set_job_status(job_id, status)

    def request_job_stop(self, job_id: str) -> None:
        state_module.request_job_stop(job_id)

    def request_job_pause(self, job_id: str) -> None:
        state_module.request_job_pause(job_id)

    def request_job_resume(self, job_id: str) -> None:
        state_module.request_job_resume(job_id)

    def clear_job_control(self, job_id: str) -> None:
        state_module.clear_job_control(job_id)

    def log_event(
        self,
        account_id: str,
        username: str,
        event: str,
        *,
        detail: str = "",
        status: str = "",
    ) -> None:
        state_module.log_event(
            account_id,
            username,
            event,
            detail=detail,
            status=status,
        )


default_state_gateway = StateGateway()
