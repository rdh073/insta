"""Campaign Monitor workflow graph.

Topology:
  START
    → load_recent_jobs
      [no jobs / error]           → finish → END
    → group_by_campaign
      [no groups]                 → finish → END
    → evaluate_outcome
    → suggest_next_action
      [request_decision==False]   → finish → END
    → request_operator_decision   ← INTERRUPT (if request_decision==True)
      [skip / no decision]        → finish → END
      [approve / modify]          → create_followup_task → finish → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.campaign_monitor.nodes import CampaignMonitorNodes
from ai_copilot.application.campaign_monitor.state import CampaignMonitorState


def build_campaign_monitor_graph(nodes: CampaignMonitorNodes, checkpointer=None):
    """Build the Campaign Monitor StateGraph.

    Args:
        nodes: CampaignMonitorNodes with wired port dependencies.
        checkpointer: LangGraph checkpointer (required for interrupt/resume).

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(CampaignMonitorState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    graph.add_node("load_recent_jobs",           nodes.load_recent_jobs_node)
    graph.add_node("group_by_campaign",          nodes.group_by_campaign_node)
    graph.add_node("evaluate_outcome",           nodes.evaluate_outcome_node)
    graph.add_node("suggest_next_action",        nodes.suggest_next_action_node)
    graph.add_node("request_operator_decision",  nodes.request_operator_decision_node)
    graph.add_node("create_followup_task",       nodes.create_followup_task_node)
    graph.add_node("finish",                     nodes.finish_node)

    # ── Entry ──────────────────────────────────────────────────────────────────
    graph.add_edge(START, "load_recent_jobs")

    # ── Fail-fast: no jobs ─────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "load_recent_jobs",
        nodes.route_after_load,
        {
            "group_by_campaign": "group_by_campaign",
            "finish": "finish",
        },
    )

    # ── Fail-fast: no campaign groups ──────────────────────────────────────────
    graph.add_conditional_edges(
        "group_by_campaign",
        nodes.route_after_grouping,
        {
            "evaluate_outcome": "evaluate_outcome",
            "finish": "finish",
        },
    )

    # ── Linear: evaluate → suggest ─────────────────────────────────────────────
    graph.add_edge("evaluate_outcome", "suggest_next_action")

    # ── Decision gate: interrupt or recommend-only ─────────────────────────────
    graph.add_conditional_edges(
        "suggest_next_action",
        nodes.route_for_decision_gate,
        {
            "request_operator_decision": "request_operator_decision",
            "finish": "finish",
        },
    )

    # ── After interrupt: skip → finish, approve → followup ────────────────────
    graph.add_conditional_edges(
        "request_operator_decision",
        nodes.route_after_decision,
        {
            "create_followup_task": "create_followup_task",
            "finish": "finish",
        },
    )

    # ── Followup → finish ──────────────────────────────────────────────────────
    graph.add_edge("create_followup_task", "finish")

    # ── Terminal ───────────────────────────────────────────────────────────────
    graph.add_edge("finish", END)

    return graph.compile(checkpointer=checkpointer)
