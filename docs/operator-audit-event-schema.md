# Operator Copilot Audit Event Schema

Canonical event taxonomy and payload contract for `AuditLogPort.log(event_type, data)`.

`event_type` must be one of the keys below.
Each event lists `required` payload keys and `optional` payload keys.

```json
{
  "operator_request": {
    "required": [
      "operator_request",
      "step",
      "thread_id"
    ],
    "optional": []
  },
  "planner_decision": {
    "required": [
      "stage",
      "thread_id"
    ],
    "optional": [
      "block_reason",
      "blocked",
      "context_available",
      "conversational",
      "copilot_memory_namespace",
      "dropped_tool_calls",
      "error",
      "execution_plan",
      "mentions",
      "normalized_goal",
      "proposed_tool_calls",
      "runtime_context_keys"
    ]
  },
  "policy_gate": {
    "required": [
      "blocked_names",
      "executable_count",
      "flags",
      "proposed_count",
      "risk_assessment",
      "thread_id"
    ],
    "optional": []
  },
  "approval_submitted": {
    "required": [
      "approval_request",
      "thread_id"
    ],
    "optional": []
  },
  "approval_result": {
    "required": [
      "approval_result",
      "thread_id"
    ],
    "optional": [
      "dropped_tool_calls",
      "edited_call_count",
      "reason",
      "sanitized_call_count"
    ]
  },
  "tool_execution": {
    "required": [
      "args",
      "call_id",
      "result_keys",
      "thread_id",
      "tool_name"
    ],
    "optional": [
      "error",
      "status"
    ]
  },
  "execution_failure": {
    "required": [
      "call_id",
      "error",
      "thread_id",
      "tool_name"
    ],
    "optional": [
      "failure_kind",
      "status"
    ]
  },
  "review_finding": {
    "required": [
      "matched_intent",
      "recommendation",
      "thread_id",
      "warnings"
    ],
    "optional": [
      "parse_error"
    ]
  },
  "stop_reason": {
    "required": [
      "stop_reason",
      "thread_id"
    ],
    "optional": [
      "reason"
    ]
  },
  "node_error": {
    "required": [
      "error_class",
      "error_message",
      "node_name",
      "thread_id"
    ],
    "optional": []
  }
}
```
