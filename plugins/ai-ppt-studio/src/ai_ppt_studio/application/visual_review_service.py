"""Authoritative v2.2 visual professional-review projection and writes."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from itertools import permutations
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.review_commands import fingerprint, replay_ref, stable_id
from ai_ppt_studio.application.review_session_service import (
    authoritative_target_publication_revision,
)
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
    validate_visual_brief,
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


class _UntrustedCurrentContractReviewMarksError(ContractValidationError):
    """Raised for a well-formed current mark set with stale or foreign lineage."""


LEGACY_TEXT_ANCHOR_REPRESENTATION = "browser-v1"
CURRENT_TEXT_ANCHOR_REPRESENTATION = "browser-v2"
LEGACY_CONTRACT_MARK_FINGERPRINT_OPERATION = (
    "save-visual-contract-review-marks"
)
CURRENT_CONTRACT_MARK_FINGERPRINT_OPERATION = (
    "save-visual-contract-review-marks-v2"
)
NO_PREVIOUS_CONTRACT_MARK_SET = "none"
TRUSTED_PREVIOUS_CONTRACT_MARK_SET = "trusted"
DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET = "dropped-untrusted"
MAX_LEGACY_FINGERPRINT_REORDER_MARKS = 8
ECMASCRIPT_WHITESPACE_RUN = re.compile(
    "[\\u0009-\\u000D\\u0020\\u00A0\\u1680\\u2000-\\u200A"
    "\\u2028\\u2029\\u202F\\u205F\\u3000\\uFEFF]+"
)
ECMASCRIPT_WHITESPACE_EDGE = re.compile(
    "^[\\u0009-\\u000D\\u0020\\u00A0\\u1680\\u2000-\\u200A"
    "\\u2028\\u2029\\u202F\\u205F\\u3000\\uFEFF]+|"
    "[\\u0009-\\u000D\\u0020\\u00A0\\u1680\\u2000-\\u200A"
    "\\u2028\\u2029\\u202F\\u205F\\u3000\\uFEFF]+$"
)


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
REVIEWABLE_VISUAL_BRIEF_FIELDS = (
    "design_proposition",
    "audience_fit",
    "decision_task",
    "design_stance",
    "emotional_boundary",
    "brand_boundary",
    "density_strategy",
    "narrative_rhythm",
    "imagery_strategy",
    "diagram_strategy",
    "powerpoint_constraints",
    "forbidden_patterns",
    "five_second_test_contract",
    "design_philosophy_refs",
)
MARKABLE_VISUAL_BRIEF_FIELDS = tuple(
    field
    for field in REVIEWABLE_VISUAL_BRIEF_FIELDS
    if field != "design_proposition"
)
REVIEWABLE_DESIGN_SYSTEM_FIELDS = (
    "theme_proposition",
    "composition_grammar",
    "color_tokens",
    "typography_tokens",
    "page_families",
    "density_rhythm",
    "cross_slide_rhythm_rules",
    "emphasis_budget",
    "imagery_strategy",
    "image_language",
    "diagram_strategy",
    "diagram_language",
    "table_strategy",
    "editability_rules",
    "accessibility_rules",
    "forbidden_patterns",
    "five_second_test_rules",
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
    "reader_judgment",
    "primary_relationship",
    "secondary_relationship",
    "visual_mechanism",
    "focal_point",
    "asset_roles",
    "forbidden_patterns",
    "previous_rhythm_relation",
    "next_rhythm_relation",
    "text_density_budget",
    "powerpoint_implementation_requirements",
    "acceptance_evidence_plan",
)


class VisualReviewService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self, review_session_id: str) -> dict[str, Any]:
        from ai_ppt_studio.application.image_led_service import is_image_led

        context = self._context(review_session_id)
        (
            state,
            contract_ref,
            contract,
            brief_ref,
            brief,
            design_ref,
            design,
            anchor_ref,
            anchors,
            session,
        ) = context
        anchor_feedback_batch_ref = state.artifact_heads.get(
            "visual/anchor-feedback-batch", ""
        )
        contract_review_marks_ref = state.artifact_heads.get(
            "visual/contract-review-marks", ""
        )
        anchor_identity = contract.get("anchor_identity") or {}
        projected_session = copy.deepcopy(session)
        projected_session["review_status"] = {
            "gate": "G3",
            "status": state.gate_status.get("G3", "locked"),
        }
        return {
            "project_id": state.project_id,
            "project_name": self._project_name(state),
            "review_type": "visual-professional",
            **(
                {
                    "projection_contract": (
                        "image-led-formal-visual-review/v1"
                    )
                }
                if is_image_led(self.kernel)
                else {}
            ),
            "review_session_id": session["review_session_id"],
            "review_session": projected_session,
            "source_version": session["source_version"],
            "revision": session["revision"],
            "authoritative_revision": state.revision,
            "visual_contract_ref": contract_ref,
            "visual_brief_ref": brief_ref,
            "visual_brief": self._project_visual_brief(brief),
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
                self._current_contract_review_marks(
                    state=state,
                    session=session,
                    source_version=session["source_version"],
                    contract_ref=contract_ref,
                    contract=contract,
                    brief=brief,
                    design=design,
                    anchor_identity=anchors,
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
            reference, _replay_state = replay
            batch = validate_anchor_feedback_batch(
                self._payload(reference, "visual-anchor-feedback-batch")
            )
            (
                current_state,
                current_contract_ref,
                _current_contract,
                _current_brief_ref,
                _current_brief,
                current_design_ref,
                _current_design,
                current_anchor_ref,
                current_anchors,
                current_session,
            ) = self._context(
                review_session_id,
                source_version=source_version,
            )
            current_batch = self._current_anchor_feedback_batch(
                state=current_state,
                session=current_session,
                source_version=source_version,
                contract_ref=current_contract_ref,
                design_ref=current_design_ref,
                anchor_ref=current_anchor_ref,
                anchors=current_anchors,
            )
            if (
                current_state.artifact_heads.get(slot) != reference
                or current_batch != batch
            ):
                raise ContractValidationError(
                    "Processed AnchorFeedbackBatch is forged, foreign, or stale"
                )
            return reference, batch, current_state
        context = self._context(
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        (
            state,
            contract_ref,
            _contract,
            _brief_ref,
            _brief,
            design_ref,
            _design,
            anchor_ref,
            anchors,
            _session,
        ) = context
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
        if len({mark["mark_id"] for mark in normalized}) != len(normalized):
            raise ContractValidationError(
                "Visual contract mark ids must be unique"
            )
        if any(
            mark.get("anchor_representation_version")
            == LEGACY_TEXT_ANCHOR_REPRESENTATION
            for mark in normalized
        ):
            raise ContractValidationError(
                "browser-v1 text anchors are read-only historical records"
            )
        mark_set_id = stable_id(
            "visual-contract-marks",
            review_session_id,
            command_id,
        )
        semantic_values = {
            "review_session_id": review_session_id,
            "source_version": source_version,
            "mark_set_id": mark_set_id,
            "marks": sorted(
                normalized,
                key=lambda item: item["mark_id"],
            ),
        }
        legacy_command_fingerprint = fingerprint(
            LEGACY_CONTRACT_MARK_FINGERPRINT_OPERATION,
            {
                "review_session_id": review_session_id,
                "source_version": source_version,
                "marks": normalized,
            },
        )
        normalized = [
            {
                **mark,
                "anchor_representation_version": (
                    CURRENT_TEXT_ANCHOR_REPRESENTATION
                ),
            }
            if mark["target_type"] == "text-range"
            else mark
            for mark in normalized
        ]
        slot = "visual/contract-review-marks"
        replay = None
        replay_state = self.kernel.load()
        replay_revision = replay_state.processed_commands.get(command_id)
        if replay_revision is not None:
            (
                _replay_previous_disposition,
                replay_previous_ref,
                _replay_previous_mark_set,
            ) = self._latest_contract_review_mark_set_before(
                source_revision=replay_revision,
                state=replay_state,
            )
            current_error: ContractValidationError | None = None
            for previous_disposition in (
                NO_PREVIOUS_CONTRACT_MARK_SET,
                TRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
            ):
                try:
                    replay = replay_ref(
                        self.kernel,
                        command_id,
                        fingerprint(
                            CURRENT_CONTRACT_MARK_FINGERPRINT_OPERATION,
                            {
                                **semantic_values,
                                "previous_mark_set_ref": replay_previous_ref,
                                "previous_mark_set_disposition": (
                                    previous_disposition
                                ),
                            },
                        ),
                        slot,
                    )
                    break
                except ContractValidationError as error:
                    current_error = current_error or error
            if replay is None:
                try:
                    replay = replay_ref(
                        self.kernel,
                        command_id,
                        legacy_command_fingerprint,
                        slot,
                    )
                except ContractValidationError:
                    if current_error is not None:
                        raise current_error
                    raise
        if replay:
            reference, state = replay
            (
                current_state,
                current_contract_ref,
                current_contract,
                _current_brief_ref,
                current_brief,
                _current_design_ref,
                current_design,
                _current_anchor_ref,
                current_anchors,
                current_session,
            ) = self._context(
                review_session_id,
                source_version=source_version,
            )
            mark_set = self._validated_contract_review_marks(
                raw=self._payload(reference, "visual-contract-review-mark-set"),
                mark_set_ref=reference,
                require_current_head_continuity=False,
                state=current_state,
                session=current_session,
                source_version=source_version,
                contract_ref=current_contract_ref,
                contract=current_contract,
                brief=current_brief,
                design=current_design,
                anchor_identity=current_anchors,
            )
            return reference, mark_set, current_state
        context = self._context(
            review_session_id,
            source_version=source_version,
            expected_revision=expected_revision,
        )
        (
            state,
            contract_ref,
            contract,
            _brief_ref,
            brief,
            _design_ref,
            design,
            _anchor_ref,
            anchors,
            _session,
        ) = context
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
                brief=brief,
                design=design,
                anchor_identity=anchors,
            )
            if mark["target_type"] == "text-range":
                self._validate_text_anchor(mark, target_value)
        (
            history_disposition,
            previous_mark_set_ref,
            _history_mark_set,
        ) = self._latest_contract_review_mark_set_before(
            source_revision=expected_revision + 1,
            state=state,
        )
        try:
            current = self._current_contract_review_marks(
                state=state,
                session=_session,
                source_version=source_version,
                contract_ref=contract_ref,
                contract=contract,
                brief=brief,
                design=design,
                anchor_identity=anchors,
            )
        except _UntrustedCurrentContractReviewMarksError:
            current = None
            previous_mark_set_disposition = (
                DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET
            )
        else:
            previous_mark_set_disposition = (
                TRUSTED_PREVIOUS_CONTRACT_MARK_SET
                if current is not None
                else history_disposition
            )
        command_fingerprint = fingerprint(
            CURRENT_CONTRACT_MARK_FINGERPRINT_OPERATION,
            {
                **semantic_values,
                "previous_mark_set_ref": previous_mark_set_ref,
                "previous_mark_set_disposition": (
                    previous_mark_set_disposition
                ),
            },
        )
        merged = {
            item["mark_id"]: item
            for item in (current or {}).get("marks", [])
        }
        merged.update({item["mark_id"]: item for item in normalized})
        mark_set = validate_visual_contract_review_mark_set(
            {
                "mark_set_id": mark_set_id,
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
        brief: dict[str, Any],
        design: dict[str, Any],
        anchor_identity: dict[str, Any],
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
        if mark["deck_section_id"] == "visual-brief":
            if target_key not in MARKABLE_VISUAL_BRIEF_FIELDS:
                raise ContractValidationError(
                    "Visual Brief mark target_key is not reviewable"
                )
            return cls._project_visual_brief(brief)[target_key]
        if mark["deck_section_id"] != "deck-design-system":
            raise ContractValidationError(
                "Visual contract mark deck_section_id is not reviewable"
            )
        if target_key not in REVIEWABLE_DESIGN_SYSTEM_FIELDS:
            raise ContractValidationError(
                "Deck design system mark target_key is not reviewable"
            )
        projected = cls._project_deck_design_system(design, anchor_identity)
        target_value = projected[target_key]
        if target_key == "typography_tokens" and "fallback_fonts" in projected:
            target_value = {
                **(target_value if isinstance(target_value, dict) else {}),
                "fallback_fonts": projected["fallback_fonts"],
            }
        return target_value

    @staticmethod
    def _ordered_contract_record(
        value: Any,
        fields: tuple[str, ...],
    ) -> Any:
        if not isinstance(value, dict):
            return copy.deepcopy(value)
        return {
            field: copy.deepcopy(value.get(field))
            for field in fields
        }

    @classmethod
    def _ordered_contract_record_list(
        cls,
        value: Any,
        fields: tuple[str, ...],
    ) -> Any:
        if not isinstance(value, list):
            return copy.deepcopy(value)
        return [
            cls._ordered_contract_record(item, fields)
            for item in value
        ]

    @classmethod
    def _trim_projected_contract_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return ECMASCRIPT_WHITESPACE_EDGE.sub("", value)
        if isinstance(value, dict):
            return {
                key: cls._trim_projected_contract_text(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._trim_projected_contract_text(item) for item in value]
        return copy.deepcopy(value)

    @classmethod
    def _project_visual_brief(cls, brief: dict[str, Any]) -> dict[str, Any]:
        projected = {
            key: copy.deepcopy(
                brief.get(key, [] if key == "design_philosophy_refs" else None)
            )
            for key in REVIEWABLE_VISUAL_BRIEF_FIELDS
        }
        projected["five_second_test_contract"] = cls._ordered_contract_record(
            projected["five_second_test_contract"],
            ("prompt", "expected_judgment", "record_fields"),
        )
        return cls._trim_projected_contract_text(projected)

    @staticmethod
    def _ecmascript_array_index(key: Any) -> int | None:
        if not isinstance(key, str):
            return None
        if key == "0":
            return 0
        if (
            not key
            or key.startswith("0")
            or not key.isascii()
            or not key.isdigit()
        ):
            return None
        if len(key) > 10 or (
            len(key) == 10 and key > "4294967294"
        ):
            return None
        return int(key)

    @staticmethod
    def _ecmascript_object_values(value: dict[Any, Any]) -> list[Any]:
        indexed: list[tuple[int, Any]] = []
        ordinary: list[Any] = []
        for key, item in value.items():
            index = VisualReviewService._ecmascript_array_index(key)
            if index is None:
                ordinary.append(item)
            else:
                indexed.append((index, item))
        return [item for _index, item in sorted(indexed)] + ordinary

    @staticmethod
    def _contract_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, dict):
            return " ".join(
                text
                for item in VisualReviewService._ecmascript_object_values(value)
                if (text := VisualReviewService._contract_text(item))
            )
        if isinstance(value, (list, tuple)):
            return " ".join(
                text
                for item in value
                if (text := VisualReviewService._contract_text(item))
            )
        return str(value)

    @staticmethod
    def _legacy_contract_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            return "".join(
                VisualReviewService._legacy_contract_text(item)
                for item in value.values()
            )
        if isinstance(value, (list, tuple)):
            return "".join(
                VisualReviewService._legacy_contract_text(item)
                for item in value
            )
        return str(value)

    @classmethod
    def _validate_legacy_text_anchor(
        cls,
        mark: dict[str, Any],
        target_value: Any,
    ) -> None:
        target_text = cls._normalized_contract_text(
            cls._legacy_contract_text(target_value)
        )
        selected_text = cls._normalized_contract_text(mark["selected_text"])
        context_before = cls._normalized_contract_text(mark["context_before"])
        context_after = cls._normalized_contract_text(mark["context_after"])
        anchored = f"{context_before}{selected_text}{context_after}"
        if not target_text or not selected_text or anchored not in target_text:
            raise ContractValidationError(
                "Text-range mark does not match the legacy contract target"
            )

    @staticmethod
    def _normalized_contract_text(value: str) -> str:
        return ECMASCRIPT_WHITESPACE_RUN.sub(" ", value).strip(" ")

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
        anchored = False
        offset = target_text.find(selected_text)
        while target_text and selected_text and offset >= 0:
            expected_before = ECMASCRIPT_WHITESPACE_EDGE.sub(
                "",
                target_text[max(0, offset - 80):offset],
            )
            selected_end = offset + len(selected_text)
            expected_after = ECMASCRIPT_WHITESPACE_EDGE.sub(
                "",
                target_text[selected_end:selected_end + 80],
            )
            if (
                context_before == expected_before
                and context_after == expected_after
            ):
                anchored = True
                break
            offset = target_text.find(selected_text, offset + 1)
        if not anchored:
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
        projected["emphasis_budget"] = (
            VisualReviewService._ordered_contract_record(
                projected["emphasis_budget"],
                (
                    "max_primary_focal_points_per_slide",
                    "max_accent_color_roles",
                    "consecutive_high_density_slide_limit",
                ),
            )
        )
        projected["anchor_specification"] = (
            VisualReviewService._ordered_contract_record(
                projected["anchor_specification"],
                ("slide_ids", "selection_reason", "native_first_frozen"),
            )
        )
        return VisualReviewService._trim_projected_contract_text(projected)

    @classmethod
    def _project_slide_contract(cls, slide: dict[str, Any]) -> dict[str, Any]:
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
        projected = {
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
        projected["regions"] = cls._ordered_contract_record_list(
            projected["regions"],
            ("region_id", "purpose"),
        )
        projected["acceptance_criteria"] = cls._ordered_contract_record_list(
            projected["acceptance_criteria"],
            ("criterion_id", "level", "expected_outcome"),
        )
        projected["asset_roles"] = cls._ordered_contract_record_list(
            projected["asset_roles"],
            ("asset_id", "role", "source_ref", "narrative_task", "replaceable"),
        )
        projected["text_density_budget"] = cls._ordered_contract_record(
            projected["text_density_budget"],
            ("max_body_lines", "max_text_blocks", "reduction_strategy"),
        )
        powerpoint = cls._ordered_contract_record(
            projected["powerpoint_implementation_requirements"],
            (
                "object_plan",
                "connector_semantics",
                "layout_constraints",
                "native_bitmap_routing",
                "degradation_strategy",
            ),
        )
        if isinstance(powerpoint, dict):
            powerpoint["object_plan"] = cls._ordered_contract_record_list(
                powerpoint["object_plan"],
                ("role", "object_type", "layer", "editability"),
            )
            powerpoint["connector_semantics"] = (
                cls._ordered_contract_record_list(
                    powerpoint["connector_semantics"],
                    (
                        "from_role",
                        "to_role",
                        "meaning",
                        "direction",
                        "crossing_forbidden",
                    ),
                )
            )
            powerpoint["layout_constraints"] = cls._ordered_contract_record(
                powerpoint["layout_constraints"],
                ("entry_region", "focal_region", "minimum_clear_space"),
            )
        projected["powerpoint_implementation_requirements"] = powerpoint
        projected["acceptance_evidence_plan"] = cls._ordered_contract_record(
            projected["acceptance_evidence_plan"],
            (
                "automated_checks",
                "human_review_checks",
                "target_powerpoint_checks",
                "user_review_question",
            ),
        )
        projected = cls._trim_projected_contract_text(projected)
        if "image_led" in slide:
            from ai_ppt_studio.domains.visual.contracts import image_led_visible_fields
            exact = image_led_visible_fields(slide["image_led"]["selected_copy"])
            projected["neutral_title"] = exact["neutral_title"]
            projected["anchor_title"] = exact["neutral_title"]
            projected["visible_copy"] = [block["text"] for block in exact["visible_copy_blocks"]]
        return projected

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
        brief_ref = state.artifact_heads.get("visual/brief", "")
        design_ref = state.artifact_heads.get("visual/design-system", "")
        visual_contract_set_ref = state.artifact_heads.get("visual/contracts", "")
        anchor_ref = state.artifact_heads.get("visual/anchors", "")
        if (
            not reading_ref
            or not brief_ref
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
        if design.get("visual_brief_ref") != brief_ref:
            raise GateBlockedError(
                "visual-review", ("visual-brief-lineage-stale",)
            )
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            native = ImageLedNativeService(self.kernel)
            visual_contract_set, _plan = native.current_contract_plan()
            anchors = native.current_anchors()
        else:
            visual_contract_set = validate_visual_contract_set(
                copy.deepcopy(self._payload(visual_contract_set_ref, 'visual-contract-set')), copy.deepcopy(blueprint))
            anchors = validate_anchor_slide_set(copy.deepcopy(self._payload(anchor_ref, 'anchor-slide-set')),
                copy.deepcopy(visual_contract_set))
        current_g2 = GateEvaluator(self.kernel).validate_current_g2_evidence()
        brief = validate_visual_brief(
            copy.deepcopy(self._payload(brief_ref, "visual-brief")),
            current_g2["policy"].required_target_ids,
        )
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
        authoritative_revision = authoritative_target_publication_revision(
            self.kernel,
            state,
            "visual-professional",
            contract_ref,
        )
        if session["revision"] != authoritative_revision:
            raise ReviewSourceStaleError(
                str(session["revision"]), str(authoritative_revision)
            )
        return (
            state,
            contract_ref,
            contract,
            brief_ref,
            brief,
            design_ref,
            design,
            anchor_ref,
            anchors,
            session,
        )

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
            "visual_compilation_plan_ref": current_g2[
                "compilation_plan_ref"
            ],
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

    def _current_contract_review_marks(
        self,
        *,
        state,
        session: dict[str, Any],
        source_version: str,
        contract_ref: str,
        contract: dict[str, Any],
        brief: dict[str, Any],
        design: dict[str, Any],
        anchor_identity: dict[str, Any],
    ) -> dict[str, Any] | None:
        mark_set_ref = state.artifact_heads.get(
            "visual/contract-review-marks",
            "",
        )
        if not mark_set_ref:
            return None
        return self._validated_contract_review_marks(
            raw=self._payload(
                mark_set_ref,
                "visual-contract-review-mark-set",
            ),
            mark_set_ref=mark_set_ref,
            require_current_head_continuity=True,
            state=state,
            session=session,
            source_version=source_version,
            contract_ref=contract_ref,
            contract=contract,
            brief=brief,
            design=design,
            anchor_identity=anchor_identity,
        )

    def _validated_contract_review_marks(
        self,
        *,
        raw: dict[str, Any],
        mark_set_ref: str,
        require_current_head_continuity: bool,
        state,
        session: dict[str, Any],
        source_version: str,
        contract_ref: str,
        contract: dict[str, Any],
        brief: dict[str, Any],
        design: dict[str, Any],
        anchor_identity: dict[str, Any],
    ) -> dict[str, Any]:
        mark_set = validate_visual_contract_review_mark_set(copy.deepcopy(raw))
        session_revision = session["revision"]
        lineage_matches = (
            mark_set["project_id"] == state.project_id
            and mark_set["review_session_id"] == session["review_session_id"]
            and mark_set["visual_contract_ref"] == contract_ref
            and mark_set["source_version"] == source_version
            and session_revision <= mark_set["revision"] <= state.revision
        )
        lineage_matches = lineage_matches and (
            self._has_contract_review_mark_set_provenance(
                mark_set=mark_set,
                mark_set_ref=mark_set_ref,
                require_current_head_continuity=(
                    require_current_head_continuity
                ),
                state=state,
                review_session_id=session["review_session_id"],
                session_revision=session_revision,
            )
        )
        valid_slides = {
            item.get("slide_id") for item in contract.get("slide_contracts") or []
        }
        for mark in mark_set["marks"]:
            lineage_matches = lineage_matches and (
                mark["visual_contract_ref"] == contract_ref
                and mark["source_version"] == source_version
                and session_revision <= mark["revision"] <= mark_set["revision"]
                and mark["created_by"] == "user"
            )
            if mark["slide_id"]:
                lineage_matches = lineage_matches and mark["slide_id"] in valid_slides
            try:
                target_value = self._contract_mark_target_value(
                    mark=mark,
                    contract=contract,
                    brief=brief,
                    design=design,
                    anchor_identity=anchor_identity,
                )
                if mark["target_type"] == "text-range":
                    representation = mark.get(
                        "anchor_representation_version"
                    )
                    if representation == CURRENT_TEXT_ANCHOR_REPRESENTATION:
                        self._validate_text_anchor(mark, target_value)
                    else:
                        if not self._has_legacy_text_anchor_provenance(
                            mark=mark,
                            state=state,
                            review_session_id=session["review_session_id"],
                            session_revision=session["revision"],
                        ):
                            raise ContractValidationError(
                                "Legacy text-range mark has no trusted save provenance"
                            )
                        self._validate_legacy_text_anchor(mark, target_value)
                        mark["anchor_representation_version"] = (
                            LEGACY_TEXT_ANCHOR_REPRESENTATION
                        )
            except (ContractValidationError, ReviewSourceStaleError):
                lineage_matches = False
        if not lineage_matches:
            raise _UntrustedCurrentContractReviewMarksError(
                "VisualContractReviewMarkSet is forged, foreign, or stale"
            )
        return mark_set

    def _has_contract_review_mark_set_provenance(
        self,
        *,
        mark_set: dict[str, Any],
        mark_set_ref: str,
        require_current_head_continuity: bool,
        state,
        review_session_id: str,
        session_revision: int,
    ) -> bool:
        source_revision = mark_set["revision"] + 1
        if source_revision > state.revision:
            return False
        try:
            event = json.loads(
                (
                    self.kernel.events_root
                    / f"r{source_revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if not isinstance(event, dict):
                return False
            command_id = event.get("command_id")
            source_ref = dict(event.get("artifact_heads") or {}).get(
                "visual/contract-review-marks",
                "",
            )
            if (
                event.get("revision") != source_revision
                or event.get("event_type")
                != "visual.contract-review-marks-saved"
                or not isinstance(command_id, str)
                or not command_id
                or state.processed_commands.get(command_id) != source_revision
                or source_ref != mark_set_ref
            ):
                return False
            source_mark_set = validate_visual_contract_review_mark_set(
                self._payload(
                    source_ref,
                    "visual-contract-review-mark-set",
                )
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ContractValidationError,
        ):
            return False
        if (
            source_mark_set != mark_set
            or source_mark_set["project_id"] != state.project_id
            or source_mark_set["review_session_id"] != review_session_id
            or (
                require_current_head_continuity
                and not self._contract_review_mark_head_is_continuous(
                    mark_set_ref=mark_set_ref,
                    source_revision=source_revision,
                    state=state,
                )
            )
            or not all(
                item["visual_contract_ref"]
                == source_mark_set["visual_contract_ref"]
                and item["source_version"]
                == source_mark_set["source_version"]
                and session_revision <= item["revision"]
                <= source_mark_set["revision"]
                and item["created_by"] == "user"
                for item in source_mark_set["marks"]
            )
        ):
            return False
        return self._contract_mark_event_fingerprint_matches(
            event=event,
            source_revision=source_revision,
            source_mark_set=source_mark_set,
            state=state,
            session_revision=session_revision,
        )

    def _contract_review_mark_head_is_continuous(
        self,
        *,
        mark_set_ref: str,
        source_revision: int,
        state,
    ) -> bool:
        if (
            state.artifact_heads.get("visual/contract-review-marks", "")
            != mark_set_ref
        ):
            return False
        for revision in range(source_revision + 1, state.revision + 1):
            try:
                event = json.loads(
                    (
                        self.kernel.events_root
                        / f"r{revision:08d}.json"
                    ).read_text(encoding="utf-8")
                )
                if not isinstance(event, dict):
                    return False
                command_id = event.get("command_id")
                if (
                    event.get("revision") != revision
                    or not isinstance(command_id, str)
                    or not command_id
                    or state.processed_commands.get(command_id) != revision
                    or dict(event.get("artifact_heads") or {}).get(
                        "visual/contract-review-marks",
                        "",
                    )
                    != mark_set_ref
                ):
                    return False
            except (
                OSError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                return False
        return True

    def _contract_mark_event_fingerprint_matches(
        self,
        *,
        event: dict[str, Any],
        source_revision: int,
        source_mark_set: dict[str, Any],
        state,
        session_revision: int,
    ) -> bool:
        submitted_marks = [
            item
            for item in source_mark_set["marks"]
            if item["revision"] == source_mark_set["revision"]
        ]
        if not submitted_marks:
            return False
        event_fingerprint = event.get("command_fingerprint")
        if (
            not isinstance(event_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", event_fingerprint) is None
        ):
            return False
        (
            previous_disposition,
            previous_ref,
            previous_mark_set,
        ) = self._latest_contract_review_mark_set_before(
            source_revision=source_revision,
            state=state,
        )
        if previous_mark_set is not None:
            if (
                previous_mark_set["project_id"]
                != source_mark_set["project_id"]
                or previous_mark_set["review_session_id"]
                != source_mark_set["review_session_id"]
                or previous_mark_set["visual_contract_ref"]
                != source_mark_set["visual_contract_ref"]
                or previous_mark_set["source_version"]
                != source_mark_set["source_version"]
                or not (
                    session_revision <= previous_mark_set["revision"]
                    < source_mark_set["revision"]
                )
                or not all(
                    session_revision <= item["revision"]
                    <= previous_mark_set["revision"]
                    for item in previous_mark_set["marks"]
                )
                or not self._has_contract_review_mark_set_provenance(
                    mark_set=previous_mark_set,
                    mark_set_ref=previous_ref,
                    require_current_head_continuity=False,
                    state=state,
                    review_session_id=source_mark_set[
                        "review_session_id"
                    ],
                    session_revision=session_revision,
                )
            ):
                previous_mark_set = None
                previous_disposition = (
                    DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET
                )

        semantic_marks = sorted(
            submitted_marks,
            key=lambda item: item["mark_id"],
        )
        semantic_values = {
            "review_session_id": source_mark_set["review_session_id"],
            "source_version": source_mark_set["source_version"],
            "mark_set_id": stable_id(
                "visual-contract-marks",
                source_mark_set["review_session_id"],
                event["command_id"],
            ),
            "marks": semantic_marks,
            "previous_mark_set_ref": previous_ref,
            "previous_mark_set_disposition": previous_disposition,
        }
        current_fingerprints = {
            fingerprint(
                CURRENT_CONTRACT_MARK_FINGERPRINT_OPERATION,
                semantic_values,
            )
        }
        semantic_unversioned = []
        for item in semantic_marks:
            unversioned = dict(item)
            unversioned.pop("anchor_representation_version", None)
            semantic_unversioned.append(unversioned)
        current_fingerprints.add(
            fingerprint(
                CURRENT_CONTRACT_MARK_FINGERPRINT_OPERATION,
                {
                    **semantic_values,
                    "marks": semantic_unversioned,
                },
            )
        )
        current_fingerprint_matches = (
            event_fingerprint in current_fingerprints
        )
        if (
            current_fingerprint_matches
            and source_mark_set["mark_set_id"]
            != semantic_values["mark_set_id"]
        ):
            return False
        if (
            not current_fingerprint_matches
            and previous_disposition
            == DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET
        ):
            return False

        ordered_candidates: Any = [submitted_marks]
        if (
            previous_mark_set is not None
            and 2 <= len(submitted_marks)
            <= MAX_LEGACY_FINGERPRINT_REORDER_MARKS
        ):
            previous_ids = [
                item["mark_id"]
                for item in previous_mark_set["marks"]
            ]
            previous_id_set = set(previous_ids)
            submitted_ids = [
                item["mark_id"] for item in submitted_marks
            ]
            source_ids = [
                item["mark_id"] for item in source_mark_set["marks"]
            ]
            new_ids = [
                mark_id
                for mark_id in source_ids
                if mark_id not in previous_id_set
            ]
            if (
                any(
                    mark_id in previous_id_set
                    for mark_id in submitted_ids
                )
                and source_ids == [*previous_ids, *new_ids]
            ):
                ordered_candidates = permutations(submitted_marks)

        for ordered_marks in ordered_candidates:
            ordered = list(ordered_marks)
            values = {
                "review_session_id": source_mark_set[
                    "review_session_id"
                ],
                "source_version": source_mark_set["source_version"],
                "marks": ordered,
            }
            candidate_fingerprints = {
                fingerprint(
                    LEGACY_CONTRACT_MARK_FINGERPRINT_OPERATION,
                    values,
                )
            }
            ordered_unversioned = []
            for item in ordered:
                unversioned = dict(item)
                unversioned.pop(
                    "anchor_representation_version",
                    None,
                )
                ordered_unversioned.append(unversioned)
            candidate_fingerprints.add(
                fingerprint(
                    LEGACY_CONTRACT_MARK_FINGERPRINT_OPERATION,
                    {**values, "marks": ordered_unversioned},
                )
            )
            if (
                not current_fingerprint_matches
                and event_fingerprint not in candidate_fingerprints
            ):
                continue
            merged = {
                item["mark_id"]: item
                for item in [
                    {
                        **previous_item,
                        "anchor_representation_version": (
                            LEGACY_TEXT_ANCHOR_REPRESENTATION
                        ),
                    }
                    if (
                        previous_item["target_type"] == "text-range"
                        and not previous_item.get(
                            "anchor_representation_version"
                        )
                    )
                    else previous_item
                    for previous_item in (previous_mark_set or {}).get(
                        "marks",
                        [],
                    )
                ]
            }
            merged.update({item["mark_id"]: item for item in ordered})
            if list(merged.values()) == source_mark_set["marks"]:
                return True
        return False

    def _latest_contract_review_mark_set_before(
        self,
        *,
        source_revision: int,
        state,
    ) -> tuple[str, str, dict[str, Any] | None]:
        expected_ref: str | None = None
        for revision in range(source_revision - 1, 0, -1):
            try:
                event = json.loads(
                    (
                        self.kernel.events_root
                        / f"r{revision:08d}.json"
                    ).read_text(encoding="utf-8")
                )
                if not isinstance(event, dict):
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref or "",
                        None,
                    )
                mark_set_ref = dict(
                    event.get("artifact_heads") or {}
                ).get("visual/contract-review-marks", "")
                if not isinstance(mark_set_ref, str):
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref or "",
                        None,
                    )
                if expected_ref is None:
                    expected_ref = mark_set_ref
                elif mark_set_ref != expected_ref:
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref,
                        None,
                    )
                command_id = event.get("command_id")
                if (
                    event.get("revision") != revision
                    or not isinstance(command_id, str)
                    or not command_id
                    or state.processed_commands.get(command_id) != revision
                ):
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref,
                        None,
                    )
                if (
                    expected_ref == ""
                    and self._contract_review_mark_head_was_formally_removed(
                        event=event,
                        revision=revision,
                        state=state,
                    )
                ):
                    return NO_PREVIOUS_CONTRACT_MARK_SET, "", None
                if (
                    event.get("event_type")
                    != "visual.contract-review-marks-saved"
                ):
                    continue
                if not mark_set_ref:
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref,
                        None,
                    )
                mark_set = validate_visual_contract_review_mark_set(
                    self._payload(
                        mark_set_ref,
                        "visual-contract-review-mark-set",
                    )
                )
                if mark_set["revision"] + 1 != revision:
                    return (
                        DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                        expected_ref,
                        None,
                    )
                return (
                    TRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                    mark_set_ref,
                    mark_set,
                )
            except (
                OSError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ContractValidationError,
            ):
                return (
                    DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                    expected_ref or "",
                    None,
                )
        if expected_ref:
            return (
                DROPPED_UNTRUSTED_PREVIOUS_CONTRACT_MARK_SET,
                expected_ref,
                None,
            )
        return NO_PREVIOUS_CONTRACT_MARK_SET, "", None

    def _contract_review_mark_head_was_formally_removed(
        self,
        *,
        event: dict[str, Any],
        revision: int,
        state,
    ) -> bool:
        if event.get("event_type") != "gate.G3.reopened":
            return False
        if dict(event.get("gate_updates") or {}) != {
            "G1": "open",
            "G2": "locked",
            "G3": "locked",
            "G4": "locked",
        }:
            return False
        removals = event.get("artifact_head_removals")
        if not isinstance(removals, dict):
            return False
        removed_ref = removals.get("visual/contract-review-marks")
        if not isinstance(removed_ref, str) or not removed_ref:
            return False
        try:
            if (
                ArtifactReference.parse(removed_ref).kind
                != "visual-contract-review-mark-set"
            ):
                return False
            previous_event = json.loads(
                (
                    self.kernel.events_root
                    / f"r{revision - 1:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if not isinstance(previous_event, dict):
                return False
            previous_command_id = previous_event.get("command_id")
            previous_heads = previous_event.get("artifact_heads")
            current_heads = event.get("artifact_heads")
            if not isinstance(previous_heads, dict) or not isinstance(
                current_heads,
                dict,
            ):
                return False
            visual_contract_ref = previous_heads.get("visual/contract")
            if (
                not isinstance(visual_contract_ref, str)
                or not visual_contract_ref
            ):
                return False
            expected_removals = {
                slot: reference
                for slot, reference in previous_heads.items()
                if slot.startswith(("visual/", "delivery/", "chat-delivery/"))
                or slot
                in {
                    "gate/G3/confirmation",
                    "gate/G4/confirmation",
                    "project/completion",
                    "experience/retrospective/job",
                }
            }
            if removals != expected_removals:
                return False
            reopen_ref = current_heads.get("gate/G3/reopen")
            if not isinstance(reopen_ref, str) or not reopen_ref:
                return False
            expected_heads = {
                slot: reference
                for slot, reference in previous_heads.items()
                if slot not in expected_removals
            }
            expected_heads["gate/G3/reopen"] = reopen_ref
            if current_heads != expected_heads:
                return False
            reopen = self._payload(reopen_ref, "g3-reopen")
            reason = reopen.get("reason")
            reopened_at = reopen.get("reopened_at")
            if (
                reopen.get("gate") != "G3"
                or reopen.get("project_id") != state.project_id
                or reopen.get("visual_contract_ref") != visual_contract_ref
                or reopen.get("status") != "reopened"
                or not isinstance(reason, str)
                or not reason
                or reason != reason.strip()
                or not isinstance(reopened_at, str)
                or event.get("gate_evidence_refs") != [visual_contract_ref]
                or event.get("command_fingerprint")
                != fingerprint("reopen-g3", {"reason": reason})
            ):
                return False
            reopened_timestamp = datetime.fromisoformat(
                reopened_at.replace("Z", "+00:00")
            )
            return (
                reopened_timestamp.tzinfo is not None
                and previous_heads.get("visual/contract-review-marks")
                == removed_ref
                and previous_event.get("revision") == revision - 1
                and isinstance(previous_command_id, str)
                and bool(previous_command_id)
                and state.processed_commands.get(previous_command_id)
                == revision - 1
                and dict(previous_event.get("artifact_heads") or {}).get(
                    "visual/contract-review-marks",
                    "",
                )
                == removed_ref
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ContractValidationError,
        ):
            return False

    def _has_legacy_text_anchor_provenance(
        self,
        *,
        mark: dict[str, Any],
        state,
        review_session_id: str,
        session_revision: int,
    ) -> bool:
        source_revision = mark["revision"] + 1
        if source_revision > state.revision:
            return False
        try:
            event = json.loads(
                (
                    self.kernel.events_root
                    / f"r{source_revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if not isinstance(event, dict):
                return False
            command_id = event.get("command_id")
            source_ref = dict(event.get("artifact_heads") or {}).get(
                "visual/contract-review-marks",
                "",
            )
            if (
                event.get("revision") != source_revision
                or event.get("event_type")
                != "visual.contract-review-marks-saved"
                or not isinstance(command_id, str)
                or not command_id
                or state.processed_commands.get(command_id) != source_revision
                or not isinstance(source_ref, str)
                or not source_ref
            ):
                return False
            source_mark_set = validate_visual_contract_review_mark_set(
                self._payload(
                    source_ref,
                    "visual-contract-review-mark-set",
                )
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ContractValidationError,
        ):
            return False
        if (
            source_mark_set["project_id"] != state.project_id
            or source_mark_set["review_session_id"] != review_session_id
            or source_mark_set["visual_contract_ref"]
            != mark["visual_contract_ref"]
            or source_mark_set["source_version"] != mark["source_version"]
            or source_mark_set["revision"] != mark["revision"]
            or not all(
                session_revision <= item["revision"]
                <= source_mark_set["revision"]
                for item in source_mark_set["marks"]
            )
        ):
            return False
        source_mark = next(
            (
                item
                for item in source_mark_set["marks"]
                if item["mark_id"] == mark["mark_id"]
            ),
            None,
        )
        if (
            source_mark is None
            or source_mark["target_type"] != "text-range"
            or source_mark.get("anchor_representation_version")
            == CURRENT_TEXT_ANCHOR_REPRESENTATION
        ):
            return False
        comparable_source = dict(source_mark)
        comparable_source.pop("anchor_representation_version", None)
        comparable_mark = dict(mark)
        comparable_mark.pop("anchor_representation_version", None)
        if comparable_source != comparable_mark:
            return False
        submitted_marks = [
            item
            for item in source_mark_set["marks"]
            if item["revision"] == source_mark_set["revision"]
        ]
        if not any(
            item["mark_id"] == mark["mark_id"]
            for item in submitted_marks
        ):
            return False
        values = {
            "review_session_id": source_mark_set["review_session_id"],
            "source_version": source_mark_set["source_version"],
            "marks": submitted_marks,
        }
        candidate_fingerprints = {
            fingerprint("save-visual-contract-review-marks", values)
        }
        unversioned_marks = []
        for item in submitted_marks:
            unversioned = dict(item)
            unversioned.pop("anchor_representation_version", None)
            unversioned_marks.append(unversioned)
        candidate_fingerprints.add(
            fingerprint(
                "save-visual-contract-review-marks",
                {**values, "marks": unversioned_marks},
            )
        )
        event_fingerprint = event.get("command_fingerprint")
        if event_fingerprint in candidate_fingerprints:
            return True
        if (
            not isinstance(event_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", event_fingerprint) is None
            or len(submitted_marks) < 2
        ):
            return False
        try:
            previous_event = json.loads(
                (
                    self.kernel.events_root
                    / f"r{source_revision - 1:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if not isinstance(previous_event, dict):
                return False
            previous_revision = source_revision - 1
            previous_command_id = previous_event.get("command_id")
            if (
                previous_event.get("revision") != previous_revision
                or not isinstance(previous_command_id, str)
                or not previous_command_id
                or state.processed_commands.get(previous_command_id)
                != previous_revision
            ):
                return False
            previous_ref = dict(
                previous_event.get("artifact_heads") or {}
            ).get("visual/contract-review-marks", "")
            if not isinstance(previous_ref, str) or not previous_ref:
                return False
            previous_mark_set = validate_visual_contract_review_mark_set(
                self._payload(
                    previous_ref,
                    "visual-contract-review-mark-set",
                )
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ContractValidationError,
        ):
            return False
        if (
            previous_mark_set["project_id"]
            != source_mark_set["project_id"]
            or previous_mark_set["review_session_id"]
            != source_mark_set["review_session_id"]
            or previous_mark_set["visual_contract_ref"]
            != source_mark_set["visual_contract_ref"]
            or previous_mark_set["source_version"]
            != source_mark_set["source_version"]
            or not (
                session_revision <= previous_mark_set["revision"]
                < source_mark_set["revision"]
            )
            or not all(
                session_revision <= item["revision"]
                <= previous_mark_set["revision"]
                for item in previous_mark_set["marks"]
            )
        ):
            return False
        previous_ids = [
            item["mark_id"] for item in previous_mark_set["marks"]
        ]
        previous_id_set = set(previous_ids)
        submitted_ids = [
            item["mark_id"] for item in submitted_marks
        ]
        source_ids = [
            item["mark_id"] for item in source_mark_set["marks"]
        ]
        new_ids = [
            mark_id
            for mark_id in source_ids
            if mark_id not in previous_id_set
        ]
        merge_order_can_hide_input_order = (
            any(mark_id in previous_id_set for mark_id in submitted_ids)
            and source_ids == [*previous_ids, *new_ids]
        )
        if (
            not merge_order_can_hide_input_order
            or len(submitted_marks) > MAX_LEGACY_FINGERPRINT_REORDER_MARKS
        ):
            return False
        # Historical browser-v1 saves fingerprinted request order, while the
        # persisted dict-merge artifact retained existing mark positions.  The
        # original order is therefore recoverable only by checking its bounded
        # set of possible permutations against the immutable event fingerprint.
        for ordered_marks in permutations(submitted_marks):
            ordered = list(ordered_marks)
            if event_fingerprint == fingerprint(
                "save-visual-contract-review-marks",
                {**values, "marks": ordered},
            ):
                return True
            ordered_unversioned = []
            for item in ordered:
                unversioned = dict(item)
                unversioned.pop("anchor_representation_version", None)
                ordered_unversioned.append(unversioned)
            if event_fingerprint == fingerprint(
                "save-visual-contract-review-marks",
                {**values, "marks": ordered_unversioned},
            ):
                return True
        return False

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
