"""StateGraph builder for operator copilot topology."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.state import OperatorCopilotState


def build_operator_copilot_graph(
    nodes,
    checkpointer=None,
    store=None,
):
    """Build and compile the full operator copilot graph (9 nodes)."""
    graph = StateGraph(OperatorCopilotState)

    graph.add_node("ingest_request", nodes.ingest_request_node)
    graph.add_node("classify_goal", nodes.classify_goal_node)
    graph.add_node("plan_actions", nodes.plan_actions_node)
    graph.add_node("review_tool_policy", nodes.review_tool_policy_node)
    graph.add_node("request_approval_if_needed", nodes.request_approval_if_needed_node)
    graph.add_node("execute_tools", nodes.execute_tools_node)
    graph.add_node("review_results", nodes.review_results_node)
    graph.add_node("summarize_result", nodes.summarize_result_node)
    graph.add_node("finish", nodes.finish_node)

    graph.add_edge(START, "ingest_request")
    graph.add_edge("ingest_request", "classify_goal")

    graph.add_conditional_edges(
        "classify_goal",
        nodes.route_after_classify,
        {
            "plan_actions": "plan_actions",
            "summarize_result": "summarize_result",
        },
    )

    graph.add_conditional_edges(
        "plan_actions",
        nodes.route_after_plan,
        {
            "review_tool_policy": "review_tool_policy",
            "summarize_result": "summarize_result",
        },
    )

    graph.add_conditional_edges(
        "review_tool_policy",
        nodes.route_after_policy,
        {
            "execute_tools": "execute_tools",
            "request_approval_if_needed": "request_approval_if_needed",
            "summarize_result": "summarize_result",
        },
    )

    graph.add_conditional_edges(
        "request_approval_if_needed",
        nodes.route_after_approval,
        {
            "execute_tools": "execute_tools",
            "review_tool_policy": "review_tool_policy",
            "summarize_result": "summarize_result",
        },
    )

    graph.add_edge("execute_tools", "review_results")
    graph.add_edge("review_results", "summarize_result")
    graph.add_edge("summarize_result", "finish")
    graph.add_edge("finish", END)

    compile_kwargs: dict = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if store is not None:
        compile_kwargs["store"] = store

    return graph.compile(**compile_kwargs)
