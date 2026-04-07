"""Instagram data adapter for smart-engagement target data.

OWNERSHIP: Concrete adapter over app-owned Instagram use cases.
No direct instagrapi client usage and no vendor model leakage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai_copilot.application.smart_engagement.state import EngagementTarget
from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)
from app.application.dto.instagram_media_dto import MediaSummary


@runtime_checkable
class IdentityUseCasesPort(Protocol):
    def get_authenticated_account(self, account_id: str) -> AuthenticatedAccountProfile:
        pass

    def get_public_user_by_id(self, account_id: str, user_id: int) -> PublicUserProfile:
        pass

    def get_public_user_by_username(self, account_id: str, username: str) -> PublicUserProfile:
        pass


@runtime_checkable
class RelationshipUseCasesPort(Protocol):
    def list_followers(self, account_id: str, username: str, amount: int = 50) -> list[PublicUserProfile]:
        pass

    def list_following(self, account_id: str, username: str, amount: int = 50) -> list[PublicUserProfile]:
        pass


@runtime_checkable
class MediaUseCasesPort(Protocol):
    def get_user_medias(self, account_id: str, user_id: int, amount: int = 12) -> list[MediaSummary]:
        pass


class InstagramDataAdapter:
    """Fetches engagement targets from app-owned Instagram use-case seams."""

    def __init__(
        self,
        identity_usecases: IdentityUseCasesPort,
        relationship_usecases: RelationshipUseCasesPort,
        media_usecases: MediaUseCasesPort,
    ):
        self.identity_usecases = identity_usecases
        self.relationship_usecases = relationship_usecases
        self.media_usecases = media_usecases

    async def get_followers(
        self,
        account_id: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        clean_limit = max(1, int(limit))
        try:
            username = self._self_username(account_id)
            users = self.relationship_usecases.list_followers(
                account_id=account_id,
                username=username,
                amount=clean_limit,
            )
            filtered = self._apply_target_filters(users, filters or {})
            return [self._user_to_engagement_target(user) for user in filtered[:clean_limit]]
        except ValueError:
            raise
        except Exception:
            raise ValueError("Failed to fetch followers via relationship use cases")

    async def get_following(
        self,
        account_id: str,
        limit: int = 100,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        clean_limit = max(1, int(limit))
        try:
            username = self._self_username(account_id)
            users = self.relationship_usecases.list_following(
                account_id=account_id,
                username=username,
                amount=clean_limit,
            )
            filtered = self._apply_target_filters(users, filters or {})
            return [self._user_to_engagement_target(user) for user in filtered[:clean_limit]]
        except ValueError:
            raise
        except Exception:
            raise ValueError("Failed to fetch following via relationship use cases")

    async def get_recent_posts(
        self,
        account_id: str,
        limit: int = 50,
        filters: dict | None = None,
    ) -> list[EngagementTarget]:
        clean_limit = max(1, int(limit))
        try:
            me = self.identity_usecases.get_authenticated_account(account_id)
            posts = self.media_usecases.get_user_medias(
                account_id=account_id,
                user_id=int(me.pk),
                amount=clean_limit,
            )
            filtered = self._apply_post_filters(posts, filters or {})
            return [self._post_to_engagement_target(post) for post in filtered[:clean_limit]]
        except ValueError:
            raise
        except Exception:
            raise ValueError("Failed to fetch recent posts via media use cases")

    async def get_target_metadata(self, account_id: str, target_id: str) -> dict:
        try:
            if target_id.isdigit():
                user = self.identity_usecases.get_public_user_by_id(account_id, int(target_id))
            else:
                user = self.identity_usecases.get_public_user_by_username(account_id, target_id)
            return self._user_to_metadata(user)
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"Failed to fetch target metadata for {target_id}")

    def _self_username(self, account_id: str) -> str:
        profile = self.identity_usecases.get_authenticated_account(account_id)
        username = (profile.username or "").strip().lstrip("@")
        if not username:
            raise ValueError(f"Account {account_id} has no username")
        return username

    def _user_to_engagement_target(self, user: PublicUserProfile) -> EngagementTarget:
        return EngagementTarget(
            target_id=user.username,
            target_type="account",
            metadata={
                "user_id": user.pk,
                "username": user.username,
                "full_name": user.full_name,
                "follower_count": user.follower_count or 0,
                "following_count": user.following_count or 0,
                "media_count": user.media_count or 0,
                "is_verified": bool(user.is_verified),
                "is_business": bool(user.is_business),
                "biography": user.biography or "",
            },
        )

    def _post_to_engagement_target(self, media: MediaSummary) -> EngagementTarget:
        total_engagement = int(media.like_count) + int(media.comment_count)
        engagement_rate = 0.0 if total_engagement <= 0 else total_engagement / (total_engagement + 1)
        return EngagementTarget(
            target_id=str(media.pk),
            target_type="post",
            metadata={
                "post_id": media.pk,
                "owner": media.owner_username,
                "caption": media.caption_text,
                "likes": media.like_count,
                "comments": media.comment_count,
                "engagement_rate": engagement_rate,
                "posted_at": media.taken_at.timestamp() if media.taken_at else None,
            },
        )

    def _user_to_metadata(self, user: PublicUserProfile) -> dict:
        media_count = int(user.media_count or 0)
        return {
            "username": user.username,
            "follower_count": int(user.follower_count or 0),
            "following_count": int(user.following_count or 0),
            "media_count": media_count,
            "is_verified": bool(user.is_verified),
            "is_business": bool(user.is_business),
            "biography": user.biography or "",
            "has_posts": media_count > 0,
        }

    def _apply_target_filters(
        self,
        users: list[PublicUserProfile],
        filters: dict,
    ) -> list[PublicUserProfile]:
        filtered = users
        if "min_followers" in filters:
            min_f = int(filters["min_followers"])
            filtered = [u for u in filtered if int(u.follower_count or 0) >= min_f]
        if "max_followers" in filters:
            max_f = int(filters["max_followers"])
            filtered = [u for u in filtered if int(u.follower_count or 0) <= max_f]
        if filters.get("has_posts"):
            filtered = [u for u in filtered if int(u.media_count or 0) > 0]
        if filters.get("is_verified"):
            filtered = [u for u in filtered if bool(u.is_verified)]
        return filtered

    def _apply_post_filters(
        self,
        posts: list[MediaSummary],
        filters: dict,
    ) -> list[MediaSummary]:
        filtered = posts
        if "min_engagement_rate" in filters:
            min_rate = float(filters["min_engagement_rate"])
            filtered = [
                p
                for p in filtered
                if ((p.like_count + p.comment_count) / (p.like_count + p.comment_count + 1)) >= min_rate
            ]
        if "min_likes" in filters:
            min_likes = int(filters["min_likes"])
            filtered = [p for p in filtered if int(p.like_count) >= min_likes]
        if "has_caption" in filters and filters["has_caption"]:
            filtered = [p for p in filtered if bool((p.caption_text or "").strip())]
        return filtered
