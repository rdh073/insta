"""FastAPI dependencies for injection."""

from __future__ import annotations

from functools import lru_cache

from app.bootstrap import create_services as compose_service_map


@lru_cache(maxsize=1)
def get_services():
    """Get application services (cached singleton)."""
    return compose_service_map()


def get_account_usecases():
    """Get account use cases via dependency injection."""
    services = get_services()
    return services["accounts"]


def get_account_auth_usecases():
    """Get account auth use cases via dependency injection."""
    services = get_services()
    return services["account_auth"]


def get_account_profile_usecases():
    """Get account profile use cases via dependency injection."""
    services = get_services()
    return services["account_profile"]


def get_account_proxy_usecases():
    """Get account proxy use cases via dependency injection."""
    services = get_services()
    return services["account_proxy"]


def get_account_totp_usecases():
    """Get account TOTP use cases via dependency injection."""
    services = get_services()
    return services["account_totp"]


def get_account_import_usecases():
    """Get account import use cases via dependency injection."""
    services = get_services()
    return services["account_import"]


def get_account_connectivity_usecases():
    """Get account connectivity use cases via dependency injection."""
    services = get_services()
    return services["account_connectivity"]


def get_account_edit_usecases():
    """Get account edit use cases (privacy/avatar/profile/presence)."""
    services = get_services()
    return services["account_edit"]


def get_account_security_usecases():
    """Get account security use cases (2FA / trusted-device posture read)."""
    services = get_services()
    return services["account_security"]


def get_account_challenge_usecases():
    """Get challenge use cases (pending/submit/cancel)."""
    services = get_services()
    return services["account_challenge"]


def get_postjob_usecases():
    """Get post job use cases via dependency injection."""
    services = get_services()
    return services["postjobs"]


def get_ai_tools():
    """Get AI tools via dependency injection."""
    services = get_services()
    return services["ai_tools"]


def get_ai_tools_list():
    """Get AI tools list via dependency injection."""
    services = get_services()
    return services["ai_tools_list"]


def get_logs_usecases():
    """Get logs use cases via dependency injection."""
    services = get_services()
    return services["logs"]


def get_identity_usecases():
    """Get identity use cases via dependency injection."""
    services = get_services()
    return services["identity"]


def get_relationship_usecases():
    """Get relationship use cases via dependency injection."""
    services = get_services()
    return services["relationships"]


def get_scheduler():
    """Get scheduler via dependency injection."""
    services = get_services()
    return services["scheduler"]


def get_post_job_control():
    """Get post-job control adapter (stop/pause/resume/status)."""
    services = get_services()
    return services["post_job_control"]


def get_oauth_token_store():
    """Get OAuth token store via dependency injection."""
    services = get_services()
    return services["oauth_token_store"]


def get_session_store():
    """Get session store via dependency injection."""
    services = get_services()
    return services["session_store"]


# PHASE D MIGRATION: get_ai_chat_usecases removed (legacy non-graph assistant)


def get_tool_registry():
    """Get AI tool registry via dependency injection."""
    services = get_services()
    return services["tool_registry"]


def get_ai_gateway():
    """Get AI gateway via dependency injection."""
    services = get_services()
    return services["ai_gateway"]


# PHASE C MIGRATION: get_ai_graph_chat_usecases removed (legacy read-only graph stack)


def get_smart_engagement_usecases():
    """Get smart engagement use cases via dependency injection (recommendation mode)."""
    services = get_services()
    return services["smart_engagement"]


def get_smart_engagement_rec():
    """Get recommendation-mode smart engagement use case (NoOp executor injected)."""
    services = get_services()
    return services["smart_engagement_rec"]


def get_smart_engagement_exec():
    """Get execute-mode smart engagement use case (None if feature flag is off)."""
    services = get_services()
    return services["smart_engagement_exec"]


def get_smart_engagement_execution_enabled() -> bool:
    """Check if execution mode feature flag is enabled."""
    services = get_services()
    return services.get("smart_engagement_execution_enabled", False)


def get_media_usecases():
    """Get media use cases via dependency injection."""
    services = get_services()
    return services["media"]


def get_hashtag_usecases():
    """Get hashtag use cases via dependency injection."""
    services = get_services()
    return services["hashtag"]


def get_collection_usecases():
    """Get collection use cases via dependency injection."""
    services = get_services()
    return services["collection"]


def get_insight_usecases():
    """Get insight use cases via dependency injection."""
    services = get_services()
    return services["insight"]


def get_story_usecases():
    """Get story use cases via dependency injection."""
    services = get_services()
    return services["story"]


def get_highlight_usecases():
    """Get highlight use cases via dependency injection."""
    services = get_services()
    return services["highlight"]


def get_comment_usecases():
    """Get comment use cases via dependency injection."""
    services = get_services()
    return services["comment"]


def get_direct_usecases():
    """Get direct use cases via dependency injection."""
    services = get_services()
    return services["direct"]


def get_approval_adapter():
    """Get approval adapter via dependency injection."""
    services = get_services()
    return services["approval_adapter"]


def get_audit_log_adapter():
    """Get audit log adapter via dependency injection."""
    services = get_services()
    return services["audit_log_adapter"]


def get_proxy_pool_usecases():
    """Get proxy pool use cases via dependency injection."""
    services = get_services()
    return services["proxy_pool"]



def get_dashboard_auth_usecases():
    """Get dashboard auth use cases via dependency injection."""
    services = get_services()
    return services["dashboard_auth"]


def get_account_repo():
    """Get raw account repository (for credential reads)."""
    services = get_services()
    return services["_account_repo"]


def get_templates_usecases():
    """Get templates use cases via dependency injection."""
    services = get_services()
    return services["templates"]
