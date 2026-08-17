"""Immutable content-review batch submit and withdrawal service."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from ai_ppt_studio.application.content_review._shared import (
    DecisionLineageMismatchError,
    decision_lineage,
    fingerprint,
    payload,
    replay_ref,
    review_context,
    stable_id,
)
from ai_ppt_studio.domains.content.page_decisions import DECISIONS
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import ContentWorkflowError, GateBlockedError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentReviewBatchService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def submit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        source_version: str,
    ):
        values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
        }
        command_fingerprint = fingerprint("submit-content-review-batch", values)
        slot = "content/review-batch"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_content_review_batch(
                payload(self.kernel, reference, "content-review-batch")
            ), state
        context = review_context(
            self.kernel,
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        current_ref = context.state.artifact_heads.get(slot, "")
        if current_ref:
            current = validate_content_review_batch(
                payload(self.kernel, current_ref, "content-review-batch")
            )
            if current["status"] == "submitted":
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_FROZEN",
                    "The current review batch is already submitted",
                )
        decisions = self._ordered_decisions(context)
        if len(decisions) != len(context.blueprint["slides"]):
            raise GateBlockedError(
                "content-review-batch",
                (
                    "page-decisions-incomplete:"
                    f"{len(context.blueprint['slides']) - len(decisions)}",
                ),
            )
        now = datetime.now(timezone.utc).isoformat()
        counts = Counter(row[1]["decision"] for row in decisions)
        batch = validate_content_review_batch(
            {
                "batch_id": stable_id(
                    "content-review-batch", review_session_id, source_version, command_id
                ),
                "project_id": context.state.project_id,
                "review_session_id": review_session_id,
                "source_version": source_version,
                "reading_blueprint_ref": context.blueprint_ref,
                "slide_ids": [row[1]["slide_id"] for row in decisions],
                "decision_refs": [row[0] for row in decisions],
                "counts": {choice: counts.get(choice, 0) for choice in DECISIONS},
                "status": "submitted",
                "immutable_after_submit": True,
                "submitted_at": now,
                "withdrawn_at": "",
                "supersedes_ref": current_ref,
            }
        )
        session = validate_review_session(
            {**context.session, "status": "submitted", "submitted_at": now},
            trusted_receipts=True,
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.review-batch-submitted",
            artifact_updates={
                slot: ("content-review-batch", batch),
                "review/session/content-full-deck": ("review-session", session),
            },
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], batch, committed

    def withdraw(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        source_version: str,
    ):
        values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
        }
        command_fingerprint = fingerprint("withdraw-content-review-batch", values)
        slot = "content/review-batch"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_content_review_batch(
                payload(self.kernel, reference, "content-review-batch")
            ), state
        context = review_context(
            self.kernel,
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        current_ref = context.state.artifact_heads.get(slot, "")
        if not current_ref:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_STALE", "No current submitted batch"
            )
        current = validate_content_review_batch(
            payload(self.kernel, current_ref, "content-review-batch")
        )
        if current["status"] != "submitted":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_STALE", "The current batch is not submitted"
            )
        decisions = self._ordered_decisions(context)
        if (
            [reference for reference, _decision in decisions]
            != current["decision_refs"]
            or [decision["slide_id"] for _reference, decision in decisions]
            != current["slide_ids"]
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_STALE",
                "Submitted PageDecision identities are no longer current",
            )
        if context.state.artifact_heads.get("content/revision-plan"):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "A batch with a proposed revision plan cannot be withdrawn",
            )
        withdrawn = validate_content_review_batch(
            {
                **current,
                "batch_id": stable_id("withdrawn-review-batch", current_ref, command_id),
                "status": "withdrawn",
                "withdrawn_at": datetime.now(timezone.utc).isoformat(),
                "supersedes_ref": current_ref,
            }
        )
        session = validate_review_session(
            {**context.session, "status": "ready", "submitted_at": None},
            trusted_receipts=True,
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.review-batch-withdrawn",
            artifact_updates={
                slot: ("content-review-batch", withdrawn),
                "review/session/content-full-deck": ("review-session", session),
            },
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], withdrawn, committed

    def _ordered_decisions(self, context):
        by_slide = {}
        for slide in context.blueprint["slides"]:
            slot = f"content/review/decision/{slide['slide_id']}"
            reference = context.state.artifact_heads.get(slot, "")
            if not reference:
                continue
            try:
                decision = decision_lineage(
                    self.kernel,
                    reference,
                    {
                        "project_id": context.state.project_id,
                        "review_session_id": context.session["review_session_id"],
                        "source_version": context.blueprint["source_version"],
                        "reading_blueprint_ref": context.blueprint_ref,
                        "slide_id": slide["slide_id"],
                        "slide_order": slide["order"],
                        "slide_title_snapshot": slide["neutral_title"],
                    },
                )
            except DecisionLineageMismatchError as error:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_STALE", "A PageDecision is stale"
                ) from error
            if (
                decision["reading_blueprint_ref"] != context.blueprint_ref
                or decision["source_version"] != context.blueprint["source_version"]
                or decision["slide_id"] != slide["slide_id"]
                or decision["slide_order"] != slide["order"]
                or decision["slide_title_snapshot"] != slide["neutral_title"]
            ):
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_STALE", "A PageDecision is stale"
                )
            by_slide[slide["slide_id"]] = (reference, decision)
        return [by_slide[slide["slide_id"]] for slide in context.blueprint["slides"] if slide["slide_id"] in by_slide]


__all__ = ["ContentReviewBatchService"]
