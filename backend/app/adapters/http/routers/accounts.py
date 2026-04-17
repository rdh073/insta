"""Account management endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Response, UploadFile, File

# Server-side cooldown for bulk profile hydration — prevents the frontend from
# accidentally triggering a burst of user_info() calls on every reconnect.
_BULK_HYDRATE_COOLDOWN_SEC = 300  # 5 minutes
_last_bulk_hydrate_ts: float = 0.0

from app.adapters.http.event_bus import account_event_bus
from app.adapters.http.streaming import sse_response
from pydantic import BaseModel

from app.adapters.http.schemas.accounts import (
    LoginRequest,
    TwoFARequest,
    ProxyRequest,
    BulkAccountIds,
    BulkProxyRequest,
    TOTPSetupRequest,
    ImportAccountsRequest,
)
from app.adapters.http.dependencies import (
    get_account_auth_usecases,
    get_account_challenge_usecases,
    get_account_connectivity_usecases,
    get_account_edit_usecases,
    get_account_profile_usecases,
    get_account_proxy_usecases,
    get_account_security_usecases,
    get_account_totp_usecases,
    get_account_import_usecases,
    get_account_repo,
    get_session_store,
)
from app.adapters.http.utils import format_error, format_instagram_failure
from app.application.dto.account_dto import LoginRequest as DTOLoginRequest

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
logger = logging.getLogger(__name__)


def _account_failure_stream_payload(usecases, account_id: str, status: str) -> dict:
    """Build account_updated payload with persisted failure detail when present."""
    payload: dict = {"id": account_id, "status": status}
    repo = getattr(usecases, "account_repo", None)
    if repo is None:
        return payload

    try:
        account = repo.get(account_id) or {}
    except Exception:
        return payload

    if (last_error := account.get("last_error")) is not None:
        payload["last_error"] = last_error
    if (last_error_code := account.get("last_error_code")) is not None:
        payload["last_error_code"] = last_error_code
    return payload


def _hydrate_and_publish(usecases: "AccountAuthUseCases", account_id: str) -> None:
    """Fetch full profile (name, pic, followers, following) and push SSE events.

    Makes two sequential Instagram API calls:
    1. account_info() — validates session, gets full_name + profile_pic_url
    2. user_info(pk)  — gets follower_count + following_count

    Both results are published independently so the frontend updates as each
    call completes rather than waiting for both.  The fresh profile_pic_url is
    also pre-downloaded into the avatar disk cache while the signed CDN URL is
    still valid, so images survive URL expiry on subsequent page loads.
    """
    from app.adapters.http.routers.media_proxy import warm_image_cache

    result = usecases.hydrate_account_profile(account_id)
    if result:
        account_event_bus.publish("account_updated", result)
        if pic_url := result.get("profile_pic_url"):
            warm_image_cache(pic_url)
    elif not usecases.client_repo.exists(account_id):
        # Hard session failure: hydrate_account_profile evicted the client and
        # persisted the derived status (error/challenge/2fa_required). Push it
        # immediately so SSE reflects the canonical backend state.
        persisted_status = usecases.status_repo.get(account_id, "error")
        account_event_bus.publish(
            "account_updated",
            _account_failure_stream_payload(usecases, account_id, persisted_status),
        )
        return  # No point fetching follower counts if the session is dead.

    counts = usecases.refresh_follower_counts(account_id)
    if counts:
        account_event_bus.publish("account_updated", counts)


def _refresh_counts_and_publish(usecases, account_id: str) -> None:
    """Fetch follower/following via user_info() and push an SSE event."""
    result = usecases.refresh_follower_counts(account_id)
    if result:
        account_event_bus.publish("account_updated", result)


def _bulk_hydrate_sequential(usecases, account_ids: list, delay: float = 3.0) -> None:
    """Refresh follower/following counts one-by-one with delay between calls.

    Uses user_info() (not account_info) — session is already validated at
    login time. Sequential + delay avoids Instagram rate-limiting from
    concurrent requests on the same IP.

    Skips accounts that are currently in a rate-limit cooldown window so the
    bulk job does not hammer Instagram while an account is already blocked.
    Delay increased to 3 s (from 1.5 s) to be conservative.
    """
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard
    _log = __import__("logging").getLogger(__name__)

    for i, account_id in enumerate(account_ids):
        limited, retry_after = rate_limit_guard.is_limited(account_id)
        if limited:
            _log.debug(
                "bulk_hydrate: skipping %s — rate-limited for %.0fs", account_id, retry_after
            )
        else:
            _refresh_counts_and_publish(usecases, account_id)
        if i < len(account_ids) - 1:
            time.sleep(delay)


@router.get("/events")
async def account_events():
    """SSE stream for real-time account updates.

    Clients connect once and receive ``account_updated`` events whenever
    background tasks (e.g. profile hydration) mutate account state.

    Event format::

        data: {"type": "account_updated", "id": "<uuid>", "followers": 1234, ...}

    """
    q = account_event_bus.subscribe()

    async def generate():
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            account_event_bus.unsubscribe(q)

    return sse_response(
        generate(),
        logger=logger,
        error_event_name="run_error",
    )


def _format_error_from_failure(exc) -> tuple[int, dict]:
    """Convert exception to HTTP status and structured error detail.

    Returns a dict with 'message', 'code', and 'family' so clients can
    differentiate error types (e.g. bad_password vs challenge_required).
    Checks for attached _instagram_failure first (set by use case error handler),
    then falls back to format_instagram_failure on the raw exception.
    """
    failure = getattr(exc, "_instagram_failure", None)
    if failure is not None:
        payload = format_instagram_failure(failure)
    else:
        payload = format_instagram_failure(exc)
    return int(payload["status_code"]), {
        "message": str(payload["detail"]),
        "code": payload.get("code", "unknown_error"),
        "family": payload.get("family", "unknown"),
    }


def _serialize_account(acc, include_password: bool = False) -> dict:
    """Serialize AccountResponse to API response dict."""
    from app.application.dto.account_dto import AccountResponse

    if isinstance(acc, AccountResponse):
        return {
            "id": acc.id,
            "username": acc.username,
            "password": acc.password if include_password else "",
            "proxy": acc.proxy,
            "status": acc.status,
            "fullName": acc.full_name,
            "followers": acc.followers,
            "following": acc.following,
            "avatar": acc.avatar,
            "totpEnabled": acc.totp_enabled or False,
            "lastVerifiedAt": acc.last_verified_at,
            "lastError": acc.last_error,
            "lastErrorCode": acc.last_error_code,
            "lastErrorFamily": acc.last_error_family,
        }
    # Fallback for dict-like objects
    return {
        "id": acc.get("id", ""),
        "username": acc.get("username", ""),
        "password": acc.get("password", "") if include_password else "",
        "proxy": acc.get("proxy"),
        "status": acc.get("status", "idle"),
        "fullName": acc.get("full_name"),
        "followers": acc.get("followers"),
        "following": acc.get("following"),
        "avatar": acc.get("avatar") or acc.get("profile_pic_url"),
        "totpEnabled": acc.get("totp_enabled", False),
        "lastVerifiedAt": acc.get("last_verified_at"),
        "lastError": acc.get("last_error"),
        "lastErrorCode": acc.get("last_error_code"),
        "lastErrorFamily": acc.get("last_error_family"),
    }


@router.get("")
def list_accounts(usecases=Depends(get_account_profile_usecases)):
    """List all accounts with their status."""
    accounts = usecases.list_accounts()
    return [_serialize_account(acc) for acc in accounts]


@router.post("/login")
async def login(
    body: LoginRequest,
    background_tasks: BackgroundTasks,
    usecases=Depends(get_account_auth_usecases),
):
    """Login an Instagram account.

    The Instagram network call runs in a thread pool (non-blocking). When the
    account becomes active, profile hydration (followers/following) is
    dispatched as a background task so the response returns immediately.
    """
    try:
        request = DTOLoginRequest(
            username=body.username,
            password=body.password,
            proxy=body.proxy,
            totp_secret=body.totp_secret,
            country=body.country,
            country_code=body.country_code,
            locale=body.locale,
            timezone_offset=body.timezone_offset,
        )
        result = await asyncio.to_thread(usecases.login_account, request)
        if result.status == "active":
            background_tasks.add_task(_hydrate_and_publish, usecases, result.id)
        return _serialize_account(result)
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/login/2fa")
async def verify_2fa(
    body: TwoFARequest,
    background_tasks: BackgroundTasks,
    usecases=Depends(get_account_auth_usecases),
):
    """Complete 2FA login.

    Returns immediately after 2FA is accepted. Follower/following counts are
    fetched in the background so the frontend is not blocked.
    """
    try:
        result = await asyncio.to_thread(
            usecases.complete_2fa_login, body.account_id, body.code, body.is_totp
        )
        if result.status == "active":
            background_tasks.add_task(_hydrate_and_publish, usecases, result.id)
        return _serialize_account(result)
    except ValueError as e:
        raise HTTPException(
            status_code=404, detail=format_error(e, "Account not found")
        )
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/{account_id}/totp/setup")
def setup_totp(account_id: str, usecases=Depends(get_account_totp_usecases)):
    """Generate a new TOTP secret for an account."""
    try:
        return usecases.setup_totp(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404, detail=format_error(e, "Account not found")
        )
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/{account_id}/totp/verify")
def verify_totp_setup(
    account_id: str, body: TOTPSetupRequest, usecases=Depends(get_account_totp_usecases)
):
    """Verify TOTP secret by checking if provided code is valid."""
    try:
        return usecases.verify_totp_setup(account_id, body.secret, body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=format_error(e, "Invalid request"))
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.delete("/{account_id}/totp")
def disable_totp(account_id: str, usecases=Depends(get_account_totp_usecases)):
    """Disable TOTP for an account."""
    try:
        return usecases.disable_totp(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404, detail=format_error(e, "Account not found")
        )
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/import")
def import_accounts(
    body: ImportAccountsRequest, usecases=Depends(get_account_import_usecases)
):
    """Import accounts from text format."""
    results = usecases.import_accounts_text(body.text)
    return [
        {
            "id": r.id,
            "username": r.username,
            "status": r.status,
        }
        for r in results
    ]


@router.delete("/{account_id}")
def logout(account_id: str, usecases=Depends(get_account_auth_usecases)):
    """Logout and remove an account."""
    try:
        result = usecases.logout_account(account_id)
        return {
            "id": result.id,
            "username": result.username,
            "status": result.status,
            "server_logout": result.server_logout,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=404, detail=format_error(e, "Account not found")
        )


@router.get("/sessions/export")
def export_sessions(session_store=Depends(get_session_store)):
    """Export all session files as a JSON archive."""
    from fastapi.responses import Response

    try:
        sessions = session_store.export_all_sessions()
        content = json.dumps(sessions).encode()
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=insta-sessions.json"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=format_error(exc, "Failed to export sessions")
        )


@router.post("/sessions/import")
async def import_sessions(
    file: UploadFile = File(...), usecases=Depends(get_account_import_usecases)
):
    """Import sessions from exported JSON archive."""
    content = await file.read()
    try:
        sessions: dict = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    results = usecases.import_session_archive(sessions)
    return [
        {
            "id": r.id,
            "username": r.username,
            "status": r.status,
        }
        for r in results
    ]


class ProxyCheckRequest(BaseModel):
    proxy: str


@router.post("/proxy/check")
async def check_proxy(
    body: ProxyCheckRequest, usecases=Depends(get_account_proxy_usecases)
):
    """Test if a proxy URL is reachable and measure latency."""
    result = await usecases.check_proxy(body.proxy)
    return {
        "proxy_url":  result.proxy_url,
        "reachable":  result.reachable,
        "latency_ms": result.latency_ms,
        "ip_address": result.ip_address,
        "protocol":   result.protocol,
        "anonymity":  result.anonymity,
        "error":      result.error,
    }


@router.get("/{account_id}/proxy/check")
async def check_account_proxy(
    account_id: str,
    proxy_usecases=Depends(get_account_proxy_usecases),
    profile_usecases=Depends(get_account_profile_usecases),
):
    """Test the proxy currently assigned to an account."""
    accounts = profile_usecases.list_accounts()
    account = next((a for a in accounts if a.id == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.proxy:
        return {
            "proxy_url":  None,
            "reachable":  False,
            "protocol":   None,
            "anonymity":  None,
            "error":      "No proxy assigned to this account",
        }
    result = await proxy_usecases.check_proxy(account.proxy)
    return {
        "proxy_url":  result.proxy_url,
        "reachable":  result.reachable,
        "latency_ms": result.latency_ms,
        "ip_address": result.ip_address,
        "protocol":   result.protocol,
        "anonymity":  result.anonymity,
        "error":      result.error,
    }


@router.patch("/{account_id}/proxy")
def set_proxy(
    account_id: str, body: ProxyRequest, usecases=Depends(get_account_proxy_usecases)
):
    """Update proxy for an account."""
    try:
        result = usecases.set_account_proxy(account_id, body.proxy)
        return {
            "id": result.id,
            "username": result.username,
            "status": result.status,
            "proxy": result.proxy,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=404, detail=format_error(e, "Account not found")
        )


@router.post("/{account_id}/refresh-counts")
async def refresh_account_counts(
    account_id: str,
    background_tasks: BackgroundTasks,
    usecases=Depends(get_account_auth_usecases),
):
    """Refresh follower/following counts for one account via user_info().

    Called by the frontend when the user selects or expands an account.
    Runs in the background and pushes an account_updated SSE event when done.
    """
    background_tasks.add_task(_refresh_counts_and_publish, usecases, account_id)
    return {"status": "queued"}


@router.post("/{account_id}/relogin")
async def relogin_account(
    account_id: str,
    background_tasks: BackgroundTasks,
    usecases=Depends(get_account_auth_usecases),
):
    """Re-authenticate an existing account."""
    try:
        result = await asyncio.to_thread(usecases.relogin_account, account_id)
        if result.status == "active":
            background_tasks.add_task(_hydrate_and_publish, usecases, result.id)
        return _serialize_account(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=format_error(e, "Invalid request"))
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/bulk/relogin")
async def bulk_relogin(
    body: BulkAccountIds, usecases=Depends(get_account_auth_usecases)
):
    """Re-authenticate multiple accounts in parallel."""
    from app.application.dto.account_dto import BulkReloginRequest

    request = BulkReloginRequest(account_ids=body.account_ids, concurrency=5)
    results = await usecases.bulk_relogin_accounts(request)
    return [_serialize_account(acc) for acc in results]


@router.post("/bulk/logout")
def bulk_logout(body: BulkAccountIds, usecases=Depends(get_account_auth_usecases)):
    """Logout and remove multiple accounts."""
    try:
        results = usecases.bulk_logout_accounts(body.account_ids)
        return [
            {
                "id": acc.id,
                "username": acc.username,
                "status": acc.status,
                "server_logout": acc.server_logout,
            }
            for acc in results
        ]
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=format_error(e, "Bulk logout failed")
        )


@router.patch("/bulk/proxy")
def bulk_set_proxy(
    body: BulkProxyRequest, usecases=Depends(get_account_proxy_usecases)
):
    """Set the same proxy on multiple accounts at once."""
    results = usecases.bulk_set_proxy(body.account_ids, body.proxy)
    return [
        {
            "id": acc.id,
            "username": acc.username,
            "status": acc.status,
            "proxy": acc.proxy,
        }
        for acc in results
    ]


@router.post("/bulk/hydrate-profiles")
async def bulk_hydrate_profiles(
    background_tasks: BackgroundTasks,
    usecases=Depends(get_account_auth_usecases),
    profile_usecases=Depends(get_account_profile_usecases),
):
    """Fire-and-forget profile hydration for all active accounts.

    Schedules background tasks that fetch follower/following counts from
    Instagram and publish account_updated SSE events. Returns immediately.
    Used on app startup to populate profile data for pre-existing accounts.

    Protected by a server-side 5-minute cooldown to prevent the frontend from
    triggering a burst of user_info() calls on rapid reconnects or page reloads.
    """
    global _last_bulk_hydrate_ts
    now = time.time()
    remaining = _BULK_HYDRATE_COOLDOWN_SEC - (now - _last_bulk_hydrate_ts)
    if remaining > 0:
        return {"queued": 0, "cooldown_remaining": int(remaining)}

    accounts = profile_usecases.list_accounts()
    active_ids = [acc.id for acc in accounts if acc.status == "active"]
    if active_ids:
        _last_bulk_hydrate_ts = now
        background_tasks.add_task(_bulk_hydrate_sequential, usecases, active_ids)
    return {"queued": len(active_ids)}


@router.post("/bulk/verify")
async def bulk_verify_accounts(
    body: BulkAccountIds, usecases=Depends(get_account_connectivity_usecases)
):
    """Probe Instagram connectivity for multiple accounts (limited concurrency to avoid rate-limits)."""
    results = await usecases.bulk_verify_accounts(body.account_ids, concurrency=3)
    return [
        {
            "id": acc.id,
            "username": acc.username,
            "healthy": acc.status == "active",
            "status": acc.status,
            "last_verified_at": acc.last_verified_at,
            "last_error": acc.last_error,
            "last_error_code": acc.last_error_code,
            "last_error_family": acc.last_error_family,
        }
        for acc in results
    ]


@router.post("/{account_id}/verify")
async def verify_account(
    account_id: str, usecases=Depends(get_account_connectivity_usecases)
):
    """Probe Instagram connectivity for an active account via account_info()."""
    from app.adapters.http.routers.media_proxy import warm_image_cache

    try:
        result = await asyncio.to_thread(
            usecases.verify_account_connectivity, account_id
        )
        # Publish SSE so followers/following update live in the UI
        event_payload: dict = {"id": account_id}
        if result.followers is not None:
            event_payload["followers"] = result.followers
        if result.following is not None:
            event_payload["following"] = result.following
        if result.full_name is not None:
            event_payload["full_name"] = result.full_name
        if result.avatar is not None:
            event_payload["avatar"] = result.avatar
        if len(event_payload) > 1:
            account_event_bus.publish("account_updated", event_payload)
        # Pre-warm avatar cache while the fresh CDN URL is still valid
        if result.avatar:
            warm_image_cache(result.avatar)
        return {
            "healthy": result.status == "active",
            "status": result.status,
            "followers": result.followers,
            "following": result.following,
            "fullName": result.full_name,
            "avatar": result.avatar,
            "last_verified_at": result.last_verified_at,
            "last_error": result.last_error,
            "last_error_code": result.last_error_code,
            "last_error_family": result.last_error_family,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=format_error(e, "Account not found or not logged in"),
        )
    except Exception as e:
        status_code, detail = _format_error_from_failure(e)
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/rate-limited")
def get_rate_limited_accounts():
    """Return all accounts currently in Instagram rate-limit cooldown.

    Response::

        [
          {"account_id": "abc", "retry_after": 3547.2, "reason": "rate_limit"},
          ...
        ]
    """
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard

    limited = rate_limit_guard.get_all_limited()
    return [
        {
            "account_id": aid,
            "retry_after": round(info["retry_after"], 1),
            "reason": info["reason"],
        }
        for aid, info in limited.items()
    ]


@router.get("/{account_id}/credentials")
def get_credentials(account_id: str, repo=Depends(get_account_repo)):
    """Return stored credentials for an account (password + TOTP secret).

    Intended for the operator UI only — never expose to untrusted clients.
    """
    record = repo.get(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return {
        "username": record.username,
        "password": record.password or "",
        "totpSecret": record.totp_secret or "",
    }


class _PrivacyRequest(BaseModel):
    private: bool


class _PresenceRequest(BaseModel):
    disabled: bool


class _ProfileEditRequest(BaseModel):
    first_name: str | None = None
    biography: str | None = None
    external_url: str | None = None


def _serialize_account_profile(profile) -> dict:
    """Serialize AccountProfile DTO into the JSON envelope used by this router."""
    return {
        "id": profile.id,
        "username": profile.username,
        "isPrivate": profile.is_private,
        "fullName": profile.full_name,
        "biography": profile.biography,
        "externalUrl": profile.external_url,
        "avatar": profile.profile_pic_url,
        "presenceDisabled": profile.presence_disabled,
    }


@router.post("/{account_id}/privacy")
def set_account_privacy(
    account_id: str,
    body: _PrivacyRequest,
    usecases=Depends(get_account_edit_usecases),
):
    """Toggle account privacy (private vs public)."""
    try:
        if body.private:
            profile = usecases.set_private(account_id)
        else:
            profile = usecases.set_public(account_id)
        return _serialize_account_profile(profile)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        # ValueError without translated failure → validation/auth (400/404 family).
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/{account_id}/profile/avatar")
async def change_account_avatar(
    account_id: str,
    file: UploadFile = File(...),
    usecases=Depends(get_account_edit_usecases),
):
    """Upload a new profile picture for the account."""
    import tempfile

    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    payload = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    try:
        try:
            profile = usecases.change_avatar(account_id, tmp_path)
        except ValueError as exc:
            status_code, detail = _format_error_from_failure(exc)
            if status_code == 500:
                status_code = 400
            raise HTTPException(status_code=status_code, detail=detail)
        except Exception as exc:
            status_code, detail = _format_error_from_failure(exc)
            raise HTTPException(status_code=status_code, detail=detail)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return _serialize_account_profile(profile)


@router.patch("/{account_id}/profile")
def edit_account_profile(
    account_id: str,
    body: _ProfileEditRequest,
    usecases=Depends(get_account_edit_usecases),
):
    """Edit profile fields (first_name, biography, external_url)."""
    try:
        profile = usecases.edit_profile(
            account_id,
            first_name=body.first_name,
            biography=body.biography,
            external_url=body.external_url,
        )
        return _serialize_account_profile(profile)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/{account_id}/presence")
def set_account_presence(
    account_id: str,
    body: _PresenceRequest,
    usecases=Depends(get_account_edit_usecases),
):
    """Toggle the 'show activity status' presence flag."""
    try:
        profile = usecases.set_presence_disabled(account_id, body.disabled)
        return _serialize_account_profile(profile)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


class _ConfirmEmailRequest(BaseModel):
    email: str


class _ConfirmPhoneRequest(BaseModel):
    phone: str


def _serialize_confirmation(req) -> dict:
    return {
        "accountId": req.account_id,
        "channel": req.channel,
        "target": req.target,
        "sent": req.sent,
        "message": req.message,
        "extra": req.extra,
    }


def _serialize_security_info(info) -> dict:
    return {
        "accountId": info.account_id,
        "twoFactorEnabled": info.two_factor_enabled,
        "totpTwoFactorEnabled": info.totp_two_factor_enabled,
        "smsTwoFactorEnabled": info.sms_two_factor_enabled,
        "whatsappTwoFactorEnabled": info.whatsapp_two_factor_enabled,
        "backupCodesAvailable": info.backup_codes_available,
        "trustedDevicesCount": info.trusted_devices_count,
        "isPhoneConfirmed": info.is_phone_confirmed,
        "isEligibleForWhatsapp": info.is_eligible_for_whatsapp,
        "nationalNumber": info.national_number,
        "countryCode": info.country_code,
        "extra": info.extra,
    }


@router.post("/{account_id}/confirm-email")
def request_confirm_email(
    account_id: str,
    body: _ConfirmEmailRequest,
    usecases=Depends(get_account_edit_usecases),
):
    """Ask Instagram to deliver a confirmation code to ``email``.

    Pairs with a prior ``PATCH /profile`` that set the new email — this call
    triggers the verification step the vendor requires before the change takes
    effect.
    """
    try:
        result = usecases.request_email_confirm(account_id, body.email)
        return _serialize_confirmation(result)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


@router.post("/{account_id}/confirm-phone")
def request_confirm_phone(
    account_id: str,
    body: _ConfirmPhoneRequest,
    usecases=Depends(get_account_edit_usecases),
):
    """Ask Instagram to deliver a confirmation code to ``phone``."""
    try:
        result = usecases.request_phone_confirm(account_id, body.phone)
        return _serialize_confirmation(result)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{account_id}/security-info")
def get_account_security_info(
    account_id: str,
    usecases=Depends(get_account_security_usecases),
):
    """Read the account's 2FA / trusted-device posture."""
    try:
        info = usecases.get_account_security_info(account_id)
        return _serialize_security_info(info)
    except ValueError as exc:
        status_code, detail = _format_error_from_failure(exc)
        if status_code == 500:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as exc:
        status_code, detail = _format_error_from_failure(exc)
        raise HTTPException(status_code=status_code, detail=detail)


