"""Dependency injection container - wires services together.

OWNERSHIP: Wire ports to adapters, pass to use cases.
Constructs object graph with proper dependency direction.

Dependency flow (top → bottom):
- api (HTTP layer) depends on use_cases
- use_cases depend on graphs/ports
- graphs depend on nodes/ports
- adapters implement ports

Adapters can delegate to legacy code (main.py, services.py, instagram.py) but
don't own smart engagement logic. That logic is in graphs/nodes.
"""

from __future__ import annotations

import os

from app.application.use_cases.account import AccountUseCases
from app.application.use_cases.account.relogin import ReloginUseCases
from app.application.use_cases.account_auth import AccountAuthUseCases
from app.application.use_cases.account_connectivity import AccountConnectivityUseCases
from app.application.use_cases.account_profile import AccountProfileUseCases
from app.application.use_cases.account_proxy import AccountProxyUseCases
from app.application.use_cases.account_totp import AccountTOTPUseCases
from app.application.use_cases.account_import import AccountImportUseCases
from app.application.use_cases.post_job import PostJobUseCases
from app.application.use_cases.proxy_pool import ProxyPoolUseCases
from app.application.use_cases.logs import LogsUseCases
from app.application.use_cases.identity import IdentityUseCases
from app.application.use_cases.relationships import RelationshipUseCases
from app.application.use_cases.media import MediaUseCases
from app.application.use_cases.hashtag import HashtagUseCases
from app.application.use_cases.collection import CollectionUseCases
from app.application.use_cases.insight import InsightUseCases
from app.application.use_cases.story import StoryUseCases
from app.application.use_cases.highlight import HighlightUseCases
from app.application.use_cases.comment import CommentUseCases
from app.application.use_cases.direct import DirectUseCases
from app.application.use_cases.llm_config import LLMConfigUseCases
from app.application.use_cases.dashboard_auth import DashboardAuthUseCases

# PHASE D MIGRATION: AIChartUseCases removed (legacy non-graph assistant)
from app.adapters.persistence import (
    ActivityLogWriter,
    SessionStore,
)
from app.adapters.persistence.factory import (
    build_persistence_adapters,
    build_llm_config_repository,
    build_oauth_token_store,
)
from app.adapters.instagram import InstagramClientAdapter
from app.adapters.persistence.post_job_control_adapter import PostJobControlAdapter
from app.adapters.scheduler import PostJobQueue
from app.adapters.ai.openai_gateway import AIGateway
from app.adapters.ai.tool_registry import create_tool_registry
from app.adapters.ai.tool_executor_adapter import ToolExecutorAdapter
from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory

from app.adapters.totp_adapter import TOTPAdapter
from ai_copilot.application.use_cases.run_smart_engagement import SmartEngagementUseCase
from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter
from ai_copilot.adapters.engagement_executor_adapter import EngagementExecutorAdapter


from app.adapters.instagram.exception_handler import instagram_exception_handler

from app.adapters.instagram.identity_reader import InstagramIdentityReaderAdapter
from app.adapters.instagram.relationship_reader import (
    InstagramRelationshipReaderAdapter,
)
from app.adapters.instagram.relationship_writer import (
    InstagramRelationshipWriterAdapter,
)
from app.adapters.instagram.media_writer import InstagramMediaWriterAdapter

from app.adapters.instagram.media_reader import InstagramMediaReaderAdapter

from app.adapters.instagram.story_reader import InstagramStoryReaderAdapter

from app.adapters.instagram.story_publisher import InstagramStoryPublisherAdapter

from app.adapters.instagram.discovery_reader import InstagramDiscoveryReaderAdapter

from app.adapters.instagram.collection_reader import InstagramCollectionReaderAdapter

from app.adapters.instagram.highlight_reader import InstagramHighlightReaderAdapter

from app.adapters.instagram.highlight_writer import InstagramHighlightWriterAdapter

from app.adapters.instagram.comment_reader import InstagramCommentReaderAdapter

from app.adapters.instagram.comment_writer import InstagramCommentWriterAdapter

from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter

from app.adapters.instagram.direct_writer import InstagramDirectWriterAdapter

from app.adapters.instagram.insight_reader import InstagramInsightReaderAdapter

