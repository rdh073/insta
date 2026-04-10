"""Caption template CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.http.dependencies import get_templates_usecases

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    name: str
    caption: str
    tags: list[str] = []


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    caption: str | None = None
    tags: list[str] | None = None


def _serialize(t: dict) -> dict:
    return {
        "id": t["id"],
        "name": t["name"],
        "caption": t["caption"],
        "tags": t.get("tags", []),
        "usageCount": t.get("usage_count", 0),
        "createdAt": t.get("created_at", ""),
    }


@router.get("")
def list_templates(usecases=Depends(get_templates_usecases)):
    return [_serialize(t) for t in usecases.list_templates()]


@router.post("", status_code=201)
def create_template(body: CreateTemplateRequest, usecases=Depends(get_templates_usecases)):
    if not body.name.strip() or not body.caption.strip():
        raise HTTPException(status_code=400, detail="name and caption are required")
    template = usecases.create_template(body.name, body.caption, body.tags)
    return _serialize(template)


@router.patch("/{template_id}")
def update_template(
    template_id: str,
    body: UpdateTemplateRequest,
    usecases=Depends(get_templates_usecases),
):
    result = usecases.update_template(
        template_id,
        name=body.name,
        caption=body.caption,
        tags=body.tags,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _serialize(result)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, usecases=Depends(get_templates_usecases)):
    if not usecases.delete_template(template_id):
        raise HTTPException(status_code=404, detail="Template not found")


@router.post("/{template_id}/usage", status_code=204)
def increment_usage(template_id: str, usecases=Depends(get_templates_usecases)):
    usecases.increment_usage(template_id)
