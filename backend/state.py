"""
Shared in-memory state and helper functions.
All other modules import from here; nothing here imports from sibling modules.
"""

from __future__ import annotations

import datetime
import json
import threading
from pathlib import Path

from instagrapi import Client as IGClient
from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired, ReloginAttemptExceeded, TwoFactorRequired

__all__ = [
    "SESSIONS_DIR",
    "LOG_FILE",
    "IGClient",
    "LoginRequired",
    "BadPassword",
    "ChallengeRequired",
    "ReloginAttemptExceeded",
    "TwoFactorRequired",
    "has_account",
    "get_account",
    "set_account",
    "update_account",
    "pop_account",
    "iter_account_items",
    "account_ids",
    "find_account_id_by_username",
    "has_client",
    "get_client",
    "set_client",
    "pop_client",
    "active_client_ids",
    "get_account_status_value",
    "set_account_status",
    "clear_account_status",
    "get_job",
    "set_job",
    "delete_job",
    "iter_jobs_values",
    "clear_state",
    "log_event",
    "account_to_dict",
    "store_pending_2fa_client",
    "get_pending_2fa_client",
    "pop_pending_2fa_client",
    # Job control
    "request_job_stop",
    "request_job_pause",
    "request_job_resume",
    "is_job_stop_requested",
    "wait_if_job_paused",
    "clear_job_control",
    # Thread-safe job store
    "job_store",
    "ThreadSafeJobStore",
]

SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)
LOG_FILE = SESSIONS_DIR / "activity.log"
_ACCOUNTS_FILE = SESSIONS_DIR / "accounts.json"

_clients: dict[str, IGClient] = {}        # account_id -> logged-in client
_accounts: dict[str, dict] = {}           # account_id -> metadata dict
_account_statuses: dict[str, str] = {}    # account_id -> "active" | "error" | "idle"
_pending_2fa_clients: dict[str, IGClient] = {}  # username -> client awaiting 2FA code


# ── Thread-safe job store ────────────────────────────────────────────────────


