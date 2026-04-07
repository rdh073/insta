"""Smart engagement workflow module - LangGraph-based recommendation and approval pipeline."""

from .ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)
from .state import (
    AccountHealth,
    ApprovalRequest,
    ApprovalResult,
    AuditEvent,
    DraftPayload,
    EngagementTarget,
    ExecutionResult,
    ProposedAction,
    RiskAssessment,
    SmartEngagementState,
)

__all__ = [
    # State types
    "SmartEngagementState",
    "EngagementTarget",
    "AccountHealth",
    "ProposedAction",
    "RiskAssessment",
    "DraftPayload",
    "ApprovalRequest",
    "ApprovalResult",
    "ExecutionResult",
    "AuditEvent",
    # Ports
    "AccountContextPort",
    "EngagementCandidatePort",
    "RiskScoringPort",
    "ApprovalPort",
    "EngagementExecutorPort",
    "AuditLogPort",
]
