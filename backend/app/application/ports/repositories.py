"""Repository port interfaces - data access contracts."""

from __future__ import annotations

from typing import Optional, Protocol

from .persistence_models import AccountRecord, JobRecord


class AccountRepository(Protocol):
    """Interface for account storage and retrieval."""

    def get(self, account_id: str) -> Optional[AccountRecord]:
        """Get account metadata by ID."""
        ...

    def exists(self, account_id: str) -> bool:
        """Check if account exists."""
        ...

    def set(self, account_id: str, data: AccountRecord) -> None:
        """Store account metadata."""
        ...

    def update(self, account_id: str, **kwargs) -> None:
        """Update account metadata fields."""
        ...

    def remove(self, account_id: str) -> None:
        """Remove account from storage."""
        ...

    def find_by_username(self, username: str) -> Optional[str]:
        """Find account ID by username."""
        ...

    def list_all_ids(self) -> list[str]:
        """List all account IDs."""
        ...

    def iter_all(self) -> list[tuple[str, AccountRecord]]:
        """Iterate over all accounts (id, metadata) pairs."""
        ...


class ClientRepository(Protocol):
    """Interface for Instagram client storage."""

    def get(self, account_id: str):
        """Get Instagram client for account."""
        ...

    def set(self, account_id: str, client) -> None:
        """Store Instagram client for account."""
        ...

    def remove(self, account_id: str):
        """Remove and return Instagram client."""
        ...

    def exists(self, account_id: str) -> bool:
        """Check if account has active client."""
        ...

    def list_active_ids(self) -> list[str]:
        """List account IDs with active clients."""
        ...


class StatusRepository(Protocol):
    """Interface for account status tracking."""

    def get(self, account_id: str, default: Optional[str] = None) -> Optional[str]:
        """Get account status."""
        ...

    def set(self, account_id: str, status: str) -> None:
        """Set account status."""
        ...

    def clear(self, account_id: str) -> None:
        """Clear account status."""
        ...


class JobRepository(Protocol):
    """Interface for post job storage."""

    def get(self, job_id: str) -> Optional[JobRecord]:
        """Get job by ID."""
        ...

    def set(self, job_id: str, job: JobRecord) -> None:
        """Store job."""
        ...

    def list_all(self) -> list[JobRecord]:
        """List all jobs."""
        ...


class TemplateRepository(Protocol):
    """Interface for caption template storage."""

    def get(self, template_id: str) -> Optional[dict]:
        """Get template by ID."""
        ...

    def save(self, template: dict) -> None:
        """Create or replace a template."""
        ...

    def update(self, template_id: str, **kwargs) -> None:
        """Patch template fields."""
        ...

    def delete(self, template_id: str) -> bool:
        """Delete template. Returns True if it existed."""
        ...

    def list_all(self) -> list[dict]:
        """List all templates ordered by name."""
        ...
