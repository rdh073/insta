"""
Instagram relationships reader port.

Defines app-facing contract for follower/following discovery.
"""

from typing import Protocol

from app.application.dto.instagram_identity_dto import PublicUserProfile


class InstagramRelationshipReader(Protocol):
    """Port for reading follower/following relationships."""

    def list_followers(
        self,
        account_id: str,
        user_id: int,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List followers for a user."""
        ...

    def list_following(
        self,
        account_id: str,
        user_id: int,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List accounts followed by a user."""
        ...

    def search_followers(
        self,
        account_id: str,
        user_id: int,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's follower list (server-side)."""
        ...

    def search_following(
        self,
        account_id: str,
        user_id: int,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's following list (server-side)."""
        ...
