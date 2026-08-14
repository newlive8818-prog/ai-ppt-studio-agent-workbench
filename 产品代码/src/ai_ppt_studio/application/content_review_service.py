"""Source-bound persistence for independent content page decisions."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.domains.content.review_contracts import (
    CONTENT_PAGE_DECISIONS,
    normalize_page_decision_choice,
    validate_page_decision,
    validate_page_decision_set,
    validate_visible_copy_snapshot,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ContentWorkflowError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


PAGE_DECISION_HEAD = "content/page-decisions"
PAGE_DECISION_SET_KIND = "content-page-decision-set"
PAGE_DECISION_KIND = "content-page-decision"
VISIBLE_COPY_SNAPSHOT_KIND = "content-visible-copy-snapshot"
BLUEPRINT_HEAD = "content/blueprint"
BLUEPRINT_KIND = "content-blueprint"
PROTECTED_HEADS = (
    "content/blueprint",
    "content/acceptance",
    "feedback/governance",
    "content/change-set",
)


class ContentReviewService:
    """Save one page at a time without governance, generation, or Gate work."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def save_page_decision(
        self,
        *,
        command_id: str,
        expected_revision: int,
        source_version: str,
        review_batch_id: str,
        slide_id: str,
        decision: str,
        comment: str,
    ) -> tuple[dict[str, Any], dict[str, Any], KernelState]:
        command = self._required_text(command_id, "command_id")
        source = self._required_text(source_version, "source_version")
        batch_id = self._required_text(review_batch_id, "review_batch_id")
        target_slide_id = self._required_text(slide_id, "slide_id")
        normalized_decision, normalized_comment = (
            normalize_page_decision_choice(decision, comment)
        )
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ContractValidationError(
                "expected_revision must be a non-negative integer"
            )
        fingerprint = self._command_fingerprint(
            {
                "operation": "save-content-page-decision",
                "project_id": self.kernel.project_id,
                "source_version": source,
                "review_batch_id": batch_id,
                "slide_id": target_slide_id,
                "decision": normalized_decision,
                "comment": normalized_comment,
            }
        )

        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command in state.processed_commands:
                replay_state = self.kernel.commit(
                    command_id=command,
                    expected_revision=expected_revision,
                    event_type="content.page-decision-saved",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                return self._replay_result(command, replay_state)

            if state.revision != expected_revision:
                raise RevisionConflictError(expected_revision, state.revision)
            blueprint, slides = self._current_blueprint(state, source)
            slide = next(
                (
                    item
                    for item in slides
                    if item["slide_id"] == target_slide_id
                ),
                None,
            )
            if slide is None:
                self._conflict(
                    "The requested slide is not present in the current blueprint",
                    {
                        "source_version": source,
                        "slide_id": target_slide_id,
                    },
                )

            prior_set_ref, prior_set = self._current_decision_set(
                state=state,
                source_version=source,
                review_batch_id=batch_id,
                slides=slides,
            )
            if prior_set is not None and prior_set["status"] != "draft":
                raise ContentWorkflowError(
                    "CONTENT_PAGE_DECISION_FROZEN",
                    "CONTENT_PAGE_DECISION_FROZEN: "
                    "the current page-decision set is frozen",
                    {
                        "decision_set_ref": prior_set_ref,
                        "status": prior_set["status"],
                        "source_version": source,
                        "review_batch_id": batch_id,
                    },
                )

            prior_rows = (
                list(prior_set["decision_refs"])
                if prior_set is not None
                else []
            )
            prior_row = next(
                (
                    row
                    for row in prior_rows
                    if row["slide_id"] == target_slide_id
                ),
                None,
            )
            supersedes_ref = (
                str(prior_row["decision_ref"]) if prior_row else ""
            )
            saved_at = datetime.now(timezone.utc).isoformat()
            snapshot = validate_visible_copy_snapshot({
                "project_id": state.project_id,
                "source_version": source,
                "slide_id": target_slide_id,
                "slide_order": slide["order"],
                "slide_title_snapshot": slide["title"],
                "visible_copy": copy.deepcopy(slide["visible_copy"]),
            })
            snapshot_ref = str(
                self.kernel.artifacts.reference_for(
                    VISIBLE_COPY_SNAPSHOT_KIND, snapshot
                )
            )
            page_decision = validate_page_decision(
                {
                    "page_decision_id": str(uuid.uuid4()),
                    "review_batch_id": batch_id,
                    "project_id": state.project_id,
                    "review_type": "content",
                    "source_version": source,
                    "slide_id": target_slide_id,
                    "slide_order": slide["order"],
                    "slide_title_snapshot": slide["title"],
                    "visible_copy_snapshot_ref": snapshot_ref,
                    "decision": normalized_decision,
                    "comment": normalized_comment,
                    "saved_at": saved_at,
                    "supersedes_decision_ref": supersedes_ref,
                }
            )
            page_decision_ref = str(
                self.kernel.artifacts.reference_for(
                    PAGE_DECISION_KIND, page_decision
                )
            )
            rows_by_slide = {
                str(row["slide_id"]): dict(row) for row in prior_rows
            }
            rows_by_slide[target_slide_id] = {
                "slide_id": target_slide_id,
                "slide_order": slide["order"],
                "decision_ref": page_decision_ref,
            }
            authoritative_order = {
                item["slide_id"]: item["order"] for item in slides
            }
            rows = sorted(
                rows_by_slide.values(),
                key=lambda row: authoritative_order[str(row["slide_id"])],
            )
            decision_set = validate_page_decision_set(
                {
                    "decision_set_id": (
                        prior_set["decision_set_id"]
                        if prior_set is not None
                        else str(uuid.uuid4())
                    ),
                    "review_batch_id": batch_id,
                    "project_id": state.project_id,
                    "review_type": "content",
                    "source_version": source,
                    "expected_slide_count": len(slides),
                    "status": "draft",
                    "decision_refs": rows,
                    "updated_at": saved_at,
                }
            )

            # All validation and optimistic-revision checks precede immutable
            # object creation.  The one authoritative state mutation below is
            # the page-decision-set head commit.
            if self.kernel.load().revision != expected_revision:
                raise RevisionConflictError(
                    expected_revision, self.kernel.load().revision
                )
            before_heads = dict(state.artifact_heads)
            committed = self.kernel.commit(
                command_id=command,
                expected_revision=expected_revision,
                event_type="content.page-decision-saved",
                artifact_updates={
                    PAGE_DECISION_HEAD: (
                        PAGE_DECISION_SET_KIND,
                        decision_set,
                    )
                },
                detached_artifacts=(
                    (VISIBLE_COPY_SNAPSHOT_KIND, snapshot),
                    (PAGE_DECISION_KIND, page_decision),
                ),
                command_fingerprint=fingerprint,
            )
            self._assert_only_decision_head_changed(before_heads, committed)
            self._assert_protected_heads(before_heads, committed)
            return (
                self._page_completion(page_decision_ref, page_decision),
                self._progress(decision_set, slides),
                committed,
            )

    def _current_blueprint(
        self,
        state: KernelState,
        source_version: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        current_source = state.artifact_heads.get(BLUEPRINT_HEAD, "")
        if source_version != current_source:
            self._conflict(
                "The requested source is not the current content blueprint",
                {
                    "expected_source_version": current_source,
                    "actual_source_version": source_version,
                },
            )
        return self._resolve_blueprint(source_version)

    def _resolve_blueprint(
        self,
        source_version: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            reference = ArtifactReference.parse(source_version)
            if reference.kind != BLUEPRINT_KIND:
                raise ArtifactReferenceError(
                    "The current content blueprint head has the wrong kind"
                )
            envelope = self.kernel.artifacts.resolve(reference)
            blueprint = envelope["payload"]
        except (ArtifactReferenceError, KeyError, TypeError) as error:
            self._conflict(
                "The current content blueprint cannot be resolved safely",
                {"source_version": source_version, "reason": str(error)},
            )
        if not isinstance(blueprint, dict):
            self._conflict(
                "The current content blueprint payload is invalid",
                {"source_version": source_version},
            )
        if blueprint.get("status") != "user-reviewable":
            self._conflict(
                "The current content blueprint is not user-reviewable",
                {
                    "source_version": source_version,
                    "status": blueprint.get("status", ""),
                },
            )
        slides = self._authoritative_slides(blueprint)
        return blueprint, slides

    def _authoritative_slides(
        self, blueprint: dict[str, Any]
    ) -> list[dict[str, Any]]:
        raw_slides = blueprint.get("slides")
        if not isinstance(raw_slides, list) or not raw_slides:
            self._conflict("The current content blueprint has no valid slides", {})
        slides: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for expected_order, raw in enumerate(raw_slides, start=1):
            if not isinstance(raw, dict):
                self._conflict(
                    "The current content blueprint contains a non-object slide",
                    {"slide_order": expected_order},
                )
            slide_id = raw.get("slide_id")
            title = raw.get("title")
            order = raw.get("order")
            visible_copy = raw.get("visible_copy")
            if (
                not isinstance(slide_id, str)
                or not slide_id.strip()
                or slide_id.strip() in seen_ids
                or isinstance(order, bool)
                or order != expected_order
                or not isinstance(title, str)
                or not title.strip()
                or not isinstance(visible_copy, list)
            ):
                self._conflict(
                    "The current content blueprint slide identity is invalid",
                    {"slide_order": expected_order, "slide_id": slide_id},
                )
            normalized = copy.deepcopy(raw)
            normalized["slide_id"] = slide_id.strip()
            normalized["title"] = title.strip()
            seen_ids.add(normalized["slide_id"])
            slides.append(normalized)
        return slides

    def _current_decision_set(
        self,
        *,
        state: KernelState,
        source_version: str,
        review_batch_id: str,
        slides: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any] | None]:
        decision_set_ref = state.artifact_heads.get(PAGE_DECISION_HEAD, "")
        if not decision_set_ref:
            return "", None
        try:
            reference = ArtifactReference.parse(decision_set_ref)
            if reference.kind != PAGE_DECISION_SET_KIND:
                raise ArtifactReferenceError(
                    "The page-decision head has the wrong kind"
                )
            payload = validate_page_decision_set(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            ContentWorkflowError,
            KeyError,
            TypeError,
        ) as error:
            self._conflict(
                "The current page-decision set cannot be resolved safely",
                {"decision_set_ref": decision_set_ref, "reason": str(error)},
            )
        if payload["project_id"] != state.project_id:
            self._conflict(
                "The current page-decision set belongs to another project",
                {"decision_set_ref": decision_set_ref},
            )
        if payload["source_version"] != source_version:
            _historical_blueprint, historical_slides = (
                self._resolve_blueprint(payload["source_version"])
            )
            self._validate_decision_set_lineage(
                decision_set_ref=decision_set_ref,
                payload=payload,
                slides=historical_slides,
                project_id=state.project_id,
            )
            return decision_set_ref, None
        if payload["review_batch_id"] != review_batch_id:
            self._conflict(
                "The current source already has a different review batch",
                {
                    "decision_set_ref": decision_set_ref,
                    "expected_review_batch_id": payload["review_batch_id"],
                    "actual_review_batch_id": review_batch_id,
                },
            )
        self._validate_decision_set_lineage(
            decision_set_ref=decision_set_ref,
            payload=payload,
            slides=slides,
            project_id=state.project_id,
        )
        return decision_set_ref, payload

    def _validate_decision_set_lineage(
        self,
        *,
        decision_set_ref: str,
        payload: dict[str, Any],
        slides: list[dict[str, Any]],
        project_id: str,
    ) -> None:
        if payload["expected_slide_count"] != len(slides):
            self._conflict(
                "The page-decision set slide count differs from the blueprint",
                {
                    "decision_set_ref": decision_set_ref,
                    "expected_slide_count": len(slides),
                    "actual_slide_count": payload["expected_slide_count"],
                },
            )
        authoritative = {slide["slide_id"]: slide for slide in slides}
        for row in payload["decision_refs"]:
            slide = authoritative.get(row["slide_id"])
            if slide is None or row["slide_order"] != slide["order"]:
                self._conflict(
                    "The page-decision set does not match blueprint slide identity",
                    {"decision_set_ref": decision_set_ref, "row": row},
                )
            decision_payload = self._resolve_decision(row["decision_ref"])
            expected = {
                "project_id": project_id,
                "review_batch_id": payload["review_batch_id"],
                "source_version": payload["source_version"],
                "slide_id": row["slide_id"],
                "slide_order": row["slide_order"],
            }
            if any(
                decision_payload.get(field) != value
                for field, value in expected.items()
            ) or decision_payload["slide_title_snapshot"] != slide["title"]:
                self._conflict(
                    "A current page decision has invalid lineage",
                    {
                        "decision_set_ref": decision_set_ref,
                        "decision_ref": row["decision_ref"],
                    },
                )
            self._resolve_snapshot(
                decision_payload["visible_copy_snapshot_ref"],
                decision_payload,
                slide,
            )

    def _resolve_decision(self, reference_value: str) -> dict[str, Any]:
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != PAGE_DECISION_KIND:
                raise ArtifactReferenceError("PageDecision kind is invalid")
            return validate_page_decision(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            ContentWorkflowError,
            KeyError,
            TypeError,
        ) as error:
            self._conflict(
                "A page decision cannot be resolved safely",
                {"decision_ref": reference_value, "reason": str(error)},
            )

    def _resolve_snapshot(
        self,
        reference_value: str,
        decision: dict[str, Any],
        source_slide: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != VISIBLE_COPY_SNAPSHOT_KIND:
                raise ArtifactReferenceError(
                    "Visible-copy snapshot kind is invalid"
                )
            payload = validate_visible_copy_snapshot(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
        ) as error:
            self._conflict(
                "A visible-copy snapshot cannot be resolved safely",
                {"snapshot_ref": reference_value, "reason": str(error)},
            )
        canonical = validate_visible_copy_snapshot({
            "project_id": decision["project_id"],
            "source_version": decision["source_version"],
            "slide_id": decision["slide_id"],
            "slide_order": decision["slide_order"],
            "slide_title_snapshot": decision["slide_title_snapshot"],
            "visible_copy": copy.deepcopy(source_slide["visible_copy"]),
        })
        if payload != canonical:
            self._conflict(
                "A page snapshot differs from its immutable blueprint source",
                {"snapshot_ref": reference_value},
            )
        return payload

    def _progress(
        self,
        decision_set: dict[str, Any],
        slides: list[dict[str, Any]],
    ) -> dict[str, Any]:
        current_by_slide: dict[str, dict[str, Any]] = {}
        for row in decision_set["decision_refs"]:
            current_by_slide[row["slide_id"]] = self._resolve_decision(
                row["decision_ref"]
            )
        counts = {value: 0 for value in CONTENT_PAGE_DECISIONS}
        completed = 0
        saved_comment_count = 0
        next_incomplete_slide_id = ""
        for slide in slides:
            decision = current_by_slide.get(slide["slide_id"])
            if decision is None or not decision["completed"]:
                if not next_incomplete_slide_id:
                    next_incomplete_slide_id = slide["slide_id"]
                continue
            completed += 1
            counts[decision["decision"]] += 1
            if decision["comment"]:
                saved_comment_count += 1
        total = len(slides)
        return {
            "total": total,
            "completed": completed,
            "remaining": total - completed,
            "saved_comment_count": saved_comment_count,
            "next_incomplete_slide_id": next_incomplete_slide_id,
            "counts": {
                "approved": counts["approved"],
                "modify": counts["modify"],
                "evidence": counts["evidence"],
                "merge_or_delete": counts["merge-or-delete"],
            },
        }

    @staticmethod
    def _page_completion(
        reference: str,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "page_decision_ref": reference,
            "review_batch_id": decision["review_batch_id"],
            "source_version": decision["source_version"],
            "slide_id": decision["slide_id"],
            "slide_order": decision["slide_order"],
            "decision": decision["decision"],
            "comment": decision["comment"],
            "completed": decision["completed"],
            "visible_copy_snapshot_ref": decision[
                "visible_copy_snapshot_ref"
            ],
            "supersedes_decision_ref": decision[
                "supersedes_decision_ref"
            ],
        }

    def _replay_result(
        self,
        command_id: str,
        state: KernelState,
    ) -> tuple[dict[str, Any], dict[str, Any], KernelState]:
        revision = state.processed_commands[command_id]
        try:
            event = json.loads(
                (
                    self.kernel.events_root / f"r{revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if event.get("event_type") != "content.page-decision-saved":
                raise ValueError("Processed command is not a page-decision save")
            decision_set_ref = event["artifact_heads"][PAGE_DECISION_HEAD]
            reference = ArtifactReference.parse(decision_set_ref)
            if reference.kind != PAGE_DECISION_SET_KIND:
                raise ValueError("Processed decision-set kind is invalid")
            decision_set = validate_page_decision_set(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            source_reference = ArtifactReference.parse(
                decision_set["source_version"]
            )
            if source_reference.kind != BLUEPRINT_KIND:
                raise ValueError("Processed source kind is invalid")
            blueprint = self.kernel.artifacts.resolve(source_reference)["payload"]
            slides = self._authoritative_slides(blueprint)
            fingerprint_payload = event.get("command_fingerprint")
            if not isinstance(fingerprint_payload, str) or not fingerprint_payload:
                raise ValueError("Processed command fingerprint is missing")
            # The historical event-owned set preserves the exact current row
            # at that command revision even after later decisions replace it.
            candidates = [
                (row["decision_ref"], self._resolve_decision(row["decision_ref"]))
                for row in decision_set["decision_refs"]
            ]
            matching = [
                item
                for item in candidates
                if self._command_fingerprint(
                    {
                        "operation": "save-content-page-decision",
                        "project_id": self.kernel.project_id,
                        "source_version": item[1]["source_version"],
                        "review_batch_id": item[1]["review_batch_id"],
                        "slide_id": item[1]["slide_id"],
                        "decision": item[1]["decision"],
                        "comment": item[1]["comment"],
                    }
                )
                == fingerprint_payload
            ]
            if len(matching) != 1:
                raise ValueError(
                    "Processed page-decision result is ambiguous or unavailable"
                )
            decision_ref, decision = matching[0]
        except (
            ArtifactReferenceError,
            ContractValidationError,
            ContentWorkflowError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise ContractValidationError(
                "Processed page-decision receipt is unavailable"
            ) from error
        return (
            self._page_completion(decision_ref, decision),
            self._progress(decision_set, slides),
            state,
        )

    @staticmethod
    def _assert_only_decision_head_changed(
        before_heads: dict[str, str],
        after: KernelState,
    ) -> None:
        changed = {
            slot
            for slot in set(before_heads) | set(after.artifact_heads)
            if before_heads.get(slot) != after.artifact_heads.get(slot)
        }
        if changed != {PAGE_DECISION_HEAD}:
            raise RuntimeError(
                "Page-decision save changed unexpected artifact heads: "
                + ", ".join(sorted(changed))
            )

    @staticmethod
    def _assert_protected_heads(
        before_heads: dict[str, str],
        after: KernelState,
    ) -> None:
        for slot in PROTECTED_HEADS:
            if before_heads.get(slot) != after.artifact_heads.get(slot):
                raise RuntimeError(
                    f"Page-decision save mutated protected head {slot}"
                )

    @staticmethod
    def _command_fingerprint(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ContractValidationError(f"{field} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _conflict(message: str, details: dict[str, Any]) -> None:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            f"CONTENT_REVIEW_CONFLICT: {message}",
            details,
        )
