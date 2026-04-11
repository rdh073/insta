"""Post-job execution runtime extracted from the legacy Instagram boundary."""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait as wait_futures
from pathlib import Path

from state import ThreadSafeJobStore, get_client, job_store, log_event

from .auth import _classify_exception
from .circuit_breaker import SyncCircuitBreaker
from .upload_payloads import _build_location, _build_usertags, _dispatch_upload


logger = logging.getLogger(__name__)


_UPLOAD_TIMEOUT_BY_TYPE: dict[str, int] = {
    "photo": 90,
    "album": 240,
    "reels": 360,
    "video": 360,
    "igtv": 360,
}
_UPLOAD_TIMEOUT_DEFAULT = 240


_upload_circuit_breaker = SyncCircuitBreaker(
    "instagram_upload",
    failure_threshold=5,
    recovery_timeout=120.0,
)


class PostJobExecutor:
    """Concurrent upload engine - posts the same media to N accounts in parallel."""

    def __init__(
        self,
        store: ThreadSafeJobStore | None = None,
        upload_timeout: int | None = None,
    ) -> None:
        self._store = store or job_store
        self._upload_timeout = upload_timeout

    def _get_upload_timeout(self, media_type: str) -> int:
        if self._upload_timeout is not None:
            return self._upload_timeout
        return _UPLOAD_TIMEOUT_BY_TYPE.get(media_type, _UPLOAD_TIMEOUT_DEFAULT)

    @staticmethod
    def _notify_sse() -> None:
        """Fire an SSE push from a worker thread (best-effort, never raises)."""
        try:
            from app.adapters.scheduler.event_bus import post_job_event_bus

            post_job_event_bus.notify("job_update")
        except Exception:
            pass

    def run(self, job_id: str) -> None:
        """Execute all account uploads for *job_id* concurrently."""
        job = self._store.get(job_id)
        self._store.set_job_status(job_id, "running")
        self._notify_sse()

        try:
            media_paths: list[str] = job["_media_paths"]
            caption: str = job["caption"]
            media_type: str = job.get("mediaType", "photo")
            thumbnail_path: str | None = job.get("_thumbnail_path")
            igtv_title: str | None = job.get("_igtv_title")
            usertags_raw: list[dict] = job.get("_usertags") or []
            location_raw: dict | None = job.get("_location")
            extra_data: dict = job.get("_extra_data") or {}

            accounts = job["results"]
            if not accounts:
                self._store.set_job_status(job_id, "completed")
                self._store.clear_control(job_id)
                return

            executor = ThreadPoolExecutor(max_workers=len(accounts))
            futures = {
                executor.submit(
                    self._upload_one,
                    job_id=job_id,
                    account_id=result["accountId"],
                    username=result["username"],
                    media_paths=media_paths,
                    caption=caption,
                    media_type=media_type,
                    thumbnail_path=thumbnail_path,
                    igtv_title=igtv_title,
                    usertags_raw=usertags_raw,
                    location_raw=location_raw,
                    extra_data=extra_data,
                ): result
                for result in accounts
            }

            outer_timeout = self._get_upload_timeout(media_type) + 60
            done, not_done = wait_futures(futures.keys(), timeout=outer_timeout)
            executor.shutdown(wait=False)

            for future in not_done:
                result = futures[future]
                account_id = result["accountId"]
                current = self._store.get_result_status(job_id, account_id)
                if current not in ("success", "failed", "skipped"):
                    self._store.update_result(
                        job_id,
                        account_id,
                        status="failed",
                        error="Upload worker stalled — killed by outer deadline",
                        error_code="worker_stall",
                    )
                    self._notify_sse()

            tally = self._store.tally_results(job_id)
            self._store.clear_control(job_id)

            if tally["skipped"] > 0 and tally["success"] == 0 and tally["failed"] == 0:
                final = "stopped"
            elif tally["skipped"] > 0:
                final = "partial"
            elif tally["failed"] == 0:
                final = "completed"
            elif tally["success"] == 0:
                final = "failed"
            else:
                final = "partial"
            self._store.set_job_status(job_id, final)
            self._notify_sse()

        except Exception:
            try:
                self._store.clear_control(job_id)
                self._store.set_job_status(job_id, "failed")
                self._notify_sse()
            except Exception:
                pass
            raise

        finally:
            self._cleanup_temp_files(job)

    def _upload_one(
        self,
        *,
        job_id: str,
        account_id: str,
        username: str,
        media_paths: list[str],
        caption: str,
        media_type: str,
        thumbnail_path: str | None,
        igtv_title: str | None,
        usertags_raw: list[dict],
        location_raw: dict | None,
        extra_data: dict,
    ) -> None:
        store = self._store

        if store.is_stop_requested(job_id):
            store.update_result(job_id, account_id, status="skipped")
            return

        store.wait_if_paused(job_id)

        if store.is_stop_requested(job_id):
            store.update_result(job_id, account_id, status="skipped")
            return

        if not _upload_circuit_breaker.allow_request():
            store.update_result(
                job_id,
                account_id,
                status="failed",
                error="Instagram API circuit open — too many recent failures, will retry later",
                error_code="circuit_open",
            )
            self._notify_sse()
            logger.warning("Circuit open: skipping upload for @%s (job=%s)", username, job_id)
            return

        cl = get_client(account_id)
        if not cl:
            store.update_result(job_id, account_id, status="failed", error="Account not logged in")
            self._notify_sse()
            return

        store.update_result(job_id, account_id, status="uploading")
        self._notify_sse()
        print(
            f"[POST] Uploading for @{username}: "
            f"type={media_type} caption={repr(caption[:100])}",
            file=sys.stderr,
        )

        usertags = _build_usertags(usertags_raw)
        location = _build_location(location_raw)
        upload_timeout = self._get_upload_timeout(media_type)

        upload_exec = ThreadPoolExecutor(max_workers=1)
        upload_future = upload_exec.submit(
            _dispatch_upload,
            cl,
            media_type,
            media_paths,
            caption,
            thumbnail_path,
            igtv_title,
            usertags,
            location,
            extra_data,
        )

        try:
            upload_future.result(timeout=upload_timeout)

        except FuturesTimeoutError:
            store.update_result(
                job_id,
                account_id,
                status="failed",
                error=f"Upload timed out after {upload_timeout}s",
                error_code="upload_timeout",
            )
            self._notify_sse()
            _upload_circuit_breaker.record_failure(retryable=True)
            log_event(account_id, username, "post_failed", detail="upload_timeout")
            return

        except Exception as error:
            failure = _classify_exception(
                error,
                operation="post_media",
                account_id=account_id,
                username=username,
            )
            store.update_result(
                job_id,
                account_id,
                status="failed",
                error=failure.user_message,
                error_code=failure.code,
            )
            self._notify_sse()
            _upload_circuit_breaker.record_failure(retryable=failure.retryable)
            log_event(
                account_id,
                username,
                "post_failed",
                detail=failure.detail or failure.user_message,
            )
            return

        finally:
            upload_exec.shutdown(wait=False)

        store.update_result(job_id, account_id, status="success")
        self._notify_sse()
        _upload_circuit_breaker.record_success()
        log_event(account_id, username, "post_success", detail=f"job={job_id}")

    @staticmethod
    def _cleanup_temp_files(job: dict) -> None:
        for path in job.get("_media_paths", []):
            Path(path).unlink(missing_ok=True)
            if path.endswith((".mp4", ".mov")):
                Path(path + ".jpg").unlink(missing_ok=True)
        thumb = job.get("_thumbnail_path")
        if thumb:
            Path(thumb).unlink(missing_ok=True)


_executor = PostJobExecutor()


def run_post_job(job_id: str) -> None:
    """Legacy entry point - delegates to PostJobExecutor."""
    _executor.run(job_id)
