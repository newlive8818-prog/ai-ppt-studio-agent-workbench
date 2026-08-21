"""Atomic PageDecision writer with no content or Gate side effects."""

from __future__ import annotations

from datetime import datetime, timezone
from ai_ppt_studio.application.content_review._shared import (
    decision_lineage,
    fingerprint,
    payload,
    replay_ref,
    review_context,
    stable_id,
)
from ai_ppt_studio.domains.content.page_decisions import (
    normalize_decision,
    validate_page_decision,
)
from ai_ppt_studio.errors import ContentWorkflowError, ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentDecisionService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def save(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        source_version: str,
        slide_id: str,
        decision: str,
        comment: str,
    ):
        choice, note = normalize_decision(decision, comment)
        values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
            "slide_id": slide_id,
            "decision": choice,
            "comment": note,
        }
        command_fingerprint = fingerprint("save-content-page-decision", values)
        slot = f"content/review/decision/{slide_id}"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_page_decision(
                payload(self.kernel, reference, "content-page-decision")
            ), state
        context = review_context(
            self.kernel,
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        if not isinstance(slide_id, str) or not slide_id:
            raise ContractValidationError("slide_id must be a non-empty string")
        current_batch = context.state.artifact_heads.get("content/review-batch", "")
        if current_batch:
            batch = payload(self.kernel, current_batch, "content-review-batch")
            if batch.get("status") == "submitted" and batch.get("source_version") == source_version:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_FROZEN",
                    "Submitted review decisions are immutable",
                )
        slide = next(
            (row for row in context.blueprint["slides"] if row["slide_id"] == slide_id),
            None,
        )
        if slide is None:
            raise ContractValidationError("slide_id is not in the current blueprint")
        previous = context.state.artifact_heads.get(slot, "")
        if previous:
            expected_prior = {
                "project_id": context.state.project_id,
                "review_session_id": review_session_id,
                "source_version": source_version,
                "reading_blueprint_ref": context.blueprint_ref,
                "slide_id": slide_id,
                "slide_order": slide["order"],
                "slide_title_snapshot": slide["neutral_title"],
            }
            decision_lineage(self.kernel, previous, expected_prior)
        decision_payload = validate_page_decision(
            {
                "page_decision_id": stable_id(
                    "page-decision", review_session_id, slide_id, command_id
                ),
                "project_id": context.state.project_id,
                "review_session_id": review_session_id,
                "source_version": source_version,
                "reading_blueprint_ref": context.blueprint_ref,
                "slide_id": slide_id,
                "slide_order": slide["order"],
                "slide_title_snapshot": slide["neutral_title"],
                "decision": choice,
                "comment": note,
                "status": "completed",
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "supersedes_decision_ref": previous,
            }
        )
        before_gates = dict(context.state.gate_status)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.page-decision-saved",
            artifact_updates={slot: ("content-page-decision", decision_payload)},
            command_fingerprint=command_fingerprint,
        )
        if committed.gate_status != before_gates:
            raise RuntimeError("PageDecision unexpectedly changed Gate state")
        reference = committed.artifact_heads[slot]
        return reference, decision_payload, committed


__all__ = ["ContentDecisionService"]
