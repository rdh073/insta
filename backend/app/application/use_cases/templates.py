"""Caption template use cases — create, list, update, delete, track usage."""

from __future__ import annotations

import uuid
import datetime


class TemplatesUseCase:
    """CRUD and usage tracking for caption templates."""

    def __init__(self, repo) -> None:
        self.repo = repo

    def list_templates(self) -> list[dict]:
        return self.repo.list_all()

    def create_template(self, name: str, caption: str, tags: list[str]) -> dict:
        template = {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "caption": caption.strip(),
            "tags": [t.strip() for t in tags if t.strip()],
            "usage_count": 0,
            "created_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        }
        self.repo.save(template)
        return template

    def update_template(
        self,
        template_id: str,
        *,
        name: str | None = None,
        caption: str | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        template = self.repo.get(template_id)
        if template is None:
            return None
        updates: dict = {}
        if name is not None:
            updates["name"] = name.strip()
        if caption is not None:
            updates["caption"] = caption.strip()
        if tags is not None:
            updates["tags"] = [t.strip() for t in tags if t.strip()]
        if updates:
            self.repo.update(template_id, **updates)
        return self.repo.get(template_id)

    def delete_template(self, template_id: str) -> bool:
        return self.repo.delete(template_id)

    def increment_usage(self, template_id: str) -> None:
        template = self.repo.get(template_id)
        if template is not None:
            self.repo.update(template_id, usage_count=template.get("usage_count", 0) + 1)
