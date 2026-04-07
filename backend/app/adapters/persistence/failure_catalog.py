"""Catalog for persistence adapter failure messages.

Defines app-owned, stable failure codes/messages for adapter-level
translation so vendor errors are not leaked to upper layers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersistenceFailureSpec:
    code: str
    message_template: str


SPEC_PERSISTENCE_INFRA_ERROR = PersistenceFailureSpec(
    code="persistence_infrastructure_error",
    message_template="Persistence operation failed ({operation}).",
)


def build_persistence_failure_message(operation: str) -> str:
    op = operation.strip() or "unknown"
    return SPEC_PERSISTENCE_INFRA_ERROR.message_template.format(operation=op)

