"""Compatibility module for legacy imports.

Canonical implementation now lives in `interaction_values_core.py`.
Keep this file as re-export layer to avoid breaking older imports.
"""

from __future__ import annotations

from .interaction_values_core import *  # noqa: F401,F403

