"""Identity routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.http.dependencies import get_identity_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_public_profile

router = APIRouter()


@router.get("/identity/{account_id}/me")
def get_authenticated_identity(
    account_id: str, usecases=Depends(get_identity_usecases)
):
    """Read authenticated account profile through IdentityUseCases."""
    try:
        profile = usecases.get_authenticated_account(account_id)
        return {
            "pk": profile.pk,
            "username": profile.username,
            "fullName": profile.full_name,
            "biography": profile.biography,
            "profilePicUrl": profile.profile_pic_url,
            "externalUrl": profile.external_url,
            "isPrivate": profile.is_private,
            "isVerified": profile.is_verified,
            "isBusiness": profile.is_business,
            "email": profile.email,
            "phoneNumber": profile.phone_number,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=format_error(exc, "Account not found")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Identity read failed")
        )


@router.get("/identity/{account_id}/user/{username}")
def get_public_user_by_username(
    account_id: str,
    username: str,
    usecases=Depends(get_identity_usecases),
):
    """Resolve a public Instagram username to its numeric user ID and profile."""
    try:
        profile = usecases.get_public_user_by_username(account_id, username)
        return _to_public_profile(profile)
    except InstagramRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=format_error(
                exc, "Rate limited by Instagram. Please wait before trying again."
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=format_error(exc, "User not found"))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "User lookup failed")
        )
