"""
Instagram collection reader adapter.

Maps instagrapi Collection objects to stable DTOs.
Routes all media results through the shared MediaSummary contract.
"""

from typing import Any

from app.application.dto.instagram_discovery_dto import CollectionSummary
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.media_reader import InstagramMediaReaderAdapter
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramCollectionReaderAdapter:
    """
    Adapter for reading Instagram saved collections via instagrapi.

    Maps vendor Collection objects to stable DTOs.
    Centralizes vendor-to-DTO translation for collection reads.
    All media results are converted to MediaSummary to prevent vendor leakage.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize collection reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def list_collections(self, account_id: str) -> list[CollectionSummary]:
        """
        List all saved collections for the authenticated account.

        Args:
            account_id: The application account ID (for client lookup).

        Returns:
            List of CollectionSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to list collections
            collections = client.collections()

            # Map each collection to DTO
            return [self._map_collection_to_summary(col) for col in collections]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_collections", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_collection_pk_by_name(self, account_id: str, name: str) -> int:
        """
        Look up collection primary key by name.

        Args:
            account_id: The application account ID (for client lookup).
            name: Collection name to search for.

        Returns:
            Collection primary key.

        Raises:
            ValueError: If account not found, client not authenticated, or collection not found.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to get collection pk by name
            collection_pk = client.collection_pk_by_name(name)

            if collection_pk is None:
                raise ValueError(f"Collection '{name}' not found")

            return collection_pk

        except ValueError:
            raise
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_collection_pk_by_name", account_id=account_id
            )
            raise ValueError(failure.user_message)

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
            last_media_pk: For pagination, fetch posts after this media PK.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to get collection posts
            # Note: pagination via last_media_pk is handled by the vendor
            medias = client.collection_medias(
                collection_pk,
                amount=amount,
                last_media_pk=last_media_pk if last_media_pk > 0 else None,
            )

            # Map each media to DTO
            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_collection_posts", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def list_liked_medias(
        self,
        account_id: str,
        amount: int = 21,
        last_media_pk: int = 0,
    ) -> list[MediaSummary]:
        """
        List posts the authenticated account has liked.

        Args:
            account_id: The application account ID (for client lookup).
            amount: Number of posts to retrieve (default 21).
            last_media_pk: Pagination cursor; 0 starts from beginning.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            medias = client.liked_medias(amount=amount, last_media_pk=last_media_pk)

            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_liked_medias", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_collection_to_summary(collection: Any) -> CollectionSummary:
        """
        Map instagrapi Collection object to CollectionSummary DTO.

        Args:
            collection: instagrapi Collection object.

        Returns:
            CollectionSummary DTO.
        """
        return CollectionSummary(
            pk=collection.pk,
            name=collection.name,
            media_count=getattr(collection, "media_count", None),
        )
