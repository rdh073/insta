"""Durable SQL repository implementations for application ports.

All SQL-specific errors are caught and translated to app-owned errors.
This adapter layer is responsible for keeping vendor details away from
application/use-cases.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from app.application.ports.persistence_models import AccountRecord, JobRecord, ProxyRecord
from app.domain.proxy import Proxy, ProxyAnonymity, ProxyProtocol

from .errors import PersistenceInfrastructureError
from .failure_catalog import build_persistence_failure_message
from .sql_store import AccountRow, AccountStatusRow, JobRow, ProxyRow, TemplateRow, SqlitePersistenceStore
from .state_gateway import default_state_gateway


def _wrap_sql_error(func):
    """Decorator to wrap SQLAlchemy errors as app-owned failures.

    Translates database errors to application-level exceptions while
    preserving error context. Ensures application layer never sees
    SQLAlchemy-specific exceptions.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as exc:
            raise PersistenceInfrastructureError(
                build_persistence_failure_message(func.__name__)
            ) from exc

    return wrapper


class SqlAccountRepository:
    """SQL-backed account repository."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @staticmethod
    def _to_record(row: AccountRow) -> AccountRecord:
        return AccountRecord(
            username=row.username,
            password=row.password,
            proxy=row.proxy,
            country=row.country,
            country_code=row.country_code,
            locale=row.locale,
            timezone_offset=row.timezone_offset,
            totp_secret=row.totp_secret,
            totp_enabled=row.totp_enabled,
            full_name=row.full_name,
            followers=row.followers,
            following=row.following,
            profile_pic_url=row.profile_pic_url,
            last_verified_at=row.last_verified_at,
            last_error=row.last_error,
            last_error_code=row.last_error_code,
        )

    @staticmethod
    def _apply_record(row: AccountRow, record: AccountRecord) -> None:
        row.username = record.username
        row.password = record.password
        row.proxy = record.proxy
        row.country = record.country
        row.country_code = record.country_code
        row.locale = record.locale
        row.timezone_offset = record.timezone_offset
        row.totp_secret = record.totp_secret
        row.totp_enabled = record.totp_enabled
        row.full_name = record.full_name
        row.followers = record.followers
        row.following = record.following
        row.profile_pic_url = record.profile_pic_url
        row.last_verified_at = record.last_verified_at
        row.last_error = record.last_error
        row.last_error_code = record.last_error_code

    @_wrap_sql_error
    def get(self, account_id: str) -> Optional[AccountRecord]:
        with self.store.session_scope() as session:
            row = session.get(AccountRow, account_id)
            if row is None:
                return None
            return self._to_record(row)

    @_wrap_sql_error
    def exists(self, account_id: str) -> bool:
        with self.store.session_scope() as session:
            return session.get(AccountRow, account_id) is not None

    @_wrap_sql_error
    def set(self, account_id: str, data: AccountRecord | dict) -> None:
        record = data if isinstance(data, AccountRecord) else AccountRecord.from_dict(data)
        with self.store.session_scope() as session:
            row = session.get(AccountRow, account_id)
            if row is None:
                row = AccountRow(account_id=account_id, username=record.username)
                session.add(row)
            self._apply_record(row, record)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def update(self, account_id: str, **kwargs) -> None:
        current = self.get(account_id)
        if current is None:
            return
        merged = current.to_dict()
        merged.update(kwargs)
        self.set(account_id, AccountRecord.from_dict(merged))

    @_wrap_sql_error
    def remove(self, account_id: str) -> None:
        with self.store.session_scope() as session:
            row = session.get(AccountRow, account_id)
            if row is not None:
                session.delete(row)
            status_row = session.get(AccountStatusRow, account_id)
            if status_row is not None:
                session.delete(status_row)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def find_by_username(self, username: str) -> Optional[str]:
        with self.store.session_scope() as session:
            row = (
                session.query(AccountRow)
                .filter(AccountRow.username == username)
                .one_or_none()
            )
            return row.account_id if row is not None else None

    @_wrap_sql_error
    def list_all_ids(self) -> list[str]:
        with self.store.session_scope() as session:
            rows = session.query(AccountRow.account_id).all()
            return [account_id for (account_id,) in rows]

    @_wrap_sql_error
    def iter_all(self) -> list[tuple[str, AccountRecord]]:
        with self.store.session_scope() as session:
            rows = session.query(AccountRow).all()
            return [(row.account_id, self._to_record(row)) for row in rows]


class SqlStatusRepository:
    """SQL-backed account status repository."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @_wrap_sql_error
    def get(self, account_id: str, default: Optional[str] = None) -> Optional[str]:
        fallback = default if default is not None else "idle"
        with self.store.session_scope() as session:
            row = session.get(AccountStatusRow, account_id)
            return row.status if row is not None else fallback

    @_wrap_sql_error
    def set(self, account_id: str, status: str) -> None:
        with self.store.session_scope() as session:
            row = session.get(AccountStatusRow, account_id)
            if row is None:
                row = AccountStatusRow(account_id=account_id, status=status)
                session.add(row)
            else:
                row.status = status
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def clear(self, account_id: str) -> None:
        with self.store.session_scope() as session:
            row = session.get(AccountStatusRow, account_id)
            if row is not None:
                session.delete(row)
            if self.store.get_active_session() is None:
                session.commit()


