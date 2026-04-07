"""Domain services for Instagram interaction rules spanning multiple aggregates.

Services encapsulate business logic that involves multiple aggregates or
external context that cannot live in a single aggregate.

Characteristics:
  - Stateless (no instance variables)
  - Coordinate operations across aggregates
  - Enforce cross-aggregate invariants
  - No dependencies on framework, HTTP, or vendor code
  - May depend on adapter-provided context (e.g., user relationships, permissions)
"""

from __future__ import annotations

from typing import Optional

from app.domain.aggregates_core import (
    CommentAggregate,
    StoryAggregate,
    DirectThreadAggregate,
    DirectMessageAggregate,
)
from app.domain.interaction_values_core import (
    StoryAudience,
    InvalidComposite,
)


# ============================================================================
# Story Audience Service
# ============================================================================

class StoryAudienceService:
    """Domain service for story visibility rules.

    Handles validation of audience constraints and visibility logic
    that spans Story aggregate and external context (user relationships).

    Rules:
      - 'default' audience: visible to all followers
      - 'close_friends' audience: visible only to explicitly marked close friends
      - Story deletion: only owner can delete
    """

    @staticmethod
    def validate_audience_consistency(story: StoryAggregate) -> None:
        """Validate that story audience is properly configured.

        Args:
            story: StoryAggregate to validate.

        Raises:
            InvalidComposite: If audience constraints are violated.
        """
        # Ensure audience is one of the valid values (already checked in StoryAudience enum)
        # Additional rule: if audience is close_friends, story owner must exist
        if story.audience == StoryAudience.CLOSE_FRIENDS:
            if story.owner_user_id is None:
                raise InvalidComposite(
                    "StoryAudienceService: close_friends stories must have owner_user_id"
                )

    @staticmethod
    def can_view_story(story: StoryAggregate, viewer_user_id: int, is_close_friend: bool = False) -> bool:
        """Determine if a user can view a story based on audience.

        Args:
            story: StoryAggregate to check visibility.
            viewer_user_id: User ID attempting to view.
            is_close_friend: Whether viewer is marked as close friend (context from adapter).

        Returns:
            True if viewer can see the story, False otherwise.

        Note: This service bridges domain rules with adapter context.
        The is_close_friend flag comes from the adapter/relationship layer.
        """
        # Story owner can always view their own stories
        if story.owner_user_id and int(story.owner_user_id) == viewer_user_id:
            return True

        # Check audience rules
        if story.audience == StoryAudience.DEFAULT:
            return True  # Visible to all followers (adapter validates follower relationship)

        if story.audience == StoryAudience.CLOSE_FRIENDS:
            return is_close_friend  # Only close friends can view

        return False  # Default deny


# ============================================================================
# Comment Thread Service
# ============================================================================

class CommentThreadService:
    """Domain service for comment thread rules.

    Handles validation of comment relationships and reply chains
    that span multiple CommentAggregates.

    Rules:
      - Comments belong to a single media (media_id is immutable)
      - Reply chains: reply_to_comment_id must exist and be in same thread
      - Top-level comments: reply_to_comment_id is None
    """

    @staticmethod
    def validate_reply_chain(reply: CommentAggregate, parent: Optional[CommentAggregate] = None) -> None:
        """Validate that a reply is part of a valid chain.

        Args:
            reply: CommentAggregate being created as a reply.
            parent: Parent CommentAggregate (if reply). None if top-level.

        Raises:
            InvalidComposite: If reply chain is invalid.
        """
        if reply.is_reply():
            # Reply must have a parent
            if parent is None:
                raise InvalidComposite(
                    "CommentThreadService: reply_to_comment_id specified but parent comment not found"
                )
            # Parent must be in same media
            if reply.media_id.value != parent.media_id.value:
                raise InvalidComposite(
                    "CommentThreadService: reply must be in same media as parent comment"
                )
        else:
            # Top-level comment must not have parent
            if parent is not None:
                raise InvalidComposite(
                    "CommentThreadService: top-level comment must not reference parent"
                )

    @staticmethod
    def can_delete_comment(comment: CommentAggregate, requester_user_id: int, comment_owner_id: int) -> bool:
        """Determine if a user can delete a comment.

        Args:
            comment: CommentAggregate to potentially delete.
            requester_user_id: User ID requesting deletion.
            comment_owner_id: User ID who posted the comment.

        Returns:
            True if deletion is allowed, False otherwise.

        Rules:
          - Only comment owner can delete their own comments
          - Media owner can delete comments on their media
          - Administrators can delete any comment (not implemented at domain level)
        """
        # Only the comment owner can delete it (simplified rule)
        # Full implementation would include media owner and admin privileges
        return requester_user_id == comment_owner_id


