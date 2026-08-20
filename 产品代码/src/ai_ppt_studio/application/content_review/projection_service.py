"""Read-only full-deck projection from current accepted v2.2 content."""

from __future__ import annotations

import copy
from typing import Any

from ai_ppt_studio.application.content_review._shared import (
    decision_lineage,
    payload,
    review_context,
)
from ai_ppt_studio.domains.content.page_decisions import validate_page_decision
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentReviewProjectionService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self, review_session_id: str) -> dict[str, Any]:
        context = review_context(self.kernel, review_session_id)
        slides = []
        for source_slide in context.blueprint["slides"]:
            projected_slide = copy.deepcopy(source_slide)
            customer_decision_item = projected_slide.pop("customer_decision_item")
            projected_slide["customerJudgment"] = customer_decision_item["text"]
            slides.append(projected_slide)
        decisions = self._decisions(context.blueprint_ref)
        completed = len(decisions)
        total = len(slides)
        batch = self._optional("content/review-batch", "content-review-batch")
        plan = self._optional(
            "content/revision-plan", "content-batch-revision-plan"
        )
        return {
            "project_id": context.state.project_id,
            "review_type": "content-full-deck",
            "review_session_id": context.session["review_session_id"],
            "review_session": copy.deepcopy(context.session),
            "source_version": context.blueprint["source_version"],
            "revision": context.session["revision"],
            "authoritative_revision": context.state.revision,
            "reading_blueprint_ref": context.blueprint_ref,
            "material_mode": context.blueprint["material_mode"],
            "section_flow": copy.deepcopy(context.blueprint["section_flow"]),
            "slides": slides,
            "decisions": decisions,
            "progress": {
                "completed": completed,
                "total": total,
                "remaining": total - completed,
                "unsaved": 0,
            },
            "batch": batch,
            "revision_plan": plan,
            "content_acceptance_ref": context.acceptance_ref,
        }

    def _decisions(self, blueprint_ref: str) -> list[dict[str, Any]]:
        rows = []
        for slot, reference in self.kernel.load().artifact_heads.items():
            if not slot.startswith("content/review/decision/"):
                continue
            current = validate_page_decision(
                payload(self.kernel, reference, "content-page-decision")
            )
            if current["reading_blueprint_ref"] != blueprint_ref:
                continue
            decision = decision_lineage(
                self.kernel,
                reference,
                {"reading_blueprint_ref": blueprint_ref},
            )
            if decision["reading_blueprint_ref"] == blueprint_ref:
                rows.append(decision)
        return sorted(rows, key=lambda row: row["slide_order"])

    def _optional(self, slot: str, kind: str) -> dict[str, Any] | None:
        reference = self.kernel.load().artifact_heads.get(slot, "")
        if not reference:
            return None
        value = payload(self.kernel, reference, kind)
        if kind == "content-review-batch":
            return validate_content_review_batch(value)
        return value


__all__ = ["ContentReviewProjectionService"]
