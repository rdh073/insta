"""Smart engagement workflow graph - todo-4 topology.

11-node graph with strict routing rules and interrupt/resume for approval.

Topology:
  START
    → ingest_goal
    → load_account_context
      [account not healthy] → log_outcome → finish → END
    → discover_candidates
      [no candidates]       → log_outcome → finish → END
    → rank_candidates
    → draft_action
    → score_risk
      [risk too high]       → log_outcome → finish → END
    → gate_by_mode
      [recommendation]      → log_outcome → finish → END
    → request_approval  ←── interrupt here; resume with decision
      [rejected/timeout]    → log_outcome → finish → END
    → execute_action
    → log_outcome
    → finish
    → END

Routing rules (fail-fast):
  - account_not_healthy    → log_outcome
  - no_candidates          → log_outcome
  - risk_threshold_exceeded → log_outcome
  - mode=recommendation    → log_outcome
  - approval rejected      → log_outcome
  - only approved          → execute_action

Failure rules enforced in nodes:
  - max 1 discovery cycle per run (discovery_attempted)
  - max 1 approval per run (approval_attempted)
  - no infinite loops for finding "better" targets
  - retry only for technical adapter errors
  - approval timeout treated as rejection (inside request_approval_node)
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes
from ai_copilot.application.smart_engagement.state import SmartEngagementState


def build_smart_engagement_graph(nodes: SmartEngagementNodes, checkpointer=None, store=None):
    """Build the 11-node smart engagement workflow graph.

    Args:
        nodes: SmartEngagementNodes instance with 7 port dependencies
        checkpointer: LangGraph checkpointer (required for interrupt/resume).
                      If None, interrupt will not persist state between calls.
        store: LangGraph Store for cross-thread memory (optional).

    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(SmartEngagementState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("ingest_goal",           nodes.ingest_goal_node)
    graph.add_node("load_account_context",  nodes.load_account_context_node)
    graph.add_node("discover_candidates",   nodes.discover_candidates_node)
    graph.add_node("rank_candidates",       nodes.rank_candidates_node)
    graph.add_node("draft_action",          nodes.draft_action_node)
    graph.add_node("score_risk",            nodes.score_risk_node)
    graph.add_node("gate_by_mode",          nodes.gate_by_mode_node)
    graph.add_node("request_approval",      nodes.request_approval_node)
    graph.add_node("execute_action",        nodes.execute_action_node)
    graph.add_node("log_outcome",           nodes.log_outcome_node)
    graph.add_node("finish",               nodes.finish_node)

    # ── Entry ──────────────────────────────────────────────────────────────────
    graph.add_edge(START, "ingest_goal")
    graph.add_edge("ingest_goal", "load_account_context")

    # ── Fail-fast: account health ──────────────────────────────────────────────
    graph.add_conditional_edges(
        "load_account_context",
        nodes.route_after_account_context,
        {
            "discover_candidates": "discover_candidates",
            "log_outcome": "log_outcome",
        },
    )

    # ── Fail-fast: no candidates ───────────────────────────────────────────────
    graph.add_conditional_edges(
        "discover_candidates",
        nodes.route_after_discovery,
        {
            "rank_candidates": "rank_candidates",
            "log_outcome": "log_outcome",
        },
    )

    # ── Linear: rank → draft → score ──────────────────────────────────────────
    graph.add_edge("rank_candidates", "draft_action")
    graph.add_edge("draft_action", "score_risk")

    # ── Fail-fast: high risk ───────────────────────────────────────────────────
    graph.add_conditional_edges(
        "score_risk",
        nodes.route_after_risk,
        {
            "gate_by_mode": "gate_by_mode",
            "log_outcome": "log_outcome",
        },
    )

    # ── Mode gate ─────────────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "gate_by_mode",
        nodes.route_by_mode,
        {
            "request_approval": "request_approval",
            "log_outcome": "log_outcome",
        },
    )

    # ── Approval (interrupt) → execute or skip ─────────────────────────────────
    graph.add_conditional_edges(
        "request_approval",
        nodes.route_after_approval,
        {
            "execute_action": "execute_action",
            "log_outcome": "log_outcome",
        },
    )

    # ── Execute → outcome ──────────────────────────────────────────────────────
    graph.add_edge("execute_action", "log_outcome")

    # ── All paths → finish → END ───────────────────────────────────────────────
    graph.add_edge("log_outcome", "finish")
    graph.add_edge("finish", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if store is not None:
        compile_kwargs["store"] = store
    return graph.compile(**compile_kwargs)
