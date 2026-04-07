"""
Instagram identity DTOs - stable contracts for account and user data.

Separates authenticated account profiles (with private fields) from
public user profiles to prevent vendor model leakage into application layer.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AuthenticatedAccountProfile:
    """
    Authenticated account profile with private/self-only fields.

    Represents the logged-in account retrieved via account_info().
    Includes private fields like email and phone_number that are only
    available to the authenticated user.
    """

    pk: int
    """Instagram account ID."""

    username: str
    """Account username."""

    full_name: Optional[str] = None
    """Full name displayed on profile."""

    biography: Optional[str] = None
    """Profile biography/bio text."""

    profile_pic_url: Optional[str] = None
    """URL to profile picture."""

    follower_count: Optional[int] = None
    """Number of followers."""

    following_count: Optional[int] = None
    """Number of accounts this user follows."""

    external_url: Optional[str] = None
    """External URL in profile (link in bio)."""

    is_private: Optional[bool] = None
    """Whether the account is private."""

    is_verified: Optional[bool] = None
    """Whether the account is Instagram verified."""

    is_business: Optional[bool] = None
    """Whether the account is a business account."""

    email: Optional[str] = None
    """Email address (self-only field)."""

    phone_number: Optional[str] = None
    """Phone number (self-only field)."""


@dataclass(frozen=True)
class PublicUserProfile:
    """
    Public user profile - no private fields.

    Represents a user profile accessible via user_info() or user_info_by_username().
    Contains only public-facing information and engagement metrics.
    """

    pk: int
    """Instagram user ID."""

    username: str
    """Username."""

    full_name: Optional[str] = None
    """Full name displayed on profile."""

    biography: Optional[str] = None
    """Profile biography/bio text."""

    profile_pic_url: Optional[str] = None
    """URL to profile picture."""

    follower_count: Optional[int] = None
    """Number of followers."""

    following_count: Optional[int] = None
    """Number of accounts this user follows."""

    media_count: Optional[int] = None
    """Number of media items posted."""

    is_private: Optional[bool] = None
    """Whether the account is private."""

    is_verified: Optional[bool] = None
    """Whether the account is Instagram verified."""

    is_business: Optional[bool] = None
    """Whether the account is a business account."""
