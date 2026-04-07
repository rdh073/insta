"""Domain value objects for Instagram interaction rules.

These value objects encapsulate identifier normalization, enumeration validation,
and composite rule checking that was previously scattered across use cases.

Characteristics:
  - Immutable (frozen dataclass)
  - Embeds validation at construction
  - No framework or vendor dependencies
  - Raises app-owned DomainValidationError on violation
  - Single responsibility (one rule per class)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ============================================================================
# Domain Exceptions
# ============================================================================

class DomainValidationError(Exception):
    """Base exception for domain validation failures."""
    pass


class InvalidIdentifier(DomainValidationError):
    """Identifier validation failure (empty, wrong type, out of range)."""
    pass


class InvalidEnumValue(DomainValidationError):
    """Enumeration value not in allowed set."""
    pass


class InvalidComposite(DomainValidationError):
    """Multi-field or complex validation failure."""
    pass


# ============================================================================
# Numeric Identifiers (Value Objects)
# ============================================================================

@dataclass(frozen=True)
class StoryPK:
    """Instagram story primary key (positive integer)."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value <= 0:
            raise InvalidIdentifier(
                f"StoryPK must be a positive integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class UserID:
    """Instagram user ID (positive integer)."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value <= 0:
            raise InvalidIdentifier(
                f"UserID must be a positive integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class CommentID:
    """Instagram comment ID (positive integer)."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value <= 0:
            raise InvalidIdentifier(
                f"CommentID must be a positive integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


# ============================================================================
# String Identifiers (Value Objects)
# ============================================================================

@dataclass(frozen=True)
class MediaID:
    """Instagram media identifier (non-empty string after strip)."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidIdentifier(
                "MediaID must not be empty"
            )
        # Store the cleaned value
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DirectThreadID:
    """Instagram direct message thread ID (non-empty string after strip)."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidIdentifier(
                "DirectThreadID must not be empty"
            )
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DirectMessageID:
    """Instagram direct message ID (non-empty string after strip)."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidIdentifier(
                "DirectMessageID must not be empty"
            )
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Enumeration Value Objects
# ============================================================================

class MediaKind(str, Enum):
    """Type of media in story or post."""
    PHOTO = "photo"
    VIDEO = "video"

    @classmethod
    def validate(cls, value: str) -> MediaKind:
        """Validate and return MediaKind.

        Args:
            value: String value to validate.

        Returns:
            MediaKind enum member.

        Raises:
            InvalidEnumValue: If value is not in the enum.
        """
        try:
            return cls(value)
        except ValueError:
            allowed = ", ".join(m.value for m in cls)
            raise InvalidEnumValue(
                f"MediaKind must be one of {{{allowed}}}, got {value!r}"
            )


class StoryAudience(str, Enum):
    """Story visibility scope."""
    DEFAULT = "default"
    CLOSE_FRIENDS = "close_friends"

    @classmethod
    def validate(cls, value: str) -> StoryAudience:
        """Validate and return StoryAudience.

        Args:
            value: String value to validate.

        Returns:
            StoryAudience enum member.

        Raises:
            InvalidEnumValue: If value is not in the enum.
        """
        try:
            return cls(value)
        except ValueError:
            allowed = ", ".join(a.value for a in cls)
            raise InvalidEnumValue(
                f"StoryAudience must be one of {{{allowed}}}, got {value!r}"
            )


# ============================================================================
# Bounded Integer Value Objects
# ============================================================================

@dataclass(frozen=True)
class QueryAmount:
    """Non-negative integer for query result limit (0 = all)."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value < 0:
            raise InvalidIdentifier(
                f"QueryAmount must be a non-negative integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class PageSize:
    """Positive integer for pagination page size."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value < 1:
            raise InvalidIdentifier(
                f"PageSize must be a positive integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class ThreadMessageLimit:
    """Positive integer for message count limit per thread."""
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value < 1:
            raise InvalidIdentifier(
                f"ThreadMessageLimit must be a positive integer, got {self.value!r}"
            )

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


# ============================================================================
# Composite Value Objects (Collections & Complex Rules)
# ============================================================================

@dataclass(frozen=True)
class UserIDList:
    """Non-empty list of positive integer user IDs."""
    values: tuple[int, ...]

    def __init__(self, user_ids: list[int] | tuple[int, ...]):
        if not user_ids:
            raise InvalidComposite("UserIDList must not be empty")
        for uid in user_ids:
            if not isinstance(uid, int) or uid <= 0:
                raise InvalidComposite(
                    f"All UserIDs must be positive integers, got {uid!r}"
                )
        object.__setattr__(self, 'values', tuple(user_ids))

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> int:
        return self.values[index]


# ============================================================================
# String Validation Value Objects
# ============================================================================

@dataclass(frozen=True)
class StoryURL:
    """Instagram story URL (must start with 'http')."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidComposite(
                "StoryURL must not be empty"
            )
        if not clean.startswith("http"):
            raise InvalidComposite(
                f"StoryURL must start with 'http', got {self.value!r}"
            )
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CommentText:
    """Non-empty comment text (after strip)."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidComposite(
                "CommentText must not be empty"
            )
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SearchQuery:
    """Non-empty search query (after strip)."""
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidComposite(
                "SearchQuery must not be empty"
            )
        object.__setattr__(self, 'value', clean)

    def __str__(self) -> str:
        return self.value


# ============================================================================
# Optional Identifiers
# ============================================================================

@dataclass(frozen=True)
class OptionalReplyTarget:
    """Optional comment ID for reply flow (if present: positive integer)."""
    value: Optional[int]

    def __post_init__(self):
        if self.value is not None:
            if not isinstance(self.value, int) or self.value <= 0:
                raise InvalidIdentifier(
                    f"ReplyTarget must be None or positive integer, got {self.value!r}"
                )

    def is_reply(self) -> bool:
        """Check if this is a reply (not top-level)."""
        return self.value is not None

    def __str__(self) -> str:
        return str(self.value) if self.value is not None else "(none)"
