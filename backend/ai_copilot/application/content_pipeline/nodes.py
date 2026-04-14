"""Node functions for Content Pipeline workflow.

OWNERSHIP: Business logic via ports. No direct LLM or SDK calls.

Topology:
  ingest_campaign_brief
  → generate_caption          (CaptionGeneratorPort; increments revision_count)
  → validate_caption          (CaptionValidatorPort)
      [passed]                → select_target_accounts
      [failed + count < max]  → generate_caption  (LOOP — back-edge)
      [failed + count >= max] → finish(validation_failed)
  → select_target_accounts
      [no accounts]           → finish(no_targets)
  → operator_approval         ← INTERRUPT
      [rejected]              → finish(rejected)
      [approved]              → schedule_draft
      [edited]                → schedule_draft (with operator caption)
  → schedule_draft            (PostSchedulerPort)
  → finish

Loop guard: revision_count < max_revisions
"""

from __future__ import annotations

import time

from langgraph.types import interrupt

from ai_copilot.application.content_pipeline.ports import (
    ALLOWED_SCHEDULE_RESULT_STATUSES,
    CaptionGeneratorPort,
    CaptionValidatorPort,
    PostSchedulerPort,
)
from ai_copilot.application.content_pipeline.state import ContentPipelineState


class ContentPipelineNodes:
    def __init__(
        self,
        caption_generator: CaptionGeneratorPort,
        caption_validator: CaptionValidatorPort,
        post_scheduler: PostSchedulerPort,
        account_usecases=None,
    ):
        self.caption_generator = caption_generator
        self.caption_validator = caption_validator
        self.post_scheduler = post_scheduler
        self._account = account_usecases

    def _event(self, event_type: str, node_name: str, data: dict) -> dict:
        return {"event_type": event_type, "node_name": node_name, "event_data": data, "timestamp": time.time()}

    @staticmethod
    def _normalize_status(value: object) -> str:
        return str(value or "").strip().lower()

    def _validate_schedule_result(self, result: dict) -> tuple[str, str] | None:
        job_id = str(result.get("job_id", "") or "").strip()
        status = self._normalize_status(result.get("status"))
        if not job_id or status not in ALLOWED_SCHEDULE_RESULT_STATUSES:
            return None
        return job_id, status

    # =========================================================================
    # Node 1: ingest_campaign_brief
    # =========================================================================

    async def ingest_campaign_brief_node(self, state: ContentPipelineState) -> dict:
        """Validate the brief is non-empty, initialise state."""
        brief = state.get("campaign_brief", "").strip()
        if not brief:
            return {
                "outcome_reason": "Campaign brief is empty",
                "stop_reason": "invalid_input",
                "step_count": 1,
                "audit_trail": [self._event("invalid_brief", "ingest_campaign_brief", {})],
            }
        return {
            "step_count": 1,
            "audit_trail": [self._event("brief_ingested", "ingest_campaign_brief", {
                "brief_length": len(brief),
                "media_refs": len(state.get("media_refs", [])),
            })],
        }

    def route_after_ingest(self, state: ContentPipelineState) -> str:
        if state.get("stop_reason"):
            return "finish"
        return "generate_caption"

    # =========================================================================
    # Node 2: generate_caption
    # =========================================================================

    async def generate_caption_node(self, state: ContentPipelineState) -> dict:
        revision = state.get("revision_count", 0)
        max_rev = state.get("max_revisions", 3)

        # Loop guard
        if revision >= max_rev:
            return {
                "outcome_reason": f"Max revisions reached ({revision}/{max_rev}) without passing validation",
                "stop_reason": "validation_failed",
                "audit_trail": [self._event("max_revisions", "generate_caption", {
                    "revision_count": revision, "max": max_rev,
                })],
            }

        try:
            caption = await self.caption_generator.generate(
                campaign_brief=state["campaign_brief"],
                media_refs=state.get("media_refs", []),
                previous_feedback=state.get("caption_feedback"),
                attempt=revision + 1,
            )
        except Exception as exc:
            return {
                "outcome_reason": f"Caption generation failed: {str(exc)[:80]}",
                "stop_reason": "error",
                "audit_trail": [self._event("generation_failed", "generate_caption", {"error": str(exc)[:80]})],
            }

        return {
            "caption": caption,
            "revision_count": revision + 1,
            "validation_passed": False,
            "validation_errors": [],
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("caption_generated", "generate_caption", {
                "attempt": revision + 1,
                "caption_length": len(caption),
            })],
        }

    def route_after_generate(self, state: ContentPipelineState) -> str:
        if state.get("stop_reason"):
            return "finish"
        return "validate_caption"

    # =========================================================================
    # Node 3: validate_caption
    # =========================================================================

    async def validate_caption_node(self, state: ContentPipelineState) -> dict:
        caption = state.get("caption", "")
        brief = state.get("campaign_brief", "")

        try:
            result = await self.caption_validator.validate(caption, brief)
        except Exception as exc:
            result = {"passed": False, "errors": [str(exc)[:80]], "feedback": "Validation error"}

        passed = result.get("passed", False)
        errors = result.get("errors", [])
        feedback = result.get("feedback", "")

        revision = state.get("revision_count", 0)
        max_rev = state.get("max_revisions", 3)

        updates: dict = {
            "validation_passed": passed,
            "validation_errors": errors,
            "caption_feedback": feedback if not passed else None,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("caption_validated", "validate_caption", {
                "passed": passed,
                "error_count": len(errors),
                "feedback": feedback,
            })],
        }

        # Set stop_reason here so finish_node has it
        if not passed and revision >= max_rev:
            updates["stop_reason"] = "validation_failed"
            updates["outcome_reason"] = f"Caption failed validation after {revision} revision(s)"

        return updates

    def route_after_validate(self, state: ContentPipelineState) -> str:
        if state.get("stop_reason"):
            return "finish"
        if state.get("validation_passed"):
            return "select_target_accounts"
        revision = state.get("revision_count", 0)
        max_rev = state.get("max_revisions", 3)
        if revision < max_rev:
            return "generate_caption"
        return "finish"

    # =========================================================================
    # Node 4: select_target_accounts
    # =========================================================================

    async def select_target_accounts_node(self, state: ContentPipelineState) -> dict:
        """Resolve target_usernames to account IDs. Fail-fast if none valid."""
        usernames = state.get("target_usernames", [])
        resolved = []

        if self._account and usernames:
            import asyncio
            for username in usernames:
                try:
                    info = await asyncio.to_thread(self._account.get_account_by_username, username)
                    if info and info.get("id"):
                        resolved.append(info["id"])
                except Exception:
                    pass

        if not resolved and usernames:
            # Fall back to treating usernames as IDs directly (dev/test mode)
            resolved = list(usernames)

        if not resolved:
            return {
                "resolved_account_ids": [],
                "outcome_reason": "No valid target accounts found",
                "stop_reason": "no_targets",
                "audit_trail": [self._event("no_targets", "select_target_accounts", {
                    "usernames": usernames,
                })],
            }

        return {
            "resolved_account_ids": resolved,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("accounts_selected", "select_target_accounts", {
                "count": len(resolved),
            })],
        }

    def route_after_select(self, state: ContentPipelineState) -> str:
        if state.get("stop_reason"):
            return "finish"
        return "operator_approval"

    # =========================================================================
    # Node 5: operator_approval  (INTERRUPT)
    # =========================================================================

    async def operator_approval_node(self, state: ContentPipelineState) -> dict:
        """Interrupt and ask operator to approve/reject/edit the generated caption."""
        interrupt_payload = {
            "type": "content_pipeline_approval",
            "thread_id": state.get("thread_id"),
            "campaign_brief": state.get("campaign_brief"),
            "caption": state.get("caption"),
            "media_refs": state.get("media_refs", []),
            "target_usernames": state.get("target_usernames", []),
            "scheduled_at": state.get("scheduled_at"),
            "revision_count": state.get("revision_count", 0),
            "validation_errors": state.get("validation_errors", []),
            "options": ["approved", "rejected", "edited"],
            "requested_at": time.time(),
        }

        operator_response = interrupt(interrupt_payload)
        if not operator_response:
            operator_response = {"decision": "rejected", "reason": "No response"}

        decision = operator_response.get("decision", "rejected")
        edited_caption = operator_response.get("edited_caption")

        audit = self._event("approval_received", "operator_approval", {"decision": decision})

        if decision == "rejected":
            return {
                "approval_status": "rejected",
                "outcome_reason": f"Operator rejected: {operator_response.get('reason', '')}",
                "stop_reason": "rejected",
                "audit_trail": [audit],
            }

        if decision == "edited" and edited_caption:
            return {
                "approval_status": "edited",
                "caption": edited_caption,
                "operator_edit": edited_caption,
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [audit],
            }

        return {
            "approval_status": "approved",
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [audit],
        }

    def route_after_approval(self, state: ContentPipelineState) -> str:
        if state.get("stop_reason") == "rejected":
            return "finish"
        return "schedule_draft"

    # =========================================================================
    # Node 6: schedule_draft
    # =========================================================================

    async def schedule_draft_node(self, state: ContentPipelineState) -> dict:
        caption = state.get("operator_edit") or state.get("caption", "")
        usernames = state.get("target_usernames", [])
        media_refs = state.get("media_refs", [])
        scheduled_at = state.get("scheduled_at")

        try:
            result = await self.post_scheduler.schedule(
                usernames=usernames,
                caption=caption,
                media_refs=media_refs,
                scheduled_at=scheduled_at,
            )
            if not isinstance(result, dict):
                reason = f"Scheduling failed: invalid scheduler result type={type(result).__name__}"
                return {
                    "outcome_reason": reason,
                    "stop_reason": "error",
                    "audit_trail": [self._event("schedule_invalid_result", "schedule_draft", {
                        "reason": reason,
                    })],
                }

            validated = self._validate_schedule_result(result)
            if not validated:
                job_id = str(result.get("job_id", "") or "").strip()
                status = self._normalize_status(result.get("status"))
                problems = []
                if not job_id:
                    problems.append("missing job_id")
                if status not in ALLOWED_SCHEDULE_RESULT_STATUSES:
                    if status:
                        problems.append(f"unsupported status '{status}'")
                    else:
                        problems.append("missing status")

                reason = f"Scheduling failed: invalid scheduler result ({', '.join(problems)})"
                return {
                    "schedule_result": result,
                    "outcome_reason": reason,
                    "stop_reason": "error",
                    "audit_trail": [self._event("schedule_invalid_result", "schedule_draft", {
                        "job_id_present": bool(job_id),
                        "status": status or None,
                        "allowed_statuses": sorted(ALLOWED_SCHEDULE_RESULT_STATUSES),
                    })],
                }

            job_id, status = validated
            return {
                "job_id": job_id,
                "schedule_result": result,
                "outcome_reason": f"Post scheduled: job_id={job_id}",
                "stop_reason": "scheduled",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("draft_scheduled", "schedule_draft", {
                    "job_id": job_id,
                    "status": status,
                    "username_count": len(usernames),
                })],
            }
        except Exception as exc:
            return {
                "outcome_reason": f"Scheduling failed: {str(exc)[:80]}",
                "stop_reason": "error",
                "audit_trail": [self._event("schedule_failed", "schedule_draft", {"error": str(exc)[:80]})],
            }

    # =========================================================================
    # Node 7: finish
    # =========================================================================

    async def finish_node(self, state: ContentPipelineState) -> dict:
        stop_reason = state.get("stop_reason") or "completed"
        outcome_reason = state.get("outcome_reason")

        if not outcome_reason:
            if stop_reason == "scheduled":
                outcome_reason = f"Content pipeline complete — job_id={state.get('job_id')}"
            elif stop_reason == "rejected":
                outcome_reason = "Caption rejected by operator"
            elif stop_reason == "validation_failed":
                outcome_reason = "Caption failed validation after max revisions"
            elif stop_reason == "no_targets":
                outcome_reason = "No target accounts configured"
            elif stop_reason == "invalid_input":
                outcome_reason = "Invalid input: campaign brief is empty"
            else:
                outcome_reason = f"Content pipeline ended: {stop_reason}"

        return {"stop_reason": stop_reason, "outcome_reason": outcome_reason}
