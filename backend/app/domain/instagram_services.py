"""Compatibility module for legacy domain service imports.

Canonical implementation now lives in `services_core.py`.
Keep this file as re-export layer to avoid breaking older imports.
"""

from __future__ import annotations

from .services_core import *  # noqa: F401,F403

