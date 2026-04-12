"""
Instagram story publisher adapter.

Maps story publication requests to instagrapi Story upload methods.
Handles composition spec conversion, audience mapping, and media preparation.
"""

from pathlib import Path
from typing import Any, Optional

from instagrapi.types import (
    StoryHashtag,
    StoryLink,
    StoryMedia,
    StoryMention,
    StoryPoll,
    StorySticker,
    StoryLocation,
)

from app.application.dto.instagram_story_dto import (
    StoryActionReceipt,
    StoryDetail,
    StoryHashtagSpec,
    StoryLinkSpec,
    StoryLocationSpec,
    StoryMediaSpec,
    StoryMentionSpec,
    StoryPollSpec,
    StoryPublishRequest,
    StoryStickerSpec,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.story_reader import InstagramStoryReaderAdapter
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramStoryPublisherAdapter:
    """
    Adapter for publishing and managing Instagram stories via instagrapi.

    Handles story creation, deletion, and lifecycle operations.
    Centralizes vendor-specific concerns:
    - Choosing photo_upload_to_story vs video_upload_to_story
    - Converting audience="close_friends" to vendor extra_data={"audience": "besties"}
    - Building vendor StoryLink, StoryMention, etc. from spec fields
    - Resolving mention/hashtag/location objects via API lookups before upload
    """

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo
        self.story_reader = InstagramStoryReaderAdapter(client_repo)

    def publish_story(
        self,
        account_id: str,
        request: StoryPublishRequest,
    ) -> StoryDetail:
        """
        Publish a story with optional overlays.

        Resolves mention users, hashtag objects, and locations via instagrapi
        API calls before building the vendor composition objects and uploading.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            self._validate_overlay_specs(request)

            # Build vendor story composition objects.
            # Mentions/hashtags/locations require API lookups — client is passed in.
            vendor_links = self._build_story_links(request.links)
            vendor_mentions = self._build_story_mentions(client, request.mentions)
            vendor_hashtags = self._build_story_hashtags(client, request.hashtags)
            vendor_locations = self._build_story_locations(client, request.locations)
            vendor_stickers = self._build_story_stickers(request.stickers)
            vendor_polls = self._build_story_polls(request.polls)
            vendor_medias = self._build_story_medias(request.medias)

            extra_data = self._build_extra_data(request.audience)

            if request.media_kind == "photo":
                # photo_upload_to_story has NO thumbnail parameter
                story = client.photo_upload_to_story(
                    path=Path(request.media_path),
                    caption=request.caption or "",
                    mentions=vendor_mentions,
                    locations=vendor_locations,
                    links=vendor_links,
                    hashtags=vendor_hashtags,
                    stickers=vendor_stickers,
                    medias=vendor_medias,
                    polls=vendor_polls,
                    extra_data=extra_data,
                )
            elif request.media_kind == "video":
                story = client.video_upload_to_story(
                    path=Path(request.media_path),
                    caption=request.caption or "",
                    thumbnail=Path(request.thumbnail_path) if request.thumbnail_path else None,
                    mentions=vendor_mentions,
                    locations=vendor_locations,
                    links=vendor_links,
                    hashtags=vendor_hashtags,
                    stickers=vendor_stickers,
                    medias=vendor_medias,
                    polls=vendor_polls,
                    extra_data=extra_data,
                )
            else:
                raise ValueError(f"Unknown media kind: {request.media_kind}")

            return self.story_reader._map_story_to_detail(story)

        except ValueError:
            raise
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="publish_story", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def delete_story(
        self,
        account_id: str,
        story_pk: int,
    ) -> StoryActionReceipt:
        """Delete a story by primary key."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            client.story_delete(story_pk)
            return StoryActionReceipt(
                action_id=f"delete_{story_pk}",
                success=True,
                reason="Story deleted successfully",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="delete_story", account_id=account_id
            )
            return StoryActionReceipt(
                action_id=f"delete_{story_pk}",
                success=False,
                reason=failure.user_message,
            )

    def mark_seen(
        self,
        account_id: str,
        story_pks: list[int],
        skipped_story_pks: list[int] | None = None,
    ) -> StoryActionReceipt:
        """Mark stories as seen."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            client.story_seen(
                story_pks,
                skipped_story_pks=skipped_story_pks or [],
            )
            return StoryActionReceipt(
                action_id=f"mark_seen_{len(story_pks)}",
                success=True,
                reason=f"Marked {len(story_pks)} stories as seen",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="mark_story_seen", account_id=account_id
            )
            return StoryActionReceipt(
                action_id=f"mark_seen_{len(story_pks)}",
                success=False,
                reason=failure.user_message,
            )

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_overlay_specs(request: StoryPublishRequest) -> None:
        """Ensure all overlay specs are application-owned DTO types."""
        if not all(isinstance(s, StoryLinkSpec) for s in request.links):
            raise ValueError("links must contain StoryLinkSpec items")
        if not all(isinstance(s, StoryLocationSpec) for s in request.locations):
            raise ValueError("locations must contain StoryLocationSpec items")
        if not all(isinstance(s, StoryMentionSpec) for s in request.mentions):
            raise ValueError("mentions must contain StoryMentionSpec items")
        if not all(isinstance(s, StoryHashtagSpec) for s in request.hashtags):
            raise ValueError("hashtags must contain StoryHashtagSpec items")
        if not all(isinstance(s, StoryStickerSpec) for s in request.stickers):
            raise ValueError("stickers must contain StoryStickerSpec items")
        if not all(isinstance(s, StoryPollSpec) for s in request.polls):
            raise ValueError("polls must contain StoryPollSpec items")
        if not all(isinstance(s, StoryMediaSpec) for s in request.medias):
            raise ValueError("medias must contain StoryMediaSpec items")

    # ── Overlay builders ──────────────────────────────────────────────────────

    @staticmethod
    def _build_story_links(specs: list[StoryLinkSpec]) -> list[StoryLink]:
        return [StoryLink(webUri=spec.web_uri) for spec in specs]

    @staticmethod
    def _build_story_mentions(client: Any, specs: list[StoryMentionSpec]) -> list[StoryMention]:
        """Resolve each mention spec to a UserShort via API, then build StoryMention."""
        mentions = []
        for spec in specs:
            try:
                if spec.username:
                    user = client.user_info_by_username(spec.username)
                else:
                    user = client.user_info(spec.user_id)
                mentions.append(StoryMention(
                    user=user,
                    x=spec.x,
                    y=spec.y,
                    width=spec.width,
                    height=spec.height,
                ))
            except Exception:
                # Skip unresolvable mentions rather than failing the whole upload
                continue
        return mentions

    @staticmethod
    def _build_story_hashtags(client: Any, specs: list[StoryHashtagSpec]) -> list[StoryHashtag]:
        """Resolve each hashtag spec to a Hashtag object via API, then build StoryHashtag."""
        hashtags = []
        for spec in specs:
            try:
                hashtag = client.hashtag_info(spec.hashtag_name)
                hashtags.append(StoryHashtag(
                    hashtag=hashtag,
                    x=spec.x,
                    y=spec.y,
                    width=spec.width,
                    height=spec.height,
                ))
            except Exception:
                continue
        return hashtags

    @staticmethod
    def _build_story_locations(client: Any, specs: list[StoryLocationSpec]) -> list[StoryLocation]:
        """Resolve each location spec to a Location object via API, then build StoryLocation."""
        locations = []
        for spec in specs:
            if spec.location_pk is None:
                continue
            try:
                location = client.location_info(spec.location_pk)
                locations.append(StoryLocation(
                    location=location,
                    x=spec.x,
                    y=spec.y,
                    width=spec.width,
                    height=spec.height,
                ))
            except Exception:
                continue
        return locations

    @staticmethod
    def _build_story_stickers(specs: list[StoryStickerSpec]) -> list[StorySticker]:
        return [
            StorySticker(
                id=spec.sticker_id,
                type=spec.sticker_type,
                x=spec.x if spec.x is not None else 0.5,
                y=spec.y if spec.y is not None else 0.5,
                width=spec.width if spec.width is not None else 0.2,
                height=spec.height if spec.height is not None else 0.2,
            )
            for spec in specs
        ]

    @staticmethod
    def _build_story_polls(specs: list[StoryPollSpec]) -> list[StoryPoll]:
        return [
            StoryPoll(
                question=spec.question,
                options=list(spec.options),
                x=spec.x,
                y=spec.y,
                width=spec.width,
                height=spec.height,
            )
            for spec in specs
        ]

    @staticmethod
    def _build_story_medias(specs: list[StoryMediaSpec]) -> list[StoryMedia]:
        return [
            StoryMedia(
                media_pk=spec.media_pk,
                x=spec.x,
                y=spec.y,
                width=spec.width,
                height=spec.height,
                rotation=spec.rotation,
            )
            for spec in specs
        ]

    @staticmethod
    def _build_extra_data(audience: str) -> dict[str, Any]:
        """Map audience to vendor extra_data. Always returns a dict (never None)."""
        if audience == "close_friends":
            return {"audience": "besties"}
        return {}
