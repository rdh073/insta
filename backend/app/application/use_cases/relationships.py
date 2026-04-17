"""Relationship use cases for Instagram follower/following reads and writes."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator

from app.application.dto.instagram_identity_dto import PublicUserProfile
from app.application.ports.instagram_identity import InstagramIdentityReader
from app.application.ports.instagram_relationships import InstagramRelationshipReader
from app.application.ports.repositories import AccountRepository, ClientRepository

logger = logging.getLogger(__name__)


class RelationshipUseCases:
    """Application orchestration for follower/following reads and mutations."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        identity_reader: InstagramIdentityReader,
        relationship_reader: InstagramRelationshipReader,
        relationship_writer=None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.identity_reader = identity_reader
        self.relationship_reader = relationship_reader
        self.relationship_writer = relationship_writer

    def list_followers(
        self,
        account_id: str,
        username: str,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List followers by resolving username into user_id first."""
        user = self._resolve_user(account_id, username)
        return self.relationship_reader.list_followers(
            account_id=account_id,
            user_id=int(user.pk),
            amount=max(1, int(amount)),
        )

    def list_following(
        self,
        account_id: str,
        username: str,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List following by resolving username into user_id first."""
        user = self._resolve_user(account_id, username)
        return self.relationship_reader.list_following(
            account_id=account_id,
            user_id=int(user.pk),
            amount=max(1, int(amount)),
        )

    def follow_user(self, account_id: str, target_username: str) -> bool:
        """Follow a user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.follow_user(account_id, user_id)

    def unfollow_user(self, account_id: str, target_username: str) -> bool:
        """Unfollow a user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.unfollow_user(account_id, user_id)

    def search_followers(
        self,
        account_id: str,
        username: str,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's follower list (server-side)."""
        user = self._resolve_user(account_id, username)
        return self.relationship_reader.search_followers(
            account_id=account_id,
            user_id=int(user.pk),
            query=query,
        )

    def search_following(
        self,
        account_id: str,
        username: str,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's following list (server-side)."""
        user = self._resolve_user(account_id, username)
        return self.relationship_reader.search_following(
            account_id=account_id,
            user_id=int(user.pk),
            query=query,
        )

    def remove_follower(self, account_id: str, target_username: str) -> bool:
        """Remove a follower by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.remove_follower(account_id, user_id)

    def close_friend_add(self, account_id: str, target_username: str) -> bool:
        """Add a user to Close Friends by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.close_friend_add(account_id, user_id)

    def close_friend_remove(self, account_id: str, target_username: str) -> bool:
        """Remove a user from Close Friends by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.close_friend_remove(account_id, user_id)

    def mute_posts(self, account_id: str, target_username: str) -> bool:
        """Mute feed posts from a followed user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.mute_posts(account_id, user_id)

    def unmute_posts(self, account_id: str, target_username: str) -> bool:
        """Unmute feed posts from a followed user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.unmute_posts(account_id, user_id)

    def mute_stories(self, account_id: str, target_username: str) -> bool:
        """Mute stories from a followed user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.mute_stories(account_id, user_id)

    def unmute_stories(self, account_id: str, target_username: str) -> bool:
        """Unmute stories from a followed user by username."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        user_id = self._resolve_user_id(account_id, target_username)
        return self.relationship_writer.unmute_stories(account_id, user_id)

    _NOTIFICATION_METHODS = {
        "posts": "set_posts_notifications",
        "videos": "set_videos_notifications",
        "reels": "set_reels_notifications",
        "stories": "set_stories_notifications",
    }

    def set_user_notifications(
        self,
        account_id: str,
        target_username: str,
        kind: str,
        enabled: bool,
    ) -> bool:
        """Toggle per-user push notifications for posts/videos/reels/stories."""
        if self.relationship_writer is None:
            raise ValueError("relationship writer not configured")
        method_name = self._NOTIFICATION_METHODS.get(kind)
        if method_name is None:
            raise ValueError(
                f"unknown notification kind '{kind}'; expected one of "
                f"{sorted(self._NOTIFICATION_METHODS)}"
            )
        user_id = self._resolve_user_id(account_id, target_username)
        method = getattr(self.relationship_writer, method_name)
        return method(account_id, user_id, bool(enabled))

    async def batch_follow(
        self,
        account_ids: list[str],
        targets: list[str],
        concurrency: int = 3,
        delay_between: float = 1.0,
    ) -> AsyncIterator[dict]:
        """Batch follow targets from multiple accounts with concurrency control.

        Yields result dicts as each operation completes (for SSE streaming).
        Per-account operations are serialized; cross-account runs in parallel.
        """
        async for result in self._batch_action(
            "follow", account_ids, targets, concurrency, delay_between
        ):
            yield result

    async def batch_unfollow(
        self,
        account_ids: list[str],
        targets: list[str],
        concurrency: int = 3,
        delay_between: float = 1.0,
    ) -> AsyncIterator[dict]:
        """Batch unfollow targets from multiple accounts with concurrency control."""
        async for result in self._batch_action(
            "unfollow", account_ids, targets, concurrency, delay_between
        ):
            yield result

    async def _batch_action(
        self,
        action: str,
        account_ids: list[str],
        targets: list[str],
        concurrency: int,
        delay_between: float,
    ) -> AsyncIterator[dict]:
        """Execute batch follow/unfollow with per-account serialization.

        Architecture:
        - asyncio.Semaphore limits total concurrent threads
        - Each account runs its target list sequentially (avoid per-account rate limit)
        - Cross-account work runs in parallel up to semaphore limit
        - Each result is yielded immediately for SSE streaming
        """
        semaphore = asyncio.Semaphore(concurrency)
        result_queue: asyncio.Queue[dict | None] = asyncio.Queue()
        fn = self.follow_user if action == "follow" else self.unfollow_user

        total = len(account_ids) * len(targets)
        completed = 0

        async def _process_account(account_id: str) -> None:
            nonlocal completed
            username = account_id
            remaining_targets = deque(targets)

            async def _enqueue_result(
                target: str, success: bool, error: str | None = None
            ) -> None:
                nonlocal completed
                result = {
                    "account_id": account_id,
                    "account": username,
                    "target": target,
                    "action": action,
                    "success": bool(success),
                }
                if error:
                    result["error"] = error[:200]
                completed += 1
                result["completed"] = completed
                result["total"] = total
                await result_queue.put(result)

            try:
                account = self.account_repo.get(account_id)
                username = (account or {}).get("username", account_id)

                while remaining_targets:
                    target = remaining_targets.popleft()
                    async with semaphore:
                        try:
                            success = await asyncio.to_thread(fn, account_id, target)
                            await _enqueue_result(target, bool(success))
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            await _enqueue_result(target, False, str(exc))

                        # Rate limit delay between actions per account
                        if delay_between > 0:
                            await asyncio.sleep(delay_between)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Account-level setup errors used to drop the whole account task and
                # stall the queue consumer. Emit failures for all remaining targets
                # so completed accounting always reaches `total`.
                logger.exception(
                    "Batch %s setup failed for account %s", action, account_id
                )
                error = str(exc)
                for target in remaining_targets:
                    await _enqueue_result(target, False, error)

        # Launch all accounts in parallel
        tasks = [asyncio.create_task(_process_account(aid)) for aid in account_ids]

        # Yield results as they arrive
        finished = 0
        while finished < total:
            item = await result_queue.get()
            if item is not None:
                yield item
                finished += 1

        # Ensure all tasks complete cleanly
        await asyncio.gather(*tasks, return_exceptions=True)

    def _resolve_user(self, account_id: str, username: str) -> PublicUserProfile:
        """Validate account state and resolve target username to full profile.

        Used for read-oriented flows (list_followers, list_following, search_*)
        that need the full PublicUserProfile DTO.
        """
        clean_username = username.strip().lstrip("@")
        if not clean_username:
            raise ValueError("username is required")
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id} is not authenticated")
        return self.identity_reader.get_public_user_by_username(
            account_id, clean_username
        )

    def _resolve_user_id(self, account_id: str, username: str) -> int:
        """Validate account state and resolve target username to numeric user ID.

        Used for write-oriented flows (follow, unfollow, remove_follower,
        close_friend_add/remove) that only need the numeric ID.  Avoids
        fetching the full profile to minimise API round-trips and reduce
        exposure to fields that mutation endpoints do not need.
        """
        clean_username = username.strip().lstrip("@")
        if not clean_username:
            raise ValueError("username is required")
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id} is not authenticated")
        return self.identity_reader.get_user_id_by_username(account_id, clean_username)
