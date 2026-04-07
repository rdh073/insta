"""Hashtag use cases - application orchestration for Instagram hashtag reads.

Enforces account preconditions and hashtag name normalization before delegating
to the InstagramDiscoveryReader port. Only hashtag methods are exposed here;
location methods live outside this vertical's scope.

Consumers (router, tool_registry, ai_copilot) must use this class instead of
calling the adapter directly.
"""

from __future__ import annotations

from app.application.dto.instagram_discovery_dto import HashtagSummary
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.ports.instagram_discovery import InstagramDiscoveryReader
from app.application.ports.repositories import AccountRepository, ClientRepository

_AMOUNT_MIN = 1
_AMOUNT_MAX = 200
_AMOUNT_DEFAULT = 12


class HashtagUseCases:
    """Application orchestration for Instagram hashtag reads.

    Owns precondition enforcement (account exists, authenticated),
    hashtag name normalization (#tag → tag), and amount clamping.
    The underlying InstagramDiscoveryReader port handles vendor calls
    and DTO mapping. Location methods on the same port are out of scope.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        discovery_reader: InstagramDiscoveryReader,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.discovery_reader = discovery_reader

    # -------------------------------------------------------------------------
    # Precondition + normalization helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    @staticmethod
    def _normalize_hashtag(name: str) -> str:
        """Strip whitespace and leading # from a hashtag name.

        Both '#python' and 'python' are accepted and normalised to 'python'.
        Raises ValueError when the result is empty.
        """
        clean = name.strip().lstrip("#").strip() if name else ""
        if not clean:
            raise ValueError("hashtag name must not be empty")
        return clean

    @staticmethod
    def _clamp_amount(amount: int) -> int:
        return max(_AMOUNT_MIN, min(amount, _AMOUNT_MAX))

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def search_hashtags(self, account_id: str, query: str) -> list[HashtagSummary]:
        """Search hashtags by query string.

        Accepts both '#trivium' and 'trivium' formats.

        Args:
            account_id: Application account ID.
            query: Search query with or without leading '#'.

        Returns:
            List of HashtagSummary results (up to ~30 from Instagram).

        Raises:
            ValueError: If account not found, not authenticated, or query empty.
        """
        self._require_authenticated(account_id)
        normalized = self._normalize_hashtag(query)
        return self.discovery_reader.search_hashtags(account_id, normalized)

    def get_hashtag(self, account_id: str, name: str) -> HashtagSummary:
        """Get hashtag metadata by name.

        Accepts both '#python' and 'python' formats.

        Args:
            account_id: Application account ID.
            name: Hashtag name with or without leading '#'.

        Returns:
            HashtagSummary with id, name, and media_count.

        Raises:
            ValueError: If account not found, not authenticated, or name empty.
        """
        self._require_authenticated(account_id)
        normalized = self._normalize_hashtag(name)
        return self.discovery_reader.get_hashtag(account_id, normalized)

    def get_hashtag_top_posts(
        self,
        account_id: str,
        name: str,
        amount: int = _AMOUNT_DEFAULT,
    ) -> list[MediaSummary]:
        """Get top (most engaged) posts for a hashtag.

        Accepts both '#python' and 'python' formats.
        Clamps amount to [1, 200].

        Args:
            account_id: Application account ID.
            name: Hashtag name with or without leading '#'.
            amount: Number of posts to retrieve. Clamped to [1, 200].

        Returns:
            List of MediaSummary for the hashtag's top posts.

        Raises:
            ValueError: If account not found, not authenticated, or name empty.
        """
        self._require_authenticated(account_id)
        normalized = self._normalize_hashtag(name)
        clamped = self._clamp_amount(amount)
        return self.discovery_reader.get_hashtag_top_posts(account_id, normalized, clamped)

    def get_hashtag_recent_posts(
        self,
        account_id: str,
        name: str,
        amount: int = _AMOUNT_DEFAULT,
    ) -> list[MediaSummary]:
        """Get recent posts for a hashtag.

        Accepts both '#python' and 'python' formats.
        Clamps amount to [1, 200].

        Args:
            account_id: Application account ID.
            name: Hashtag name with or without leading '#'.
            amount: Number of posts to retrieve. Clamped to [1, 200].

        Returns:
            List of MediaSummary for the hashtag's recent posts.

        Raises:
            ValueError: If account not found, not authenticated, or name empty.
        """
        self._require_authenticated(account_id)
        normalized = self._normalize_hashtag(name)
        clamped = self._clamp_amount(amount)
        return self.discovery_reader.get_hashtag_recent_posts(account_id, normalized, clamped)