from app.adapters.instagram.track_catalog import InstagramTrackCatalogAdapter
from app.adapters.proxy.httpx_checker import HttpxProxyCheckerAdapter
from app.adapters.proxy.proxy_parser import ProxyParser
from app.adapters.persistence.factory import build_proxy_repository, build_template_repository
from app.application.use_cases.templates import TemplatesUseCase


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_persistence():
    """Build persistence adapters and repositories."""
    (account_repo, client_repo, status_repo, job_repo, uow) = (
        build_persistence_adapters()
    )
    proxy_repo = build_proxy_repository()
    template_repo = build_template_repository()
    return account_repo, client_repo, status_repo, job_repo, uow, proxy_repo, template_repo


def _build_instagram_adapters(client_repo):
    """Build all Instagram protocol adapters."""
    return {
        "instagram": InstagramClientAdapter(),
        "totp": TOTPAdapter(),
        "identity_reader": InstagramIdentityReaderAdapter(client_repo),
        "relationship_reader": InstagramRelationshipReaderAdapter(client_repo),
        "relationship_writer": InstagramRelationshipWriterAdapter(client_repo),
        "media_reader": InstagramMediaReaderAdapter(client_repo),
        "media_writer": InstagramMediaWriterAdapter(client_repo),
        "story_reader": InstagramStoryReaderAdapter(client_repo),
        "story_publisher": InstagramStoryPublisherAdapter(client_repo),
        "discovery_reader": InstagramDiscoveryReaderAdapter(client_repo),
        "collection_reader": InstagramCollectionReaderAdapter(client_repo),
        "highlight_reader": InstagramHighlightReaderAdapter(client_repo),
        "highlight_writer": InstagramHighlightWriterAdapter(client_repo),
        "comment_reader": InstagramCommentReaderAdapter(client_repo),
        "comment_writer": InstagramCommentWriterAdapter(client_repo),
        "direct_reader": InstagramDirectReaderAdapter(client_repo),
        "direct_writer": InstagramDirectWriterAdapter(client_repo),
        "insight_reader": InstagramInsightReaderAdapter(client_repo),
        "track_catalog": InstagramTrackCatalogAdapter(client_repo),
    }


def _build_account_usecases(repos, ig, infra, *, verify_session_on_restore: bool):
    """Build all account-related use case instances."""
    account_repo, client_repo, status_repo, uow = repos
    instagram, totp, identity_reader = ig
    activity_log, proxy_checker = infra

    relogin = ReloginUseCases(
        account_repo=account_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=activity_log,
        error_handler=instagram_exception_handler,
        uow=uow,
        verify_session_on_restore=verify_session_on_restore,
    )

    legacy = AccountUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=activity_log,
        totp=totp,
        session_store=SessionStore(),
        error_handler=instagram_exception_handler,
        identity_reader=identity_reader,
        uow=uow,
        proxy_checker=proxy_checker,
        relogin_usecases=relogin,
        verify_session_on_restore=verify_session_on_restore,
    )
    auth = AccountAuthUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=activity_log,
        totp=totp,
        session_store=SessionStore(),
        error_handler=instagram_exception_handler,
        identity_reader=identity_reader,
        uow=uow,
        relogin_usecases=relogin,
        verify_session_on_restore=verify_session_on_restore,
    )
    profile = AccountProfileUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        identity_reader=identity_reader,
        error_handler=instagram_exception_handler,
    )
    proxy = AccountProxyUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        logger=activity_log,
        proxy_checker=proxy_checker,
        uow=uow,
    )
    totp_uc = AccountTOTPUseCases(
        account_repo=account_repo,
        logger=activity_log,
        totp=totp,
        uow=uow,
    )
    imp = AccountImportUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=activity_log,
        totp=totp,
        session_store=SessionStore(),
        error_handler=instagram_exception_handler,
        identity_reader=identity_reader,
        uow=uow,
        verify_session_on_restore=verify_session_on_restore,
    )
    connectivity = AccountConnectivityUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        identity_reader=identity_reader,
        error_handler=instagram_exception_handler,
        logger=activity_log,
    )
    return {
        "legacy": legacy,
        "relogin": relogin,
        "auth": auth,
        "profile": profile,
        "proxy": proxy,
        "totp": totp_uc,
        "import": imp,
        "connectivity": connectivity,
    }