class SqlJobRepository:
    """SQL-backed job repository.

    Dual-writes to state._jobs so that run_post_job (which reads from the
    in-memory state directly) can execute jobs regardless of persistence backend.
    """

    def __init__(self, store: SqlitePersistenceStore, gateway=default_state_gateway):
        self.store = store
        self.gateway = gateway

    @staticmethod
    def _to_record(row: JobRow) -> JobRecord:
        return JobRecord(
            id=row.job_id,
            caption=row.caption,
            status=row.status,
            targets=list(row.targets or []),
            results=list(row.results or []),
            created_at=row.created_at,
            media_urls=list(row.media_urls or []),
            media_type=row.media_type,
            media_paths=list(row.media_paths or []),
            scheduled_at=row.scheduled_at,
            thumbnail_path=row.thumbnail_path,
            igtv_title=row.igtv_title,
            usertags=list(row.usertags or []),
            location=row.location,
            extra_data=dict(row.extra_data or {}),
        )

    @staticmethod
    def _apply_record(row: JobRow, record: JobRecord) -> None:
        row.caption = record.caption
        row.status = record.status
        row.targets = list(record.targets)
        row.results = list(record.results)
        row.created_at = record.created_at
        row.media_urls = list(record.media_urls)
        row.media_type = record.media_type
        row.media_paths = list(record.media_paths)
        row.scheduled_at = record.scheduled_at
        row.thumbnail_path = record.thumbnail_path
        row.igtv_title = record.igtv_title
        row.usertags = list(record.usertags)
        row.location = record.location
        row.extra_data = dict(record.extra_data)

    @_wrap_sql_error
    def get(self, job_id: str) -> Optional[JobRecord]:
        with self.store.session_scope() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            return self._to_record(row)

    @_wrap_sql_error
    def set(self, job_id: str, job: JobRecord | dict) -> None:
        record = job if isinstance(job, JobRecord) else JobRecord.from_dict(job)
        with self.store.session_scope() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                row = JobRow(job_id=job_id, caption=record.caption, status=record.status)
                session.add(row)
            self._apply_record(row, record)
            if self.store.get_active_session() is None:
                session.commit()
        # Dual-write to in-memory state so run_post_job (which reads state._jobs
        # directly) can find the job regardless of persistence backend.
        self.gateway.set_job(job_id, record.to_dict())

    @_wrap_sql_error
    def delete(self, job_id: str) -> bool:
        with self.store.session_scope() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return False
            session.delete(row)
            if self.store.get_active_session() is None:
                session.commit()
        # Also remove from in-memory state so the job disappears immediately.
        self.gateway.delete_job(job_id)
        return True

    @_wrap_sql_error
    def list_all(self) -> list[JobRecord]:
        with self.store.session_scope() as session:
            rows = session.query(JobRow).all()
            return [self._to_record(row) for row in rows]


