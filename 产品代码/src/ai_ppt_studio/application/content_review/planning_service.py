"""Persist and confirm an immutable whole-deck revision plan."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from ai_ppt_studio.domains.content.review_batches import (
    REVIEW_BATCH_KIND,
    validate_content_review_batch,
)
from ai_ppt_studio.domains.content.page_decisions import (
    validate_page_decision,
    validate_page_decision_set,
)
from ai_ppt_studio.domains.content.revision_plans import (
    PLAN_ACTIONS,
    REVISION_PLAN_CONFIRMATION_KIND,
    REVISION_PLAN_KIND,
    validate_revision_plan,
    validate_revision_plan_confirmation,
)
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
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


PLAN_SLOT = "content/revision-plan"
PLAN_KIND = REVISION_PLAN_KIND
PLAN_CONFIRMATION_SLOT = "content/revision-plan-confirmation"
PLAN_CONFIRMATION_SCOPE = "content-batch-plan-confirmation"
BLUEPRINT_SLOT = "content/reading-deck-blueprint"
SESSION_SLOT = "review/session/current/content-full-deck"
SESSION_IDENTITY_SLOT_PREFIX = "review/session/"
VISUAL_SESSION_SLOT = "review/session/current/visual-professional"
DOWNSTREAM_CURRENT_PREFIXES = (
    "visual/",
    "delivery/",
    "chat-delivery/",
    "gate/",
    "review-marks/visual",
)


class ContentBatchPlanningService:
    """Persist one chief-authored cross-page proposal for a submitted batch."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def save_revision_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_batch_ref: str,
        producer_id: str,
        summary: str,
        page_actions: list[dict[str, Any]],
    ) -> tuple[str, Any]:
        command = str(command_id or "").strip()
        if not command:
            raise ContractValidationError("command_id is required")
        if str(producer_id).strip() != "presales-solution-chief":
            raise ContractValidationError(
                "Only the presales chief can propose revisions"
            )
        reference = ArtifactReference.parse(str(review_batch_ref))
        if reference.kind != REVIEW_BATCH_KIND:
            raise ContractValidationError("review_batch_ref has the wrong kind")
        normalized_summary = str(summary or "").strip()
        if not normalized_summary:
            raise ContractValidationError("Revision plan summary is required")
        if not isinstance(page_actions, list):
            raise ContractValidationError(
                "Revision plan must cover every reviewed page"
            )
        seen: set[str] = set()
        normalized_actions: list[dict[str, str]] = []
        for item in page_actions:
            if not isinstance(item, dict):
                raise ContractValidationError("Revision plan page action is invalid")
            slide_id = str(item.get("slide_id") or "").strip()
            action = str(item.get("action") or "").strip()
            rationale = str(item.get("rationale") or "").strip()
            if (
                not slide_id
                or slide_id in seen
                or action not in PLAN_ACTIONS
                or not rationale
            ):
                raise ContractValidationError("Revision plan page action is invalid")
            seen.add(slide_id)
            normalized_actions.append(
                {"slide_id": slide_id, "action": action, "rationale": rationale}
            )
        fingerprint = self._fingerprint(
            {
                "operation": "save-v22-content-batch-revision-plan",
                "expected_revision": expected_revision,
                "review_batch_ref": str(reference),
                "producer_id": producer_id,
                "summary": normalized_summary,
                "page_actions": normalized_actions,
            }
        )
        state = self.kernel.load()
        if command in state.processed_commands:
            return self._replay_plan(
                command,
                fingerprint,
                state,
                review_batch_ref=str(reference),
                producer_id="presales-solution-chief",
                summary=normalized_summary,
                page_actions=normalized_actions,
            )
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        if state.artifact_heads.get("content/review-batch") != str(reference):
            raise ContractValidationError("review_batch_ref is not current")
        batch = validate_content_review_batch(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        if batch["status"] != "submitted":
            raise ContractValidationError("Revision plan requires a submitted batch")
        current_plan_ref = str(state.artifact_heads.get(PLAN_SLOT) or "")
        if current_plan_ref:
            current_plan_reference = ArtifactReference.parse(current_plan_ref)
            if current_plan_reference.kind != PLAN_KIND:
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_CONFLICT",
                    "Current content revision plan has the wrong kind",
                )
            current_plan = validate_revision_plan(
                self.kernel.artifacts.resolve(current_plan_reference)["payload"]
            )
            if (
                current_plan["review_batch_ref"] == str(reference)
                and current_plan["status"] == "applied"
                and state.gate_status.get("G0") == "passed"
            ):
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_CONFLICT",
                    "This review batch already has an applied revision plan",
                )
        if len(normalized_actions) != batch["expected_slide_count"]:
            raise ContractValidationError(
                "Revision plan must cover every reviewed page"
            )
        batch_slide_ids = {
            validate_page_decision(
                self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]
            )["slide_id"]
            for ref in batch["decision_refs"]
        }
        if seen != batch_slide_ids:
            raise ContractValidationError(
                "Revision plan must target exact current batch pages"
            )
        plan = validate_revision_plan(
            {
                "plan_id": str(uuid.uuid4()),
                "project_id": state.project_id,
                "review_batch_ref": str(reference),
                "source_version": batch["source_version"],
                "producer_id": "presales-solution-chief",
                "summary": normalized_summary,
                "page_actions": normalized_actions,
                "status": "proposed",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        committed = self.kernel.commit(
            command_id=command,
            expected_revision=expected_revision,
            event_type="content.v22-revision-plan-proposed",
            artifact_updates={PLAN_SLOT: (PLAN_KIND, plan)},
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads[PLAN_SLOT], committed

    def confirmation_context(self, *, plan_ref: str) -> dict[str, Any]:
        """Return the exact trusted confirmation challenge for one plan."""

        state = self.kernel.load()
        plan = self._current_plan(state, plan_ref, status="proposed")
        batch = self._current_batch(state, plan["review_batch_ref"])
        if batch["source_version"] != plan["source_version"]:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The proposed revision plan has stale content lineage",
            )
        return self.confirmations.context(
            scope_kind=PLAN_CONFIRMATION_SCOPE,
            scope_id=f"{plan['plan_id']}:{plan_ref}",
            source_version=plan["source_version"],
            evidence_refs=[plan["source_version"], plan["review_batch_ref"], plan_ref],
        )

    def confirm_revision_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_ref: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, str, Any]:
        """Consume one host assertion and lock the current proposed plan."""

        command = str(command_id or "").strip()
        assertion = str(host_confirmation_assertion or "").strip()
        if not command or not assertion:
            raise ContractValidationError(
                "command_id and host_confirmation_assertion are required"
            )
        fingerprint = self._fingerprint(
            {
                "operation": "confirm-v22-content-batch-revision-plan",
                "expected_revision": expected_revision,
                "plan_ref": plan_ref,
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
                "host_confirmation_assertion_sha256": hashlib.sha256(
                    assertion.encode("utf-8")
                ).hexdigest(),
            }
        )
        state = self.kernel.load()
        if command in state.processed_commands:
            return self._replay_confirmation(command, fingerprint)
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        context = self.confirmation_context(plan_ref=plan_ref)
        plan = self._current_plan(state, plan_ref, status="proposed")
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=context,
            source_version=plan["source_version"],
            challenge_id=str(challenge_id),
            challenge_revision=challenge_revision,
            host_confirmation_assertion=assertion,
        )
        confirmation = {
            **scoped,
            "revision_plan_ref": plan_ref,
            "review_batch_ref": plan["review_batch_ref"],
            "source_version": plan["source_version"],
        }
        confirmed_plan = validate_revision_plan(
            {
                **plan,
                "status": "confirmed",
                "supersedes_ref": plan_ref,
                "confirmed_at": scoped["confirmed_at"],
            }
        )
        try:
            committed = self.kernel.commit(
                command_id=command,
                expected_revision=expected_revision,
                event_type="content.v22-revision-plan-confirmed",
                artifact_updates={
                    PLAN_SLOT: (PLAN_KIND, confirmed_plan),
                    PLAN_CONFIRMATION_SLOT: (
                        REVISION_PLAN_CONFIRMATION_KIND,
                        confirmation,
                    ),
                },
                confirmation_consumptions=consumptions,
                command_fingerprint=fingerprint,
            )
        except ConfirmationTransactionError as error:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The trusted revision-plan confirmation was rejected",
                {"kernel_error_code": error.code},
            ) from None
        return (
            committed.artifact_heads[PLAN_CONFIRMATION_SLOT],
            committed.artifact_heads[PLAN_SLOT],
            committed,
        )

    def apply_confirmed_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_confirmation_ref: str,
        new_blueprint: dict[str, Any],
    ) -> tuple[str, Any]:
        """Publish chief-produced new content and invalidate prior review state."""

        command = str(command_id or "").strip()
        if not command:
            raise ContractValidationError("command_id is required")
        fingerprint = self._fingerprint(
            {
                "operation": "apply-v22-confirmed-content-batch-plan",
                "expected_revision": expected_revision,
                "plan_confirmation_ref": plan_confirmation_ref,
                "new_blueprint": new_blueprint,
            }
        )
        state = self.kernel.load()
        if command in state.processed_commands:
            return self._replay_application(command, fingerprint)
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        confirmation = self._current_confirmation(state, plan_confirmation_ref)
        plan = self._confirmed_plan(state, confirmation)
        old_blueprint_ref = str(state.artifact_heads.get(BLUEPRINT_SLOT) or "")
        if old_blueprint_ref != plan["source_version"]:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Confirmed revision plan is not bound to the current content source",
            )
        blueprint = validate_reading_deck_blueprint(new_blueprint)
        if blueprint["project_id"] != state.project_id:
            raise ContractValidationError("New reading deck belongs to another project")
        if blueprint["source_version"] == old_blueprint_ref:
            raise ContractValidationError("New reading deck must have a new source version")
        candidate_ref = str(
            self.kernel.artifacts.reference_for("reading-deck-blueprint", blueprint)
        )
        if candidate_ref == old_blueprint_ref:
            raise ContractValidationError("New reading deck must differ from the old artifact")
        removals = {
            "content/gate/evidence",
            "content/gate/presales-reading",
            "content/acceptance",
            "content/page-decisions",
            "content/review-batch",
            PLAN_SLOT,
            PLAN_CONFIRMATION_SLOT,
            SESSION_SLOT,
            VISUAL_SESSION_SLOT,
        }
        removals.update(
            slot
            for slot in state.artifact_heads
            if slot.startswith(DOWNSTREAM_CURRENT_PREFIXES)
        )
        updates: dict[str, tuple[str, dict[str, Any]]] = {
            BLUEPRINT_SLOT: ("reading-deck-blueprint", blueprint)
        }
        for session_slot in (SESSION_SLOT, VISUAL_SESSION_SLOT):
            old_session_ref = str(state.artifact_heads.get(session_slot) or "")
            if not old_session_ref:
                continue
            session = validate_review_session(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(old_session_ref)
                )["payload"],
                current_revision=state.revision,
            )
            superseded = validate_review_session(
                {**session, "status": "superseded"},
                current_revision=state.revision,
            )
            updates[
                f"{SESSION_IDENTITY_SLOT_PREFIX}{superseded['review_session_id']}"
            ] = ("review-session", superseded)
        active_ref = str(state.artifact_heads.get("agent/task/active") or "")
        if active_ref:
            removals.add("agent/task/active")
            task = self.kernel.artifacts.resolve(
                ArtifactReference.parse(active_ref)
            )["payload"]
            if task.get("status") not in {"completed", "invalidated"}:
                invalidated = {
                    **task,
                    "status": "invalidated",
                    "progress": {
                        "stage": "invalidated",
                        "done": task.get("progress", {}).get("done", 0),
                        "total": task.get("progress", {}).get("total", 1),
                    },
                    "invalidated_by_gate": "G0",
                    "invalidation_reason": "content-blueprint-republished",
                }
                updates[f"agent/task/{task['task_id']}"] = (
                    "agent-task",
                    invalidated,
                )
        application = {
            "project_id": state.project_id,
            "old_source_version": old_blueprint_ref,
            "new_source_version": candidate_ref,
            "revision_plan_ref": confirmation["revision_plan_ref"],
            "confirmed_plan_ref": state.artifact_heads[PLAN_SLOT],
            "plan_confirmation_ref": plan_confirmation_ref,
            "review_batch_ref": plan["review_batch_ref"],
            "result": "new-reading-deck-blueprint-published",
        }
        committed = self.kernel.commit(
            command_id=command,
            expected_revision=expected_revision,
            event_type="content.v22-confirmed-revision-plan-applied",
            artifact_updates=updates,
            detached_artifacts=(("content-revision-plan-application", application),),
            artifact_removals=tuple(sorted(removals)),
            gate_mutation=GateEvaluator(self.kernel).content_source_republished(
                old_blueprint_ref=old_blueprint_ref,
                new_blueprint_ref=candidate_ref,
            ),
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads[BLUEPRINT_SLOT], committed

    def apply_no_change_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_confirmation_ref: str,
    ) -> tuple[str, Any]:
        """Mark a fully-approved current plan applied without rewriting content."""

        command = str(command_id or "").strip()
        if not command:
            raise ContractValidationError("command_id is required")
        fingerprint = self._fingerprint(
            {
                "operation": "apply-v22-no-change-content-batch-plan",
                "expected_revision": expected_revision,
                "plan_confirmation_ref": plan_confirmation_ref,
            }
        )
        state = self.kernel.load()
        if command in state.processed_commands:
            return self._replay_no_change_application(command, fingerprint)
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        confirmation = self._current_confirmation(state, plan_confirmation_ref)
        plan = self._confirmed_plan(state, confirmation)
        batch = self._current_batch(state, plan["review_batch_ref"])
        blueprint_ref = str(state.artifact_heads.get(BLUEPRINT_SLOT) or "")
        acceptance_ref = str(state.artifact_heads.get("content/acceptance") or "")
        if (
            plan["source_version"] != blueprint_ref
            or batch["source_version"] != blueprint_ref
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The no-change plan is not bound to the current content source",
            )
        if any(value for key, value in batch["counts"].items() if key != "approved"):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "A non-approved page requires a new reading deck version",
            )
        if any(action["action"] != "keep" for action in plan["page_actions"]):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "A revision plan with page changes cannot be applied without content",
            )
        current_plan_ref = str(state.artifact_heads[PLAN_SLOT])
        applied_plan = validate_revision_plan(
            {
                **plan,
                "status": "applied",
                "supersedes_ref": current_plan_ref,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        application = {
            "project_id": state.project_id,
            "source_version": plan["source_version"],
            "review_batch_ref": plan["review_batch_ref"],
            "revision_plan_ref": confirmation["revision_plan_ref"],
            "confirmed_plan_ref": current_plan_ref,
            "plan_confirmation_ref": plan_confirmation_ref,
            "result": "all-pages-approved-without-content-revision",
        }
        gate_mutation = GateEvaluator(self.kernel).content_user_reviewable(
            acceptance_ref,
            blueprint_ref,
        )
        committed = self.kernel.commit(
            command_id=command,
            expected_revision=expected_revision,
            event_type="content.v22-no-change-revision-plan-applied",
            artifact_updates={PLAN_SLOT: (PLAN_KIND, applied_plan)},
            detached_artifacts=(("content-revision-plan-application", application),),
            gate_mutation=gate_mutation,
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads[PLAN_SLOT], committed

    def _current_plan(
        self, state: Any, plan_ref: str, *, status: str
    ) -> dict[str, Any]:
        reference = ArtifactReference.parse(str(plan_ref))
        if reference.kind != PLAN_KIND or state.artifact_heads.get(PLAN_SLOT) != str(reference):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Only the exact current revision plan can be confirmed",
            )
        plan = validate_revision_plan(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        if plan["status"] != status:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Revision plan is not in the required lifecycle state",
            )
        return plan

    def _current_batch(self, state: Any, batch_ref: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(str(batch_ref))
        if (
            reference.kind != REVIEW_BATCH_KIND
            or state.artifact_heads.get("content/review-batch") != str(reference)
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Revision plan no longer targets the current review batch",
            )
        batch = validate_content_review_batch(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        if batch["status"] != "submitted":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Revision plan requires a submitted review batch",
            )
        return batch

    def _current_confirmation(
        self, state: Any, confirmation_ref: str
    ) -> dict[str, Any]:
        reference = ArtifactReference.parse(str(confirmation_ref))
        if (
            reference.kind != REVISION_PLAN_CONFIRMATION_KIND
            or state.artifact_heads.get(PLAN_CONFIRMATION_SLOT) != str(reference)
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Revision plan confirmation is not current",
            )
        return validate_revision_plan_confirmation(
            self.kernel.artifacts.resolve(reference)["payload"]
        )

    def _confirmed_plan(
        self, state: Any, confirmation: dict[str, Any]
    ) -> dict[str, Any]:
        current_ref = str(state.artifact_heads.get(PLAN_SLOT) or "")
        plan = self._current_plan(state, current_ref, status="confirmed")
        if (
            plan.get("supersedes_ref") != confirmation["revision_plan_ref"]
            or plan["review_batch_ref"] != confirmation["review_batch_ref"]
            or plan["source_version"] != confirmation["source_version"]
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Confirmed revision plan does not match its confirmation receipt",
            )
        self._current_batch(state, plan["review_batch_ref"])
        return plan

    def _replay_plan(
        self,
        command_id: str,
        fingerprint: str,
        state: Any,
        *,
        review_batch_ref: str,
        producer_id: str,
        summary: str,
        page_actions: list[dict[str, str]],
    ) -> tuple[str, Any]:
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
            raise ContractValidationError(
                "Processed revision plan has different semantics"
            ) from exc
        if not isinstance(event, dict):
            raise ContractValidationError(
                "Processed revision plan has different semantics"
            )
        if event.get("command_fingerprint") != fingerprint:
            raise ContractValidationError(
                "Processed command has different semantics"
            )
        try:
            heads = event.get("artifact_heads")
            if (
                event.get("command_id") != command_id
                or event.get("event_type")
                != "content.v22-revision-plan-proposed"
                or not isinstance(heads, dict)
            ):
                raise ValueError("receipt mismatch")
            ref = str(heads.get(PLAN_SLOT) or "")
            reference = ArtifactReference.parse(ref)
            if reference.kind != PLAN_KIND:
                raise ValueError("result kind mismatch")
            plan = validate_revision_plan(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            batch_reference = ArtifactReference.parse(plan["review_batch_ref"])
            if batch_reference.kind != REVIEW_BATCH_KIND:
                raise ValueError("plan batch kind mismatch")
            batch = validate_content_review_batch(
                self.kernel.artifacts.resolve(batch_reference)["payload"]
            )
            decision_set_reference = ArtifactReference.parse(
                batch["decision_set_ref"]
            )
            if decision_set_reference.kind != "content-page-decision-set":
                raise ValueError("batch decision-set kind mismatch")
            decision_set = validate_page_decision_set(
                self.kernel.artifacts.resolve(decision_set_reference)["payload"]
            )
            if decision_set["status"] != "frozen":
                raise ValueError("batch decision set is not frozen")
            reviewed_slide_ids: set[str] = set()
            for row, decision_ref in zip(
                decision_set["decision_refs"], batch["decision_refs"]
            ):
                if str(row["decision_ref"]) != str(decision_ref):
                    raise ValueError("batch decision order mismatch")
                decision = validate_page_decision(
                    self.kernel.artifacts.resolve(
                        ArtifactReference.parse(str(decision_ref))
                    )["payload"]
                )
                if (
                    decision["project_id"] != state.project_id
                    or decision["source_version"] != batch["source_version"]
                    or decision["review_batch_id"] != batch["review_batch_id"]
                    or decision["slide_id"] != row["slide_id"]
                    or decision["slide_order"] != row["slide_order"]
                ):
                    raise ValueError("batch decision lineage mismatch")
                reviewed_slide_ids.add(decision["slide_id"])
            if (
                plan["status"] != "proposed"
                or plan["project_id"] != state.project_id
                or plan["review_batch_ref"] != review_batch_ref
                or plan["source_version"] != batch["source_version"]
                or plan["producer_id"] != producer_id
                or plan["summary"] != summary
                or plan["page_actions"] != page_actions
                or batch["project_id"] != state.project_id
                or batch["status"] != "submitted"
                or batch["decision_set_ref"] != str(decision_set_reference)
                or decision_set["project_id"] != state.project_id
                or decision_set["source_version"] != batch["source_version"]
                or decision_set["review_batch_id"] != batch["review_batch_id"]
                or decision_set["expected_slide_count"]
                != batch["expected_slide_count"]
                or len(decision_set["decision_refs"])
                != batch["expected_slide_count"]
                or len(reviewed_slide_ids) != batch["expected_slide_count"]
                or {action["slide_id"] for action in page_actions}
                != reviewed_slide_ids
            ):
                raise ValueError("result identity mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed revision plan has different semantics"
            ) from exc
        return ref, state

    def _replay_confirmation(
        self, command_id: str, fingerprint: str
    ) -> tuple[str, str, Any]:
        state = self.kernel.load()
        event = self._processed_event(
            state,
            command_id=command_id,
            event_type="content.v22-revision-plan-confirmed",
            fingerprint=fingerprint,
            error_message=(
                "Processed revision-plan confirmation has different semantics"
            ),
        )
        try:
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict):
                raise TypeError("artifact_heads must be an object")
            confirmation_ref = str(
                heads.get(PLAN_CONFIRMATION_SLOT) or ""
            )
            confirmation_reference = ArtifactReference.parse(confirmation_ref)
            if confirmation_reference.kind != REVISION_PLAN_CONFIRMATION_KIND:
                raise ValueError("confirmation kind mismatch")
            confirmation = validate_revision_plan_confirmation(
                self.kernel.artifacts.resolve(confirmation_reference)["payload"]
            )
            confirmed_plan_ref = str(heads.get(PLAN_SLOT) or "")
            confirmed_reference = ArtifactReference.parse(confirmed_plan_ref)
            if confirmed_reference.kind != PLAN_KIND:
                raise ValueError("confirmed plan kind mismatch")
            confirmed_plan = validate_revision_plan(
                self.kernel.artifacts.resolve(confirmed_reference)["payload"]
            )
            proposed_reference = ArtifactReference.parse(
                confirmation["revision_plan_ref"]
            )
            if proposed_reference.kind != PLAN_KIND:
                raise ValueError("proposed plan kind mismatch")
            proposed_plan = validate_revision_plan(
                self.kernel.artifacts.resolve(proposed_reference)["payload"]
            )
            if (
                confirmation["project_id"] != state.project_id
                or confirmed_plan["project_id"] != state.project_id
                or proposed_plan["project_id"] != state.project_id
                or confirmed_plan["status"] != "confirmed"
                or proposed_plan["status"] != "proposed"
                or confirmed_plan.get("supersedes_ref")
                != confirmation["revision_plan_ref"]
                or confirmed_plan["review_batch_ref"]
                != confirmation["review_batch_ref"]
                or confirmed_plan["source_version"]
                != confirmation["source_version"]
                or proposed_plan["review_batch_ref"]
                != confirmation["review_batch_ref"]
                or proposed_plan["source_version"]
                != confirmation["source_version"]
            ):
                raise ValueError("confirmation lineage mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed revision-plan confirmation has different semantics"
            ) from exc
        return confirmation_ref, confirmed_plan_ref, state

    def _replay_application(
        self, command_id: str, fingerprint: str
    ) -> tuple[str, Any]:
        state = self.kernel.load()
        event = self._processed_event(
            state,
            command_id=command_id,
            event_type="content.v22-confirmed-revision-plan-applied",
            fingerprint=fingerprint,
            error_message=(
                "Processed revision-plan application has different semantics"
            ),
        )
        try:
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict):
                raise TypeError("artifact_heads must be an object")
            ref = str(heads.get(BLUEPRINT_SLOT) or "")
            reference = ArtifactReference.parse(ref)
            if reference.kind != "reading-deck-blueprint":
                raise ValueError("result kind mismatch")
            blueprint = validate_reading_deck_blueprint(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            application = self._application_receipt(
                event,
                state,
                result="new-reading-deck-blueprint-published",
                source_field="old_source_version",
            )
            if (
                blueprint["project_id"] != state.project_id
                or application.get("new_source_version") != ref
            ):
                raise ValueError("application result mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed revision-plan application has different semantics"
            ) from exc
        return ref, state

    def _replay_no_change_application(
        self, command_id: str, fingerprint: str
    ) -> tuple[str, Any]:
        state = self.kernel.load()
        event = self._processed_event(
            state,
            command_id=command_id,
            event_type="content.v22-no-change-revision-plan-applied",
            fingerprint=fingerprint,
            error_message=(
                "Processed no-change plan application has different semantics"
            ),
        )
        try:
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict):
                raise TypeError("artifact_heads must be an object")
            ref = str(heads.get(PLAN_SLOT) or "")
            reference = ArtifactReference.parse(ref)
            if reference.kind != PLAN_KIND:
                raise ValueError("result kind mismatch")
            applied_plan = validate_revision_plan(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            application = self._application_receipt(
                event,
                state,
                result="all-pages-approved-without-content-revision",
                source_field="source_version",
            )
            if (
                applied_plan["project_id"] != state.project_id
                or applied_plan["status"] != "applied"
                or applied_plan.get("supersedes_ref")
                != application["confirmed_plan_ref"]
                or applied_plan["review_batch_ref"]
                != application["review_batch_ref"]
                or applied_plan["source_version"]
                != application["source_version"]
            ):
                raise ValueError("application result mismatch")
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed no-change plan application has different semantics"
            ) from exc
        return ref, state

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

    def _application_receipt(
        self,
        event: dict[str, Any],
        state: Any,
        *,
        result: str,
        source_field: str,
    ) -> dict[str, Any]:
        detached_refs = event.get("detached_artifact_refs")
        if not isinstance(detached_refs, list):
            raise TypeError("detached_artifact_refs must be an array")
        application_refs: list[ArtifactReference] = []
        for value in detached_refs:
            reference = ArtifactReference.parse(str(value))
            if reference.kind == "content-revision-plan-application":
                application_refs.append(reference)
        if len(application_refs) != 1:
            raise ValueError("application receipt is missing or ambiguous")
        application = self.kernel.artifacts.resolve(application_refs[0])["payload"]
        if not isinstance(application, dict):
            raise TypeError("application receipt must be an object")
        for field, kind in (
            (source_field, "reading-deck-blueprint"),
            ("revision_plan_ref", PLAN_KIND),
            ("confirmed_plan_ref", PLAN_KIND),
            ("plan_confirmation_ref", REVISION_PLAN_CONFIRMATION_KIND),
            ("review_batch_ref", REVIEW_BATCH_KIND),
        ):
            reference = ArtifactReference.parse(str(application.get(field) or ""))
            if reference.kind != kind:
                raise ValueError(f"{field} kind mismatch")
        confirmation = validate_revision_plan_confirmation(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(application["plan_confirmation_ref"])
            )["payload"]
        )
        proposed_plan = validate_revision_plan(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(application["revision_plan_ref"])
            )["payload"]
        )
        confirmed_plan = validate_revision_plan(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(application["confirmed_plan_ref"])
            )["payload"]
        )
        batch = validate_content_review_batch(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(application["review_batch_ref"])
            )["payload"]
        )
        source_ref = application[source_field]
        if (
            application.get("project_id") != state.project_id
            or application.get("result") != result
            or confirmation["project_id"] != state.project_id
            or proposed_plan["project_id"] != state.project_id
            or confirmed_plan["project_id"] != state.project_id
            or batch["project_id"] != state.project_id
            or proposed_plan["status"] != "proposed"
            or confirmed_plan["status"] != "confirmed"
            or confirmation["revision_plan_ref"]
            != application["revision_plan_ref"]
            or confirmation["review_batch_ref"]
            != application["review_batch_ref"]
            or confirmation["source_version"] != source_ref
            or proposed_plan["review_batch_ref"]
            != application["review_batch_ref"]
            or proposed_plan["source_version"] != source_ref
            or confirmed_plan.get("supersedes_ref")
            != application["revision_plan_ref"]
            or confirmed_plan["review_batch_ref"]
            != application["review_batch_ref"]
            or confirmed_plan["source_version"] != source_ref
            or batch["source_version"] != source_ref
        ):
            raise ValueError("application lineage mismatch")
        return application

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        return hashlib.sha256(canonical_json(value)).hexdigest()


__all__ = ["ContentBatchPlanningService"]