class _ChallengeSubmitRequest(BaseModel):
    code: str


def _serialize_challenge_pending(pending) -> dict:
    return {
        "account_id": pending.account_id,
        "username": pending.username,
        "method": pending.method,
        "contact_hint": pending.contact_hint,
        "created_at": pending.created_at,
    }


def _serialize_challenge_resolution(resolution) -> dict:
    return {
        "account_id": resolution.account_id,
        "status": resolution.status,
        "message": resolution.message,
        "next_step": resolution.next_step,
    }


@router.get("/challenges/pending")
def list_pending_challenges(usecases=Depends(get_account_challenge_usecases)):
    """List every in-flight Instagram login challenge."""
    return [_serialize_challenge_pending(p) for p in usecases.list_pending()]


@router.get("/{account_id}/challenge")
def get_pending_challenge(
    account_id: str, usecases=Depends(get_account_challenge_usecases)
):
    """Return the pending challenge for ``account_id`` (204 when absent)."""
    try:
        pending = usecases.get(account_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=format_error(exc, "Account not found")
        )
    if pending is None:
        return Response(status_code=204)
    return _serialize_challenge_pending(pending)


@router.post("/{account_id}/challenge/submit")
def submit_challenge_code(
    account_id: str,
    body: _ChallengeSubmitRequest,
    usecases=Depends(get_account_challenge_usecases),
):
    """Submit the 6-digit code the operator received for ``account_id``."""
    try:
        resolution = usecases.submit_code(account_id, body.code)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=format_error(exc, "Account not found")
        )
    payload = _serialize_challenge_resolution(resolution)
    if resolution.status == "failed":
        raise HTTPException(status_code=400, detail=payload)
    return payload


@router.delete("/{account_id}/challenge")
def cancel_challenge(
    account_id: str, usecases=Depends(get_account_challenge_usecases)
):
    """Cancel a pending challenge so the blocked login() call raises."""
    try:
        usecases.cancel(account_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=format_error(exc, "Account not found")
        )
    return Response(status_code=204)


@router.delete("/rate-limited/{account_id}")
def clear_rate_limit(account_id: str):
    """Manually clear the rate-limit cooldown for an account.

    Useful after re-authentication or proxy rotation.
    """
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard

    rate_limit_guard.clear(account_id)
    return {"cleared": account_id}