def _build_instagram_usecases(account_repo, client_repo, ig_adapters):
    """Build vertical Instagram use cases (media, stories, highlights, etc.)."""
    return {
        "identity": IdentityUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            identity_reader=ig_adapters["identity_reader"],
        ),
        "relationships": RelationshipUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            identity_reader=ig_adapters["identity_reader"],
            relationship_reader=ig_adapters["relationship_reader"],
            relationship_writer=ig_adapters["relationship_writer"],
        ),
        "media": MediaUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            media_reader=ig_adapters["media_reader"],
            media_writer=ig_adapters["media_writer"],
        ),
        "hashtag": HashtagUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            discovery_reader=ig_adapters["discovery_reader"],
        ),
        "collection": CollectionUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            collection_reader=ig_adapters["collection_reader"],
        ),
        "insight": InsightUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            insight_reader=ig_adapters["insight_reader"],
        ),
        "story": StoryUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            story_reader=ig_adapters["story_reader"],
            story_publisher=ig_adapters["story_publisher"],
        ),
        "highlight": HighlightUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            highlight_reader=ig_adapters["highlight_reader"],
            highlight_writer=ig_adapters["highlight_writer"],
        ),
        "comment": CommentUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            comment_reader=ig_adapters["comment_reader"],
            comment_writer=ig_adapters["comment_writer"],
        ),
    }


def _build_ai_services(
    account_usecases,
    postjob_usecases,
    ig_usecases,
    account_uc_map,
    oauth_token_store,
    proxy_pool_usecases=None,
):
    """Build AI gateway, tool registry, provider router, and smart engagement."""
    ai_gateway = AIGateway()
    tool_registry = create_tool_registry(
        account_usecases,
        postjob_usecases,
        hashtag_use_cases=ig_usecases["hashtag"],
        collection_use_cases=ig_usecases["collection"],
        media_use_cases=ig_usecases["media"],
        story_use_cases=ig_usecases["story"],
        highlight_use_cases=ig_usecases["highlight"],
        comment_use_cases=ig_usecases["comment"],
        direct_use_cases=ig_usecases.get("direct"),
        insight_use_cases=ig_usecases["insight"],
        relationship_use_cases=ig_usecases["relationships"],
        account_profile_usecases=account_uc_map["profile"],
        account_auth_usecases=account_uc_map["auth"],
        account_proxy_usecases=account_uc_map["proxy"],
        proxy_pool_usecases=proxy_pool_usecases,
    )

    # Provider-routed LLM gateway
    _allowed_tools = ["list_accounts", "get_account_info", "get_post_jobs"]
    _provider_feature_flags = {
        "ENABLE_PROVIDER_OPENAI_CODEX": os.getenv(
            "ENABLE_PROVIDER_OPENAI_CODEX", "true"
        ).lower()
        == "true",
        "ENABLE_PROVIDER_CLAUDE_CODE": os.getenv(
            "ENABLE_PROVIDER_CLAUDE_CODE", "true"
        ).lower()
        == "true",
    }

    from app.adapters.ai.provider_router import ProviderRouter
    from app.adapters.ai.provider_router_adapter import ProviderRouterAdapter
    from app.adapters.ai.codex_oauth_client import CodexOAuthClient
    from app.adapters.ai.codex_oauth_gateway import CodexOAuthGateway
    from app.adapters.ai.codex_wham import CodexWHAMClient
    from app.adapters.ai.anthropic_oauth_client import AnthropicOAuthClient
    from app.adapters.ai.anthropic_messages_gateway import AnthropicMessagesGateway
    from app.adapters.ai.anthropic_message_filter import AnthropicMessageFilter

    provider_router = ProviderRouter(
        openai_gateway=ai_gateway,
        codex_gateway=CodexOAuthGateway(
            oauth_client=CodexOAuthClient(token_store=oauth_token_store),
            wham_client=CodexWHAMClient(),
        ),
        anthropic_gateway=AnthropicMessagesGateway(
            oauth_client=AnthropicOAuthClient(token_store=oauth_token_store),
            message_filter=AnthropicMessageFilter(),
        ),
        feature_flags=_provider_feature_flags,
    )

    return {
        "ai_gateway": ai_gateway,
        "tool_registry": tool_registry,
        "llm_gateway_adapter": ProviderRouterAdapter(provider_router),
        "tool_executor_adapter": ToolExecutorAdapter(tool_registry, _allowed_tools),
        "checkpoint_factory": ConfigurableCheckpointFactory.from_env(),
    }