class ThreadSafeJobStore:
    """Thread-safe container for post-job state.

    All mutations to job dicts, stop flags, and pause events go through
    a single ``threading.Lock``.  The lock is held only for fast dict
    operations — never during I/O — so contention is negligible.

    ``threading.Event`` objects (pause/resume) are inherently thread-safe
    and are waited on **outside** the lock to avoid deadlocks.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}
        self._stop_flags: dict[str, bool] = {}
        self._pause_events: dict[str, threading.Event] = {}

    # ── job CRUD ──────────────────────────────────────────────────────────

    def put(self, job_id: str, job: dict) -> None:
        """Store (or overwrite) a job dict."""
        with self._lock:
            self._jobs[job_id] = job

    def get(self, job_id: str) -> dict:
        """Return the live job dict.  Raises ``KeyError`` if missing."""
        with self._lock:
            return self._jobs[job_id]

    def list_all(self) -> list[dict]:
        """Return a snapshot list of every job dict (shallow copies)."""
        with self._lock:
            return list(self._jobs.values())

    # ── fine-grained mutations ────────────────────────────────────────────

    def set_job_status(self, job_id: str, status: str) -> None:
        with self._lock:
            self._jobs[job_id]["status"] = status

    def update_result(
        self,
        job_id: str,
        account_id: str,
        *,
        status: str,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Update a single per-account result inside a job."""
        with self._lock:
            for result in self._jobs[job_id]["results"]:
                if result["accountId"] == account_id:
                    result["status"] = status
                    if error is not None:
                        result["error"] = error
                    if error_code is not None:
                        result["errorCode"] = error_code
                    break

    def get_result_status(self, job_id: str, account_id: str) -> str | None:
        """Read a single account's current status within a job."""
        with self._lock:
            for result in self._jobs[job_id]["results"]:
                if result["accountId"] == account_id:
                    return result.get("status")
        return None

    def tally_results(self, job_id: str) -> dict[str, int]:
        """Return ``{success: N, failed: N, skipped: N}``."""
        with self._lock:
            results = self._jobs[job_id]["results"]
            return {
                "success": sum(1 for r in results if r.get("status") == "success"),
                "failed": sum(1 for r in results if r.get("status") == "failed"),
                "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            }

    # ── stop / pause control ──────────────────────────────────────────────

    def request_stop(self, job_id: str) -> None:
        with self._lock:
            self._stop_flags[job_id] = True
            evt = self._pause_events.get(job_id)
        # Release pause *outside* the lock so the waiting thread can proceed.
        if evt is not None:
            evt.set()

    def is_stop_requested(self, job_id: str) -> bool:
        with self._lock:
            return self._stop_flags.get(job_id, False)

    def request_pause(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._pause_events:
                self._pause_events[job_id] = threading.Event()
            self._pause_events[job_id].clear()  # clear = paused

    def request_resume(self, job_id: str) -> None:
        with self._lock:
            evt = self._pause_events.get(job_id)
        if evt is not None:
            evt.set()

    def wait_if_paused(self, job_id: str) -> None:
        """Block the calling thread while the job is paused."""
        with self._lock:
            evt = self._pause_events.get(job_id)
        if evt is not None and not evt.is_set():
            evt.wait()

    def clear_control(self, job_id: str) -> None:
        """Remove stop/pause state after a job finishes."""
        with self._lock:
            self._stop_flags.pop(job_id, None)
            self._pause_events.pop(job_id, None)

    # ── bulk ──────────────────────────────────────────────────────────────

    def delete(self, job_id: str) -> bool:
        """Remove a job and its control state.  Returns True if it existed."""
        with self._lock:
            existed = self._jobs.pop(job_id, None) is not None
            self._stop_flags.pop(job_id, None)
            self._pause_events.pop(job_id, None)
        return existed

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._stop_flags.clear()
            self._pause_events.clear()


# Module-level singleton — importable everywhere.
job_store = ThreadSafeJobStore()


def _save_accounts() -> None:
    try:
        _ACCOUNTS_FILE.write_text(json.dumps(_accounts, indent=2))
    except OSError:
        pass


def _load_accounts() -> None:
    if not _ACCOUNTS_FILE.exists():
        return
    try:
        data = json.loads(_ACCOUNTS_FILE.read_text())
        if isinstance(data, dict):
            _accounts.update(data)
    except (OSError, json.JSONDecodeError):
        pass


_load_accounts()


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")


def _log_event(account_id: str, username: str, event: str, detail: str = "", status: str = "") -> None:
    entry = {
        "ts": _utc_now_iso(),
        "account_id": account_id,
        "username": username,
        "event": event,
        "detail": detail,
        "status": status,
    }
    try:
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as exc:
        raise RuntimeError(f"Failed to write activity log at {LOG_FILE}") from exc


def _account_to_dict(account_id: str, status: str = "idle", error: str | None = None) -> dict:
    meta = _accounts.get(account_id, {})
    return {
        "id": account_id,
        "username": meta.get("username", ""),
        "password": meta.get("password", ""),
        "proxy": meta.get("proxy"),
        "status": status,
        "error": error,
        "fullName": meta.get("full_name"),
        "followers": meta.get("followers"),
        "following": meta.get("following"),
        "totpEnabled": meta.get("totp_enabled", False),
        "avatar": meta.get("profile_pic_url"),
    }


def has_account(account_id: str) -> bool:
    return account_id in _accounts


def get_account(account_id: str) -> dict | None:
    return _accounts.get(account_id)


def set_account(account_id: str, meta: dict) -> None:
    _accounts[account_id] = meta
    _save_accounts()


def update_account(account_id: str, **updates) -> None:
    if account_id not in _accounts:
        _accounts[account_id] = {}
    _accounts[account_id].update(**updates)
    _save_accounts()


def pop_account(account_id: str) -> dict | None:
    result = _accounts.pop(account_id, None)
    _save_accounts()
    return result


def store_pending_2fa_client(username: str, client: IGClient) -> None:
    _pending_2fa_clients[username] = client


def get_pending_2fa_client(username: str) -> IGClient | None:
    return _pending_2fa_clients.get(username)


def pop_pending_2fa_client(username: str) -> IGClient | None:
    return _pending_2fa_clients.pop(username, None)


def iter_account_items():
    return _accounts.items()


def account_ids() -> list[str]:
    return list(_accounts.keys())


def find_account_id_by_username(username: str) -> str | None:
    normalized = username.lstrip("@")
    for account_id, meta in _accounts.items():
        if meta.get("username") == normalized:
            return account_id
    return None


def has_client(account_id: str) -> bool:
    return account_id in _clients


def get_client(account_id: str):
    return _clients.get(account_id)


def set_client(account_id: str, client: IGClient) -> None:
    _clients[account_id] = client


def pop_client(account_id: str):
    return _clients.pop(account_id, None)


def active_client_ids() -> list[str]:
    return list(_clients.keys())


def get_account_status_value(account_id: str, default: str = "idle") -> str:
    return _account_statuses.get(account_id, default)


def set_account_status(account_id: str, status: str) -> None:
    _account_statuses[account_id] = status


def clear_account_status(account_id: str) -> None:
    _account_statuses.pop(account_id, None)


def get_job(job_id: str) -> dict:
    return job_store.get(job_id)


def set_job(job_id: str, job: dict) -> None:
    job_store.put(job_id, job)


def delete_job(job_id: str) -> bool:
    """Remove a job from the in-memory store.  Returns True if it existed."""
    return job_store.delete(job_id)


def iter_jobs_values():
    return job_store.list_all()


# ── Job lifecycle control (delegates to job_store) ────────────────────────────

def request_job_stop(job_id: str) -> None:
    """Signal the job loop to stop after the current account finishes."""
    job_store.request_stop(job_id)


def is_job_stop_requested(job_id: str) -> bool:
    return job_store.is_stop_requested(job_id)


def request_job_pause(job_id: str) -> None:
    """Signal the job loop to pause before the next account."""
    job_store.request_pause(job_id)


def request_job_resume(job_id: str) -> None:
    """Release a paused job."""
    job_store.request_resume(job_id)


def wait_if_job_paused(job_id: str) -> None:
    """Block the calling thread if the job is paused; return when resumed or stopped."""
    job_store.wait_if_paused(job_id)


def clear_job_control(job_id: str) -> None:
    """Remove stop/pause state after a job finishes."""
    job_store.clear_control(job_id)


def clear_state() -> None:
    _clients.clear()
    _accounts.clear()
    _account_statuses.clear()
    job_store.clear()


def log_event(account_id: str, username: str, event: str, detail: str = "", status: str = "") -> None:
    _log_event(account_id, username, event, detail=detail, status=status)


def account_to_dict(account_id: str, status: str = "idle", error: str | None = None) -> dict:
    return _account_to_dict(account_id, status=status, error=error)
