from __future__ import annotations

from pathlib import Path
from typing import Callable


def _build_usertags(specs: list[dict]):
    """Build instagrapi Usertag objects from [{user_id, username, x, y}] dicts."""
    from instagrapi.types import UserShort, Usertag

    tags = []
    for spec in specs:
        try:
            user = UserShort(
                pk=str(spec["user_id"]),
                username=spec.get("username", ""),
            )
            tags.append(
                Usertag(
                    user=user,
                    x=float(spec.get("x", 0.5)),
                    y=float(spec.get("y", 0.5)),
                )
            )
        except Exception:
            continue
    return tags


def _build_location(loc: dict | None):
    """Build an instagrapi Location from {name, lat, lng} dict, or None."""
    if not loc:
        return None
    from instagrapi.types import Location

    try:
        return Location(
            name=loc["name"],
            lat=loc.get("lat"),
            lng=loc.get("lng"),
        )
    except Exception:
        return None


def _upload_reels(
    cl, media_paths, caption, thumbnail_path, igtv_title, usertags, location, extra_data
):
    cl.clip_upload(
        Path(media_paths[0]),
        caption=caption,
        thumbnail=Path(thumbnail_path) if thumbnail_path else None,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_igtv(
    cl, media_paths, caption, thumbnail_path, igtv_title, usertags, location, extra_data
):
    cl.igtv_upload(
        Path(media_paths[0]),
        title=igtv_title or "",
        caption=caption,
        thumbnail=Path(thumbnail_path) if thumbnail_path else None,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_photo(
    cl,
    media_paths,
    caption,
    thumbnail_path,  # unused: photos do not support custom thumbnails
    igtv_title,  # unused: N/A for photos
    usertags,
    location,
    extra_data,
):
    cl.photo_upload(
        Path(media_paths[0]),
        caption=caption,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_album(
    cl,
    media_paths,
    caption,
    thumbnail_path,  # unused: albums do not support custom thumbnails
    igtv_title,  # unused: N/A for albums
    usertags,
    location,
    extra_data,
):
    cl.album_upload(
        [Path(p) for p in media_paths],
        caption=caption,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


# Type alias for all upload strategy functions.
# Each strategy receives the same 8 arguments so _dispatch_upload can call any of them uniformly.
_UploadFn = Callable[..., None]

# Maps media_type string → upload function.
# Add a new entry here to support future media types without touching _upload_one.
_UPLOAD_STRATEGIES: dict[str, _UploadFn] = {
    "reels": _upload_reels,
    "video": _upload_reels,  # alias — same behaviour as reels
    "igtv": _upload_igtv,
    "photo": _upload_photo,
    "album": _upload_album,
}

_DEFAULT_UPLOAD_STRATEGY: _UploadFn = _upload_album  # fallback for unknown types


def _dispatch_upload(
    cl,
    media_type: str,
    media_paths: list[str],
    caption: str,
    thumbnail_path: str | None,
    igtv_title: str | None,
    usertags,
    location,
    extra_data: dict,
) -> None:
    """Select and invoke the correct upload strategy for *media_type*."""
    strategy: _UploadFn = _UPLOAD_STRATEGIES.get(media_type, _DEFAULT_UPLOAD_STRATEGY)
    strategy(
        cl,
        media_paths,
        caption,
        thumbnail_path,
        igtv_title,
        usertags,
        location,
        extra_data,
    )