def _build_smart_engagement(account_usecases, ig_usecases, ai_services):
    """Build mode-gated smart engagement use cases."""
    from langgraph.store.memory import InMemoryStore

    from ai_copilot.adapters.account_context_adapter import AccountContextAdapter
    from ai_copilot.adapters.circuit_breaker import (
        CircuitBreaker,
        CircuitProtectedProxy,
    )
    from ai_copilot.adapters.engagement_candidate_adapter import (
        EngagementCandidateAdapter,
    )
    from ai_copilot.adapters.engagement_memory_adapter import (
        LangGraphStoreMemoryAdapter,
    )
    from ai_copilot.adapters.instagram_data_adapter import InstagramDataAdapter
    from ai_copilot.adapters.risk_scoring_adapter import RiskScoringAdapter
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter
    from ai_copilot.adapters.file_audit_log_adapter import FileAuditLogAdapter

    # Raw adapters
    raw_account_context = AccountContextAdapter(account_service=account_usecases)
    instagram_data = InstagramDataAdapter(
        identity_usecases=ig_usecases["identity"],
        relationship_usecases=ig_usecases["relationships"],
        media_usecases=ig_usecases["media"],
    )
    raw_candidates = EngagementCandidateAdapter(data_port=instagram_data)

    # Circuit breakers — protect nodes from cascading failures
    account_context = CircuitProtectedProxy(
        raw_account_context,
        CircuitBreaker("account_context", failure_threshold=3, recovery_timeout=60.0),
    )
    candidates = CircuitProtectedProxy(
        raw_candidates,
        CircuitBreaker(
            "candidate_discovery", failure_threshold=3, recovery_timeout=60.0
        ),
    )

    # Cross-thread engagement memory (shared Store for both use cases)
    engagement_store = InMemoryStore()
    engagement_memory = LangGraphStoreMemoryAdapter(engagement_store)

    risk = RiskScoringAdapter()
    approval = InMemoryApprovalAdapter()
    audit_log = FileAuditLogAdapter()
    checkpoint_factory = ai_services["checkpoint_factory"]

    rec = SmartEngagementUseCase(
        account_context=account_context,
        candidate_discovery=candidates,
        risk_scoring=risk,
        approval=approval,
        executor=NoOpExecutorAdapter(),
        audit_log=audit_log,
        engagement_memory=engagement_memory,
        checkpoint_factory=checkpoint_factory,
        store=engagement_store,
        max_steps=11,
    )

    _execution_enabled = (
        os.getenv("SMART_ENGAGEMENT_EXECUTION_ENABLED", "true").lower() == "true"
    )
    exe = None
    if _execution_enabled:
        raw_executor = EngagementExecutorAdapter(
            account_id="",
            direct_use_cases=ig_usecases.get("direct"),
            comment_use_cases=ig_usecases["comment"],
            identity_use_cases=ig_usecases["identity"],
        )
        executor = CircuitProtectedProxy(
            raw_executor,
            CircuitBreaker("executor", failure_threshold=3, recovery_timeout=120.0),
        )
        exe = SmartEngagementUseCase(
            account_context=account_context,
            candidate_discovery=candidates,
            risk_scoring=risk,
            approval=approval,
            executor=executor,
            audit_log=audit_log,
            engagement_memory=engagement_memory,
            checkpoint_factory=checkpoint_factory,
            store=engagement_store,
            max_steps=11,
        )

    return {
        "rec": rec,
        "exec": exe,
        "execution_enabled": _execution_enabled,
        "approval_adapter": approval,
        "audit_log_adapter": audit_log,
    }


# ── Public entry point ────────────────────────────────────────────────────────


