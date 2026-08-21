"""Source-bound persistence for independent content page decisions."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.domains.content.review_contracts import (
    CONTENT_PAGE_DECISIONS,
    normalize_page_decision_choice,
    validate_content_batch_revision_plan,
    validate_content_blueprint,
    validate_content_review_batch,
    validate_content_review_batch_withdrawal,
    validate_page_decision,
    validate_page_decision_set,
    validate_persisted_page_decision,
    validate_persisted_page_decision_set,
    validate_visible_copy_snapshot,
)
from ai_ppt_studio.domains.content.contracts import (
    REQUIRED_CONTENT_REVIEW_ROLES,
    aggregate_content_reviews,
    validate_content_review,
    validate_content_stage,
)
from ai_ppt_studio.domains.content.framework import (
    validate_framework_confirmation,
    validate_framework_draft,
    validate_full_deck_expansion_authorization,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContractValidationError,
    ContentWorkflowError,
    GateBlockedError,
    ProposalOnlyIdentityViolationError,
    RevisionConflictError,
)
from ai_ppt_studio.application.scoped_confirmation import (
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import (
    CONFIRMATION_LEDGER_SLOT,
    ProjectKernel,
)


PAGE_DECISION_HEAD = "content/page-decisions"
PAGE_DECISION_SET_KIND = "content-page-decision-set"
PAGE_DECISION_KIND = "content-page-decision"
VISIBLE_COPY_SNAPSHOT_KIND = "content-visible-copy-snapshot"
BLUEPRINT_HEAD = "content/blueprint"
BLUEPRINT_KIND = "content-blueprint"
REVIEW_BATCH_HEAD = "content/review-batch"
REVIEW_BATCH_KIND = "content-review-batch"
REVIEW_BATCH_SUBMISSION_SCOPE = "content-review-batch-submission"
REVIEW_BATCH_WITHDRAWAL_HEAD = "content/review-batch-withdrawal"
REVIEW_BATCH_WITHDRAWAL_KIND = "content-review-batch-withdrawal"
REVIEW_BATCH_WITHDRAWAL_SCOPE = "content-review-batch-withdrawal"
PUBLIC_SCOPED_CONFIRMATION_FIELDS = (
    "project_id",
    "project_root",
    "scope_kind",
    "scope_id",
    "source_version",
    "evidence_refs",
    "challenge_id",
    "challenge_revision",
)
MAX_DECISION_LINEAGE_DEPTH = 1024
CONTENT_REVIEW_BATCH_FOLLOW_UP = (
    "读取已冻结的内容审核批次，结合当前完整蓝图、目录框架、证据地图和跨页关系，"
    "先提出整套修改方案；在用户确认方案前，不生成 ContentChangeSet 或新蓝图。"
)
CONTENT_SIDEBAR_PHASES = (
    "content-producing",
    "content-hard-gate-review",
    "full-deck-review-ready",
    "review-batch-submitted",
    "batch-plan-proposed",
    "batch-plan-confirmed",
)
PROTECTED_HEADS = (
    "content/blueprint",
    "content/acceptance",
    "feedback/governance",
    "content/change-set",
)
CONTENT_WORKFLOW_LINEAGE_FIELDS = (
    "framework_ref",
    "framework_confirmation_ref",
    "full_deck_expansion_authorization_ref",
)
CONTENT_ACCEPTANCE_FIELDS = frozenset(
    {
        "target_ref",
        "review_record_refs",
        "required_roles",
        "all_applicable_checks",
        "overall_result",
        "passed_at",
        "supersedes_blueprint_ref",
        "review_batch_ref",
        "batch_revision_plan_ref",
        "batch_plan_confirmation_ref",
        *CONTENT_WORKFLOW_LINEAGE_FIELDS,
    }
)
CONFIRMATION_FIELDS = frozenset(
    {
        "project_id",
        "scope_kind",
        "scope_id",
        "source_version",
        "evidence_refs",
        "challenge_id",
        "challenge_revision",
        "user_action_ref",
        "user_message_ref",
        "confirmation_identity_type",
        "host_assertion_sha256",
        "confirmed_at",
        "framework_ref",
        "framework_revision",
        "challenge_identity",
    }
)
AUTHORIZATION_FIELDS = frozenset(
    {*CONFIRMATION_FIELDS, "framework_confirmation_ref"}
)
PUBLICATION_EVENT_REQUIRED_FIELDS = frozenset(
    {
        "transaction_id",
        "command_id",
        "event_type",
        "revision",
        "artifact_heads",
        "artifact_head_removals",
        "confirmation_consumptions",
        "confirmation_artifact_bindings",
        "gate_updates",
        "gate_evidence_refs",
    }
)


class ContentReviewService:
    """Save one page at a time without governance, generation, or Gate work."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def current_decision_set(self, source_version: str) -> dict[str, Any]:
        """Project the current source's decision set without inheriting history."""

        source = self._required_text(source_version, "source_version")
        state = self.kernel.load()
        _blueprint, slides = self._current_blueprint(state, source)
        head = state.artifact_heads.get(PAGE_DECISION_HEAD, "")
        if head:
            reference = ArtifactReference.parse(head)
            if reference.kind != PAGE_DECISION_SET_KIND:
                self._conflict(
                    "The page-decision head has the wrong kind",
                    {"decision_set_ref": head},
                )
            payload = validate_persisted_page_decision_set(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            if payload["source_version"] == source:
                _ref, current = self._current_decision_set(
                    state=state,
                    source_version=source,
                    review_batch_id=payload["review_batch_id"],
                    slides=slides,
                )
                if current is not None:
                    return current
        return {
            "decision_set_id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{state.project_id}:{source}:fresh-decision-set",
                )
            ),
            "review_batch_id": "",
            "project_id": state.project_id,
            "review_type": "content",
            "source_version": source,
            "expected_slide_count": len(slides),
            "status": "draft",
            "decision_refs": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def progress(self, source_version: str) -> dict[str, Any]:
        """Return progress for only the requested current blueprint version."""

        source = self._required_text(source_version, "source_version")
        state = self.kernel.load()
        _blueprint, slides = self._current_blueprint(state, source)
        decision_set = self.current_decision_set(source)
        if not decision_set["decision_refs"]:
            return {
                "total": len(slides),
                "completed": 0,
                "remaining": len(slides),
                "saved_comment_count": 0,
                "next_incomplete_slide_id": slides[0]["slide_id"],
                "counts": {
                    "approved": 0,
                    "modify": 0,
                    "evidence": 0,
                    "merge_or_delete": 0,
                },
            }
        return self._progress(decision_set, slides)

    def content_sidebar_projection(self) -> dict[str, Any]:
        """Project content-production progress or the complete reviewable deck."""

        state = self.kernel.load()
        blueprint_ref = state.artifact_heads.get(BLUEPRINT_HEAD, "")
        mission_summary = self._mission_summary(state)
        if not blueprint_ref:
            phase = (
                "content-hard-gate-review"
                if state.artifact_heads.get("content/draft")
                else "content-producing"
            )
            return {
                "display_policy": "content-sidebar-progress",
                "phase": phase,
                "project_id": state.project_id,
                "revision": state.revision,
                "mission_summary": mission_summary,
                "next_action": "continue-content-production",
            }

        blueprint, slides = self._current_blueprint(state, blueprint_ref)
        decision_set = self.current_decision_set(blueprint_ref)
        progress = self.progress(blueprint_ref)
        decisions_by_slide: dict[str, dict[str, Any]] = {}
        for row in decision_set["decision_refs"]:
            decision = self._resolve_decision(str(row["decision_ref"]))
            decisions_by_slide[str(decision["slide_id"])] = decision

        batch_ref, batch = self._current_source_batch(state, blueprint_ref)
        batch_status = str(batch.get("status") or "draft")
        phase_by_batch_status = {
            "submitted": "review-batch-submitted",
            "plan-proposed": "batch-plan-proposed",
            "plan-confirmed": "batch-plan-confirmed",
        }
        phase = phase_by_batch_status.get(
            batch_status, "full-deck-review-ready"
        )
        frozen = decision_set.get("status") != "draft" or batch_status in {
            "submitted",
            "plan-proposed",
            "plan-confirmed",
            "applied",
            "superseded",
        }
        projected_slides: list[dict[str, Any]] = []
        for slide in slides:
            projected = self._sidebar_slide(slide)
            decision = decisions_by_slide.get(str(slide["slide_id"]))
            projected["decision_state"] = {
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
            }
            projected_slides.append(projected)

        plan_ref, plan = self._current_source_plan(state, blueprint_ref)
        confirmation_ref = (
            state.artifact_heads.get("content/batch-plan-confirmation", "")
            if plan_ref
            else ""
        )
        return {
            "display_policy": "content-sidebar-full-deck",
            "phase": phase,
            "project_id": state.project_id,
            "revision": state.revision,
            "mission_summary": mission_summary,
            "material_mode": str(
                blueprint.get("material_mode") or "mixed-evidence"
            ),
            "chapters": self._sidebar_chapters(slides),
            "source_version": blueprint_ref,
            "slides": projected_slides,
            "review_progress": progress,
            "decision_set": {
                "decision_set_id": decision_set["decision_set_id"],
                "review_batch_id": decision_set["review_batch_id"],
                "status": decision_set["status"],
            },
            "current_batch": {
                "batch_ref": batch_ref,
                "review_batch_id": str(batch.get("review_batch_id") or ""),
                "status": batch_status,
            },
            "current_plan": {
                "plan_ref": plan_ref,
                "confirmation_ref": confirmation_ref,
                "status": batch_status
                if batch_status in {"plan-proposed", "plan-confirmed"}
                else "",
                "requires_blueprint_revision": bool(
                    plan.get("requires_blueprint_revision")
                ),
            },
            "previous_round": self._previous_round(blueprint),
            "next_action": self._sidebar_next_action(phase),
        }

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
            batch_ref, current_batch = self._current_review_batch(
                state=state,
                source_version=source,
                review_batch_id=batch_id,
                slides=slides,
                allow_missing=True,
            )
            if current_batch is not None and current_batch["status"] in {
                "submitted",
                "plan-proposed",
                "plan-confirmed",
                "applied",
            }:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_FROZEN",
                    "CONTENT_REVIEW_BATCH_FROZEN: the current review batch is frozen",
                    {
                        "batch_ref": batch_ref,
                        "status": current_batch["status"],
                        "source_version": source,
                        "review_batch_id": batch_id,
                    },
                )
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

    def submission_context(
        self,
        *,
        source_version: str,
        review_batch_id: str,
    ) -> dict[str, Any]:
        """Return one read-only, revision-bound complete-batch challenge."""

        source = self._required_text(source_version, "source_version")
        batch_id = self._required_text(review_batch_id, "review_batch_id")
        state = self.kernel.load()
        internal = self._submission_context_from_state(
            state=state,
            source_version=source,
            review_batch_id=batch_id,
        )
        return self._public_submission_context(internal)

    def submit_review_batch(
        self,
        *,
        command_id: str,
        expected_revision: int,
        source_version: str,
        review_batch_id: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, str, KernelState]:
        """Freeze one complete decision set without starting downstream work."""

        command = self._required_text(command_id, "command_id")
        source = self._required_text(source_version, "source_version")
        batch_id = self._required_text(review_batch_id, "review_batch_id")
        assertion = self._required_text(
            host_confirmation_assertion, "host_confirmation_assertion"
        )
        fingerprint = self._command_fingerprint(
            {
                "operation": "submit-content-review-batch",
                "project_id": self.kernel.project_id,
                "source_version": source,
                "review_batch_id": batch_id,
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
                "host_confirmation_assertion_sha256": hashlib.sha256(
                    assertion.encode("utf-8")
                ).hexdigest(),
            }
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command,
                    expected_revision=expected_revision,
                    event_type="content.review-batch-submitted",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                return self._replay_batch_submission(command, replay)
            self._require_expected_revision(expected_revision, state.revision)
            current = self._submission_context_from_state(
                state=state,
                source_version=source,
                review_batch_id=batch_id,
            )
            scoped, consumptions = self.confirmations.confirmation_payload(
                current=current,
                source_version=source,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=assertion,
            )
            identity = str(
                scoped.get("user_action_ref")
                or scoped.get("user_message_ref")
                or ""
            )
            current_batch_ref = str(current.get("current_batch_ref") or "")
            batch = validate_content_review_batch(
                {
                    "review_batch_id": batch_id,
                    "project_id": state.project_id,
                    "review_type": "content",
                    "source_version": source,
                    "decision_set_ref": current["decision_set_ref"],
                    "page_snapshot_refs": current["page_snapshot_refs"],
                    "decision_refs": current["ordered_decision_refs"],
                    "expected_slide_count": current["expected_slide_count"],
                    "counts": current["counts"],
                    "status": "submitted",
                    "submitted_at": scoped["confirmed_at"],
                    "submitted_by": identity,
                    "supersedes_ref": current_batch_ref,
                    **scoped,
                },
                authoritative_slides=current["authoritative_slides"],
                decisions_by_ref=current["decisions_by_ref"],
            )
            before_heads = dict(state.artifact_heads)
            try:
                committed = self.kernel.commit(
                    command_id=command,
                    expected_revision=expected_revision,
                    event_type="content.review-batch-submitted",
                    artifact_updates={
                        REVIEW_BATCH_HEAD: (REVIEW_BATCH_KIND, batch)
                    },
                    confirmation_consumptions=consumptions,
                    command_fingerprint=fingerprint,
                )
            except ConfirmationTransactionError as error:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_CONFLICT",
                    "The trusted batch-submission transaction was rejected",
                    {
                        "scope_kind": REVIEW_BATCH_SUBMISSION_SCOPE,
                        "scope_id": current["scope_id"],
                        "kernel_error_code": error.code,
                        "revision": self.kernel.load().revision,
                    },
                ) from None
            changed = {
                slot
                for slot in set(before_heads) | set(committed.artifact_heads)
                if before_heads.get(slot) != committed.artifact_heads.get(slot)
            }
            if changed != {REVIEW_BATCH_HEAD, CONFIRMATION_LEDGER_SLOT}:
                raise RuntimeError(
                    "Review-batch submission changed unexpected heads: "
                    + ", ".join(sorted(changed))
                )
            self._assert_protected_heads(before_heads, committed)
            return (
                committed.artifact_heads[REVIEW_BATCH_HEAD],
                CONTENT_REVIEW_BATCH_FOLLOW_UP,
                committed,
            )

    def withdrawal_context(
        self,
        *,
        source_version: str,
        review_batch_id: str,
    ) -> dict[str, Any]:
        """Return the exact action context for a submitted pre-plan batch."""

        source = self._required_text(source_version, "source_version")
        batch_id = self._required_text(review_batch_id, "review_batch_id")
        state = self.kernel.load()
        internal = self._withdrawal_context_from_state(
            state=state,
            source_version=source,
            review_batch_id=batch_id,
        )
        return self._public_withdrawal_context(internal)

    def _withdrawal_context_from_state(
        self,
        *,
        state: KernelState,
        source_version: str,
        review_batch_id: str,
    ) -> dict[str, Any]:
        source = source_version
        batch_id = review_batch_id
        _blueprint, slides = self._current_blueprint(state, source)
        batch_ref, batch = self._current_review_batch(
            state=state,
            source_version=source,
            review_batch_id=batch_id,
            slides=slides,
            allow_missing=False,
        )
        if batch is None or batch["status"] != "submitted":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_NOT_WITHDRAWABLE",
                "CONTENT_REVIEW_BATCH_NOT_WITHDRAWABLE: only an exact submitted batch can be withdrawn",
                {
                    "batch_ref": batch_ref,
                    "status": batch["status"] if batch else "missing",
                    "source_version": source,
                    "review_batch_id": batch_id,
                },
            )
        decision_set_ref = batch["decision_set_ref"]
        if state.artifact_heads.get(PAGE_DECISION_HEAD) != decision_set_ref:
            self._conflict(
                "The submitted batch decision set is no longer current",
                {
                    "batch_ref": batch_ref,
                    "expected_decision_set_ref": decision_set_ref,
                    "actual_decision_set_ref": state.artifact_heads.get(
                        PAGE_DECISION_HEAD, ""
                    ),
                },
            )
        ordered_decision_refs = list(batch["decision_refs"])
        base = self.confirmations.context(
            scope_kind=REVIEW_BATCH_WITHDRAWAL_SCOPE,
            scope_id=batch_id,
            source_version=source,
            evidence_refs=[
                source,
                batch_ref,
                decision_set_ref,
                *ordered_decision_refs,
            ],
        )
        if base["challenge_revision"] != state.revision:
            raise RevisionConflictError(state.revision, base["challenge_revision"])
        return {
            **base,
            "review_batch_id": batch_id,
            "submitted_batch_ref": batch_ref,
            "decision_set_ref": decision_set_ref,
            "ordered_decision_refs": ordered_decision_refs,
            "page_snapshot_refs": list(batch["page_snapshot_refs"]),
            "expected_slide_count": batch["expected_slide_count"],
            "counts": copy.deepcopy(batch["counts"]),
            "authoritative_slides": copy.deepcopy(slides),
            "submitted_batch": copy.deepcopy(batch),
        }

    def withdraw_review_batch(
        self,
        *,
        command_id: str,
        expected_revision: int,
        source_version: str,
        review_batch_id: str,
        reason: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, KernelState]:
        """Withdraw a submitted pre-plan batch into one fresh draft lineage."""

        command = self._required_text(command_id, "command_id")
        source = self._required_text(source_version, "source_version")
        batch_id = self._required_text(review_batch_id, "review_batch_id")
        normalized_reason = self._required_text(reason, "reason")
        assertion = self._required_text(
            host_confirmation_assertion, "host_confirmation_assertion"
        )
        fingerprint = self._command_fingerprint(
            {
                "operation": "withdraw-content-review-batch",
                "project_id": self.kernel.project_id,
                "source_version": source,
                "review_batch_id": batch_id,
                "reason": normalized_reason,
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
                "host_confirmation_assertion_sha256": hashlib.sha256(
                    assertion.encode("utf-8")
                ).hexdigest(),
            }
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command,
                    expected_revision=expected_revision,
                    event_type="content.review-batch-withdrawn",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                return self._replay_batch_withdrawal(command, replay)
            self._require_expected_revision(expected_revision, state.revision)
            current = self._withdrawal_context_from_state(
                state=state,
                source_version=source,
                review_batch_id=batch_id,
            )
            if current["challenge_revision"] != state.revision:
                raise RevisionConflictError(
                    state.revision, current["challenge_revision"]
                )
            scoped, consumptions = self.confirmations.confirmation_payload(
                current=current,
                source_version=source,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=assertion,
            )
            identity = str(
                scoped.get("user_action_ref")
                or scoped.get("user_message_ref")
                or ""
            )
            withdrawn_at = str(scoped["confirmed_at"])
            new_batch_id = str(uuid.uuid4())
            old_decisions = [
                (
                    reference,
                    self._resolve_decision(reference),
                )
                for reference in current["ordered_decision_refs"]
            ]
            cloned_decisions: list[dict[str, Any]] = []
            cloned_rows: list[dict[str, Any]] = []
            for old_ref, old_decision in old_decisions:
                clone = validate_page_decision(
                    {
                        **old_decision,
                        "page_decision_id": str(uuid.uuid4()),
                        "review_batch_id": new_batch_id,
                        "saved_at": withdrawn_at,
                        "supersedes_decision_ref": old_ref,
                    }
                )
                clone_ref = str(
                    self.kernel.artifacts.reference_for(
                        PAGE_DECISION_KIND, clone
                    )
                )
                cloned_decisions.append(clone)
                cloned_rows.append(
                    {
                        "slide_id": clone["slide_id"],
                        "slide_order": clone["slide_order"],
                        "decision_ref": clone_ref,
                    }
                )
            new_set = validate_page_decision_set(
                {
                    "decision_set_id": str(uuid.uuid4()),
                    "review_batch_id": new_batch_id,
                    "project_id": state.project_id,
                    "review_type": "content",
                    "source_version": source,
                    "expected_slide_count": current["expected_slide_count"],
                    "status": "draft",
                    "decision_refs": cloned_rows,
                    "updated_at": withdrawn_at,
                }
            )
            new_set_ref = str(
                self.kernel.artifacts.reference_for(
                    PAGE_DECISION_SET_KIND, new_set
                )
            )
            submitted_batch_ref = str(current["submitted_batch_ref"])
            submitted_batch = copy.deepcopy(current["submitted_batch"])
            superseded_batch = validate_content_review_batch(
                {
                    **submitted_batch,
                    "status": "superseded",
                    "supersedes_ref": submitted_batch_ref,
                },
                authoritative_slides=current["authoritative_slides"],
                decisions_by_ref={
                    reference: decision
                    for reference, decision in old_decisions
                },
                prior_submitted=submitted_batch,
            )
            superseded_batch_ref = str(
                self.kernel.artifacts.reference_for(
                    REVIEW_BATCH_KIND, superseded_batch
                )
            )
            cloned_by_ref = {
                row["decision_ref"]: decision
                for row, decision in zip(cloned_rows, cloned_decisions)
            }
            draft_batch = validate_content_review_batch(
                {
                    "review_batch_id": new_batch_id,
                    "project_id": state.project_id,
                    "review_type": "content",
                    "source_version": source,
                    "decision_set_ref": new_set_ref,
                    "page_snapshot_refs": list(
                        current["page_snapshot_refs"]
                    ),
                    "decision_refs": [
                        row["decision_ref"] for row in cloned_rows
                    ],
                    "expected_slide_count": current[
                        "expected_slide_count"
                    ],
                    "counts": copy.deepcopy(current["counts"]),
                    "status": "draft",
                    "submitted_at": "",
                    "submitted_by": "",
                    "supersedes_ref": "",
                    "scope_kind": "",
                    "scope_id": "",
                    "evidence_refs": [],
                    "challenge_id": "",
                    "challenge_revision": 0,
                    "user_action_ref": "",
                    "user_message_ref": "",
                    "confirmation_identity_type": "",
                    "host_assertion_sha256": "",
                    "confirmed_at": "",
                },
                authoritative_slides=current["authoritative_slides"],
                decisions_by_ref=cloned_by_ref,
            )
            withdrawal = validate_content_review_batch_withdrawal(
                {
                    "withdrawal_id": str(uuid.uuid4()),
                    "project_id": state.project_id,
                    "review_batch_id": batch_id,
                    "source_version": source,
                    "submitted_batch_ref": submitted_batch_ref,
                    "superseded_batch_ref": superseded_batch_ref,
                    "replacement_review_batch_id": new_batch_id,
                    "reason": normalized_reason,
                    "withdrawn_at": withdrawn_at,
                    "withdrawn_by": identity,
                    **scoped,
                }
            )
            before_heads = dict(state.artifact_heads)
            try:
                committed = self.kernel.commit(
                    command_id=command,
                    expected_revision=expected_revision,
                    event_type="content.review-batch-withdrawn",
                    artifact_updates={
                        REVIEW_BATCH_WITHDRAWAL_HEAD: (
                            REVIEW_BATCH_WITHDRAWAL_KIND,
                            withdrawal,
                        ),
                        REVIEW_BATCH_HEAD: (REVIEW_BATCH_KIND, draft_batch),
                        PAGE_DECISION_HEAD: (
                            PAGE_DECISION_SET_KIND,
                            new_set,
                        ),
                    },
                    detached_artifacts=(
                        *tuple(
                            (PAGE_DECISION_KIND, decision)
                            for decision in cloned_decisions
                        ),
                        (REVIEW_BATCH_KIND, superseded_batch),
                    ),
                    confirmation_consumptions=consumptions,
                    command_fingerprint=fingerprint,
                )
            except ConfirmationTransactionError as error:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_CONFLICT",
                    "The trusted batch-withdrawal transaction was rejected",
                    {
                        "scope_kind": REVIEW_BATCH_WITHDRAWAL_SCOPE,
                        "scope_id": batch_id,
                        "kernel_error_code": error.code,
                        "revision": self.kernel.load().revision,
                    },
                ) from None
            changed = {
                slot
                for slot in set(before_heads) | set(committed.artifact_heads)
                if before_heads.get(slot) != committed.artifact_heads.get(slot)
            }
            expected_changed = {
                REVIEW_BATCH_WITHDRAWAL_HEAD,
                REVIEW_BATCH_HEAD,
                PAGE_DECISION_HEAD,
                CONFIRMATION_LEDGER_SLOT,
            }
            if changed != expected_changed:
                raise RuntimeError(
                    "Review-batch withdrawal changed unexpected heads: "
                    + ", ".join(sorted(changed))
                )
            self._assert_protected_heads(before_heads, committed)
            return new_batch_id, committed

    def _submission_context_from_state(
        self,
        *,
        state: KernelState,
        source_version: str,
        review_batch_id: str,
    ) -> dict[str, Any]:
        _blueprint, slides = self._current_blueprint(state, source_version)
        batch_ref, batch = self._current_review_batch(
            state=state,
            source_version=source_version,
            review_batch_id=review_batch_id,
            slides=slides,
            allow_missing=True,
        )
        if batch is not None and batch["status"] != "draft":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "CONTENT_REVIEW_BATCH_FROZEN: the current review batch is frozen",
                {
                    "batch_ref": batch_ref,
                    "status": batch["status"],
                    "source_version": source_version,
                    "review_batch_id": review_batch_id,
                },
            )
        decision_set_ref, decision_set = self._current_decision_set(
            state=state,
            source_version=source_version,
            review_batch_id=review_batch_id,
            slides=slides,
        )
        if decision_set is None:
            self._incomplete(slides, {})
        replacement_signal = bool(
            state.artifact_heads.get(REVIEW_BATCH_WITHDRAWAL_HEAD, "")
        ) or self._decision_set_has_cross_batch_lineage(decision_set)
        if batch is None and replacement_signal:
            self._conflict(
                "A replacement decision set requires its exact current draft batch",
                {
                    "decision_set_ref": decision_set_ref,
                    "review_batch_id": review_batch_id,
                    "withdrawal_ref": state.artifact_heads.get(
                        REVIEW_BATCH_WITHDRAWAL_HEAD, ""
                    ),
                },
            )
        if batch is not None:
            self._validate_replacement_draft_lineage(
                state=state,
                batch_ref=batch_ref,
                batch=batch,
                decision_set_ref=decision_set_ref,
                decision_set=decision_set,
                slides=slides,
            )
        decisions_by_ref = {
            row["decision_ref"]: self._resolve_decision(row["decision_ref"])
            for row in decision_set["decision_refs"]
        }
        progress = self._progress(decision_set, slides)
        if progress["remaining"]:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_INCOMPLETE",
                "CONTENT_REVIEW_BATCH_INCOMPLETE: all pages need a completed decision",
                {**progress, "decision_set_ref": decision_set_ref},
            )
        ordered_decision_refs = [
            row["decision_ref"] for row in decision_set["decision_refs"]
        ]
        if len(ordered_decision_refs) != len(slides):
            self._incomplete(
                slides,
                {decision["slide_id"]: decision for decision in decisions_by_ref.values()},
                decision_set_ref=decision_set_ref,
            )
        page_snapshot_refs = [
            decisions_by_ref[reference]["visible_copy_snapshot_ref"]
            for reference in ordered_decision_refs
        ]
        base = self.confirmations.context(
            scope_kind=REVIEW_BATCH_SUBMISSION_SCOPE,
            scope_id=f"{review_batch_id}:{source_version}",
            source_version=source_version,
            evidence_refs=[
                source_version,
                decision_set_ref,
                *ordered_decision_refs,
            ],
        )
        if base["challenge_revision"] != state.revision:
            raise RevisionConflictError(state.revision, base["challenge_revision"])
        return {
            **base,
            "review_batch_id": review_batch_id,
            "decision_set_ref": decision_set_ref,
            "ordered_decision_refs": ordered_decision_refs,
            "page_snapshot_refs": page_snapshot_refs,
            "expected_slide_count": len(slides),
            "counts": copy.deepcopy(progress["counts"]),
            "current_batch_ref": batch_ref,
            "authoritative_slides": copy.deepcopy(slides),
            "decisions_by_ref": copy.deepcopy(decisions_by_ref),
        }

    @staticmethod
    def _public_submission_context(internal: dict[str, Any]) -> dict[str, Any]:
        return {
            field: copy.deepcopy(internal[field])
            for field in PUBLIC_SCOPED_CONFIRMATION_FIELDS
        }

    @staticmethod
    def _public_withdrawal_context(internal: dict[str, Any]) -> dict[str, Any]:
        return {
            field: copy.deepcopy(internal[field])
            for field in PUBLIC_SCOPED_CONFIRMATION_FIELDS
        }

    def _incomplete(
        self,
        slides: list[dict[str, Any]],
        decisions_by_slide: dict[str, dict[str, Any]],
        *,
        decision_set_ref: str = "",
    ) -> None:
        completed = sum(
            1
            for slide in slides
            if decisions_by_slide.get(slide["slide_id"], {}).get("completed")
        )
        next_incomplete = next(
            (
                slide["slide_id"]
                for slide in slides
                if not decisions_by_slide.get(slide["slide_id"], {}).get(
                    "completed"
                )
            ),
            "",
        )
        raise ContentWorkflowError(
            "CONTENT_REVIEW_BATCH_INCOMPLETE",
            "CONTENT_REVIEW_BATCH_INCOMPLETE: all pages need a completed decision",
            {
                "total": len(slides),
                "completed": completed,
                "remaining": len(slides) - completed,
                "next_incomplete_slide_id": next_incomplete,
                "decision_set_ref": decision_set_ref,
            },
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
        return self._resolve_blueprint(
            source_version,
            state=state,
            require_current=True,
        )

    def _resolve_blueprint(
        self,
        source_version: str,
        *,
        state: KernelState,
        require_current: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            reference = ArtifactReference.parse(source_version)
            if reference.kind != BLUEPRINT_KIND:
                raise ArtifactReferenceError(
                    "The current content blueprint head has the wrong kind"
                )
            envelope = self.kernel.artifacts.resolve(reference)
            raw_blueprint = envelope["payload"]
            blueprint = validate_content_blueprint(raw_blueprint)
            if blueprint != raw_blueprint:
                raise ContractValidationError(
                    "ContentBlueprint payload is not canonical"
                )
            self._validate_blueprint_chain(
                blueprint=blueprint,
                state=state,
            )
            self._validate_blueprint_publication(
                source_version=source_version,
                blueprint=blueprint,
                state=state,
                require_current=require_current,
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            ContentWorkflowError,
            GateBlockedError,
            ProposalOnlyIdentityViolationError,
            json.JSONDecodeError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            self._conflict(
                "The current content blueprint cannot be resolved safely",
                {"source_version": source_version, "reason": str(error)},
            )
        slides = self._authoritative_slides(blueprint)
        return blueprint, slides

    def _validate_blueprint_chain(
        self,
        *,
        blueprint: dict[str, Any],
        state: KernelState,
    ) -> None:
        lineage = {
            field: blueprint[field]
            for field in CONTENT_WORKFLOW_LINEAGE_FIELDS
        }
        stage_definitions = (
            (
                "strategy",
                "strategy_ref",
                "presales-content-strategy",
                "presales-content-strategy",
            ),
            (
                "claim-map",
                "claim_evidence_map_ref",
                "claim-evidence-map",
                "claim-evidence-map",
            ),
            (
                "argument-map",
                "argument_map_ref",
                "deck-argument-map",
                "deck-argument-map",
            ),
            (
                "slide-draft-set",
                "draft_ref",
                "slide-draft-set",
                "slide-draft-set",
            ),
        )
        stage_payloads: dict[str, dict[str, Any]] = {}
        for stage, ref_field, kind, artifact_type in stage_definitions:
            raw = self._resolve_payload(blueprint[ref_field], kind)
            normalized = validate_content_stage(stage, copy.deepcopy(raw))
            if normalized != raw or raw.get("artifact_type") != artifact_type:
                raise ContractValidationError(
                    f"{ref_field} does not contain a canonical {stage} payload"
                )
            self._require_lineage(raw, lineage, ref_field)
            stage_payloads[stage] = raw

        strategy = stage_payloads["strategy"]
        claim_map = stage_payloads["claim-map"]
        argument_map = stage_payloads["argument-map"]
        draft = stage_payloads["slide-draft-set"]
        if (
            claim_map.get("strategy_ref") != blueprint["strategy_ref"]
            or argument_map.get("strategy_ref") != blueprint["strategy_ref"]
            or argument_map.get("claim_evidence_map_ref")
            != blueprint["claim_evidence_map_ref"]
            or draft.get("argument_map_ref") != blueprint["argument_map_ref"]
        ):
            raise ContractValidationError(
                "ContentBlueprint upstream stage references are inconsistent"
            )
        identity_mode = strategy.get("content_identity_mode")
        if identity_mode not in {"material-backed", "proposal-only"} or any(
            payload.get("content_identity_mode") != identity_mode
            for payload in (claim_map, argument_map, draft)
        ):
            raise ContractValidationError(
                "ContentBlueprint content identity mode is inconsistent"
            )
        mission_confirmation_ref = self._exact_reference(
            strategy.get("mission_confirmation_ref"),
            "mission-confirmation",
        )
        self._resolve_payload(mission_confirmation_ref, "mission-confirmation")
        if any(
            payload.get("mission_confirmation_ref")
            != mission_confirmation_ref
            for payload in (claim_map, argument_map, draft)
        ):
            raise ContractValidationError(
                "ContentBlueprint mission confirmation lineage is inconsistent"
            )
        self._resolve_payload(strategy.get("mission_ref"), "mission-draft")
        if identity_mode == "material-backed":
            material_ref = self._exact_reference(
                strategy.get("material_inventory_ref"),
                "material-inventory",
            )
            self._resolve_payload(material_ref, "material-inventory")
            for claim in claim_map["claims"]:
                for reference in claim["evidence_refs"]:
                    if reference != material_ref:
                        raise ContractValidationError(
                            "Claim evidence does not bind the strategy material"
                        )
            for slide in draft["slides"]:
                for reference in slide["source_refs"]:
                    if reference != material_ref:
                        raise ContractValidationError(
                            "Slide source does not bind the strategy material"
                        )

        if (
            blueprint["strategy"] != strategy
            or blueprint["claim_evidence_map"] != claim_map
            or blueprint["argument_map"] != argument_map
            or blueprint["slides"] != draft["slides"]
        ):
            raise ContractValidationError(
                "ContentBlueprint embedded content differs from its references"
            )

        framework = self._resolve_payload(
            lineage["framework_ref"], "content-framework-draft"
        )
        if validate_framework_draft(copy.deepcopy(framework)) != framework:
            raise ContractValidationError(
                "Content framework payload is not canonical"
            )
        if framework.get("mission_confirmation_ref") != mission_confirmation_ref:
            raise ContractValidationError(
                "Content framework binds a different mission confirmation"
            )
        confirmation = self._resolve_payload(
            lineage["framework_confirmation_ref"],
            "content-framework-confirmation",
        )
        authorization = self._resolve_payload(
            lineage["full_deck_expansion_authorization_ref"],
            "full-deck-expansion-authorization",
        )
        self._validate_framework_confirmation_payload(
            confirmation,
            framework_ref=lineage["framework_ref"],
            mission_confirmation_ref=mission_confirmation_ref,
            project_id=state.project_id,
        )
        self._validate_expansion_authorization_payload(
            authorization,
            framework_ref=lineage["framework_ref"],
            confirmation_ref=lineage["framework_confirmation_ref"],
            mission_confirmation_ref=mission_confirmation_ref,
            project_id=state.project_id,
        )
        acceptance = self._resolve_payload(
            blueprint["acceptance_ref"], "content-acceptance"
        )
        self._validate_acceptance(
            acceptance,
            draft_ref=blueprint["draft_ref"],
            lineage=lineage,
        )

    def _validate_framework_confirmation_payload(
        self,
        payload: dict[str, Any],
        *,
        framework_ref: str,
        mission_confirmation_ref: str,
        project_id: str,
    ) -> None:
        if set(payload) != CONFIRMATION_FIELDS:
            raise ContractValidationError(
                "FrameworkConfirmation has an invalid formal schema"
            )
        normalized = validate_framework_confirmation(copy.deepcopy(payload))
        expected = {
            "project_id": project_id,
            "framework_ref": framework_ref,
        }
        if (
            any(normalized.get(key) != value for key, value in expected.items())
            or any(payload.get(key) != value for key, value in normalized.items())
        ):
            raise ContractValidationError(
                "FrameworkConfirmation binding is inconsistent"
            )
        self._validate_confirmation_common(payload)
        if (
            payload["scope_kind"] != "content-framework-confirmation"
            or payload["scope_id"] != framework_ref
            or payload["source_version"] != framework_ref
            or payload["evidence_refs"]
            != [framework_ref, mission_confirmation_ref]
        ):
            raise ContractValidationError(
                "FrameworkConfirmation scope is inconsistent"
            )

    def _validate_expansion_authorization_payload(
        self,
        payload: dict[str, Any],
        *,
        framework_ref: str,
        confirmation_ref: str,
        mission_confirmation_ref: str,
        project_id: str,
    ) -> None:
        if set(payload) != AUTHORIZATION_FIELDS:
            raise ContractValidationError(
                "FullDeckExpansionAuthorization has an invalid formal schema"
            )
        normalized = validate_full_deck_expansion_authorization(
            copy.deepcopy(payload)
        )
        expected = {
            "project_id": project_id,
            "framework_ref": framework_ref,
            "framework_confirmation_ref": confirmation_ref,
        }
        if (
            any(normalized.get(key) != value for key, value in expected.items())
            or any(payload.get(key) != value for key, value in normalized.items())
        ):
            raise ContractValidationError(
                "FullDeckExpansionAuthorization binding is inconsistent"
            )
        self._validate_confirmation_common(payload)
        if (
            payload["scope_kind"]
            != "content-full-deck-expansion-authorization"
            or payload["scope_id"] != confirmation_ref
            or payload["source_version"] != framework_ref
            or payload["evidence_refs"]
            != [framework_ref, confirmation_ref, mission_confirmation_ref]
        ):
            raise ContractValidationError(
                "FullDeckExpansionAuthorization scope is inconsistent"
            )

    def _validate_confirmation_common(self, payload: dict[str, Any]) -> None:
        challenge_revision = payload.get("challenge_revision")
        if (
            isinstance(challenge_revision, bool)
            or not isinstance(challenge_revision, int)
            or challenge_revision < 1
            or payload.get("framework_revision") != challenge_revision
            or payload.get("challenge_identity") != payload.get("challenge_id")
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(payload.get("challenge_id") or "")
            )
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(payload.get("host_assertion_sha256") or ""),
            )
        ):
            raise ContractValidationError(
                "Confirmation challenge binding is invalid"
            )
        identity_type = payload.get("confirmation_identity_type")
        action_ref = payload.get("user_action_ref")
        message_ref = payload.get("user_message_ref")
        if (
            identity_type not in {"host-action", "verified-message"}
            or not isinstance(action_ref, str)
            or not isinstance(message_ref, str)
            or (identity_type == "host-action" and (not action_ref or message_ref))
            or (
                identity_type == "verified-message"
                and (not message_ref or action_ref)
            )
        ):
            raise ContractValidationError(
                "Confirmation identity binding is invalid"
            )
        self._iso_timestamp(payload.get("confirmed_at"), "confirmed_at")

    def _validate_acceptance(
        self,
        payload: dict[str, Any],
        *,
        draft_ref: str,
        lineage: dict[str, str],
    ) -> None:
        if set(payload) != CONTENT_ACCEPTANCE_FIELDS:
            raise ContractValidationError(
                "ContentAcceptance has an invalid formal schema"
            )
        self._require_lineage(payload, lineage, "acceptance_ref")
        if payload.get("target_ref") != draft_ref:
            raise ContractValidationError(
                "ContentAcceptance targets a different draft"
            )
        refs = payload.get("review_record_refs")
        if (
            not isinstance(refs, list)
            or len(refs) != len(REQUIRED_CONTENT_REVIEW_ROLES)
        ):
            raise ContractValidationError(
                "ContentAcceptance review references are incomplete"
            )
        records: list[tuple[str, dict[str, Any]]] = []
        for expected_role, reference in zip(REQUIRED_CONTENT_REVIEW_ROLES, refs):
            review = self._resolve_payload(reference, "content-review-record")
            normalized = validate_content_review(copy.deepcopy(review))
            if normalized != review:
                raise ContractValidationError(
                    "Content review record is not canonical"
                )
            self._require_lineage(review, lineage, "review_record_ref")
            if (
                review.get("reviewer_role") != expected_role
                or review.get("target_ref") != draft_ref
                or review.get("input_version") != draft_ref
            ):
                raise ContractValidationError(
                    "Content review record lineage is inconsistent"
                )
            records.append((reference, review))
        aggregated = aggregate_content_reviews(draft_ref, records)
        if any(payload.get(key) != value for key, value in aggregated.items()):
            raise ContractValidationError(
                "ContentAcceptance differs from its review aggregation"
            )
        if self._iso_timestamp(payload.get("passed_at"), "passed_at") != payload.get(
            "passed_at"
        ):
            raise ContractValidationError(
                "ContentAcceptance passed_at is not canonical"
            )

    def _validate_blueprint_publication(
        self,
        *,
        source_version: str,
        blueprint: dict[str, Any],
        state: KernelState,
        require_current: bool,
    ) -> None:
        if require_current and (
            state.artifact_heads.get(BLUEPRINT_HEAD) != source_version
        ):
            raise ContractValidationError(
                "ContentBlueprint is not the current published head"
            )
        expected_heads = {
            "content/blueprint": source_version,
            "content/acceptance": blueprint["acceptance_ref"],
            "content/strategy": blueprint["strategy_ref"],
            "content/claim-map": blueprint["claim_evidence_map_ref"],
            "content/argument-map": blueprint["argument_map_ref"],
            "content/draft": blueprint["draft_ref"],
            "content/framework-draft": blueprint["framework_ref"],
            "content/framework-confirmation": blueprint[
                "framework_confirmation_ref"
            ],
            "content/full-deck-expansion-authorization": blueprint[
                "full_deck_expansion_authorization_ref"
            ],
        }
        matches: list[dict[str, Any]] = []
        transaction_ids: set[str] = set()
        final_transaction_id = ""
        for revision in range(1, state.revision + 1):
            path = self.kernel.events_root / f"r{revision:08d}.json"
            event = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(event, dict) or event.get("revision") != revision:
                raise ContractValidationError(
                    "Project event chronology is incomplete or corrupt"
                )
            command_id = event.get("command_id")
            transaction_id = self._canonical_uuid(
                event.get("transaction_id"),
                "event transaction_id",
            )
            if (
                not isinstance(command_id, str)
                or not command_id
                or state.processed_commands.get(command_id) != revision
                or not isinstance(event.get("artifact_heads"), dict)
            ):
                raise ContractValidationError(
                    "Project event receipt is incomplete or corrupt"
                )
            if transaction_id in transaction_ids:
                raise ContractValidationError(
                    "Project event transaction identities are not unique"
                )
            transaction_ids.add(transaction_id)
            final_transaction_id = transaction_id
            if (
                event.get("event_type") == "content.accepted-internally"
                and event["artifact_heads"].get(BLUEPRINT_HEAD)
                == source_version
            ):
                matches.append(event)
        state_transaction_id = self._canonical_uuid(
            state.last_transaction_id,
            "state last_transaction_id",
        )
        if final_transaction_id != state_transaction_id:
            raise ContractValidationError(
                "Final event transaction does not match project state"
            )
        if len(matches) != 1:
            raise ContractValidationError(
                "ContentBlueprint lacks one unambiguous publication receipt"
            )
        publication = matches[0]
        if (
            not PUBLICATION_EVENT_REQUIRED_FIELDS.issubset(publication)
            or not isinstance(publication["artifact_head_removals"], dict)
            or not isinstance(publication["confirmation_consumptions"], dict)
            or not isinstance(
                publication["confirmation_artifact_bindings"], dict
            )
            or not isinstance(publication["gate_updates"], dict)
            or not isinstance(publication["gate_evidence_refs"], list)
        ):
            raise ContractValidationError(
                "ContentBlueprint publication receipt is incomplete"
            )
        if any(
            publication["artifact_heads"].get(slot) != reference
            for slot, reference in expected_heads.items()
        ) or publication.get("gate_updates", {}).get("G0") != "user-reviewable":
            raise ContractValidationError(
                "ContentBlueprint publication receipt has inconsistent heads"
            )
        if publication.get("gate_evidence_refs") != [
            blueprint["acceptance_ref"],
            source_version,
        ]:
            raise ContractValidationError(
                "ContentBlueprint publication evidence is inconsistent"
            )

    def _resolve_payload(self, reference_value: object, kind: str) -> dict[str, Any]:
        reference_text = self._exact_reference(reference_value, kind)
        payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(reference_text)
        )["payload"]
        if not isinstance(payload, dict):
            raise ContractValidationError(
                f"{kind} artifact payload must be an object"
            )
        return copy.deepcopy(payload)

    @staticmethod
    def _exact_reference(reference_value: object, kind: str) -> str:
        if not isinstance(reference_value, str) or not reference_value:
            raise ContractValidationError(f"{kind} reference is required")
        reference = ArtifactReference.parse(reference_value)
        if reference.kind != kind:
            raise ContractValidationError(
                f"Artifact reference must have kind {kind}"
            )
        return str(reference)

    @staticmethod
    def _require_lineage(
        payload: dict[str, Any],
        lineage: dict[str, str],
        label: str,
    ) -> None:
        if any(payload.get(field) != value for field, value in lineage.items()):
            raise ContractValidationError(
                f"{label} has inconsistent framework lineage"
            )

    @staticmethod
    def _iso_timestamp(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ContractValidationError(f"{field} must be an ISO timestamp")
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise ContractValidationError(
                f"{field} must be an ISO timestamp"
            ) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ContractValidationError(f"{field} must include a timezone")
        return text

    @staticmethod
    def _canonical_uuid(value: object, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise ContractValidationError(f"{field} must be a canonical UUID")
        try:
            parsed = uuid.UUID(value)
        except (AttributeError, ValueError) as error:
            raise ContractValidationError(
                f"{field} must be a canonical UUID"
            ) from error
        canonical = str(parsed)
        if value != canonical:
            raise ContractValidationError(f"{field} must be a canonical UUID")
        return canonical

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
            raw_payload = self.kernel.artifacts.resolve(reference)["payload"]
            payload = validate_persisted_page_decision_set(
                raw_payload
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
                self._resolve_blueprint(
                    payload["source_version"],
                    state=state,
                    require_current=False,
                )
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

    def _current_review_batch(
        self,
        *,
        state: KernelState,
        source_version: str,
        review_batch_id: str,
        slides: list[dict[str, Any]],
        allow_missing: bool,
    ) -> tuple[str, dict[str, Any] | None]:
        batch_ref = state.artifact_heads.get(REVIEW_BATCH_HEAD, "")
        if not batch_ref:
            if allow_missing:
                return "", None
            self._conflict("A current content review batch is required", {})
        batch = self._resolve_review_batch_ref(
            batch_ref,
            state=state,
            slides=(
                slides
                if self._batch_source_hint(batch_ref) == source_version
                else None
            ),
        )
        if batch["source_version"] != source_version:
            self._resolve_blueprint(
                batch["source_version"], state=state, require_current=False
            )
            if allow_missing:
                return batch_ref, None
            self._conflict(
                "The current review batch belongs to another source",
                {
                    "batch_ref": batch_ref,
                    "expected_source_version": source_version,
                    "actual_source_version": batch["source_version"],
                },
            )
        if batch["review_batch_id"] != review_batch_id:
            self._conflict(
                "The current source already has a different review batch",
                {
                    "batch_ref": batch_ref,
                    "expected_review_batch_id": batch["review_batch_id"],
                    "actual_review_batch_id": review_batch_id,
                },
            )
        return batch_ref, batch

    def _validate_replacement_draft_lineage(
        self,
        *,
        state: KernelState,
        batch_ref: str,
        batch: dict[str, Any],
        decision_set_ref: str,
        decision_set: dict[str, Any],
        slides: list[dict[str, Any]],
    ) -> None:
        """Revalidate every immutable edge inherited by a withdrawn draft."""

        try:
            if batch["status"] != "draft":
                raise ContractValidationError(
                    "A replacement review batch must remain draft"
                )
            withdrawal_ref = state.artifact_heads.get(
                REVIEW_BATCH_WITHDRAWAL_HEAD, ""
            )
            withdrawal_reference = ArtifactReference.parse(withdrawal_ref)
            if withdrawal_reference.kind != REVIEW_BATCH_WITHDRAWAL_KIND:
                raise ArtifactReferenceError(
                    "Replacement draft lacks a current withdrawal receipt"
                )
            withdrawal_raw = self.kernel.artifacts.resolve(
                withdrawal_reference
            )["payload"]
            withdrawal = validate_content_review_batch_withdrawal(
                withdrawal_raw
            )
            if withdrawal != withdrawal_raw:
                raise ContractValidationError(
                    "Withdrawal receipt is not canonical"
                )
            self._validate_withdrawal_confirmation(
                withdrawal_ref=withdrawal_ref,
                withdrawal=withdrawal,
                state=state,
            )
            if (
                withdrawal["project_id"] != state.project_id
                or withdrawal["source_version"] != batch["source_version"]
                or withdrawal["replacement_review_batch_id"]
                != batch["review_batch_id"]
                or decision_set["project_id"] != state.project_id
                or decision_set["source_version"] != batch["source_version"]
                or decision_set["review_batch_id"]
                != batch["review_batch_id"]
                or decision_set["expected_slide_count"]
                != batch["expected_slide_count"]
            ):
                raise ContractValidationError(
                    "Replacement draft does not match its withdrawal receipt"
                )

            withdrawal_events: list[dict[str, Any]] = []
            for revision in range(1, state.revision + 1):
                event_path = self.kernel.events_root / f"r{revision:08d}.json"
                event = json.loads(event_path.read_text(encoding="utf-8"))
                if (
                    isinstance(event, dict)
                    and event.get("revision") == revision
                    and event.get("event_type")
                    == "content.review-batch-withdrawn"
                    and isinstance(event.get("artifact_heads"), dict)
                    and event["artifact_heads"].get(
                        REVIEW_BATCH_WITHDRAWAL_HEAD
                    )
                    == withdrawal_ref
                ):
                    withdrawal_events.append(event)
            if len(withdrawal_events) != 1:
                raise ContractValidationError(
                    "Withdrawal receipt lacks one unambiguous event"
                )
            withdrawal_heads = withdrawal_events[0]["artifact_heads"]
            if (
                withdrawal_heads.get(REVIEW_BATCH_HEAD) != batch_ref
                or withdrawal_heads.get(PAGE_DECISION_HEAD)
                != batch["decision_set_ref"]
            ):
                raise ContractValidationError(
                    "Replacement draft differs from its withdrawal event"
                )

            submitted_ref = withdrawal["submitted_batch_ref"]
            submitted = self._resolve_review_batch_ref(
                submitted_ref,
                state=state,
                slides=slides,
            )
            superseded_ref = withdrawal["superseded_batch_ref"]
            superseded = self._resolve_review_batch_ref(
                superseded_ref,
                state=state,
                slides=slides,
            )
            validate_content_review_batch(
                superseded,
                prior_submitted=submitted,
            )
            if (
                submitted["status"] != "submitted"
                or superseded["status"] != "superseded"
                or superseded["supersedes_ref"] != submitted_ref
                or submitted["decision_refs"] != superseded["decision_refs"]
                or withdrawal["evidence_refs"]
                != [
                    submitted["source_version"],
                    submitted_ref,
                    submitted["decision_set_ref"],
                    *submitted["decision_refs"],
                ]
            ):
                raise ContractValidationError(
                    "Submitted and superseded withdrawal lineage is invalid"
                )

            original_set = self._resolve_decision_set_reference(
                batch["decision_set_ref"]
            )
            if (
                original_set["project_id"] != state.project_id
                or original_set["source_version"] != batch["source_version"]
                or original_set["review_batch_id"]
                != batch["review_batch_id"]
                or [
                    row["decision_ref"]
                    for row in original_set["decision_refs"]
                ]
                != batch["decision_refs"]
                or len(decision_set["decision_refs"])
                != len(batch["decision_refs"])
            ):
                raise ContractValidationError(
                    "Replacement draft decision-set lineage is invalid"
                )

            for index, (
                slide,
                old_ref,
                clone_ref,
                current_row,
            ) in enumerate(
                zip(
                    slides,
                    submitted["decision_refs"],
                    batch["decision_refs"],
                    decision_set["decision_refs"],
                ),
                start=1,
            ):
                expected_identity = {
                    "project_id": state.project_id,
                    "source_version": batch["source_version"],
                    "slide_id": slide["slide_id"],
                    "slide_order": index,
                }
                old_decision = self._resolve_decision(old_ref)
                clone = self._resolve_decision(clone_ref)
                if (
                    any(
                        old_decision.get(field) != value
                        or clone.get(field) != value
                        for field, value in expected_identity.items()
                    )
                    or clone["review_batch_id"] != batch["review_batch_id"]
                    or clone["supersedes_decision_ref"] != old_ref
                    or current_row["slide_id"] != slide["slide_id"]
                    or current_row["slide_order"] != index
                    or any(
                        clone[field] != old_decision[field]
                        for field in (
                            "slide_title_snapshot",
                            "visible_copy_snapshot_ref",
                            "decision",
                            "comment",
                            "completed",
                        )
                    )
                ):
                    raise ContractValidationError(
                        "A replacement clone differs from its submitted decision"
                    )
                self._validate_decision_lineage(
                    start_ref=old_ref,
                    expected_identity=expected_identity,
                )
                self._validate_decision_lineage(
                    start_ref=current_row["decision_ref"],
                    expected_identity={
                        **expected_identity,
                        "review_batch_id": batch["review_batch_id"],
                    },
                    required_ancestor_ref=clone_ref,
                )
        except ContentWorkflowError:
            raise
        except (
            ArtifactReferenceError,
            ConfirmationTransactionError,
            ContractValidationError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._conflict(
                "The replacement review-batch lineage cannot be resolved safely",
                {
                    "batch_ref": batch_ref,
                    "decision_set_ref": decision_set_ref,
                    "reason": str(error),
                },
            )

    def _decision_set_has_cross_batch_lineage(
        self,
        decision_set: dict[str, Any],
    ) -> bool:
        expected_batch_id = decision_set["review_batch_id"]
        for row in decision_set["decision_refs"]:
            reference = row["decision_ref"]
            seen: set[str] = set()
            for _depth in range(MAX_DECISION_LINEAGE_DEPTH):
                if not reference or reference in seen:
                    break
                seen.add(reference)
                decision = self._resolve_decision(reference)
                if decision["review_batch_id"] != expected_batch_id:
                    return True
                reference = decision["supersedes_decision_ref"]
            if reference in seen:
                self._conflict(
                    "Page-decision lineage is cyclic",
                    {"decision_ref": row["decision_ref"]},
                )
            if reference:
                self._conflict(
                    "Page-decision lineage exceeds the maximum depth",
                    {"decision_ref": row["decision_ref"]},
                )
        return False

    def _validate_decision_lineage(
        self,
        *,
        start_ref: str,
        expected_identity: dict[str, Any],
        required_ancestor_ref: str = "",
    ) -> None:
        reference = start_ref
        seen: set[str] = set()
        for _depth in range(MAX_DECISION_LINEAGE_DEPTH):
            if not reference or reference in seen:
                break
            seen.add(reference)
            decision = self._resolve_decision(reference)
            if any(
                decision.get(field) != value
                for field, value in expected_identity.items()
            ):
                raise ContractValidationError(
                    "A page-decision lineage identity is inconsistent"
                )
            if required_ancestor_ref and reference == required_ancestor_ref:
                return
            reference = decision["supersedes_decision_ref"]
        if reference in seen:
            raise ContractValidationError("Page-decision lineage is cyclic")
        if reference:
            raise ContractValidationError(
                "Page-decision lineage exceeds the maximum depth"
            )
        if required_ancestor_ref:
            raise ContractValidationError(
                "Page-decision lineage lacks the required inherited clone"
            )

    def _batch_source_hint(self, batch_ref: str) -> str:
        try:
            reference = ArtifactReference.parse(batch_ref)
            if reference.kind != REVIEW_BATCH_KIND:
                raise ArtifactReferenceError("Review-batch head kind is invalid")
            payload = self.kernel.artifacts.resolve(reference)["payload"]
            if not isinstance(payload, dict):
                raise TypeError("Review-batch payload is not an object")
            source = payload.get("source_version")
            if not isinstance(source, str) or not source:
                raise ValueError("Review-batch source is missing")
            return source
        except (
            ArtifactReferenceError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            self._conflict(
                "The current review batch cannot be resolved safely",
                {"batch_ref": batch_ref, "reason": str(error)},
            )

    def _resolve_review_batch_ref(
        self,
        batch_ref: str,
        *,
        state: KernelState,
        slides: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        try:
            reference = ArtifactReference.parse(batch_ref)
            if reference.kind != REVIEW_BATCH_KIND:
                raise ArtifactReferenceError("Review-batch kind is invalid")
            raw = self.kernel.artifacts.resolve(reference)["payload"]
            structural = validate_content_review_batch(raw)
            source_slides = slides
            if source_slides is None:
                _blueprint, source_slides = self._resolve_blueprint(
                    structural["source_version"],
                    state=state,
                    require_current=False,
                )
            decisions = {
                decision_ref: self._resolve_decision(decision_ref)
                for decision_ref in structural["decision_refs"]
            }
            batch = validate_content_review_batch(
                raw,
                authoritative_slides=source_slides,
                decisions_by_ref=decisions,
            )
            if batch["project_id"] != state.project_id:
                raise ContractValidationError(
                    "Review batch belongs to another project"
                )
            decision_set = self._resolve_decision_set_reference(
                batch["decision_set_ref"]
            )
            if (
                decision_set["project_id"] != state.project_id
                or decision_set["review_batch_id"] != batch["review_batch_id"]
                or decision_set["source_version"] != batch["source_version"]
                or decision_set["expected_slide_count"]
                != batch["expected_slide_count"]
                or [
                    row["decision_ref"]
                    for row in decision_set["decision_refs"]
                ]
                != batch["decision_refs"]
            ):
                raise ContractValidationError(
                    "Review batch differs from its decision-set source"
                )
            if batch["status"] not in {"draft", "ready"}:
                self._validate_review_batch_confirmation(
                    batch_ref=batch_ref,
                    batch=batch,
                    state=state,
                )
        except (
            ArtifactReferenceError,
            ConfirmationTransactionError,
            ContractValidationError,
            ContentWorkflowError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            self._conflict(
                "The current review batch cannot be resolved safely",
                {"batch_ref": batch_ref, "reason": str(error)},
            )
        return batch

    def _resolve_decision_set_reference(self, reference_value: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(reference_value)
        if reference.kind != PAGE_DECISION_SET_KIND:
            raise ArtifactReferenceError("Decision-set reference kind is invalid")
        return validate_persisted_page_decision_set(
            self.kernel.artifacts.resolve(reference)["payload"]
        )

    def _validate_review_batch_confirmation(
        self,
        *,
        batch_ref: str,
        batch: dict[str, Any],
        state: KernelState,
    ) -> None:
        challenge_body = {
            "project_id": state.project_id,
            "project_root": str(self.kernel.project_root),
            "scope_kind": batch["scope_kind"],
            "scope_id": batch["scope_id"],
            "source_version": batch["source_version"],
            "evidence_refs": batch["evidence_refs"],
            "challenge_revision": batch["challenge_revision"],
        }
        if self.confirmations.challenge_id(challenge_body) != batch["challenge_id"]:
            raise ContractValidationError(
                "Review-batch confirmation challenge is inconsistent"
            )
        identity = batch["user_action_ref"] or batch["user_message_ref"]
        expected_owner = f"{batch['scope_kind']}:{batch['scope_id']}"
        bound_ref = self.kernel.confirmation_artifact_binding(identity)
        if batch["status"] == "submitted":
            expected_binding = batch_ref
        else:
            expected_binding = self._submitted_ancestor_ref(batch)
        if (
            self.kernel.confirmation_owner(identity) != expected_owner
            or bound_ref != expected_binding
        ):
            raise ContractValidationError(
                "Review-batch confirmation ledger binding is invalid"
            )

    def _submitted_ancestor_ref(self, batch: dict[str, Any]) -> str:
        reference = batch.get("supersedes_ref", "")
        seen: set[str] = set()
        while reference:
            if reference in seen:
                raise ContractValidationError("Review-batch lifecycle is cyclic")
            seen.add(reference)
            parsed = ArtifactReference.parse(reference)
            if parsed.kind != REVIEW_BATCH_KIND:
                raise ArtifactReferenceError(
                    "Review-batch lifecycle reference kind is invalid"
                )
            raw = self.kernel.artifacts.resolve(parsed)["payload"]
            ancestor = validate_content_review_batch(raw)
            validate_content_review_batch(
                batch,
                prior_submitted=ancestor,
            )
            if ancestor["status"] == "submitted":
                return reference
            reference = ancestor["supersedes_ref"]
        raise ContractValidationError(
            "Review-batch lifecycle lacks a submitted ancestor"
        )

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
            return validate_persisted_page_decision(
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
            _blueprint, slides = self._resolve_blueprint(
                decision_set["source_version"],
                state=state,
                require_current=False,
            )
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

    def _replay_batch_submission(
        self,
        command_id: str,
        state: KernelState,
    ) -> tuple[str, str, KernelState]:
        revision = state.processed_commands[command_id]
        try:
            event = json.loads(
                (
                    self.kernel.events_root / f"r{revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if event.get("event_type") != "content.review-batch-submitted":
                raise ValueError("Processed command is not a batch submission")
            batch_ref = event["artifact_heads"][REVIEW_BATCH_HEAD]
            batch = self._resolve_review_batch_ref(
                batch_ref,
                state=state,
                slides=None,
            )
            if batch["status"] != "submitted":
                raise ValueError("Processed submission batch is not submitted")
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
                "Processed review-batch submission receipt is unavailable"
            ) from error
        return batch_ref, CONTENT_REVIEW_BATCH_FOLLOW_UP, state

    def _replay_batch_withdrawal(
        self,
        command_id: str,
        state: KernelState,
    ) -> tuple[str, KernelState]:
        revision = state.processed_commands[command_id]
        try:
            event = json.loads(
                (
                    self.kernel.events_root / f"r{revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if event.get("event_type") != "content.review-batch-withdrawn":
                raise ValueError("Processed command is not a batch withdrawal")
            withdrawal_ref = event["artifact_heads"][
                REVIEW_BATCH_WITHDRAWAL_HEAD
            ]
            reference = ArtifactReference.parse(withdrawal_ref)
            if reference.kind != REVIEW_BATCH_WITHDRAWAL_KIND:
                raise ArtifactReferenceError(
                    "Processed withdrawal kind is invalid"
                )
            withdrawal = validate_content_review_batch_withdrawal(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            self._validate_withdrawal_confirmation(
                withdrawal_ref=withdrawal_ref,
                withdrawal=withdrawal,
                state=state,
            )
            replacement_batch_id = withdrawal[
                "replacement_review_batch_id"
            ]
            replacement_ref = event["artifact_heads"][REVIEW_BATCH_HEAD]
            replacement = self._resolve_review_batch_ref(
                replacement_ref,
                state=state,
                slides=None,
            )
            if (
                replacement["status"] != "draft"
                or replacement["review_batch_id"] != replacement_batch_id
            ):
                raise ValueError(
                    "Processed withdrawal replacement batch is invalid"
                )
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
                "Processed review-batch withdrawal receipt is unavailable"
            ) from error
        return replacement_batch_id, state

    def _validate_withdrawal_confirmation(
        self,
        *,
        withdrawal_ref: str,
        withdrawal: dict[str, Any],
        state: KernelState,
    ) -> None:
        challenge_body = {
            "project_id": state.project_id,
            "project_root": str(self.kernel.project_root),
            "scope_kind": withdrawal["scope_kind"],
            "scope_id": withdrawal["scope_id"],
            "source_version": withdrawal["source_version"],
            "evidence_refs": withdrawal["evidence_refs"],
            "challenge_revision": withdrawal["challenge_revision"],
        }
        identity = (
            withdrawal["user_action_ref"]
            or withdrawal["user_message_ref"]
        )
        expected_owner = (
            f"{withdrawal['scope_kind']}:{withdrawal['scope_id']}"
        )
        try:
            owner = self.kernel.confirmation_owner(identity)
            binding = self.kernel.confirmation_artifact_binding(identity)
        except ConfirmationTransactionError as error:
            raise ContractValidationError(
                "Withdrawal confirmation ledger is corrupt"
            ) from error
        if (
            withdrawal["project_id"] != state.project_id
            or self.confirmations.challenge_id(challenge_body)
            != withdrawal["challenge_id"]
            or owner != expected_owner
            or binding != withdrawal_ref
        ):
            raise ContractValidationError(
                "Withdrawal confirmation binding is invalid"
            )

    def _optional_head_payload(
        self,
        state: KernelState,
        *,
        slot: str,
        kind: str,
        validator: Any,
    ) -> tuple[str, dict[str, Any]]:
        reference_value = state.artifact_heads.get(slot, "")
        if not reference_value:
            return "", {}
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != kind:
                raise ArtifactReferenceError(f"{slot} has the wrong kind")
            payload = validator(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
        ) as error:
            raise ContractValidationError(
                f"Cannot project authoritative {slot}"
            ) from error
        return reference_value, copy.deepcopy(payload)

    def _mission_summary(self, state: KernelState) -> dict[str, str]:
        reference_value = state.artifact_heads.get("mission/draft", "")
        if not reference_value:
            return {
                "topic": "",
                "primary_audience": "",
                "decision_question_or_next_action": "",
            }
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != "mission-draft":
                raise ArtifactReferenceError("Mission draft has the wrong kind")
            payload = self.kernel.artifacts.resolve(reference)["payload"]
            if not isinstance(payload, dict):
                raise TypeError("Mission draft is not an object")
        except (ArtifactReferenceError, KeyError, TypeError) as error:
            raise ContractValidationError(
                "Cannot project the authoritative mission summary"
            ) from error
        return {
            "topic": str(payload.get("topic") or ""),
            "primary_audience": str(payload.get("primary_audience") or ""),
            "decision_question_or_next_action": str(
                payload.get("decision_question_or_next_action")
                or payload.get("desired_judgment_or_action")
                or ""
            ),
        }

    @staticmethod
    def _sidebar_slide(slide: dict[str, Any]) -> dict[str, Any]:
        """Expose the current neutral review vocabulary across legacy/new blueprints."""

        sequence = slide.get("sequence")
        sequence_row = sequence if isinstance(sequence, dict) else {}
        analysis = slide.get("analysis_or_proposal_blocks")
        analysis_rows = copy.deepcopy(analysis) if isinstance(analysis, list) else []
        if not analysis_rows and slide.get("customer_judgment"):
            analysis_rows = [
                {
                    "identity": "AI 分析（历史蓝图迁移）",
                    "text": str(slide["customer_judgment"]),
                }
            ]
        return {
            "slide_id": str(slide.get("slide_id") or ""),
            "order": int(slide.get("order") or 0),
            "section_id": str(
                slide.get("section_id") or slide.get("chapter_id") or ""
            ),
            "neutral_title": str(
                slide.get("neutral_title") or slide.get("title") or ""
            ),
            "page_task": str(
                slide.get("page_task")
                or slide.get("page_purpose")
                or slide.get("communication_goal")
                or ""
            ),
            "reading_question": str(
                slide.get("reading_question")
                or slide.get("user_judgment_prompt")
                or ""
            ),
            "visible_copy": copy.deepcopy(
                slide.get("visible_copy_blocks")
                or slide.get("visible_copy")
                or []
            ),
            "identity_labels": copy.deepcopy(
                slide.get("identity_labels") or []
            ),
            "evidence_items": copy.deepcopy(
                slide.get("evidence_bindings")
                or slide.get("evidence_items")
                or []
            ),
            "analysis_or_proposal_blocks": analysis_rows,
            "solution_mapping_refs": copy.deepcopy(
                slide.get("solution_mapping_refs") or []
            ),
            "source_refs": copy.deepcopy(slide.get("source_refs") or []),
            "speaker_notes": str(slide.get("speaker_notes") or ""),
            "reading_quality": copy.deepcopy(
                slide.get("reading_quality") or {}
            ),
            "previous_relation": str(
                slide.get("previous_relation")
                or sequence_row.get("transition_from_previous")
                or ""
            ),
            "next_relation": str(
                slide.get("next_relation")
                or sequence_row.get("transition_to_next")
                or ""
            ),
        }

    @staticmethod
    def _sidebar_chapters(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chapters: list[dict[str, Any]] = []
        seen: set[str] = set()
        for slide in slides:
            section_id = str(
                slide.get("section_id") or slide.get("chapter_id") or "deck"
            )
            if section_id in seen:
                continue
            seen.add(section_id)
            chapters.append(
                {
                    "section_id": section_id,
                    "title": str(
                        slide.get("section_title")
                        or slide.get("chapter_title")
                        or section_id
                    ),
                    "first_slide_id": str(slide.get("slide_id") or ""),
                }
            )
        return chapters

    @staticmethod
    def _framework_sidebar_payload(
        *,
        framework_ref: str,
        framework: dict[str, Any],
        framework_confirmation_ref: str,
        authorization_ref: str,
    ) -> dict[str, Any]:
        return {
            "source_version": framework_ref,
            "core_proposition": str(
                framework.get("core_proposition") or ""
            ),
            "persuasion_path": copy.deepcopy(
                framework.get("persuasion_path") or []
            ),
            "chapters": copy.deepcopy(framework.get("chapters") or []),
            "structural_risks": copy.deepcopy(
                framework.get("structural_risks") or []
            ),
            "highest_impact_question": str(
                framework.get("highest_impact_question") or ""
            ),
            "confirmed": bool(framework_confirmation_ref),
            "expansion_authorized": bool(authorization_ref),
        }

    def _current_source_batch(
        self, state: KernelState, source_version: str
    ) -> tuple[str, dict[str, Any]]:
        reference_value = state.artifact_heads.get(REVIEW_BATCH_HEAD, "")
        if not reference_value:
            return "", {}
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != REVIEW_BATCH_KIND:
                raise ArtifactReferenceError("Review batch has the wrong kind")
            payload = validate_content_review_batch(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
        ) as error:
            raise ContractValidationError(
                "Cannot project the authoritative content review batch"
            ) from error
        if payload["source_version"] != source_version:
            return "", {}
        return reference_value, payload

    def _current_source_plan(
        self, state: KernelState, source_version: str
    ) -> tuple[str, dict[str, Any]]:
        reference_value = state.artifact_heads.get(
            "content/batch-revision-plan", ""
        )
        if not reference_value:
            return "", {}
        try:
            reference = ArtifactReference.parse(reference_value)
            if reference.kind != "content-batch-revision-plan":
                raise ArtifactReferenceError("Revision plan has the wrong kind")
            payload = validate_content_batch_revision_plan(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
        ) as error:
            raise ContractValidationError(
                "Cannot project the authoritative content revision plan"
            ) from error
        if payload["source_version"] != source_version:
            return "", {}
        return reference_value, copy.deepcopy(payload)

    @staticmethod
    def _previous_round(blueprint: dict[str, Any]) -> dict[str, Any] | None:
        previous_source = str(
            blueprint.get("supersedes_blueprint_ref") or ""
        )
        if not previous_source:
            return None
        return {
            "source_version": previous_source,
            "review_batch_ref": str(blueprint.get("review_batch_ref") or ""),
            "revision_plan_ref": str(
                blueprint.get("batch_revision_plan_ref") or ""
            ),
            "plan_confirmation_ref": str(
                blueprint.get("batch_plan_confirmation_ref") or ""
            ),
            "result": "superseded-by-current-blueprint",
        }

    @staticmethod
    def _sidebar_next_action(phase: str) -> str:
        return {
            "full-deck-review-ready": "review-complete-deck",
            "review-batch-submitted": "prepare-whole-deck-revision-plan",
            "batch-plan-proposed": "confirm-whole-deck-revision-plan",
            "batch-plan-confirmed": "apply-confirmed-revision-plan",
        }.get(phase, "continue-chat")

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
    def _require_expected_revision(expected: object, actual: int) -> None:
        if (
            isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 0
        ):
            raise ContractValidationError(
                "expected_revision must be a non-negative integer"
            )
        if expected != actual:
            raise RevisionConflictError(expected, actual)

    @staticmethod
    def _conflict(message: str, details: dict[str, Any]) -> None:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            f"CONTENT_REVIEW_CONFLICT: {message}",
            details,
        )
