"""
Instagram collection reader port.

Defines the application-facing contract for reading authenticated user's saved collections.
Separates collection (saved/authenticated) reads from public discovery reads.
All media results use the shared MediaSummary DTO, never raw vendor Media.
"""

from typing import Protocol

from app.application.dto.instagram_discovery_dto import CollectionSummary
from app.application.dto.instagram_media_dto import MediaSummary


class InstagramCollectionReader(Protocol):
    """
    Port for reading Instagram saved collections (authenticated state).

    Collections are user-owned saved content lists. This port handles retrieval
    of collection metadata and collection-owned media.
    Implementation depends on instagrapi; application layer depends on DTOs.
    All media results are returned as MediaSummary to prevent vendor leakage.

    Note: Collection writes (media_save, media_unsave) are deferred to a separate port.
    """

    def list_collections(self, account_id: str) -> list[CollectionSummary]:
        """
        List all saved collections for the authenticated account.

        Args:
            account_id: The application account ID (for client lookup).

        Returns:
            List of CollectionSummary for all user collections.

        Raises:
            Exception: If account not authenticated or list fails.
        """
        ...

    def get_collection_pk_by_name(self, account_id: str, name: str) -> int:
        """
        Look up collection primary key by collection name.

        Args:
            account_id: The application account ID (for client lookup).
            name: Collection name to search for.

        Returns:
            Collection primary key.

        Raises:
            Exception: If collection not found or lookup fails.
        """
        ...

    def get_collection_posts(
        self,
        account_id: str,
        collection_pk: int,
        amount: int = 21,
        last_media_pk: int = 0,
    ) -> list[MediaSummary]:
        """
        Get posts from a saved collection with optional pagination.

        Args:
            account_id: The application account ID (for client lookup).
            collection_pk: The Instagram collection primary key.
            amount: Number of posts to retrieve (default 21).
            last_media_pk: For pagination, fetch posts after this media PK (0 = start from beginning).

        Returns:
            List of MediaSummary for collection's posts.

        Raises:
            Exception: If collection not found or read fails.
        """
        ...
