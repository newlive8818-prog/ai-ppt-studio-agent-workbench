"""v2.2 immutable whole-deck review-batch submission."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
from ai_ppt_studio.domains.content.page_decisions import (
    validate_page_decision,
    validate_page_decision_set,
)
from ai_ppt_studio.domains.content.review_batches import (
    REVIEW_BATCH_KIND,
    SUBMISSION_SCOPE,
    validate_content_review_batch,
)
from ai_ppt_studio.domains.content.revision_plans import (
    REVISION_PLAN_KIND,
    validate_revision_plan,
)
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContentWorkflowError,
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.artifacts import canonical_json
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


DECISION_SET_SLOT = "content/page-decisions"
REVIEW_BATCH_SLOT = "content/review-batch"
SESSION_SLOT = "review/session/current/content-full-deck"
SESSION_IDENTITY_SLOT_PREFIX = "review/session/"
PLAN_SLOT = "content/revision-plan"
FOLLOW_UP = "已提交，等待整套修改方案"


def _review_session_id(identity: tuple[str, str, str, str, int]) -> str:
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "review-session-" + hashlib.sha256(encoded).hexdigest()[:24]


class ContentReviewBatchService:
    """Freeze a complete v2.2 PageDecision set behind trusted user intent."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.projection = ContentReviewProjectionService(kernel)
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def submission_context(
        self, *, review_session_id: str, review_batch_id: str
    ) -> dict[str, Any]:
        batch_id = str(review_batch_id or "").strip()
        if not batch_id:
            raise ContractValidationError("review_batch_id is required")
        view = self.projection.project(review_session_id=review_session_id)
        progress = view["review_progress"]
        if progress["remaining"]:
            next_slide = next(
                slide["slide_id"]
                for slide in view["slides"]
                if not slide["decision_state"]["completed"]
            )
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_INCOMPLETE",
                "Every page must have a saved current PageDecision",
                {
                    "review_batch_id": batch_id,
                    "source_version": view["source_version"],
                    "remaining": progress["remaining"],
                    "next_incomplete_slide_id": next_slide,
                },
            )
        state = self.kernel.load()
        decision_set_ref = str(state.artifact_heads.get(DECISION_SET_SLOT) or "")
        if not decision_set_ref:
            raise ContractValidationError("Content review decision set is missing")
        details = self._decision_details(
            decision_set_ref=decision_set_ref,
            view=view,
            review_batch_id=batch_id,
        )
        base = self.confirmations.context(
            scope_kind=SUBMISSION_SCOPE,
            scope_id=f"{batch_id}:{view['source_version']}",
            source_version=view["source_version"],
            evidence_refs=[
                view["source_version"],
                decision_set_ref,
                *details["decision_refs"],
            ],
        )
        return {
            **base,
            "review_session_id": review_session_id,
            "review_session": view["review_session"],
            "review_batch_id": batch_id,
            "revision": state.revision,
            "decision_set_ref": decision_set_ref,
            "expected_slide_count": progress["total"],
            "counts": progress["counts"],
            **details,
        }

    def submit_review_batch(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        review_batch_id: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, str, Any]:
        """Atomically freeze decisions, the batch, and its ReviewSession."""

        command = str(command_id or "").strip()
        assertion = str(host_confirmation_assertion or "").strip()
        if not command or not assertion:
            raise ContractValidationError(
                "command_id and host_confirmation_assertion are required"
            )
        initial = self.kernel.load()
        fingerprint = hashlib.sha256(
            canonical_json(
                {
                    "operation": "submit-v22-content-review-batch",
                    "expected_revision": expected_revision,
                    "review_session_id": review_session_id,
                    "review_batch_id": review_batch_id,
                    "challenge_id": challenge_id,
                    "challenge_revision": challenge_revision,
                    "host_confirmation_assertion_sha256": hashlib.sha256(
                        assertion.encode("utf-8")
                    ).hexdigest(),
                }
            )
        ).hexdigest()
        if command in initial.processed_commands:
            return self._replay_submission(
                command,
                fingerprint,
                review_session_id=str(review_session_id).strip(),
                review_batch_id=str(review_batch_id).strip(),
            )
        if expected_revision != initial.revision:
            raise RevisionConflictError(expected_revision, initial.revision)
        context = self.submission_context(
            review_session_id=review_session_id,
            review_batch_id=review_batch_id,
        )
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=context,
            source_version=str(context["source_version"]),
            challenge_id=str(challenge_id),
            challenge_revision=challenge_revision,
            host_confirmation_assertion=assertion,
        )
        decision_set = self._decision_set(context["decision_set_ref"])
        frozen_set = validate_page_decision_set(
            {
                **decision_set,
                "status": "frozen",
                "updated_at": scoped["confirmed_at"],
            }
        )
        frozen_decision_set_ref = str(
            self.kernel.artifacts.reference_for(
                "content-page-decision-set", frozen_set
            )
        )
        submitted_by = str(
            scoped["user_action_ref"] or scoped["user_message_ref"]
        )
        current_batch_ref = str(
            initial.artifact_heads.get(REVIEW_BATCH_SLOT) or ""
        )
        batch = validate_content_review_batch(
            {
                "review_batch_id": context["review_batch_id"],
                "project_id": initial.project_id,
                "review_type": "content",
                "source_version": context["source_version"],
                "decision_set_ref": frozen_decision_set_ref,
                "page_snapshot_refs": context["page_snapshot_refs"],
                "decision_refs": context["decision_refs"],
                "expected_slide_count": context["expected_slide_count"],
                "counts": context["counts"],
                "status": "submitted",
                "submitted_at": scoped["confirmed_at"],
                "submitted_by": submitted_by,
                "supersedes_ref": current_batch_ref,
                **scoped,
            }
        )
        submitted_session = validate_review_session(
            {
                **context["review_session"],
                "status": "submitted",
                "submitted_at": scoped["confirmed_at"],
            },
            current_revision=initial.revision,
        )
        try:
            committed = self.kernel.commit(
                command_id=command,
                expected_revision=expected_revision,
                event_type="content.v22-review-batch-submitted",
                artifact_updates={
                    DECISION_SET_SLOT: ("content-page-decision-set", frozen_set),
                    REVIEW_BATCH_SLOT: (REVIEW_BATCH_KIND, batch),
                    SESSION_SLOT: ("review-session", submitted_session),
                    f"{SESSION_IDENTITY_SLOT_PREFIX}{submitted_session['review_session_id']}": (
                        "review-session",
                        submitted_session,
                    ),
                },
                confirmation_consumptions=consumptions,
                command_fingerprint=fingerprint,
            )
        except ConfirmationTransactionError as error:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The trusted batch-submission transaction was rejected",
                {"kernel_error_code": error.code},
            ) from None
        return (
            committed.artifact_heads[REVIEW_BATCH_SLOT],
            FOLLOW_UP,
            committed,
        )

    def withdrawal_context(
        self, *, review_session_id: str, review_batch_id: str
    ) -> dict[str, Any]:
        """Return the sole trusted action context for a pre-plan withdrawal."""

        view = self.projection.project(review_session_id=review_session_id)
        state = self.kernel.load()
        batch_ref = str(state.artifact_heads.get(REVIEW_BATCH_SLOT) or "")
        if not batch_ref:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "There is no submitted content review batch to withdraw",
            )
        batch = self._batch(batch_ref)
        if (
            batch["status"] != "submitted"
            or batch["review_batch_id"] != str(review_batch_id).strip()
            or batch["source_version"] != view["source_version"]
            or batch["decision_set_ref"]
            != state.artifact_heads.get(DECISION_SET_SLOT, "")
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "Only the exact current submitted batch can be withdrawn",
            )
        plan_ref = str(state.artifact_heads.get(PLAN_SLOT) or "")
        if plan_ref:
            plan_reference = ArtifactReference.parse(plan_ref)
            if plan_reference.kind != REVISION_PLAN_KIND:
                raise ContractValidationError(
                    "Current content revision plan has the wrong kind"
                )
            plan = validate_revision_plan(
                self.kernel.artifacts.resolve(plan_reference)["payload"]
            )
            if plan["review_batch_ref"] == batch_ref:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_FROZEN",
                    "A revision plan already targets the submitted review batch",
                )
        decision_set = self._decision_set(batch["decision_set_ref"])
        if decision_set["status"] != "frozen":
            raise ContractValidationError(
                "Submitted ContentReviewBatch must reference a frozen decision set"
            )
        base = self.confirmations.context(
            scope_kind="content-review-batch-withdrawal",
            scope_id=batch["review_batch_id"],
            source_version=batch["source_version"],
            evidence_refs=[
                batch["source_version"],
                batch_ref,
                batch["decision_set_ref"],
                *batch["decision_refs"],
            ],
        )
        return {
            **base,
            "review_session": view["review_session"],
            "review_session_id": review_session_id,
            "review_batch_id": batch["review_batch_id"],
            "submitted_batch_ref": batch_ref,
            "submitted_batch": batch,
            "decision_set": decision_set,
        }

    def withdraw_review_batch(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        review_batch_id: str,
        reason: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[dict[str, Any], Any]:
        """Keep a submitted batch immutable and reopen an editable replacement."""

        command = str(command_id or "").strip()
        explanation = str(reason or "").strip()
        assertion = str(host_confirmation_assertion or "").strip()
        if not command or not explanation or not assertion:
            raise ContractValidationError(
                "command_id, reason, and host_confirmation_assertion are required"
            )
        state = self.kernel.load()
        fingerprint = hashlib.sha256(
            canonical_json(
                {
                    "operation": "withdraw-v22-content-review-batch",
                    "expected_revision": expected_revision,
                    "review_session_id": review_session_id,
                    "review_batch_id": review_batch_id,
                    "reason": explanation,
                    "challenge_id": challenge_id,
                    "challenge_revision": challenge_revision,
                    "host_confirmation_assertion_sha256": hashlib.sha256(
                        assertion.encode("utf-8")
                    ).hexdigest(),
                }
            )
        ).hexdigest()
        if command in state.processed_commands:
            return self._replay_withdrawal(
                command,
                fingerprint,
                review_session_id=str(review_session_id).strip(),
                review_batch_id=str(review_batch_id).strip(),
                reason=explanation,
            )
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        context = self.withdrawal_context(
            review_session_id=review_session_id,
            review_batch_id=review_batch_id,
        )
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=context,
            source_version=str(context["source_version"]),
            challenge_id=str(challenge_id),
            challenge_revision=challenge_revision,
            host_confirmation_assertion=assertion,
        )
        replacement_batch_id = str(uuid.uuid4())
        cloned_decisions: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        for decision_ref in context["submitted_batch"]["decision_refs"]:
            previous = validate_page_decision(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(decision_ref)
                )["payload"]
            )
            clone = validate_page_decision(
                {
                    **previous,
                    "page_decision_id": str(uuid.uuid4()),
                    "review_batch_id": replacement_batch_id,
                    "saved_at": scoped["confirmed_at"],
                    "supersedes_decision_ref": decision_ref,
                }
            )
            clone_ref = str(
                self.kernel.artifacts.reference_for("content-page-decision", clone)
            )
            cloned_decisions.append(clone)
            rows.append(
                {
                    "slide_id": clone["slide_id"],
                    "slide_order": clone["slide_order"],
                    "decision_ref": clone_ref,
                }
            )
        decision_set = validate_page_decision_set(
            {
                "decision_set_id": str(uuid.uuid4()),
                "review_batch_id": replacement_batch_id,
                "project_id": state.project_id,
                "source_version": context["source_version"],
                "expected_slide_count": context["submitted_batch"][
                    "expected_slide_count"
                ],
                "status": "draft",
                "decision_refs": rows,
                "updated_at": scoped["confirmed_at"],
            }
        )
        old_session = validate_review_session(
            {**context["review_session"], "status": "superseded"},
            current_revision=state.revision,
        )
        replacement_session = validate_review_session(
            {
                **context["review_session"],
                "review_session_id": _review_session_id(
                    (
                        state.project_id,
                        str(context["review_session"]["review_type"]),
                        str(context["review_session"]["target_artifact_ref"]),
                        str(context["review_session"]["source_version"]),
                        state.revision,
                    )
                ),
                "revision": state.revision,
                "status": "ready",
                "host_open_status": "not-requested",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "created_at": scoped["confirmed_at"],
                "last_opened_at": None,
                "submitted_at": None,
            },
            current_revision=state.revision,
        )
        withdrawal = {
            "withdrawal_id": str(uuid.uuid4()),
            "project_id": state.project_id,
            "review_batch_id": context["review_batch_id"],
            "source_version": context["source_version"],
            "submitted_batch_ref": context["submitted_batch_ref"],
            "replacement_review_batch_id": replacement_batch_id,
            "replacement_decision_set_ref": str(
                self.kernel.artifacts.reference_for(
                    "content-page-decision-set", decision_set
                )
            ),
            "reason": explanation,
            "withdrawn_at": scoped["confirmed_at"],
            **scoped,
        }
        try:
            committed = self.kernel.commit(
                command_id=command,
                expected_revision=expected_revision,
                event_type="content.v22-review-batch-withdrawn",
                artifact_updates={
                    DECISION_SET_SLOT: ("content-page-decision-set", decision_set),
                    "content/review-batch-withdrawal": (
                        "content-review-batch-withdrawal",
                        withdrawal,
                    ),
                    f"{SESSION_IDENTITY_SLOT_PREFIX}{old_session['review_session_id']}": (
                        "review-session",
                        old_session,
                    ),
                    SESSION_SLOT: ("review-session", replacement_session),
                    f"{SESSION_IDENTITY_SLOT_PREFIX}{replacement_session['review_session_id']}": (
                        "review-session",
                        replacement_session,
                    ),
                },
                detached_artifacts=tuple(
                    ("content-page-decision", item) for item in cloned_decisions
                ),
                artifact_removals=(REVIEW_BATCH_SLOT,),
                confirmation_consumptions=consumptions,
                command_fingerprint=fingerprint,
            )
        except ConfirmationTransactionError as error:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The trusted batch-withdrawal transaction was rejected",
                {"kernel_error_code": error.code},
            ) from None
        return (
            {
                "review_batch_id": replacement_batch_id,
                "decision_set_ref": committed.artifact_heads[DECISION_SET_SLOT],
                "decision_set": decision_set,
                "review_session_id": replacement_session["review_session_id"],
            },
            committed,
        )

    def _decision_details(
        self,
        *,
        decision_set_ref: str,
        view: dict[str, Any],
        review_batch_id: str,
    ) -> dict[str, list[str]]:
        decision_set = self._decision_set(decision_set_ref)
        if decision_set["status"] != "draft":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "The current content review batch is already frozen",
                {"decision_set_ref": decision_set_ref},
            )
        if (
            decision_set["project_id"] != view["project_id"]
            or decision_set["source_version"] != view["source_version"]
            or decision_set["review_batch_id"] != review_batch_id
            or decision_set["expected_slide_count"] != len(view["slides"])
        ):
            raise ContractValidationError(
                "Content review decision set is not current for this batch"
            )
        expected_slides = [slide["slide_id"] for slide in view["slides"]]
        decision_refs: list[str] = []
        snapshot_refs: list[str] = []
        for expected_slide, row in zip(expected_slides, decision_set["decision_refs"]):
            decision_ref = str(row["decision_ref"])
            decision = validate_page_decision(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(decision_ref)
                )["payload"]
            )
            if (
                row["slide_id"] != expected_slide
                or decision["slide_id"] != expected_slide
                or decision["project_id"] != view["project_id"]
                or decision["source_version"] != view["source_version"]
                or decision["review_batch_id"] != review_batch_id
                or not decision["completed"]
            ):
                raise ContractValidationError(
                    "Content review decision set has invalid current lineage"
                )
            decision_refs.append(decision_ref)
            snapshot_refs.append(decision["visible_copy_snapshot_ref"])
        if len(decision_refs) != len(expected_slides):
            raise ContractValidationError("Content review decision set is incomplete")
        return {
            "decision_refs": decision_refs,
            "page_snapshot_refs": snapshot_refs,
        }

    def _decision_set(self, decision_set_ref: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(decision_set_ref)
        if reference.kind != "content-page-decision-set":
            raise ContractValidationError(
                "Content review decision set has the wrong kind"
            )
        return validate_page_decision_set(
            self.kernel.artifacts.resolve(reference)["payload"]
        )

    def _batch(self, batch_ref: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(batch_ref)
        if reference.kind != REVIEW_BATCH_KIND:
            raise ContractValidationError("Content review batch has the wrong kind")
        return validate_content_review_batch(
            self.kernel.artifacts.resolve(reference)["payload"]
        )

    def _replay_submission(
        self,
        command_id: str,
        fingerprint: str,
        *,
        review_session_id: str,
        review_batch_id: str,
    ) -> tuple[str, str, Any]:
        state = self.kernel.load()
        event = self._processed_event(
            state,
            command_id=command_id,
            event_type="content.v22-review-batch-submitted",
            fingerprint=fingerprint,
            error_message=(
                "Processed content review batch command has different semantics"
            ),
        )
        try:
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict):
                raise TypeError("artifact_heads must be an object")
            batch_ref = str(heads.get(REVIEW_BATCH_SLOT) or "")
            reference = ArtifactReference.parse(batch_ref)
            if reference.kind != REVIEW_BATCH_KIND:
                raise ValueError("result kind mismatch")
            batch = validate_content_review_batch(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            blueprint = self._source_blueprint(
                batch["source_version"], state.project_id
            )
            decision_set_ref = str(heads.get(DECISION_SET_SLOT) or "")
            decision_set = self._decision_set(decision_set_ref)
            session_ref = str(heads.get(SESSION_SLOT) or "")
            session_reference = ArtifactReference.parse(session_ref)
            if session_reference.kind != "review-session":
                raise ValueError("session kind mismatch")
            session = validate_review_session(
                self.kernel.artifacts.resolve(session_reference)["payload"],
                current_revision=state.revision,
            )
            identity_ref = str(
                heads.get(
                    f"{SESSION_IDENTITY_SLOT_PREFIX}{session['review_session_id']}"
                )
                or ""
            )
            if (
                batch["status"] != "submitted"
                or batch["project_id"] != state.project_id
                or batch["review_batch_id"] != review_batch_id
                or batch["decision_set_ref"] != decision_set_ref
                or decision_set["status"] != "frozen"
                or decision_set["project_id"] != state.project_id
                or decision_set["source_version"] != batch["source_version"]
                or decision_set["review_batch_id"] != review_batch_id
                or decision_set["expected_slide_count"]
                != batch["expected_slide_count"]
                or len(decision_set["decision_refs"])
                != batch["expected_slide_count"]
                or len(batch["decision_refs"])
                != batch["expected_slide_count"]
                or len(batch["page_snapshot_refs"])
                != batch["expected_slide_count"]
                or session["review_session_id"] != review_session_id
                or session["project_id"] != state.project_id
                or session["review_type"] != "content-full-deck"
                or session["status"] != "submitted"
                or session["target_artifact_ref"] != batch["source_version"]
                or session["source_version"] != blueprint["source_version"]
                or identity_ref != session_ref
            ):
                raise ValueError("result identity mismatch")
            for row, decision_ref, snapshot_ref in zip(
                decision_set["decision_refs"],
                batch["decision_refs"],
                batch["page_snapshot_refs"],
            ):
                if str(row["decision_ref"]) != str(decision_ref):
                    raise ValueError("batch decision order mismatch")
                decision = validate_page_decision(
                    self.kernel.artifacts.resolve(
                        ArtifactReference.parse(str(decision_ref))
                    )["payload"]
                )
                snapshot = self._snapshot(str(snapshot_ref))
                if (
                    decision["project_id"] != state.project_id
                    or decision["source_version"] != batch["source_version"]
                    or decision["review_batch_id"] != review_batch_id
                    or decision["slide_id"] != row["slide_id"]
                    or decision["slide_order"] != row["slide_order"]
                    or decision["visible_copy_snapshot_ref"] != str(snapshot_ref)
                    or snapshot["project_id"] != state.project_id
                    or snapshot["source_version"] != batch["source_version"]
                    or snapshot["slide_id"] != decision["slide_id"]
                    or snapshot["slide_order"] != decision["slide_order"]
                    or snapshot["slide_title_snapshot"]
                    != decision["slide_title_snapshot"]
                    or not isinstance(snapshot["visible_copy_blocks"], list)
                ):
                    raise ValueError("submitted decision lineage mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed content review batch command has different semantics"
            ) from exc
        return batch_ref, FOLLOW_UP, state

    def _replay_withdrawal(
        self,
        command_id: str,
        fingerprint: str,
        *,
        review_session_id: str,
        review_batch_id: str,
        reason: str,
    ) -> tuple[dict[str, Any], Any]:
        state = self.kernel.load()
        event = self._processed_event(
            state,
            command_id=command_id,
            event_type="content.v22-review-batch-withdrawn",
            fingerprint=fingerprint,
            error_message=(
                "Processed content review withdrawal has different semantics"
            ),
        )
        try:
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict):
                raise TypeError("artifact_heads must be an object")
            removals = event.get("artifact_head_removals")
            if not isinstance(removals, dict):
                raise TypeError("artifact_head_removals must be an object")
            withdrawal_ref = str(heads.get("content/review-batch-withdrawal") or "")
            withdrawal_reference = ArtifactReference.parse(withdrawal_ref)
            if withdrawal_reference.kind != "content-review-batch-withdrawal":
                raise ValueError("withdrawal kind mismatch")
            withdrawal = self.kernel.artifacts.resolve(withdrawal_reference)["payload"]
            if not isinstance(withdrawal, dict):
                raise TypeError("withdrawal payload must be an object")
            submitted_batch_ref = str(withdrawal.get("submitted_batch_ref") or "")
            submitted_reference = ArtifactReference.parse(submitted_batch_ref)
            if submitted_reference.kind != REVIEW_BATCH_KIND:
                raise ValueError("submitted batch kind mismatch")
            submitted_batch = self._batch(submitted_batch_ref)
            blueprint = self._source_blueprint(
                submitted_batch["source_version"], state.project_id
            )
            submitted_set = self._decision_set(submitted_batch["decision_set_ref"])
            decision_set_ref = str(heads.get(DECISION_SET_SLOT) or "")
            decision_set = self._decision_set(decision_set_ref)
            session_ref = str(heads.get(SESSION_SLOT) or "")
            session_reference = ArtifactReference.parse(session_ref)
            if session_reference.kind != "review-session":
                raise ValueError("session kind mismatch")
            session = validate_review_session(
                self.kernel.artifacts.resolve(session_reference)["payload"],
                current_revision=state.revision,
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
            identity_ref = str(
                heads.get(
                    f"{SESSION_IDENTITY_SLOT_PREFIX}{session['review_session_id']}"
                )
                or ""
            )
            if (
                decision_set["status"] != "draft"
                or decision_set["project_id"] != state.project_id
                or decision_set["review_batch_id"]
                != str(withdrawal.get("replacement_review_batch_id") or "")
                or decision_set["source_version"]
                != str(withdrawal.get("source_version") or "")
                or session["project_id"] != state.project_id
                or session["review_type"] != "content-full-deck"
                or session["status"] != "ready"
                or session["target_artifact_ref"]
                != decision_set["source_version"]
                or session["review_session_id"] != expected_session_id
                or identity_ref != session_ref
                or withdrawal.get("project_id") != state.project_id
                or str(withdrawal.get("review_batch_id") or "") != review_batch_id
                or str(withdrawal.get("reason") or "") != reason
                or submitted_batch_ref != removals.get(REVIEW_BATCH_SLOT)
                or str(withdrawal.get("replacement_decision_set_ref") or "")
                != decision_set_ref
                or submitted_batch["project_id"] != state.project_id
                or submitted_batch["status"] != "submitted"
                or submitted_batch["review_batch_id"] != review_batch_id
                or submitted_batch["source_version"] != decision_set["source_version"]
                or submitted_set["status"] != "frozen"
                or submitted_set["project_id"] != state.project_id
                or submitted_set["source_version"] != submitted_batch["source_version"]
                or submitted_set["review_batch_id"] != review_batch_id
                or submitted_set["expected_slide_count"]
                != submitted_batch["expected_slide_count"]
                or decision_set["expected_slide_count"]
                != submitted_batch["expected_slide_count"]
                or len(submitted_set["decision_refs"])
                != submitted_batch["expected_slide_count"]
                or len(decision_set["decision_refs"])
                != submitted_batch["expected_slide_count"]
            ):
                raise ValueError("result identity mismatch")
            old_session_ref = str(
                heads.get(f"{SESSION_IDENTITY_SLOT_PREFIX}{review_session_id}")
                or ""
            )
            old_session_reference = ArtifactReference.parse(old_session_ref)
            if old_session_reference.kind != "review-session":
                raise ValueError("submitted session kind mismatch")
            old_session = validate_review_session(
                self.kernel.artifacts.resolve(old_session_reference)["payload"],
                current_revision=state.revision,
            )
            if (
                old_session["review_session_id"] != review_session_id
                or old_session["project_id"] != state.project_id
                or old_session["review_type"] != "content-full-deck"
                or old_session["status"] != "superseded"
                or old_session["target_artifact_ref"]
                != submitted_batch["source_version"]
                or old_session["source_version"] != blueprint["source_version"]
            ):
                raise ValueError("submitted session lineage mismatch")
            for prior_row, prior_ref, replacement_row in zip(
                submitted_set["decision_refs"],
                submitted_batch["decision_refs"],
                decision_set["decision_refs"],
            ):
                if str(prior_row["decision_ref"]) != str(prior_ref):
                    raise ValueError("submitted decision order mismatch")
                previous = validate_page_decision(
                    self.kernel.artifacts.resolve(
                        ArtifactReference.parse(str(prior_ref))
                    )["payload"]
                )
                decision = validate_page_decision(
                    self.kernel.artifacts.resolve(
                        ArtifactReference.parse(str(replacement_row["decision_ref"]))
                    )["payload"]
                )
                if (
                    previous["project_id"] != state.project_id
                    or previous["source_version"] != submitted_batch["source_version"]
                    or previous["review_batch_id"] != review_batch_id
                    or previous["slide_id"] != prior_row["slide_id"]
                    or previous["slide_order"] != prior_row["slide_order"]
                    or decision["review_batch_id"] != decision_set["review_batch_id"]
                    or decision["project_id"] != decision_set["project_id"]
                    or decision["source_version"]
                    != decision_set["source_version"]
                    or decision["slide_id"] != replacement_row["slide_id"]
                    or decision["slide_order"] != replacement_row["slide_order"]
                    or decision["slide_id"] != previous["slide_id"]
                    or decision["slide_order"] != previous["slide_order"]
                    or decision["visible_copy_snapshot_ref"]
                    != previous["visible_copy_snapshot_ref"]
                    or decision["supersedes_decision_ref"] != str(prior_ref)
                ):
                    raise ValueError("decision identity mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed content review withdrawal has different semantics"
            ) from exc
        return (
            {
                "review_batch_id": decision_set["review_batch_id"],
                "decision_set_ref": decision_set_ref,
                "decision_set": decision_set,
                "review_session_id": session["review_session_id"],
            },
            state,
        )

    def _snapshot(self, snapshot_ref: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(snapshot_ref)
        if reference.kind != "content-visible-copy-snapshot":
            raise ContractValidationError("Content review snapshot has the wrong kind")
        snapshot = self.kernel.artifacts.resolve(reference)["payload"]
        if not isinstance(snapshot, dict):
            raise ContractValidationError("Content review snapshot is invalid")
        required_text = (
            "project_id",
            "source_version",
            "slide_id",
            "slide_title_snapshot",
        )
        if any(not str(snapshot.get(field) or "").strip() for field in required_text):
            raise ContractValidationError("Content review snapshot is invalid")
        order = snapshot.get("slide_order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ContractValidationError("Content review snapshot is invalid")
        if not isinstance(snapshot.get("visible_copy_blocks"), list):
            raise ContractValidationError("Content review snapshot is invalid")
        return snapshot

    def _source_blueprint(
        self, source_version: str, project_id: str
    ) -> dict[str, Any]:
        reference = ArtifactReference.parse(source_version)
        if reference.kind != "reading-deck-blueprint":
            raise ContractValidationError(
                "Content review source must be a ReadingDeckBlueprint"
            )
        blueprint = validate_reading_deck_blueprint(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        if blueprint["project_id"] != project_id:
            raise ContractValidationError(
                "Content review source project does not match the current project"
            )
        return blueprint

    def _processed_event(
        self,
        state: Any,
        *,
        command_id: str,
        event_type: str,
        fingerprint: str,
        error_message: str,
    ) -> dict[str, Any]:
        revision = state.processed_commands.get(command_id)
        events_root = getattr(self.kernel, "events_root", None)
        try:
            if revision is None or events_root is None:
                raise ValueError("receipt unavailable")
            event = json.loads(
                (events_root / f"r{revision:08d}.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ContractValidationError(error_message) from exc
        if not isinstance(event, dict):
            raise ContractValidationError(error_message)
        if event.get("command_fingerprint") != fingerprint:
            raise ContractValidationError(
                "Processed command has different semantics"
            )
        if (
            event.get("command_id") != command_id
            or event.get("event_type") != event_type
        ):
            raise ContractValidationError(error_message)
        return event


__all__ = ["ContentReviewBatchService", "FOLLOW_UP"]
