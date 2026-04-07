"""Collection use cases - application orchestration for Instagram saved collections.

Enforces account preconditions, name normalization, and parameter validation
before delegating to the InstagramCollectionReader port. Consumers (router,
tool_registry, ai_copilot) must use this class instead of the adapter directly.

Not-found and invalid-name contracts are owned here:
  - Empty or whitespace-only collection name → ValueError before any port call
  - Collection name not found → ValueError propagated from port (not hidden)
  - Invalid collection_pk → ValueError before any port call
"""

from __future__ import annotations

from app.application.dto.instagram_discovery_dto import CollectionSummary
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.ports.instagram_collections import InstagramCollectionReader
from app.application.ports.repositories import AccountRepository, ClientRepository

_AMOUNT_MIN = 1
_AMOUNT_MAX = 200
_AMOUNT_DEFAULT = 21  # instagrapi default for collections


class CollectionUseCases:
    """Application orchestration for Instagram saved collection reads.

    Owns precondition enforcement (account exists, authenticated),
    collection name normalization, and collection_pk / amount validation.
    The underlying InstagramCollectionReader port handles vendor calls
    and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        collection_reader: InstagramCollectionReader,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.collection_reader = collection_reader

    # -------------------------------------------------------------------------
    # Precondition + validation helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    @staticmethod
    def _normalize_collection_name(name: str) -> str:
        """Strip whitespace from a collection name and reject empty values.

        Raises:
            ValueError: When the cleaned name is empty.
        """
        clean = name.strip() if name else ""
        if not clean:
            raise ValueError("collection name must not be empty")
        return clean

    @staticmethod
    def _clamp_amount(amount: int) -> int:
        return max(_AMOUNT_MIN, min(amount, _AMOUNT_MAX))

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def list_collections(self, account_id: str) -> list[CollectionSummary]:
        """List all saved collections for the authenticated account.

        Args:
            account_id: Application account ID.

        Returns:
            List of CollectionSummary (may be empty if no collections saved).

        Raises:
            ValueError: If account not found or not authenticated.
        """
        self._require_authenticated(account_id)
        return self.collection_reader.list_collections(account_id)

    def get_collection_pk_by_name(self, account_id: str, name: str) -> int:
        """Look up a collection primary key by its name.

        Collection name is trimmed of surrounding whitespace before lookup.
        Raises ValueError (not-found contract) if no collection matches the name.

        Args:
            account_id: Application account ID.
            name: Collection display name (may have surrounding whitespace).

        Returns:
            The collection's primary key (positive integer).

        Raises:
            ValueError: If account not found, not authenticated, name empty,
                        or collection with that name does not exist.
        """
        self._require_authenticated(account_id)
        normalized = self._normalize_collection_name(name)
        return self.collection_reader.get_collection_pk_by_name(account_id, normalized)

    def get_collection_posts(
        self,
        account_id: str,
        collection_pk: int,
        amount: int = _AMOUNT_DEFAULT,
        last_media_pk: int = 0,
    ) -> list[MediaSummary]:
        """Get posts from a saved collection with optional cursor-based pagination.

        Amount is clamped to [1, 200]. last_media_pk = 0 starts from beginning.

        Args:
            account_id: Application account ID.
            collection_pk: The Instagram collection primary key (positive integer).
            amount: Number of posts to retrieve. Clamped to [1, 200].
            last_media_pk: Pagination cursor — fetch posts after this media PK.
                           Use 0 (default) to start from the beginning.

        Returns:
            List of MediaSummary for the collection's posts.

        Raises:
            ValueError: If account not found, not authenticated, or collection_pk invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(collection_pk, int) or collection_pk <= 0:
            raise ValueError(
                f"collection_pk must be a positive integer, got {collection_pk!r}"
            )
        if not isinstance(last_media_pk, int) or last_media_pk < 0:
            raise ValueError(
                f"last_media_pk must be a non-negative integer, got {last_media_pk!r}"
            )
        clamped = self._clamp_amount(amount)
        return self.collection_reader.get_collection_posts(
            account_id, collection_pk, clamped, last_media_pk
        )
