"""Collection routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_collection_usecases
from app.adapters.http.utils import format_error

from .mappers import _to_media

router = APIRouter()


@router.get("/collection/{account_id}")
def list_collections(
    account_id: str,
    usecases=Depends(get_collection_usecases),
):
    """List all saved collections for an account via CollectionUseCases."""
    try:
        collections = usecases.list_collections(account_id)
        return [
            {
                "pk": c.pk,
                "name": c.name,
                "type": c.collection_type,
                "mediaCount": c.media_count,
            }
            for c in collections
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List collections failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List collections failed")
        )


@router.get("/collection/{account_id}/posts")
def get_collection_posts(
    account_id: str,
    name: str = Query(..., description="Collection name"),
    amount: int = Query(21, ge=1, le=200),
    last_media_pk: int = Query(0, ge=0),
    usecases=Depends(get_collection_usecases),
):
    """Get posts in a named collection via CollectionUseCases."""
    try:
        collection_pk = usecases.get_collection_pk_by_name(account_id, name)
        posts = usecases.get_collection_posts(
            account_id, collection_pk, amount=amount, last_media_pk=last_media_pk
        )
        return {
            "collection": name,
            "count": len(posts),
            "posts": [_to_media(m) for m in posts],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Collection posts failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Collection posts failed")
        )
