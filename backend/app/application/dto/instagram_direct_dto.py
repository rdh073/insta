"""
Instagram direct message DTOs - application-owned contracts for DM data.

Separates direct read/write concerns from vendor DirectThread and DirectMessage types.
Prevents instagrapi Direct objects from leaking into application or AI layers.

NAMING RULE: Use direct_thread_id and direct_message_id to avoid collision with
workflow thread_id used by AI graph execution and checkpointing.

All DTOs are frozen (immutable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DirectParticipantSummary:
    """Direct thread participant metadata.

    Represents a user in a direct message conversation.
    """
    user_id: int
    username: str
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_private: Optional[bool] = None


@dataclass(frozen=True)
class DirectMessageSummary:
    """Individual direct message metadata.

    Represents a single message in a direct conversation.
    Text-first design: media sharing deferred until real consumer needs it.
    """
    direct_message_id: str
    direct_thread_id: Optional[str] = None
    sender_user_id: Optional[int] = None
    sent_at: Optional[datetime] = None
    item_type: Optional[str] = None
    text: Optional[str] = None
    is_shh_mode: Optional[bool] = None


@dataclass(frozen=True)
class DirectThreadSummary:
    """Direct thread (conversation) metadata without messages.

    Represents a direct conversation without full message history.
    Used for inbox listing.
    """
    direct_thread_id: str
    pk: Optional[int] = None
    participants: list[DirectParticipantSummary] = field(default_factory=list)
    last_message: Optional[DirectMessageSummary] = None
    is_pending: bool = False


@dataclass(frozen=True)
class DirectSearchUserSummary:
    """Direct search result user metadata.

    Represents an instagrapi UserShort result from direct_search().
    """
    user_id: int
    username: str
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    is_private: Optional[bool] = None
    is_verified: Optional[bool] = None


@dataclass(frozen=True)
class DirectThreadDetail:
    """Direct thread with full message history.

    Represents a direct conversation with all messages retrieved.
    """
    summary: DirectThreadSummary
    messages: list[DirectMessageSummary] = field(default_factory=list)


@dataclass(frozen=True)
class DirectActionReceipt:
    """Result of a direct message action (send, delete, etc.).

    Provides stable feedback on DM operations.
    """
    action_id: str
    success: bool
    reason: str = ""


@dataclass(frozen=True)
class DirectMessageAck:
    """Acknowledgement for a direct-message attachment send/share operation.

    Covers photo/video/voice uploads and media/story shares fanned out
    to one or more threads. ``message_id`` is the vendor-returned identifier
    when instagrapi supplies one; absent otherwise.
    """
    thread_ids: list[str]
    kind: str
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
