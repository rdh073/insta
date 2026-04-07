"""Highlight vertical domain entrypoint and value objects."""

from __future__ import annotations

from dataclasses import dataclass

from .interaction_values_core import InvalidComposite, InvalidIdentifier, StoryPK
from .aggregates_core import HighlightAggregate


@dataclass(frozen=True)
class HighlightPK:
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value <= 0:
            raise InvalidIdentifier(
                f"highlight_pk must be a positive integer, got {self.value!r}"
            )

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class HighlightTitle:
    value: str

    def __post_init__(self):
        clean = self.value.strip() if self.value else ""
        if not clean:
            raise InvalidComposite("title must not be empty")
        object.__setattr__(self, "value", clean)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class StoryPKList:
    values: tuple[int, ...]

    def __init__(self, story_ids: list[int], *, label: str = "story_ids"):
        if not story_ids:
            raise InvalidComposite(f"{label} must not be empty")
        normalized: list[int] = []
        for sid in story_ids:
            normalized.append(int(StoryPK(sid)))
        object.__setattr__(self, "values", tuple(normalized))

    def __iter__(self):
        return iter(self.values)


@dataclass(frozen=True)
class CoverStoryID:
    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value < 0:
            raise InvalidIdentifier(
                f"cover_story_id must be a non-negative integer, got {self.value!r}"
            )

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class HighlightCropRect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_list(cls, crop_rect: list[float]) -> "HighlightCropRect":
        if len(crop_rect) != 4:
            raise InvalidComposite(
                f"crop_rect must have exactly 4 elements [x, y, width, height], got {len(crop_rect)}"
            )
        values: list[float] = []
        for val in crop_rect:
            if not isinstance(val, (int, float)) or not (0.0 <= float(val) <= 1.0):
                raise InvalidComposite(
                    f"crop_rect values must be floats in [0.0, 1.0], got {val!r}"
                )
            values.append(float(val))
        return cls(x=values[0], y=values[1], width=values[2], height=values[3])

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.width, self.height]


__all__ = [
    "HighlightAggregate",
    "HighlightPK",
    "HighlightTitle",
    "StoryPKList",
    "CoverStoryID",
    "HighlightCropRect",
    "InvalidComposite",
    "InvalidIdentifier",
]