class SqlProxyRepository:
    """SQL-backed proxy pool repository."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @staticmethod
    def _to_proxy(row: ProxyRow) -> Proxy:
        return Proxy(
            host=row.host,
            port=row.port,
            protocol=ProxyProtocol(row.protocol),
            anonymity=ProxyAnonymity(row.anonymity),
            latency_ms=row.latency_ms,
        )

    @_wrap_sql_error
    def save(self, proxy: Proxy) -> None:
        with self.store.session_scope() as session:
            row = (
                session.query(ProxyRow)
                .filter(ProxyRow.host == proxy.host, ProxyRow.port == proxy.port)
                .one_or_none()
            )
            if row is None:
                row = ProxyRow(
                    host=proxy.host,
                    port=proxy.port,
                    protocol=proxy.protocol.value,
                    anonymity=proxy.anonymity.value,
                    latency_ms=proxy.latency_ms,
                    url=proxy.url,
                )
                session.add(row)
            else:
                row.protocol   = proxy.protocol.value
                row.anonymity  = proxy.anonymity.value
                row.latency_ms = proxy.latency_ms
                row.url        = proxy.url
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def list_all(self) -> list[Proxy]:
        with self.store.session_scope() as session:
            rows = session.query(ProxyRow).order_by(ProxyRow.latency_ms).all()
            return [self._to_proxy(row) for row in rows]

    @_wrap_sql_error
    def delete(self, host: str, port: int) -> None:
        with self.store.session_scope() as session:
            row = (
                session.query(ProxyRow)
                .filter(ProxyRow.host == host, ProxyRow.port == port)
                .one_or_none()
            )
            if row is not None:
                session.delete(row)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def exists(self, host: str, port: int) -> bool:
        with self.store.session_scope() as session:
            return (
                session.query(ProxyRow)
                .filter(ProxyRow.host == host, ProxyRow.port == port)
                .one_or_none()
            ) is not None


class SqlTemplateRepository:
    """SQL-backed caption template repository."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @staticmethod
    def _to_dict(row: TemplateRow) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "caption": row.caption,
            "tags": row.tags or [],
            "usage_count": row.usage_count or 0,
            "created_at": row.created_at,
        }

    @_wrap_sql_error
    def get(self, template_id: str) -> dict | None:
        with self.store.session_scope() as session:
            row = session.query(TemplateRow).filter(TemplateRow.id == template_id).one_or_none()
            return self._to_dict(row) if row else None

    @_wrap_sql_error
    def save(self, template: dict) -> None:
        with self.store.session_scope() as session:
            row = session.query(TemplateRow).filter(TemplateRow.id == template["id"]).one_or_none()
            if row is None:
                row = TemplateRow(
                    id=template["id"],
                    name=template["name"],
                    caption=template["caption"],
                    tags=template.get("tags", []),
                    usage_count=template.get("usage_count", 0),
                    created_at=template.get("created_at", ""),
                )
                session.add(row)
            else:
                row.name = template["name"]
                row.caption = template["caption"]
                row.tags = template.get("tags", [])
                row.usage_count = template.get("usage_count", row.usage_count)
                row.created_at = template.get("created_at", row.created_at)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def update(self, template_id: str, **kwargs) -> None:
        with self.store.session_scope() as session:
            row = session.query(TemplateRow).filter(TemplateRow.id == template_id).one_or_none()
            if row is None:
                return
            for field, value in kwargs.items():
                if hasattr(row, field):
                    setattr(row, field, value)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def delete(self, template_id: str) -> bool:
        with self.store.session_scope() as session:
            row = session.query(TemplateRow).filter(TemplateRow.id == template_id).one_or_none()
            if row is None:
                return False
            session.delete(row)
            if self.store.get_active_session() is None:
                session.commit()
            return True

    @_wrap_sql_error
    def list_all(self) -> list[dict]:
        with self.store.session_scope() as session:
            rows = session.query(TemplateRow).order_by(TemplateRow.name).all()
            return [self._to_dict(row) for row in rows]
