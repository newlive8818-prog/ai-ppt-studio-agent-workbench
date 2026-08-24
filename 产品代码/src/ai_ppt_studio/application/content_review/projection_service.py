"""Read-only v2.2 projection for the on-demand content review surface."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ai_ppt_studio.domains.content.contracts import (
    validate_content_hard_gate_record,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.domains.content.page_decisions import (
    validate_page_decision,
    validate_page_decision_set,
)
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


BLUEPRINT_SLOT = "content/reading-deck-blueprint"
EVIDENCE_GATE_SLOT = "content/gate/evidence"
READING_GATE_SLOT = "content/gate/presales-reading"
ACCEPTANCE_SLOT = "content/acceptance"
SESSION_SLOT = "review/session/current/content-full-deck"
DECISION_SET_SLOT = "content/page-decisions"
SESSION_IDENTITY_SLOT_PREFIX = "review/session/"


def _review_session_id(identity: tuple[str, str, str, str, int]) -> str:
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "review-session-" + hashlib.sha256(encoded).hexdigest()[:24]


class ContentReviewProjectionService:
    """Expose only a current internally-passed reading deck for review."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self, *, review_session_id: str) -> dict[str, Any]:
        state = self.kernel.load()
        blueprint_ref = self._current_ref(state.artifact_heads, BLUEPRINT_SLOT)
        blueprint = validate_reading_deck_blueprint(
            self._resolve(blueprint_ref, "reading-deck-blueprint")
        )
        if blueprint["project_id"] != state.project_id:
            raise ContractValidationError(
                "ReadingDeckBlueprint project_id does not match the current project"
            )
        evidence_ref = self._passed_gate(
            state.artifact_heads,
            EVIDENCE_GATE_SLOT,
            blueprint_ref,
            expected_gate_type="evidence",
        )
        reading_ref = self._passed_gate(
            state.artifact_heads,
            READING_GATE_SLOT,
            blueprint_ref,
            expected_gate_type="presales-reading",
        )
        reading_record = validate_content_hard_gate_record(
            self._resolve(reading_ref, "content-hard-gate-record")
        )
        if reading_record.get("evidence_gate_ref") != evidence_ref:
            raise ContractValidationError(
                "Content review requires the exact evidence-gate predecessor"
            )
        acceptance_ref = self._current_ref(
            state.artifact_heads, ACCEPTANCE_SLOT
        )
        acceptance = self._resolve(acceptance_ref, "content-acceptance")
        if (
            acceptance.get("source_version") != blueprint_ref
            or acceptance.get("evidence_gate_ref") != evidence_ref
            or acceptance.get("presales_reading_gate_ref") != reading_ref
            or acceptance.get("overall_result") != "passed"
        ):
            raise ContractValidationError(
                "Content review requires the current v2.2 acceptance lineage"
            )
        session = self._current_session(
            state.artifact_heads,
            review_session_id,
            blueprint_ref,
            str(blueprint["source_version"]),
            state.project_id,
            state.revision,
        )
        decisions, frozen = self._current_decisions(
            state.artifact_heads,
            project_id=state.project_id,
            source_version=blueprint_ref,
            slides=blueprint["slides"],
        )
        slides = [
            self._project_slide(
                slide,
                decisions.get(slide["slide_id"]),
                frozen=frozen,
            )
            for slide in blueprint["slides"]
        ]
        return {
            "surface": "content-full-deck",
            "project_id": state.project_id,
            "revision": state.revision,
            "source_version": blueprint_ref,
            "review_session": session,
            "gate_status": "content-review-ready",
            "review_progress": self._progress(slides),
            "slides": slides,
        }

    def _current_session(
        self,
        heads: dict[str, str],
        review_session_id: str,
        blueprint_ref: str,
        logical_source_version: str,
        project_id: str,
        current_revision: int,
    ) -> dict[str, Any]:
        session_ref = self._current_ref(heads, SESSION_SLOT)
        session = validate_review_session(
            self._resolve(session_ref, "review-session"),
            current_revision=current_revision,
        )
        if session["review_type"] != "content-full-deck":
            raise ContractValidationError(
                "Content review session review_type must be content-full-deck"
            )
        if session["project_id"] != project_id:
            raise ContractValidationError(
                "Content review session project_id does not match the current project"
            )
        identity_ref = str(
            heads.get(
                f"{SESSION_IDENTITY_SLOT_PREFIX}{session['review_session_id']}"
            )
            or ""
        )
        if not identity_ref or identity_ref != session_ref:
            raise ContractValidationError(
                "Content review session does not match its authoritative identity head"
            )
        expected_session_id = _review_session_id(
            (
                session["project_id"],
                session["review_type"],
                session["target_artifact_ref"],
                session["source_version"],
                session["revision"],
            )
        )
        if session["review_session_id"] != expected_session_id:
            raise ContractValidationError(
                "Content review session ID does not match its immutable identity"
            )
        if (
            session["review_session_id"] != review_session_id
            or session["target_artifact_ref"] != blueprint_ref
            or session["source_version"] != logical_source_version
            or session["status"] not in {"ready", "opened", "submitted"}
        ):
            raise ContractValidationError(
                "Content review session does not match the current reading deck"
            )
        return session

    def _current_decisions(
        self,
        heads: dict[str, str],
        *,
        project_id: str,
        source_version: str,
        slides: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], bool]:
        decision_set_ref = str(heads.get(DECISION_SET_SLOT) or "")
        if not decision_set_ref:
            return {}, False
        decision_set = validate_page_decision_set(
            self._resolve(decision_set_ref, "content-page-decision-set")
        )
        expected_rows = [
            {"slide_id": slide["slide_id"], "slide_order": slide["order"]}
            for slide in slides
        ]
        actual_rows = [
            {"slide_id": row["slide_id"], "slide_order": row["slide_order"]}
            for row in decision_set["decision_refs"]
        ]
        if (
            decision_set["project_id"] != project_id
            or decision_set["source_version"] != source_version
        ):
            raise ContractValidationError(
                "Content review decision set is not current for this source"
            )
        expected_subset = [
            row
            for row in expected_rows
            if row["slide_id"] in {item["slide_id"] for item in actual_rows}
        ]
        if (
            decision_set["expected_slide_count"] != len(slides)
            or len(decision_set["decision_refs"]) > len(slides)
            or actual_rows != expected_subset
            or (
                decision_set["status"] == "frozen"
                and actual_rows != expected_rows
            )
        ):
            raise ContractValidationError(
                "Content review decision set does not map the current deck"
            )
        decisions: dict[str, dict[str, Any]] = {}
        for row in decision_set["decision_refs"]:
            decision = validate_page_decision(
                self._resolve(row["decision_ref"], "content-page-decision")
            )
            if (
                decision["project_id"] != project_id
                or decision["source_version"] != source_version
                or decision["review_batch_id"] != decision_set["review_batch_id"]
                or decision["slide_id"] != row["slide_id"]
                or decision["slide_order"] != row["slide_order"]
                or decision["slide_id"] in decisions
            ):
                raise ContractValidationError(
                    "Content review decision lineage is invalid"
                )
            decisions[decision["slide_id"]] = decision
        return decisions, decision_set["status"] == "frozen"

    def _passed_gate(
        self,
        heads: dict[str, str],
        slot: str,
        blueprint_ref: str,
        *,
        expected_gate_type: str,
    ) -> str:
        gate_ref = self._current_ref(heads, slot)
        record = validate_content_hard_gate_record(
            self._resolve(gate_ref, "content-hard-gate-record")
        )
        if (
            record.get("gate_type") != expected_gate_type
            or record.get("input_source_version") != blueprint_ref
            or record.get("overall_result") != "passed"
        ):
            raise ContractValidationError(
                f"Content review requires {slot} gate_type {expected_gate_type}"
            )
        return gate_ref

    def _current_ref(self, heads: dict[str, str], slot: str) -> str:
        value = str(heads.get(slot) or "")
        if not value:
            raise ContractValidationError(f"Content review requires {slot}")
        return value

    def _resolve(self, value: str, expected_kind: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(value)
        if reference.kind != expected_kind:
            raise ContractValidationError(
                f"Expected {expected_kind}, received {reference.kind}"
            )
        return dict(self.kernel.artifacts.resolve(reference)["payload"])

    @staticmethod
    def _project_slide(
        slide: dict[str, Any], decision: dict[str, Any] | None, *, frozen: bool
    ) -> dict[str, Any]:
        return {
            "slide_id": slide["slide_id"],
            "order": slide["order"],
            "neutral_title": slide["neutral_title"],
            "page_task": slide["page_task"],
            "reading_question": slide["reading_question"],
            "visible_copy_blocks": slide["visible_copy_blocks"],
            "identity_labels": slide["identity_labels"],
            "evidence_bindings": slide["evidence_bindings"],
            "analysis_or_proposal_blocks": slide[
                "analysis_or_proposal_blocks"
            ],
            "solution_mapping_refs": slide["solution_mapping_refs"],
            "speaker_notes": slide["speaker_notes"],
            "reading_quality": slide["reading_quality"],
            "previous_relation": slide["previous_relation"],
            "next_relation": slide["next_relation"],
            "decision_state": {
                "selected": str(decision.get("decision") or "")
                if decision
                else "",
                "comment": str(decision.get("comment") or "")
                if decision
                else "",
                "completed": bool(decision.get("completed"))
                if decision
                else False,
                "saved": decision is not None,
                "frozen": frozen,
            },
        }

    @staticmethod
    def _progress(slides: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {
            "approved": 0,
            "modify": 0,
            "evidence": 0,
            "merge_or_delete": 0,
        }
        saved_comment_count = 0
        completed = 0
        for slide in slides:
            state = slide["decision_state"]
            selected = state["selected"]
            if selected:
                counts[selected.replace("-", "_")] += 1
            if state["completed"]:
                completed += 1
            if state["comment"]:
                saved_comment_count += 1
        return {
            "total": len(slides),
            "completed": completed,
            "remaining": len(slides) - completed,
            "saved_comment_count": saved_comment_count,
            "counts": counts,
        }


__all__ = ["ContentReviewProjectionService"]