# ============================================================================
# Direct Thread Service
# ============================================================================

class DirectThreadService:
    """Domain service for direct message thread rules.

    Handles validation of thread properties and message flow rules
    that involve multiple DirectMessage aggregates.

    Rules:
      - Messages belong to a single thread (direct_thread_id is immutable)
      - 1:1 threads have exactly 2 participants
      - Group threads have 3+ participants
      - All participants can read messages
      - Only sender can delete their own message
    """

    @staticmethod
    def validate_message_in_thread(message: DirectMessageAggregate, thread: DirectThreadAggregate) -> None:
        """Validate that a message belongs to the correct thread.

        Args:
            message: DirectMessageAggregate to validate.
            thread: DirectThreadAggregate containing the message.

        Raises:
            InvalidComposite: If message/thread relationship is invalid.
        """
        if message.direct_thread_id.value != thread.direct_thread_id.value:
            raise InvalidComposite(
                f"DirectThreadService: message thread_id {message.direct_thread_id} "
                f"does not match thread_id {thread.direct_thread_id}"
            )

    @staticmethod
    def can_send_message(thread: DirectThreadAggregate, sender_user_id: int) -> bool:
        """Determine if a user can send a message to a thread.

        Args:
            thread: DirectThreadAggregate to check.
            sender_user_id: User ID attempting to send.

        Returns:
            True if sender is a participant, False otherwise.
        """
        # Only participants can send messages to thread
        for participant_id in thread.participant_user_ids:
            if int(participant_id) == sender_user_id:
                return True
        return False

    @staticmethod
    def can_read_thread(thread: DirectThreadAggregate, reader_user_id: int) -> bool:
        """Determine if a user can read messages in a thread.

        Args:
            thread: DirectThreadAggregate to check.
            reader_user_id: User ID attempting to read.

        Returns:
            True if reader is a participant, False otherwise.
        """
        # Only participants can read thread messages
        for participant_id in thread.participant_user_ids:
            if int(participant_id) == reader_user_id:
                return True
        return False

    @staticmethod
    def can_delete_message(message: DirectMessageAggregate, requester_user_id: int, sender_user_id: int) -> bool:
        """Determine if a user can delete a message.

        Args:
            message: DirectMessageAggregate to check.
            requester_user_id: User ID requesting deletion.
            sender_user_id: User ID who sent the message.

        Returns:
            True if deletion is allowed, False otherwise.

        Rules:
          - Only message sender can delete their own message
        """
        return requester_user_id == sender_user_id


# ============================================================================
# Cross-Aggregate Composition Service (Future Extension)
# ============================================================================

class InstagramInteractionCompositionService:
    """Domain service for rules spanning multiple interaction types.

    Example use cases (deferred to Phase 4+):
      - Story highlight composition (stories + highlights relationship)
      - Comment notification rules (comments + relationships)
      - Direct message persistence rules (messages + thread lifecycle)

    Note: This is a skeleton for future cross-aggregate orchestration.
    For now, individual services handle specific aggregates.
    """

    @staticmethod
    def validate_cross_aggregate_consistency() -> None:
        """Placeholder for cross-aggregate validation rules.

        Example: Ensure that when a story is deleted, its highlight references
        are automatically cleaned up or marked invalid.
        """
        # Deferred to Phase 4+ when more aggregates are in place
        pass
