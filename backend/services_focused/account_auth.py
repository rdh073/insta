from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

import state
from instagram import (
    activate_account_client,
    complete_2fa_client,
    create_authenticated_client,
)
from state import (
    TwoFactorRequired,
    account_to_dict,
    clear_account_status,
    get_account,
    get_client,
    has_account,
    has_client,
    log_event,
    pop_account,
    pop_client,
    set_account,
    update_account,
)

from .account_query import (
    find_account_id_by_username,
    get_account_status,
    get_account_username,
)
from .common import classify_exception
from .totp import generate_totp_code, normalize_totp_secret, verify_totp_code


def apply_account_proxy(account_id: str, proxy: str) -> str:
    username = get_account_username(account_id)
    update_account(account_id, proxy=proxy)
    client = get_client(account_id)
    if client:
        client.set_proxy(proxy)
    log_event(account_id, username, "proxy_changed", detail=proxy)
    return username


def login_account(
    username: str,
    password: str,
    proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    country: Optional[str] = None,
    country_code: Optional[int] = None,
    locale: Optional[str] = None,
    timezone_offset: Optional[int] = None,
) -> dict:
    existing = find_account_id_by_username(username)
    if existing and has_client(existing):
        return account_to_dict(existing, status="active")

    if totp_secret:
        totp_secret = normalize_totp_secret(totp_secret) or None

    account_id = existing or str(uuid.uuid4())
    set_account(
        account_id,
        {
            "username": username,
            "password": password,
            "proxy": proxy,
            "totp_secret": totp_secret,
            "country": country,
            "country_code": country_code,
            "locale": locale,
            "timezone_offset": timezone_offset,
        },
    )

    try:
        client = create_authenticated_client(
            username,
            password,
            proxy,
            totp_secret=totp_secret,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )
        result = activate_account_client(account_id, client)
        log_event(account_id, username, "login_success", status="active")
        return result
    except TwoFactorRequired:
        if totp_secret:
            try:
                code = generate_totp_code(totp_secret)
                client = complete_2fa_client(
                    username,
                    password,
                    code,
                    proxy,
                    country=country,
                    country_code=country_code,
                    locale=locale,
                    timezone_offset=timezone_offset,
                )
                result = activate_account_client(account_id, client)
                log_event(account_id, username, "login_success_totp", status="active")
                return result
            except Exception as exc:
                failure = classify_exception(
                    exc,
                    operation="complete_2fa",
                    account_id=account_id,
                    username=username,
                )
                log_event(
                    account_id,
                    username,
                    "login_totp_auto_failed",
                    detail=failure.user_message,
                    status="error",
                )
                pop_account(account_id)
                raise

        log_event(account_id, username, "login_2fa_required", status="2fa_required")
        return {"id": account_id, "username": username, "status": "2fa_required"}
    except Exception as exc:
        failure = classify_exception(
            exc,
            operation="login",
            account_id=account_id,
            username=username,
        )
        log_event(account_id, username, "login_failed", detail=failure.user_message, status="error")
        pop_account(account_id)
        raise


def complete_2fa_login_account(account_id: str, code: str, is_totp: bool = False) -> dict:
    if not has_account(account_id):
        raise ValueError("Account not found")

    meta = get_account(account_id) or {}
    username = meta.get("username", "")
    password = meta.get("password", "")
    proxy = meta.get("proxy")
    country = meta.get("country")
    country_code = meta.get("country_code")
    locale = meta.get("locale")
    timezone_offset = meta.get("timezone_offset")

    if is_totp:
        totp_secret = meta.get("totp_secret")
        if not totp_secret:
            raise ValueError("TOTP is not enabled for this account")
        if not verify_totp_code(totp_secret, code):
            log_event(account_id, username, "totp_verification_failed", status="error")
            raise ValueError("Invalid TOTP code")
        log_event(account_id, username, "totp_verified", status="active")

        result = activate_account_client(
            account_id,
            complete_2fa_client(
                username,
                password,
                "",
                proxy,
                country=country,
                country_code=country_code,
                locale=locale,
                timezone_offset=timezone_offset,
            ),
        )
        log_event(account_id, username, "login_success", status="active")
        return result

    try:
        client = complete_2fa_client(
            username,
            password,
            code,
            proxy,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )
        result = activate_account_client(account_id, client)
        log_event(account_id, username, "login_success", status="active")
        return result
    except Exception as exc:
        failure = classify_exception(
            exc,
            operation="complete_2fa",
            account_id=account_id,
            username=username,
        )
        log_event(account_id, username, "login_2fa_failed", detail=failure.user_message, status="error")
        raise


def import_accounts_text(text: str) -> list[dict]:
    results = []
    for line in text.strip().splitlines():
        totp_secret = None
        if "|" in line:
            line, totp_secret = line.rsplit("|", 1)
            totp_secret = totp_secret.strip()
            if totp_secret:
                totp_secret = normalize_totp_secret(totp_secret)

        parts = line.strip().split(":")
        if len(parts) < 2:
            continue

        username, password = parts[0], parts[1]
        proxy = parts[2] if len(parts) > 2 else None

        try:
            results.append(
                login_account(
                    username=username,
                    password=password,
                    proxy=proxy,
                    totp_secret=totp_secret,
                )
            )
        except Exception as exc:
            failure = classify_exception(
                exc,
                operation="login",
                username=username,
            )
            results.append(
                {
                    "id": str(uuid.uuid4()),
                    "username": username,
                    "password": password,
                    "proxy": proxy,
                    "status": "error",
                    "error": failure.user_message,
                    "errorCode": failure.code,
                }
            )

    return results


def import_session_archive(sessions: dict, sessions_dir: Path | None = None) -> list[dict]:
    target_sessions_dir = sessions_dir or state.SESSIONS_DIR
    results = []
    for username, session_data in sessions.items():
        session_file = target_sessions_dir / f"{username}.json"
        session_file.write_text(json.dumps(session_data))

        account_id = str(uuid.uuid4())
        set_account(account_id, {"username": username, "password": "", "proxy": None})
        results.append(account_to_dict(account_id, status="idle"))

    return results


def logout_account(account_id: str, detail: str = "") -> dict:
    if not has_account(account_id):
        raise ValueError("Account not found")

    username = (get_account(account_id) or {}).get("username", "")
    client = pop_client(account_id)
    if client:
        try:
            client.logout()
        except Exception:
            pass

    log_event(account_id, username, "logout", detail=detail, status="removed")
    clear_account_status(account_id)
    pop_account(account_id)
    return {"id": account_id, "username": username, "status": "removed"}


def set_account_proxy(account_id: str, proxy: str) -> dict:
    if not has_account(account_id):
        raise ValueError("Account not found")

    apply_account_proxy(account_id, proxy)
    return account_to_dict(account_id, status=get_account_status(account_id))


def bulk_logout_accounts(account_ids: list[str]) -> list[dict]:
    results = []
    for account_id in account_ids:
        try:
            results.append(logout_account(account_id, detail="bulk"))
        except ValueError:
            results.append({"id": account_id, "status": "not_found"})
    return results


def bulk_set_proxy(account_ids: list[str], proxy: str) -> list[dict]:
    results = []
    for account_id in account_ids:
        if not has_account(account_id):
            results.append({"id": account_id, "status": "not_found"})
            continue

        username = apply_account_proxy(account_id, proxy)
        results.append(
            {
                "id": account_id,
                "username": username,
                "status": "ok",
                "proxy": proxy,
            }
        )
    return results
