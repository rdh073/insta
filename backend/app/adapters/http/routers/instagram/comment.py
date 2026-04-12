"""Comment routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_comment_usecases
from app.adapters.http.schemas.instagram import (
    CommentCreateEnvelope,
    CommentDeleteEnvelope,
    CommentLikeEnvelope,
    CommentPinEnvelope,
)
from app.adapters.http.utils import format_error

from .mappers import _to_comment, _to_comment_receipt

router = APIRouter()


@router.post("/comment")
def create_comment(
    body: CommentCreateEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Create a comment or reply via CommentUseCases."""
    try:
        comment = usecases.create_comment(
            body.account_id,
            body.media_id,
            body.text,
            reply_to_comment_id=body.reply_to_comment_id,
        )
        return {
            "pk": comment.pk,
            "text": comment.text,
            "author": comment.author.username,
            "createdAt": comment.created_at.isoformat() if comment.created_at else None,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create comment failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Create comment failed")
        )


@router.get("/comment/{account_id}/{media_id}")
def list_comments(
    account_id: str,
    media_id: str,
    amount: int = Query(0, ge=0),
    usecases=Depends(get_comment_usecases),
):
    """List comments for a media item via CommentUseCases."""
    try:
        comments = usecases.list_comments(account_id, media_id, amount=amount)
        return {
            "count": len(comments),
            "comments": [
                {
                    "pk": c.pk,
                    "text": c.text,
                    "author": c.author.username,
                    "likeCount": c.like_count,
                    "createdAt": c.created_at.isoformat() if c.created_at else None,
                }
                for c in comments
            ],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments failed")
        )


@router.get("/comment/{account_id}/{media_id}/page")
def list_comments_page(
    account_id: str,
    media_id: str,
    page_size: int = Query(20, ge=1, le=200),
    cursor: str | None = Query(None),
    usecases=Depends(get_comment_usecases),
):
    """List comments page for a media item via CommentUseCases."""
    try:
        page = usecases.list_comments_page(
            account_id=account_id,
            media_id=media_id,
            page_size=page_size,
            cursor=cursor,
        )
        return {
            "count": len(page.comments),
            "nextCursor": page.next_cursor,
            "comments": [_to_comment(c) for c in page.comments],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments page failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List comments page failed")
        )


@router.post("/comment/delete")
def delete_comment(
    body: CommentDeleteEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Delete a comment via CommentUseCases."""
    try:
        receipt = usecases.delete_comment(
            account_id=body.account_id,
            media_id=body.media_id,
            comment_id=body.comment_id,
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete comment failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete comment failed")
        )


@router.post("/comment/like")
def like_comment(
    body: CommentLikeEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Like a comment."""
    try:
        receipt = usecases.like_comment(account_id=body.account_id, comment_id=body.comment_id)
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Like comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Like comment failed"))


@router.post("/comment/unlike")
def unlike_comment(
    body: CommentLikeEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Unlike a comment."""
    try:
        receipt = usecases.unlike_comment(account_id=body.account_id, comment_id=body.comment_id)
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unlike comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unlike comment failed"))


@router.post("/comment/pin")
def pin_comment(
    body: CommentPinEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Pin a comment on a post owned by the account."""
    try:
        receipt = usecases.pin_comment(
            account_id=body.account_id, media_id=body.media_id, comment_id=body.comment_id
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Pin comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Pin comment failed"))


@router.post("/comment/unpin")
def unpin_comment(
    body: CommentPinEnvelope,
    usecases=Depends(get_comment_usecases),
):
    """Unpin a comment on a post owned by the account."""
    try:
        receipt = usecases.unpin_comment(
            account_id=body.account_id, media_id=body.media_id, comment_id=body.comment_id
        )
        return _to_comment_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unpin comment failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Unpin comment failed"))
