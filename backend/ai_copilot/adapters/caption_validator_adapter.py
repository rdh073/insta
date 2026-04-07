"""CaptionValidatorAdapter — pure Python rules, no external dependencies."""

from __future__ import annotations

import re

from ai_copilot.application.content_pipeline.ports import CaptionValidatorPort

_MIN_LENGTH = 20
_MAX_LENGTH = 2200
_MAX_HASHTAGS = 30
_PROFANITY_PATTERNS = [
    r"\bf[*u]ck\b", r"\bsh[*i]t\b", r"\bass\b", r"\bbitch\b",
]


class CaptionValidatorAdapter(CaptionValidatorPort):
    """Rule-based caption validator.

    Rules checked:
    1. Minimum length (20 chars)
    2. Maximum length (2200 chars — Instagram limit)
    3. Hashtag count ≤ 30
    4. Basic profanity filter
    """

    async def validate(self, caption: str, campaign_brief: str) -> dict:
        errors: list[str] = []
        feedback_parts: list[str] = []

        if not caption or not caption.strip():
            return {"passed": False, "errors": ["Caption is empty"], "feedback": "Generate a non-empty caption."}

        stripped = caption.strip()

        # Length
        if len(stripped) < _MIN_LENGTH:
            errors.append(f"Caption too short ({len(stripped)} chars, min {_MIN_LENGTH})")
            feedback_parts.append(f"Expand the caption to at least {_MIN_LENGTH} characters.")

        if len(stripped) > _MAX_LENGTH:
            errors.append(f"Caption too long ({len(stripped)} chars, max {_MAX_LENGTH})")
            feedback_parts.append(f"Shorten the caption to under {_MAX_LENGTH} characters.")

        # Hashtag count
        hashtags = re.findall(r"#\w+", stripped)
        if len(hashtags) > _MAX_HASHTAGS:
            errors.append(f"Too many hashtags ({len(hashtags)}, max {_MAX_HASHTAGS})")
            feedback_parts.append(f"Reduce hashtags to at most {_MAX_HASHTAGS}.")

        # Profanity
        lower = stripped.lower()
        for pattern in _PROFANITY_PATTERNS:
            if re.search(pattern, lower):
                errors.append("Caption contains inappropriate language")
                feedback_parts.append("Remove any inappropriate or offensive language.")
                break

        passed = len(errors) == 0
        feedback = " ".join(feedback_parts) if feedback_parts else "Caption looks good."

        return {"passed": passed, "errors": errors, "feedback": feedback}
