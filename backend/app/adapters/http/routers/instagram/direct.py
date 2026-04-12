"""Direct message routes for Instagram transport."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.http.dependencies import get_direct_usecases
from app.adapters.http.schemas.instagram import (
    DirectDeleteMessageEnvelope,
    DirectFindOrCreateEnvelope,
    DirectSendEnvelope,
    DirectSendThreadEnvelope,
    DirectSendUsersEnvelope,
    DirectThreadActionEnvelope,
)
from app.adapters.http.utils import format_error

from .mappers import _to_direct_message, _to_direct_receipt, _to_direct_thread_detail, _to_direct_thread_summary

router = APIRouter()


@router.post("/direct/send")
def send_direct_message(
    body: DirectSendEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send a DM to a user by username via DirectUseCases."""
    try:
        message = usecases.send_to_username(body.account_id, body.username, body.text)
        return {
            "directMessageId": message.direct_message_id,
            "directThreadId": message.direct_thread_id,
            "text": message.text,
            "sentAt": message.sent_at.isoformat() if message.sent_at else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Send DM failed"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=format_error(exc, "Send DM failed"))


@router.post("/direct/find-or-create")
def find_or_create_direct_thread(
    body: DirectFindOrCreateEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Find or create a direct thread via DirectUseCases."""
    try:
        thread = usecases.find_or_create_thread(
            account_id=body.account_id,
            participant_user_ids=body.participant_user_ids,
        )
        return _to_direct_thread_summary(thread)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Find/create thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Find/create thread failed")
        )


@router.post("/direct/send-thread")
def send_direct_to_thread(
    body: DirectSendThreadEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send DM to an existing thread via DirectUseCases."""
    try:
        message = usecases.send_to_thread(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
            text=body.text,
        )
        return _to_direct_message(message)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to thread failed")
        )


@router.post("/direct/send-users")
def send_direct_to_users(
    body: DirectSendUsersEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Send DM to users via DirectUseCases."""
    try:
        message = usecases.send_to_users(
            account_id=body.account_id,
            user_ids=body.user_ids,
            text=body.text,
        )
        return _to_direct_message(message)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to users failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Send to users failed")
        )


@router.post("/direct/delete-message")
def delete_direct_message(
    body: DirectDeleteMessageEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Delete a DM message via DirectUseCases."""
    try:
        receipt = usecases.delete_message(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
            direct_message_id=body.direct_message_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete DM failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Delete DM failed")
        )


@router.post("/direct/approve-pending")
def approve_pending_direct_thread(
    body: DirectThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Approve a pending DM request, moving it to the main inbox."""
    try:
        receipt = usecases.approve_pending_thread(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Approve pending thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Approve pending thread failed")
        )


@router.post("/direct/mark-seen")
def mark_direct_thread_seen(
    body: DirectThreadActionEnvelope,
    usecases=Depends(get_direct_usecases),
):
    """Mark the most recent message in a thread as seen."""
    try:
        receipt = usecases.mark_thread_seen(
            account_id=body.account_id,
            direct_thread_id=body.direct_thread_id,
        )
        return _to_direct_receipt(receipt)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark thread seen failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Mark thread seen failed")
        )


@router.get("/direct/{account_id}/inbox")
def list_inbox(
    account_id: str,
    amount: int = Query(20, ge=1, le=100),
    usecases=Depends(get_direct_usecases),
):
    """List inbox threads via DirectUseCases."""
    try:
        threads = usecases.list_inbox_threads(account_id, amount=amount)
        return {
            "count": len(threads),
            "threads": [
                {
                    "directThreadId": t.direct_thread_id,
                    "participants": [p.username for p in t.participants],
                    "isPending": t.is_pending,
                    "lastMessage": t.last_message.text if t.last_message else None,
                }
                for t in threads
            ],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List inbox failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List inbox failed")
        )


@router.get("/direct/{account_id}/pending")
def list_pending_inbox(
    account_id: str,
    amount: int = Query(20, ge=1, le=100),
    usecases=Depends(get_direct_usecases),
):
    """List pending DM threads via DirectUseCases."""
    try:
        threads = usecases.list_pending_threads(account_id, amount=amount)
        return {
            "count": len(threads),
            "threads": [_to_direct_thread_summary(t) for t in threads],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List pending inbox failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List pending inbox failed")
        )


@router.get("/direct/{account_id}/thread/{direct_thread_id}")
def get_direct_thread(
    account_id: str,
    direct_thread_id: str,
    amount: int = Query(20, ge=1, le=200),
    usecases=Depends(get_direct_usecases),
):
    """Get a direct thread with messages via DirectUseCases."""
    try:
        thread = usecases.get_thread(account_id, direct_thread_id, amount=amount)
        return _to_direct_thread_detail(thread)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get direct thread failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Get direct thread failed")
        )


@router.get("/direct/{account_id}/thread/{direct_thread_id}/messages")
def list_direct_messages(
    account_id: str,
    direct_thread_id: str,
    amount: int = Query(20, ge=1, le=200),
    usecases=Depends(get_direct_usecases),
):
    """List direct messages in thread via DirectUseCases."""
    try:
        messages = usecases.list_messages(account_id, direct_thread_id, amount=amount)
        return {
            "count": len(messages),
            "messages": [_to_direct_message(m) for m in messages],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List direct messages failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "List direct messages failed")
        )


@router.get("/direct/{account_id}/search")
def search_direct_threads(
    account_id: str,
    query: str = Query(..., description="Search query"),
    usecases=Depends(get_direct_usecases),
):
    """Search direct threads via DirectUseCases."""
    try:
        threads = usecases.search_threads(account_id, query)
        return {
            "count": len(threads),
            "threads": [_to_direct_thread_summary(t) for t in threads],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search direct threads failed")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=format_error(exc, "Search direct threads failed")
        )
