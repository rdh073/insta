"""Legacy service facade.

This transitional wrapper preserves the historic ``services`` import surface.
New callers should prefer app/application/use_cases/ directly.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import uuid
from typing import Optional

from app.adapters.instagram.exception_handler import instagram_exception_handler
from instagram import (
    activate_account_client,
    complete_2fa_client,
    create_authenticated_client,
    relogin_account_sync,
)
from state import (
    LOG_FILE,
    SESSIONS_DIR,
    TwoFactorRequired,
    account_ids,
    account_to_dict,
    active_client_ids,
    clear_account_status,
    find_account_id_by_username as state_find_account_id_by_username,
    get_account,
    get_account_status_value,
    get_client,
    get_job,
    has_account,
    has_client,
    iter_account_items,
    iter_jobs_values,
    log_event,
    pop_account,
    pop_client,
    set_account,
    set_account_status,
    set_job,
    update_account,
)

from ._common import get_account_status
from .account_auth_service import (
    bulk_logout_accounts,
    bulk_set_proxy,
    complete_2fa_login_account,
    import_accounts_text,
    import_session_archive,
    login_account,
    logout_account,
    set_account_proxy,
)
from .account_query_service import (
    find_account_id_by_username,
    get_account_info_by_username,
    get_accounts_summary,
    list_accounts_data,
)
from .dashboard_service import get_dashboard_data, read_log_entries
from .post_job_service import (
    create_post_job,
    create_scheduled_post_draft,
    list_posts_data,
    list_recent_post_jobs,
)
from .relogin_service import (
    bulk_relogin_accounts,
    relogin_account_by_username,
    relogin_account_with_tracking,
)
from .totp_service import (
    generate_totp_code,
    generate_totp_secret,
    normalize_totp_secret,
    verify_totp_code,
)

# Keep the legacy public surface clean: avoid leaking submodule objects.
del account_auth_service, account_query_service, dashboard_service, post_job_service, relogin_service, totp_service

__all__ = [
    "LOG_FILE",
    "Optional",
    "SESSIONS_DIR",
    "TwoFactorRequired",
    "account_ids",
    "account_to_dict",
    "activate_account_client",
    "active_client_ids",
    "annotations",
    "asyncio",
    "bulk_logout_accounts",
    "bulk_relogin_accounts",
    "bulk_set_proxy",
    "clear_account_status",
    "complete_2fa_client",
    "complete_2fa_login_account",
    "create_authenticated_client",
    "create_post_job",
    "create_scheduled_post_draft",
    "datetime",
    "find_account_id_by_username",
    "generate_totp_code",
    "generate_totp_secret",
    "get_account",
    "get_account_info_by_username",
    "get_account_status",
    "get_account_status_value",
    "get_accounts_summary",
    "get_client",
    "get_dashboard_data",
    "get_job",
    "has_account",
    "has_client",
    "import_accounts_text",
    "import_session_archive",
    "instagram_exception_handler",
    "iter_account_items",
    "iter_jobs_values",
    "json",
    "list_accounts_data",
    "list_posts_data",
    "list_recent_post_jobs",
    "log_event",
    "login_account",
    "logout_account",
    "normalize_totp_secret",
    "pop_account",
    "pop_client",
    "read_log_entries",
    "relogin_account_by_username",
    "relogin_account_sync",
    "relogin_account_with_tracking",
    "set_account",
    "set_account_proxy",
    "set_account_status",
    "set_job",
    "state_find_account_id_by_username",
    "update_account",
    "uuid",
    "verify_totp_code",
]
