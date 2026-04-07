"""Content Pipeline workflow graph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ai_copilot.application.content_pipeline.nodes import ContentPipelineNodes
from ai_copilot.application.content_pipeline.state import ContentPipelineState


def build_content_pipeline_graph(nodes: ContentPipelineNodes, checkpointer=None):
    graph = StateGraph(ContentPipelineState)

    graph.add_node("ingest_campaign_brief",   nodes.ingest_campaign_brief_node)
    graph.add_node("generate_caption",        nodes.generate_caption_node)
    graph.add_node("validate_caption",        nodes.validate_caption_node)
    graph.add_node("select_target_accounts",  nodes.select_target_accounts_node)
    graph.add_node("operator_approval",       nodes.operator_approval_node)
    graph.add_node("schedule_draft",          nodes.schedule_draft_node)
    graph.add_node("finish",                  nodes.finish_node)

    graph.add_edge(START, "ingest_campaign_brief")

    graph.add_conditional_edges(
        "ingest_campaign_brief",
        nodes.route_after_ingest,
        {"generate_caption": "generate_caption", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "generate_caption",
        nodes.route_after_generate,
        {"validate_caption": "validate_caption", "finish": "finish"},
    )

    # Back-edge for revision loop
    graph.add_conditional_edges(
        "validate_caption",
        nodes.route_after_validate,
        {
            "select_target_accounts": "select_target_accounts",
            "generate_caption": "generate_caption",  # loop back
            "finish": "finish",
        },
    )

    graph.add_conditional_edges(
        "select_target_accounts",
        nodes.route_after_select,
        {"operator_approval": "operator_approval", "finish": "finish"},
    )

    graph.add_conditional_edges(
        "operator_approval",
        nodes.route_after_approval,
        {"schedule_draft": "schedule_draft", "finish": "finish"},
    )

    graph.add_edge("schedule_draft", "finish")
    graph.add_edge("finish", END)

    return graph.compile(checkpointer=checkpointer)