def create_services():
    """Create and wire all application services.

    Delegates to private builder functions grouped by subsystem.
    Returns a flat dict consumed by FastAPI dependency injection.
    """
    # ── 1. Persistence ────────────────────────────────────────────────────
    account_repo, client_repo, status_repo, job_repo, uow, proxy_repo, template_repo = (
        _build_persistence()
    )
    activity_log = ActivityLogWriter()
    proxy_checker = HttpxProxyCheckerAdapter()
    verify_session_on_restore = _bool_env("ACCOUNT_VERIFY_SESSION_ON_RESTORE", False)

    proxy_pool_usecases = ProxyPoolUseCases(
        checker=proxy_checker, repo=proxy_repo, parser=ProxyParser()
    )
    templates_usecases = TemplatesUseCase(repo=template_repo)

    # ── 2. Instagram adapters ─────────────────────────────────────────────
    ig = _build_instagram_adapters(client_repo)
    instagram = ig["instagram"]

    # ── 3. Job scheduling ─────────────────────────────────────────────────
    post_job_control = PostJobControlAdapter(job_repo=job_repo, uow=uow)

    def _run_and_sync_job(job_id: str) -> None:
        """Run the job then sync final state from in-memory store back to the DB.

        PostJobExecutor writes status/results directly to state._jobs (ThreadSafeJobStore)
        for speed, but never calls job_repo.set(). On SQL backends this means execution
        results are lost on restart. This wrapper does the sync after every job finishes
        (success, failure, or exception) — a no-op for the memory backend.
        """
        import logging
        import state as _state
        from app.application.ports.persistence_models import JobRecord as _JobRecord

        _sync_logger = logging.getLogger("instamanager.bootstrap")
        try:
            instagram.run_post_job(job_id)
        finally:
            try:
                job_dict = _state.get_job(job_id)
                job_repo.set(job_id, _JobRecord.from_dict(job_dict))
            except Exception as exc:
                _sync_logger.warning("job_sync.failed job_id=%s reason=%s", job_id, exc)

    scheduler = PostJobQueue(
        run_fn=_run_and_sync_job,
        mark_scheduled_fn=lambda jid: post_job_control.set_job_status(jid, "scheduled"),
    )

    # ── 4. Account use cases ──────────────────────────────────────────────
    acct = _build_account_usecases(
        repos=(account_repo, client_repo, status_repo, uow),
        ig=(instagram, ig["totp"], ig["identity_reader"]),
        infra=(activity_log, proxy_checker),
        verify_session_on_restore=verify_session_on_restore,
    )

    # ── 5. Post-job + logs use cases ──────────────────────────────────────
    postjob_usecases = PostJobUseCases(
        job_repo=job_repo,
        account_repo=account_repo,
        logger=activity_log,
        uow=uow,
    )

    from app.adapters.persistence.activity_log_reader import ActivityLogReaderAdapter

    logs_usecases = LogsUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        job_repo=job_repo,
        log_reader=ActivityLogReaderAdapter(),
    )

    # ── 6. Instagram vertical use cases ───────────────────────────────────
    ig_uc = _build_instagram_usecases(account_repo, client_repo, ig)
    identity_usecases = ig_uc["identity"]

    direct_usecases = DirectUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        direct_reader=ig["direct_reader"],
        direct_writer=ig["direct_writer"],
        identity_use_cases=identity_usecases,
    )
    ig_uc["direct"] = direct_usecases

    # ── 7. LLM + dashboard auth ───────────────────────────────────────────
    llm_config_usecases = LLMConfigUseCases(repo=build_llm_config_repository())
    dashboard_auth_usecases = DashboardAuthUseCases()
    oauth_token_store = build_oauth_token_store()

    # ── 8. AI services + smart engagement ─────────────────────────────────
    ai = _build_ai_services(
        acct["legacy"],
        postjob_usecases,
        ig_uc,
        acct,
        oauth_token_store,
        proxy_pool_usecases,
    )
    se = _build_smart_engagement(acct["legacy"], ig_uc, ai)

    # ── Assemble service map ──────────────────────────────────────────────
    return {
        "accounts": acct["legacy"],
        "account_auth": acct["auth"],
        "account_profile": acct["profile"],
        "account_proxy": acct["proxy"],
        "account_totp": acct["totp"],
        "account_import": acct["import"],
        "account_connectivity": acct["connectivity"],
        "postjobs": postjob_usecases,
        "logs": logs_usecases,
        "identity": identity_usecases,
        "relationships": ig_uc["relationships"],
        "media": ig_uc["media"],
        "hashtag": ig_uc["hashtag"],
        "collection": ig_uc["collection"],
        "insight": ig_uc["insight"],
        "story": ig_uc["story"],
        "highlight": ig_uc["highlight"],
        "comment": ig_uc["comment"],
        "direct": direct_usecases,
        "session_store": SessionStore(),
        "scheduler": scheduler,
        "post_job_control": post_job_control,
        "oauth_token_store": oauth_token_store,
        "_account_repo": account_repo,
        "_client_repo": client_repo,
        "_status_repo": status_repo,
        "_job_repo": job_repo,
        "_relogin_fn": acct["relogin"].relogin_account,
        "ai_gateway": ai["ai_gateway"],
        "tool_registry": ai["tool_registry"],
        "smart_engagement": se["rec"],
        "smart_engagement_rec": se["rec"],
        "smart_engagement_exec": se["exec"],
        "smart_engagement_execution_enabled": se["execution_enabled"],
        "approval_adapter": se["approval_adapter"],
        "audit_log_adapter": se["audit_log_adapter"],
        "ai_tools": ai["tool_registry"].get_schemas(),
        "ai_tools_list": ai["tool_registry"].get_schemas(),
        "track_catalog": ig["track_catalog"],
        "llm_config": llm_config_usecases,
        "dashboard_auth": dashboard_auth_usecases,
        "llm_gateway_port": ai["llm_gateway_adapter"],
        "proxy_pool": proxy_pool_usecases,
        "templates": templates_usecases,
    }
