"""Compatibility module for legacy aggregate imports.

Canonical implementation now lives in `aggregates_core.py`.
Keep this file as re-export layer to avoid breaking older imports.
"""

from __future__ import annotations

from .aggregates_core import *  # noqa: F401,F403

