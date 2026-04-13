# AI Copilot Stream Event Contract

This document defines the SSE payload contract used by AI copilot streaming endpoints.

## `node_update` (canonical)

All graph workflows now emit the same shape:

```json
{
  "type": "node_update",
  "node": "graph_node_name",
  "data": {}
}
```

Field semantics:
- `type`: always `"node_update"`
- `node`: LangGraph node name that produced the update
- `data`: JSON-safe node payload (`dict`, `list`, primitives)

Affected workflows:
- operator copilot
- smart engagement
- campaign monitor
- risk control
- account recovery
- content pipeline

## `final_response` structured artifacts

`final_response.text` remains the human-readable summary. Command workflows can also include structured fields for timeline rendering.

### `/monitor` (campaign monitor)
- `recommended_action`
- `campaign_summary`
- `followup_job_id`
- `stop_reason`

### `/risk` (risk control)
- `final_policy`
- `recheck_risk_level`
- `stop_reason`

### `/recover` (account recovery)
- `recovery_successful`
- `result`
- `stop_reason`

### `/pipeline` (content pipeline)
- `job_id`
- `caption`
- `stop_reason`

### `/engage` (smart engagement)
- `result` (recommendation/risk/approval/execution metadata)
- `stop_reason`

