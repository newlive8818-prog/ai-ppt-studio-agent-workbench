"""Authoritative v2.2 visual professional-review projection and writes."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.review_commands import fingerprint, replay_ref, stable_id
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.domains.visual.review_contracts import (
    validate_anchor_feedback_batch,
    validate_anchor_region_feedback,
    validate_visual_contract_review_mark,
    validate_visual_contract_review_mark_set,
)
from ai_ppt_studio.domains.visual.contracts import (
    validate_anchor_slide_set,
    validate_deck_design_system,
    validate_visual_contract_set,
)
from ai_ppt_studio.errors import (
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


REVIEWABLE_SLIDE_TEXT_FIELDS = (
    "page_family",
    "page_task",
    "reading_question",
    "neutral_title",
    "information_hierarchy",
    "composition_intent",
    "image_selection_and_crop",
    "typography_application",
    "color_application",
    "diagram_chart_table_treatment",
    "native_bitmap_routing",
    "editability_requirements",
    "speaker_notes",
    "previous_relation",
    "next_relation",
)
REVIEWABLE_SLIDE_NONEMPTY_LIST_FIELDS = (
    "visible_copy_blocks",
    "identity_labels",
    "solution_mapping_refs",
    "regions",
    "object_relationships",
    "reading_order",
    "fallbacks",
    "acceptance_criteria",
)
REVIEWABLE_SLIDE_OPTIONAL_LIST_FIELDS = (
    "evidence_bindings",
    "analysis_or_proposal_blocks",
    "allowed_exceptions",
)
MATERIAL_MODES = frozenset(
    {"material-backed", "mixed-evidence", "proposal-led"}
)
REVIEWABLE_DESIGN_SYSTEM_FIELDS = (
    "theme_proposition",
    "composition_grammar",
    "color_tokens",
    "typography_tokens",
    "page_families",
    "density_rhythm",
    "imagery_strategy",
    "diagram_strategy",
    "table_strategy",
    "editability_rules",
    "accessibility_rules",
    "forbidden_patterns",
    "anchor_specification",
)
REVIEWABLE_VISUAL_SLIDE_FIELDS = (
    "core_claim",
    "visible_copy",
    "speaker_notes",
    "source_refs",
    "communication_goal",
    "composition_intent",
    "information_hierarchy",
    "reading_order",
    "regions",
    "object_relationships",
    "diagram_chart_table_treatment",
    "image_selection_and_crop",
    "color_application",
    "typography_application",
    "native_bitmap_routing",
    "editability_requirements",
    "fallbacks",
    "acceptance_criteria",
)


class VisualReviewService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self, review_session_id: str) -> dict[str, Any]:
        context = self._context(review_session_id)
        state, contract_ref, contract, design_ref, design, anchor_ref, anchors, session = context
        anchor_feedback_batch_ref = state.artifact_heads.get(
            "visual/anchor-feedback-batch", ""
        )
        contract_review_marks_ref = state.artifact_heads.get(
            "visual/contract-review-marks", ""
        )
        anchor_identity = contract.get("anchor_identity") or {}
        return {
            "project_id": state.project_id,
            "project_name": self._project_name(state),
            "review_type": "visual-professional",
            "review_session_id": session["review_session_id"],
            "review_session": copy.deepcopy(session),
            "source_version": session["source_version"],
            "revision": session["revision"],
            "authoritative_revision": state.revision,
            "visual_contract_ref": contract_ref,
            "deck_design_system_ref": design_ref,
            "deck_design_system": self._project_deck_design_system(
                design, anchor_identity
            ),
            "anchor_slide_set_ref": anchor_ref,
            "anchors": copy.deepcopy(anchors["render_assets"]),
            "anchor_identity": {
                "slide_ids": copy.deepcopy(anchor_identity.get("slide_ids") or []),
                "selection_reason": str(
                    anchor_identity.get("selection_reason") or ""
                ),
                "native_first_frozen": anchor_identity.get(
                    "native_first_frozen"
                )
                is True,
            },
            "slide_visual_contracts": [
                self._project_slide_contract(slide)
                for slide in contract.get("slide_contracts") or []
            ],
            "anchor_feedback_batch": self._with_receipt_facts(
                session,
                anchor_feedback_batch_ref,
                self._current_anchor_feedback_batch(
                    state=state,
                    session=session,
                    source_version=session["source_version"],
                    contract_ref=contract_ref,
                    design_ref=design_ref,
                    anchor_ref=anchor_ref,
                    anchors=anchors,
                ),
            ),
            "anchor_feedback_batch_ref": anchor_feedback_batch_ref or None,
            "contract_review_marks": self._with_receipt_facts(
                session,
                contract_review_marks_ref,
                self._optional(
                    state, "visual/contract-review-marks", "visual-contract-review-mark-set"
                ),
            ),
            "contract_review_marks_ref": contract_review_marks_ref or None,
            "host_submission_capability": "unknown",
            "ai_receipt_capability": "unknown",
        }

    def submit_anchor_feedback_batch(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        source_version: str,
        feedback: list[dict[str, Any]],
    ):
        if not isinstance(feedback, list) or not feedback:
            raise ContractValidationError("AnchorFeedbackBatch cannot be empty")
        submitted_at = datetime.now(timezone.utc)
        normalized = [
            validate_anchor_region_feedback(
                item,
                created_not_after=submitted_at,
            )
            for item in feedback
        ]
        values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
            "feedback": normalized,
        }
        command_fingerprint = fingerprint("submit-visual-anchor-feedback-batch", values)
        slot = "visual/anchor-feedback-batch"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_anchor_feedback_batch(
                self._payload(reference, "visual-anchor-feedback-batch")
            ), state
        context = self._context(
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        state, contract_ref, _contract, design_ref, _design, anchor_ref, anchors, _session = context
        if state.artifact_heads.get(slot):
            raise ContractValidationError("Current AnchorFeedbackBatch is immutable")
        allowed_slides = set(anchors.get("slide_ids") or [])
        for item in normalized:
            if (
                item["anchor_slide_id"] not in allowed_slides
                or item["anchor_artifact_ref"] != anchor_ref
                or item["visual_source_version"] != source_version
                or item["revision"] != expected_revision
            ):
                raise ReviewSourceStaleError(source_version, str(item.get("visual_source_version") or ""))
        batch = validate_anchor_feedback_batch(
            {
                "batch_id": stable_id("anchor-feedback-batch", review_session_id, command_id),
                "project_id": state.project_id,
                "review_session_id": review_session_id,
                "visual_contract_ref": contract_ref,
                "deck_design_system_ref": design_ref,
                "anchor_slide_set_ref": anchor_ref,
                "items": normalized,
                "source_version": source_version,
                "revision": expected_revision,
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "immutable_after_submit": True,
                "submitted_at": submitted_at.isoformat(),
                "submitted_by": "user",
            }
        )
        gates = dict(state.gate_status)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.anchor-feedback-batch-submitted",
            artifact_updates={
                slot: (
                    "visual-anchor-feedback-batch",
                    batch,
                )
            },
            command_fingerprint=command_fingerprint,
        )
        if committed.gate_status != gates:
            raise RuntimeError("Visual feedback unexpectedly changed G3")
        return committed.artifact_heads[slot], batch, committed

    def save_contract_review_marks(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        source_version: str,
        marks: list[dict[str, Any]],
    ):
        if not isinstance(marks, list) or not marks:
            raise ContractValidationError("VisualContractReviewMarkSet cannot be empty")
        created_not_after = datetime.now(timezone.utc)
        normalized = [
            validate_visual_contract_review_mark(
                mark,
                created_not_after=created_not_after,
            )
            for mark in marks
        ]
        values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
            "marks": normalized,
        }
        command_fingerprint = fingerprint("save-visual-contract-review-marks", values)
        slot = "visual/contract-review-marks"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_visual_contract_review_mark_set(
                self._payload(reference, "visual-contract-review-mark-set")
            ), state
        context = self._context(
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        state, contract_ref, contract, _design_ref, design, _anchor_ref, _anchors, _session = context
        valid_slides = {item.get("slide_id") for item in contract.get("slide_contracts") or []}
        for mark in normalized:
            if (
                mark["visual_contract_ref"] != contract_ref
                or mark["source_version"] != source_version
                or mark["revision"] != expected_revision
                or (mark["slide_id"] and mark["slide_id"] not in valid_slides)
            ):
                raise ReviewSourceStaleError(source_version, str(mark.get("source_version") or ""))
            target_value = self._contract_mark_target_value(
                mark=mark,
                contract=contract,
                design=design,
            )
            if mark["target_type"] == "text-range":
                self._validate_text_anchor(mark, target_value)
        current = self._optional(
            state, "visual/contract-review-marks", "visual-contract-review-mark-set"
        )
        merged = {
            item["mark_id"]: item
            for item in (current or {}).get("marks", [])
            if item.get("source_version") == source_version
        }
        merged.update({item["mark_id"]: item for item in normalized})
        mark_set = validate_visual_contract_review_mark_set(
            {
                "mark_set_id": stable_id("visual-contract-marks", review_session_id, command_id),
                "project_id": state.project_id,
                "review_session_id": review_session_id,
                "visual_contract_ref": contract_ref,
                "source_version": source_version,
                "revision": expected_revision,
                "marks": list(merged.values()),
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        gates = dict(state.gate_status)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.contract-review-marks-saved",
            artifact_updates={
                slot: (
                    "visual-contract-review-mark-set",
                    mark_set,
                )
            },
            command_fingerprint=command_fingerprint,
        )
        if committed.gate_status != gates:
            raise RuntimeError("Visual marks unexpectedly changed G3")
        return committed.artifact_heads[slot], mark_set, committed

    @classmethod
    def _contract_mark_target_value(
        cls,
        *,
        mark: dict[str, Any],
        contract: dict[str, Any],
        design: dict[str, Any],
    ) -> Any:
        target_key = mark["target_key"]
        slide_id = mark["slide_id"]
        if slide_id:
            if target_key not in REVIEWABLE_VISUAL_SLIDE_FIELDS:
                raise ContractValidationError(
                    "Visual contract mark target_key is not reviewable"
                )
            slide = next(
                (
                    item
                    for item in contract.get("slide_contracts") or []
                    if item.get("slide_id") == slide_id
                ),
                None,
            )
            if slide is None:
                raise ReviewSourceStaleError(slide_id, "")
            return cls._project_slide_contract(slide)[target_key]
        if mark["deck_section_id"] != "deck-design-system":
            raise ContractValidationError(
                "Visual contract mark deck_section_id is not reviewable"
            )
        if target_key not in REVIEWABLE_DESIGN_SYSTEM_FIELDS:
            raise ContractValidationError(
                "Deck design system mark target_key is not reviewable"
            )
        return cls._project_deck_design_system(design, {})[target_key]

    @staticmethod
    def _contract_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            return "".join(
                VisualReviewService._contract_text(item)
                for item in value.values()
            )
        if isinstance(value, (list, tuple)):
            return "".join(
                VisualReviewService._contract_text(item) for item in value
            )
        return str(value)

    @staticmethod
    def _normalized_contract_text(value: str) -> str:
        return " ".join(value.split())

    @classmethod
    def _validate_text_anchor(
        cls,
        mark: dict[str, Any],
        target_value: Any,
    ) -> None:
        target_text = cls._normalized_contract_text(
            cls._contract_text(target_value)
        )
        selected_text = cls._normalized_contract_text(mark["selected_text"])
        context_before = cls._normalized_contract_text(mark["context_before"])
        context_after = cls._normalized_contract_text(mark["context_after"])
        anchored = f"{context_before}{selected_text}{context_after}"
        if not target_text or not selected_text or anchored not in target_text:
            raise ContractValidationError(
                "Text-range mark does not match the current contract target"
            )

    @staticmethod
    def _project_deck_design_system(
        design: dict[str, Any],
        anchor_identity: dict[str, Any],
    ) -> dict[str, Any]:
        projected = {
            key: copy.deepcopy(design.get(key))
            for key in REVIEWABLE_DESIGN_SYSTEM_FIELDS
        }
        projected["production_route"] = copy.deepcopy(
            design.get("production_route")
        )
        if design.get("fallback_fonts") is not None:
            projected["fallback_fonts"] = copy.deepcopy(
                design["fallback_fonts"]
            )
        if projected["anchor_specification"] is None and anchor_identity:
            projected["anchor_specification"] = {
                "slide_ids": copy.deepcopy(anchor_identity.get("slide_ids") or []),
                "selection_reason": str(
                    anchor_identity.get("selection_reason") or ""
                ),
                "native_first_frozen": anchor_identity.get(
                    "native_first_frozen"
                )
                is True,
            }
        return projected

    @staticmethod
    def _project_slide_contract(slide: dict[str, Any]) -> dict[str, Any]:
        if "visible_copy" in slide:
            visible_copy = copy.deepcopy(slide["visible_copy"])
        elif "visible_copy_blocks" in slide:
            blocks = slide.get("visible_copy_blocks") or []
            visible_copy = [
                str(block.get("text") or "").strip()
                for block in blocks
                if isinstance(block, dict) and str(block.get("text") or "").strip()
            ]
        else:
            visible_copy = copy.deepcopy(slide.get("frozen_copy"))
        source_refs = copy.deepcopy(slide.get("source_refs"))
        if source_refs is None:
            source_refs = []
            for binding in slide.get("evidence_bindings") or []:
                if not isinstance(binding, dict):
                    continue
                refs = binding.get("source_refs")
                if isinstance(refs, list):
                    source_refs.extend(
                        str(reference).strip()
                        for reference in refs
                        if str(reference).strip()
                    )
                elif str(binding.get("source_ref") or "").strip():
                    source_refs.append(
                        str(binding["source_ref"]).strip()
                    )
            source_refs = list(dict.fromkeys(source_refs))
        return {
            "slide_id": str(slide.get("slide_id") or ""),
            "order": slide.get("order"),
            "neutral_title": str(
                slide.get("neutral_title")
                or slide.get("title")
                or slide.get("page_task")
                or ""
            ),
            "page_family": copy.deepcopy(slide.get("page_family")),
            "anchor_title": str(
                slide.get("anchor_title")
                or slide.get("neutral_title")
                or slide.get("title")
                or ""
            ),
            "validation_purpose": str(
                slide.get("validation_purpose")
                or slide.get("anchor_validation_purpose")
                or slide.get("page_task")
                or ""
            ),
            **{
                key: copy.deepcopy(
                    visible_copy
                    if key == "visible_copy"
                    else source_refs
                    if key == "source_refs"
                    else slide.get(key)
                )
                for key in REVIEWABLE_VISUAL_SLIDE_FIELDS
            },
        }

    def _context(
        self,
        review_session_id: str,
        *,
        source_version: str | None = None,
        expected_revision: int | None = None,
    ):
        state = self.kernel.load()
        if expected_revision is not None and state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        if state.gate_status.get("G1") != "passed" or state.gate_status.get("G2") != "passed":
            raise GateBlockedError("visual-review", ("G1-G2-not-passed",))
        contract_ref = state.artifact_heads.get("visual/contract", "")
        contract = self._payload(contract_ref, "visual-contract")
        actual_source = str(contract.get("source_version") or contract_ref)
        if source_version is not None and source_version != actual_source:
            raise ReviewSourceStaleError(source_version, actual_source)
        reading_ref = state.artifact_heads.get("content/reading-blueprint", "")
        design_ref = state.artifact_heads.get("visual/design-system", "")
        visual_contract_set_ref = state.artifact_heads.get("visual/contracts", "")
        anchor_ref = state.artifact_heads.get("visual/anchors", "")
        if (
            not reading_ref
            or not visual_contract_set_ref
            or contract.get("reading_blueprint_ref") != reading_ref
            or contract.get("deck_design_system_ref") != design_ref
            or contract.get("visual_contract_set_ref")
            != visual_contract_set_ref
            or contract.get("anchor_slide_set_ref") != anchor_ref
        ):
            raise GateBlockedError("visual-review", ("visual-contract-lineage-stale",))
        blueprint = validate_reading_deck_blueprint(
            copy.deepcopy(self._payload(reading_ref, "reading-deck-blueprint"))
        )
        design = validate_deck_design_system(
            copy.deepcopy(self._payload(design_ref, "deck-design-system"))
        )
        visual_contract_set = validate_visual_contract_set(
            copy.deepcopy(
                self._payload(visual_contract_set_ref, "visual-contract-set")
            ),
            copy.deepcopy(blueprint),
        )
        anchors = validate_anchor_slide_set(
            copy.deepcopy(self._payload(anchor_ref, "anchor-slide-set")),
            copy.deepcopy(visual_contract_set),
        )
        current_g2 = GateEvaluator(self.kernel).validate_current_g2_evidence()
        self._validate_projection_contract(
            contract,
            blueprint,
            design,
            visual_contract_set,
            anchors,
            current_g2,
        )
        session_ref = state.review_session_ref("visual-professional")
        session = validate_review_session(
            self._payload(session_ref, "review-session"), trusted_receipts=True
        )
        if (
            session["review_session_id"] != review_session_id
            or session["target_artifact_ref"] != contract_ref
            or session["source_version"] != actual_source
            or session["status"] in {"superseded", "expired"}
        ):
            raise ReviewSourceStaleError(review_session_id, session["review_session_id"])
        return state, contract_ref, contract, design_ref, design, anchor_ref, anchors, session

    @staticmethod
    def _validate_projection_contract(
        contract: dict[str, Any],
        blueprint: dict[str, Any],
        design: dict[str, Any],
        visual_contract_set: dict[str, Any],
        anchors: dict[str, Any],
        current_g2: dict[str, Any],
    ) -> None:
        expected_source_version = str(
            visual_contract_set.get("source_version")
            or anchors.get("source_version")
            or design.get("source_version")
            or ""
        )
        expected = {
            "reading_blueprint_ref": contract.get("reading_blueprint_ref"),
            "deck_design_system_ref": current_g2["refs"]["design-system"],
            "visual_contract_set_ref": current_g2["refs"]["contracts"],
            "anchor_slide_set_ref": current_g2["refs"]["anchors"],
            "production_route": "strict-B",
            "reading_deck": {
                "source_version": blueprint["source_version"],
                "material_mode": blueprint["material_mode"],
                "section_flow": blueprint["section_flow"],
                "slides": blueprint["slides"],
            },
            "deck_design_system": design,
            "role_runs": visual_contract_set["role_runs"],
            "slide_contracts": visual_contract_set["slide_contracts"],
            "anchor_identity": anchors,
            "release_target_policy_ref": current_g2["policy_ref"],
            "target_evidence_refs": current_g2["target_evidence_refs"],
            "target_evidence_identities": current_g2[
                "target_evidence_identities"
            ],
            "internal_review_refs": current_g2["internal_review_refs"],
            "status": "user-reviewable",
        }
        if expected_source_version:
            expected["source_version"] = expected_source_version
        elif contract.get("source_version"):
            raise ContractValidationError(
                "Final visual contract source_version is forged or stale"
            )
        if not contract.get("reading_blueprint_ref"):
            raise ContractValidationError(
                "Final visual contract reading_blueprint_ref is required"
            )
        for field, value in expected.items():
            if contract.get(field) != value:
                raise ContractValidationError(
                    f"Final visual contract {field} is missing, forged, or stale"
                )

    def _payload(self, reference: str, kind: str) -> dict[str, Any]:
        try:
            parsed = ArtifactReference.parse(reference)
            if parsed.kind != kind:
                raise ContractValidationError(f"Expected {kind}")
            value = self.kernel.artifacts.resolve(parsed).get("payload")
        except Exception as error:
            if isinstance(error, ContractValidationError):
                raise
            raise ContractValidationError(f"Cannot resolve current {kind}") from error
        if not isinstance(value, dict):
            raise ContractValidationError(f"{kind} payload must be an object")
        return dict(value)

    def _optional(self, state, slot: str, kind: str):
        reference = state.artifact_heads.get(slot, "")
        return self._payload(reference, kind) if reference else None

    def _current_anchor_feedback_batch(
        self,
        *,
        state,
        session: dict[str, Any],
        source_version: str,
        contract_ref: str,
        design_ref: str,
        anchor_ref: str,
        anchors: dict[str, Any],
    ) -> dict[str, Any] | None:
        raw = self._optional(
            state,
            "visual/anchor-feedback-batch",
            "visual-anchor-feedback-batch",
        )
        if raw is None:
            return None
        batch = validate_anchor_feedback_batch(copy.deepcopy(raw))
        allowed_slides = set(anchors.get("slide_ids") or [])
        lineage_matches = (
            batch["project_id"] == state.project_id
            and batch["review_session_id"] == session["review_session_id"]
            and batch["visual_contract_ref"] == contract_ref
            and batch["deck_design_system_ref"] == design_ref
            and batch["anchor_slide_set_ref"] == anchor_ref
            and batch["source_version"] == source_version
            and batch["revision"] <= state.revision
            and batch["submitted_by"] == "user"
        )
        try:
            submitted_at = datetime.fromisoformat(
                batch["submitted_at"].replace("Z", "+00:00")
            )
            if submitted_at.tzinfo is None:
                raise ValueError("timezone is required")
        except (TypeError, ValueError) as error:
            raise ContractValidationError(
                "Current AnchorFeedbackBatch timestamp is invalid"
            ) from error
        for item in batch["items"]:
            try:
                created_at = datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                )
                if created_at.tzinfo is None or created_at > submitted_at:
                    raise ValueError("feedback timestamp is invalid")
            except (TypeError, ValueError) as error:
                raise ContractValidationError(
                    "Current AnchorFeedbackBatch item timestamp is invalid"
                ) from error
            lineage_matches = lineage_matches and (
                item["anchor_slide_id"] in allowed_slides
                and item["anchor_artifact_ref"] == anchor_ref
                and item["visual_source_version"] == source_version
                and item["revision"] == batch["revision"]
                and item["created_by"] == "user"
            )
        if not lineage_matches:
            raise ContractValidationError(
                "Current AnchorFeedbackBatch is forged, foreign, or stale"
            )
        return batch

    def _project_name(self, state) -> str:
        reference = state.artifact_heads.get("mission/draft", "")
        if reference:
            try:
                topic = self._payload(reference, "mission-draft").get("topic")
                if isinstance(topic, str) and topic.strip():
                    return topic.strip()
            except ContractValidationError:
                pass
        return state.project_id

    def _with_receipt_facts(
        self,
        session: dict[str, Any],
        saved_artifact_ref: str,
        saved: dict[str, Any] | None,
    ):
        if saved is None:
            return None
        saved["host_notification_status"] = (
            "sent"
            if self._bound_receipt_matches(
                session,
                saved_artifact_ref,
                map_field="host_notification_receipts",
                receipt_kind="review-host-notification-receipt",
                expected_status="sent",
            )
            else "unavailable"
        )
        saved["ai_receipt_status"] = (
            "received"
            if self._bound_receipt_matches(
                session,
                saved_artifact_ref,
                map_field="ai_receipts",
                receipt_kind="review-ai-receipt",
                expected_status="received",
            )
            else "unverified"
        )
        return saved

    def _bound_receipt_matches(
        self,
        session: dict[str, Any],
        saved_artifact_ref: str,
        *,
        map_field: str,
        receipt_kind: str,
        expected_status: str,
    ) -> bool:
        receipt_ref = (session.get(map_field) or {}).get(saved_artifact_ref, "")
        if not receipt_ref:
            return False
        try:
            receipt = self._payload(receipt_ref, receipt_kind)
        except ContractValidationError:
            return False
        return (
            receipt.get("project_id") == session["project_id"]
            and receipt.get("review_type") == "visual-professional"
            and receipt.get("review_session_id") == session["review_session_id"]
            and receipt.get("source_version") == session["source_version"]
            and receipt.get("saved_artifact_ref") == saved_artifact_ref
            and receipt.get("status") == expected_status
        )

__all__ = ["VisualReviewService"]
