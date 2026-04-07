"""Account Recovery workflow graph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.account_recovery.nodes import AccountRecoveryNodes
from ai_copilot.application.account_recovery.state import AccountRecoveryState


def build_account_recovery_graph(nodes: AccountRecoveryNodes, checkpointer=None):
    graph = StateGraph(AccountRecoveryState)

    graph.add_node("detect_issue",           nodes.detect_issue_node)
    graph.add_node("classify_issue",         nodes.classify_issue_node)
    graph.add_node("choose_recovery_path",   nodes.choose_recovery_path_node)
    graph.add_node("attempt_recovery",       nodes.attempt_recovery_node)
    graph.add_node("verify_account_health",  nodes.verify_account_health_node)
    graph.add_node("finish_unrecoverable",   nodes.finish_unrecoverable_node)
    graph.add_node("finish",                 nodes.finish_node)

    graph.add_edge(START, "detect_issue")

    graph.add_conditional_edges(
        "detect_issue",
        nodes.route_after_detect,
        {
            "classify_issue": "classify_issue",
            "verify_account_health": "verify_account_health",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "classify_issue",
        nodes.route_after_classify,
        {
            "choose_recovery_path": "choose_recovery_path",
            "verify_account_health": "verify_account_health",
            "finish_unrecoverable": "finish_unrecoverable",
        },
    )

    graph.add_conditional_edges(
        "choose_recovery_path",
        nodes.route_after_choose,
        {
            "attempt_recovery": "attempt_recovery",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "attempt_recovery",
        nodes.route_after_attempt,
        {
            "attempt_recovery": "attempt_recovery",
            "verify_account_health": "verify_account_health",
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "verify_account_health",
        nodes.route_after_health,
        {
            "choose_recovery_path": "choose_recovery_path",
            "finish": "finish",
        },
    )

    graph.add_edge("finish_unrecoverable", "finish")
    graph.add_edge("finish", END)

    return graph.compile(checkpointer=checkpointer)
