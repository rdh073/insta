"""Risk Control workflow graph.

Topology:
  START
    → load_account_signal
      [not found / error]       → finish → END
    → evaluate_risk
      [low]                     → recheck_signal → finish → END
    → choose_policy
      [continue]                → recheck_signal → finish → END
      [cooldown]                → cooldown_action → recheck_signal → finish → END
      [rotate_proxy]            → rotate_proxy_action → recheck_signal → finish → END
      [escalate]                → escalate_to_operator  ← INTERRUPT
          [abort]               → finish → END
          [approve/override]    → apply_operator_override → recheck_signal → finish → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.risk_control.nodes import RiskControlNodes
from ai_copilot.application.risk_control.state import RiskControlState


def build_risk_control_graph(nodes: RiskControlNodes, checkpointer=None):
    graph = StateGraph(RiskControlState)

    graph.add_node("load_account_signal",    nodes.load_account_signal_node)
    graph.add_node("evaluate_risk",          nodes.evaluate_risk_node)
    graph.add_node("choose_policy",          nodes.choose_policy_node)
    graph.add_node("cooldown_action",        nodes.cooldown_action_node)
    graph.add_node("rotate_proxy_action",    nodes.rotate_proxy_action_node)
    graph.add_node("escalate_to_operator",   nodes.escalate_to_operator_node)
    graph.add_node("apply_operator_override", nodes.apply_operator_override_node)
    graph.add_node("recheck_signal",         nodes.recheck_signal_node)
    graph.add_node("finish",                 nodes.finish_node)

    graph.add_edge(START, "load_account_signal")

    graph.add_conditional_edges(
        "load_account_signal",
        nodes.route_after_load,
        {"evaluate_risk": "evaluate_risk", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "evaluate_risk",
        nodes.route_after_risk,
        {"recheck_signal": "recheck_signal", "choose_policy": "choose_policy"},
    )

    graph.add_conditional_edges(
        "choose_policy",
        nodes.route_after_policy,
        {
            "cooldown_action": "cooldown_action",
            "rotate_proxy_action": "rotate_proxy_action",
            "recheck_signal": "recheck_signal",
            "escalate_to_operator": "escalate_to_operator",
        },
    )

    graph.add_edge("cooldown_action", "recheck_signal")
    graph.add_edge("rotate_proxy_action", "recheck_signal")

    graph.add_conditional_edges(
        "escalate_to_operator",
        nodes.route_after_escalation,
        {"apply_operator_override": "apply_operator_override", "finish": "finish"},
    )

    graph.add_edge("apply_operator_override", "recheck_signal")
    graph.add_edge("recheck_signal", "finish")
    graph.add_edge("finish", END)

    return graph.compile(checkpointer=checkpointer)
