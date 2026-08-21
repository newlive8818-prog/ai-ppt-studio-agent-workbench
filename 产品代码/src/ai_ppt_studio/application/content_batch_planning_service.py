"""Whole-deck planning between a frozen content review and any rewrite."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_batch_revision_plan,
    validate_content_review_batch,
    validate_persisted_page_decision,
)
from ai_ppt_studio.domains.feedback.contracts import (
    validate_feedback_governance,
    validate_raw_feedback,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContentWorkflowError,
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


PLAN_HEAD = "content/batch-revision-plan"
PLAN_KIND = "content-batch-revision-plan"
PLAN_CONFIRMATION_HEAD = "content/batch-plan-confirmation"
PLAN_CONFIRMATION_KIND = "content-batch-plan-confirmation"
PLAN_CONFIRMATION_SCOPE = "content-batch-plan-confirmation"
REVIEW_BATCH_HEAD = "content/review-batch"
REVIEW_BATCH_KIND = "content-review-batch"
BLUEPRINT_HEAD = "content/blueprint"
APPLICATION_HEAD = "content/review-batch-application"
APPLICATION_KIND = "content-review-batch-application"
PLAN_CONFIRMATION_FIELDS = frozenset(
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
        "review_batch_ref",
        "review_batch_id",
        "revision_plan_ref",
        "plan_version",
        "requires_blueprint_revision",
    }
)


class ContentBatchPlanningService:
    """Persist, confirm, and apply one complete whole-deck revision plan."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def save_revision_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> tuple[str, str, KernelState]:
        plan = validate_content_batch_revision_plan(payload)
        fingerprint = self._fingerprint(
            {"operation": "save-content-batch-revision-plan", "plan": plan}
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command_id in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command_id,
                    expected_revision=expected_revision,
                    event_type="content.batch-revision-plan-proposed",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                plan_ref, batch_ref = self._replay_heads(
                    command_id,
                    replay,
                    event_type="content.batch-revision-plan-proposed",
                    slots=(PLAN_HEAD, REVIEW_BATCH_HEAD),
                )
                return (
                    plan_ref,
                    batch_ref,
                    replay,
                )
            self._require_revision(expected_revision, state.revision)
            batch_ref, batch = self._current_batch(state)
            if batch_ref != plan["review_batch_ref"] or batch["status"] != "submitted":
                self._workflow(
                    "CONTENT_REVIEW_BATCH_NOT_SUBMITTED",
                    "Revision planning requires the exact current submitted batch",
                    {"current_batch_ref": batch_ref, "status": batch["status"]},
                )
            if (
                batch["review_batch_id"] != plan["review_batch_id"]
                or batch["source_version"] != plan["source_version"]
                or state.artifact_heads.get(BLUEPRINT_HEAD) != plan["source_version"]
            ):
                self._workflow(
                    "CONTENT_REVIEW_CONFLICT",
                    "Revision plan does not bind the current batch and source",
                )
            blueprint = self._resolve(plan["source_version"], "content-blueprint")
            authoritative_slide_ids = {
                str(slide.get("slide_id") or "")
                for slide in blueprint.get("slides", [])
                if isinstance(slide, dict) and slide.get("slide_id")
            }
            unknown_slide_ids = sorted(
                self._plan_slide_ids(plan) - authoritative_slide_ids
            )
            if unknown_slide_ids:
                self._workflow(
                    "CONTENT_BATCH_PLAN_SLIDE_UNKNOWN",
                    "Revision plan targets pages outside the current blueprint",
                    {"slide_ids": unknown_slide_ids},
                )
            if (
                not plan["requires_blueprint_revision"]
                and not self._all_approved(batch)
            ):
                self._workflow(
                    "CONTENT_BATCH_REVISION_REQUIRED",
                    "A non-approved page decision requires a blueprint revision",
                    {"counts": batch["counts"]},
                )
            lifecycle = self._advance_batch(
                batch, predecessor_ref=batch_ref, status="plan-proposed"
            )
            committed = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="content.batch-revision-plan-proposed",
                artifact_updates={
                    PLAN_HEAD: (PLAN_KIND, plan),
                    REVIEW_BATCH_HEAD: (REVIEW_BATCH_KIND, lifecycle),
                },
                command_fingerprint=fingerprint,
            )
            return (
                committed.artifact_heads[PLAN_HEAD],
                committed.artifact_heads[REVIEW_BATCH_HEAD],
                committed,
            )

    def confirmation_context(
        self, *, review_batch_id: str, plan_ref: str
    ) -> dict[str, Any]:
        state = self.kernel.load()
        plan = self._current_plan(state, plan_ref)
        batch_ref, batch = self._current_batch(state)
        if (
            batch["status"] != "plan-proposed"
            or batch["review_batch_id"] != review_batch_id
            or plan["review_batch_id"] != review_batch_id
        ):
            self._workflow(
                "CONTENT_BATCH_PLAN_NOT_PROPOSED",
                "Only the current proposed whole-deck plan can be confirmed",
            )
        return self.confirmations.context(
            scope_kind=PLAN_CONFIRMATION_SCOPE,
            scope_id=f"{review_batch_id}:{plan['plan_version']}:{plan_ref}",
            source_version=plan_ref,
            evidence_refs=[
                plan["review_batch_ref"],
                plan["source_version"],
                plan_ref,
            ],
        )

    def require_current_plan_confirmation(
        self, plan_confirmation_ref: str
    ) -> dict[str, Any]:
        """Resolve one ledger-bound current confirmation or fail closed."""

        return self._current_confirmation(
            self.kernel.load(), plan_confirmation_ref
        )

    def confirm_revision_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_batch_id: str,
        plan_ref: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, str, KernelState]:
        fingerprint = self._fingerprint(
            {
                "operation": "confirm-content-batch-revision-plan",
                "review_batch_id": review_batch_id,
                "plan_ref": plan_ref,
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
                "assertion_sha256": hashlib.sha256(
                    host_confirmation_assertion.encode("utf-8")
                ).hexdigest(),
            }
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command_id in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command_id,
                    expected_revision=expected_revision,
                    event_type="content.batch-revision-plan-confirmed",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                confirmation_ref, batch_ref = self._replay_heads(
                    command_id,
                    replay,
                    event_type="content.batch-revision-plan-confirmed",
                    slots=(PLAN_CONFIRMATION_HEAD, REVIEW_BATCH_HEAD),
                )
                return confirmation_ref, batch_ref, replay
            self._require_revision(expected_revision, state.revision)
            current = self.confirmation_context(
                review_batch_id=review_batch_id, plan_ref=plan_ref
            )
            plan = self._current_plan(state, plan_ref)
            batch_ref, batch = self._current_batch(state)
            scoped, consumptions = self.confirmations.confirmation_payload(
                current=current,
                source_version=plan_ref,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=host_confirmation_assertion,
            )
            confirmation = {
                **scoped,
                "review_batch_ref": plan["review_batch_ref"],
                "review_batch_id": review_batch_id,
                "revision_plan_ref": plan_ref,
                "plan_version": plan["plan_version"],
                "requires_blueprint_revision": plan[
                    "requires_blueprint_revision"
                ],
            }
            lifecycle = self._advance_batch(
                batch, predecessor_ref=batch_ref, status="plan-confirmed"
            )
            try:
                committed = self.kernel.commit(
                    command_id=command_id,
                    expected_revision=expected_revision,
                    event_type="content.batch-revision-plan-confirmed",
                    artifact_updates={
                        PLAN_CONFIRMATION_HEAD: (
                            PLAN_CONFIRMATION_KIND,
                            confirmation,
                        ),
                        REVIEW_BATCH_HEAD: (REVIEW_BATCH_KIND, lifecycle),
                    },
                    confirmation_consumptions=consumptions,
                    command_fingerprint=fingerprint,
                )
            except ConfirmationTransactionError:
                self._workflow(
                    "CONTENT_REVIEW_CONFLICT",
                    "The trusted plan-confirmation transaction was rejected",
                )
            return (
                committed.artifact_heads[PLAN_CONFIRMATION_HEAD],
                committed.artifact_heads[REVIEW_BATCH_HEAD],
                committed,
            )

    def create_governance_and_change_set(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_confirmation_ref: str,
    ) -> tuple[str, str, KernelState]:
        fingerprint = self._fingerprint(
            {
                "operation": "create-content-batch-governance-and-change-set",
                "plan_confirmation_ref": plan_confirmation_ref,
            }
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command_id in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command_id,
                    expected_revision=expected_revision,
                    event_type="content.batch-plan-governed-change-set-created",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                governance_ref, change_set_ref = self._replay_heads(
                    command_id,
                    replay,
                    event_type="content.batch-plan-governed-change-set-created",
                    slots=("feedback/governance", "content/change-set"),
                )
                return governance_ref, change_set_ref, replay
            self._require_revision(expected_revision, state.revision)
            confirmation = self._current_confirmation(
                state, plan_confirmation_ref
            )
            plan_ref = confirmation["revision_plan_ref"]
            plan = self._current_plan(state, plan_ref)
            _current_batch_ref, current_batch = self._current_batch(state)
            if current_batch["status"] != "plan-confirmed":
                self._workflow(
                    "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                    "The current review batch has no confirmed revision plan",
                )
            if not plan["requires_blueprint_revision"]:
                self._workflow(
                    "CONTENT_BATCH_REVISION_NOT_REQUIRED",
                    "A no-revision plan cannot create governance or a change set",
                )
            submitted = self._resolve(
                plan["review_batch_ref"], "content-review-batch"
            )
            decisions = [
                validate_persisted_page_decision(
                    self._resolve(ref, "content-page-decision")
                )
                for ref in submitted["decision_refs"]
            ]
            page_decisions = [
                {
                    "decision_ref": ref,
                    "decision": decision["decision"],
                    "comment": decision["comment"],
                }
                for ref, decision in zip(
                    submitted["decision_refs"], decisions
                )
            ]
            raw = validate_raw_feedback(
                {
                    "raw_feedback": "\n".join(
                        f"{row['decision']}: {row['comment']}".rstrip()
                        for row in page_decisions
                    ),
                    "target_refs": list(submitted["decision_refs"]),
                    "page_decisions": page_decisions,
                    "review_batch_ref": plan["review_batch_ref"],
                    "revision_plan_ref": plan_ref,
                    "plan_confirmation_ref": plan_confirmation_ref,
                    "source_version": plan["source_version"],
                }
            )
            raw_ref = str(
                self.kernel.artifacts.reference_for("raw-feedback", raw)
            )
            affected_refs = [
                ref
                for ref, decision in zip(
                    submitted["decision_refs"], decisions
                )
                if decision["decision"] != "approved"
            ]
            governance = validate_feedback_governance(
                {
                    "raw_feedback_ref": raw_ref,
                    "feedback_level": "F1",
                    "diagnosis": (
                        "已将冻结批次的逐页判断汇总为整套修改方案"
                    ),
                    "scope": "whole-deck-confirmed-plan",
                    "counterexamples": [
                        "不得把单页意见直接扩大为未确认的全稿修改"
                    ],
                    "ai_recommendation": json.dumps(
                        plan, ensure_ascii=False, sort_keys=True
                    ),
                    "preserve_refs": [plan["source_version"]],
                    "review_batch_ref": plan["review_batch_ref"],
                    "revision_plan_ref": plan_ref,
                    "plan_confirmation_ref": plan_confirmation_ref,
                    "affected_refs": affected_refs,
                    "full_deck_re_review_route": plan["re_review_scope"],
                }
            )
            governance_ref = str(
                self.kernel.artifacts.reference_for(
                    "feedback-governance-record", governance
                )
            )
            change_set = {
                "feedback_governance_record_ref": governance_ref,
                "governed_intent": governance["ai_recommendation"],
                "target_refs": list(submitted["decision_refs"]),
                "affected_refs": affected_refs,
                "preserve_refs": [plan["source_version"]],
                "scope": "whole-deck-confirmed-plan",
                "required_role_runs": ["content-repair-specialist"],
                "review_route": plan["re_review_scope"],
                "review_batch_ref": plan["review_batch_ref"],
                "revision_plan_ref": plan_ref,
                "plan_confirmation_ref": plan_confirmation_ref,
                "source_blueprint_ref": plan["source_version"],
                "status": "ready",
            }
            committed = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="content.batch-plan-governed-change-set-created",
                artifact_updates={
                    "feedback/raw": ("raw-feedback", raw),
                    "feedback/governance": (
                        "feedback-governance-record",
                        governance,
                    ),
                    "content/change-set": ("content-change-set", change_set),
                },
                command_fingerprint=fingerprint,
            )
            return (
                committed.artifact_heads["feedback/governance"],
                committed.artifact_heads["content/change-set"],
                committed,
            )

    def apply_no_revision_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_confirmation_ref: str,
    ) -> tuple[str, KernelState]:
        fingerprint = self._fingerprint(
            {
                "operation": "apply-content-batch-no-revision-plan",
                "plan_confirmation_ref": plan_confirmation_ref,
            }
        )
        with self.kernel.semantic_command(fingerprint):
            state = self.kernel.load()
            if command_id in state.processed_commands:
                replay = self.kernel.commit(
                    command_id=command_id,
                    expected_revision=expected_revision,
                    event_type="content.no-revision-plan-applied",
                    artifact_updates={},
                    command_fingerprint=fingerprint,
                )
                (applied_ref,) = self._replay_heads(
                    command_id,
                    replay,
                    event_type="content.no-revision-plan-applied",
                    slots=(REVIEW_BATCH_HEAD,),
                )
                return applied_ref, replay
            self._require_revision(expected_revision, state.revision)
            confirmation = self._current_confirmation(
                state, plan_confirmation_ref
            )
            plan = self._current_plan(state, confirmation["revision_plan_ref"])
            batch_ref, batch = self._current_batch(state)
            if (
                plan["requires_blueprint_revision"]
                or not self._all_approved(batch)
            ):
                self._workflow(
                    "CONTENT_BATCH_REVISION_REQUIRED",
                    "Only an all-approved no-revision plan can be applied directly",
                )
            if batch["status"] != "plan-confirmed":
                self._workflow(
                    "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                    "The no-revision plan must be current and confirmed",
                )
            lifecycle = self._advance_batch(
                batch, predecessor_ref=batch_ref, status="applied"
            )
            application = {
                "review_batch_id": batch["review_batch_id"],
                "review_batch_ref": plan["review_batch_ref"],
                "applied_batch_ref": str(
                    self.kernel.artifacts.reference_for(
                        REVIEW_BATCH_KIND, lifecycle
                    )
                ),
                "revision_plan_ref": confirmation["revision_plan_ref"],
                "plan_confirmation_ref": plan_confirmation_ref,
                "source_version": plan["source_version"],
                "result": "applied-without-blueprint-revision",
            }
            committed = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="content.no-revision-plan-applied",
                artifact_updates={
                    REVIEW_BATCH_HEAD: (REVIEW_BATCH_KIND, lifecycle),
                    APPLICATION_HEAD: (APPLICATION_KIND, application),
                },
                command_fingerprint=fingerprint,
            )
            return committed.artifact_heads[REVIEW_BATCH_HEAD], committed

    def _current_batch(self, state: KernelState) -> tuple[str, dict[str, Any]]:
        ref = state.artifact_heads.get(REVIEW_BATCH_HEAD, "")
        if not ref:
            self._workflow(
                "CONTENT_REVIEW_BATCH_NOT_SUBMITTED",
                "No current content review batch exists",
            )
        payload = self._resolve(ref, REVIEW_BATCH_KIND)
        return ref, validate_content_review_batch(payload)

    def _current_plan(self, state: KernelState, expected_ref: str) -> dict[str, Any]:
        if state.artifact_heads.get(PLAN_HEAD) != expected_ref:
            self._workflow(
                "CONTENT_BATCH_PLAN_NOT_CURRENT",
                "Revision plan is not the current authoritative plan",
            )
        return validate_content_batch_revision_plan(
            self._resolve(expected_ref, PLAN_KIND)
        )

    def _current_confirmation(
        self, state: KernelState, expected_ref: str
    ) -> dict[str, Any]:
        if state.artifact_heads.get(PLAN_CONFIRMATION_HEAD) != expected_ref:
            self._workflow(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "Plan confirmation is not current",
            )
        confirmation = self._resolve(expected_ref, PLAN_CONFIRMATION_KIND)
        plan_ref = str(confirmation.get("revision_plan_ref") or "")
        try:
            plan = self._current_plan(state, plan_ref)
        except (ContentWorkflowError, ContractValidationError):
            self._workflow(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "Plan confirmation does not resolve its current revision plan",
            )
        expected_evidence = [
            plan["review_batch_ref"],
            plan["source_version"],
            plan_ref,
        ]
        identity_type = confirmation.get("confirmation_identity_type")
        action_ref = confirmation.get("user_action_ref")
        message_ref = confirmation.get("user_message_ref")
        identity_valid = (
            identity_type == "host-action"
            and isinstance(action_ref, str)
            and bool(action_ref)
            and message_ref == ""
        ) or (
            identity_type == "verified-message"
            and isinstance(message_ref, str)
            and bool(message_ref)
            and action_ref == ""
        )
        challenge_body = {
            "project_id": state.project_id,
            "project_root": str(self.kernel.project_root),
            "scope_kind": PLAN_CONFIRMATION_SCOPE,
            "scope_id": confirmation.get("scope_id"),
            "source_version": plan_ref,
            "evidence_refs": expected_evidence,
            "challenge_revision": confirmation.get("challenge_revision"),
        }
        identity = str(action_ref or message_ref or "")
        try:
            ledger_valid = (
                self.kernel.confirmation_owner(identity)
                == f"{PLAN_CONFIRMATION_SCOPE}:{confirmation.get('scope_id')}"
                and self.kernel.confirmation_artifact_binding(identity)
                == expected_ref
            )
        except ConfirmationTransactionError:
            ledger_valid = False
        assertion_digest = confirmation.get("host_assertion_sha256")
        if (
            set(confirmation) != PLAN_CONFIRMATION_FIELDS
            or confirmation.get("project_id") != state.project_id
            or confirmation.get("scope_kind") != PLAN_CONFIRMATION_SCOPE
            or confirmation.get("source_version") != plan_ref
            or confirmation.get("review_batch_ref")
            != plan["review_batch_ref"]
            or confirmation.get("review_batch_id")
            != plan["review_batch_id"]
            or confirmation.get("plan_version") != plan["plan_version"]
            or confirmation.get("requires_blueprint_revision")
            != plan["requires_blueprint_revision"]
            or confirmation.get("scope_id")
            != f"{plan['review_batch_id']}:{plan['plan_version']}:{plan_ref}"
            or confirmation.get("evidence_refs") != expected_evidence
            or not identity_valid
            or self.confirmations.challenge_id(challenge_body)
            != confirmation.get("challenge_id")
            or not isinstance(assertion_digest, str)
            or len(assertion_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in assertion_digest
            )
            or not ledger_valid
        ):
            self._workflow(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "Plan confirmation lineage is invalid",
            )
        return confirmation

    def _resolve(self, value: str, expected_kind: str) -> dict[str, Any]:
        try:
            reference = ArtifactReference.parse(value)
            if reference.kind != expected_kind:
                raise ArtifactReferenceError("Unexpected artifact kind")
            payload = self.kernel.artifacts.resolve(reference)["payload"]
        except (ArtifactReferenceError, KeyError, TypeError) as error:
            raise ContractValidationError(
                f"Cannot resolve {expected_kind} artifact"
            ) from error
        if not isinstance(payload, dict):
            raise ContractValidationError(
                f"{expected_kind} payload must be an object"
            )
        return payload

    def _replay_heads(
        self,
        command_id: str,
        state: KernelState,
        *,
        event_type: str,
        slots: tuple[str, ...],
    ) -> tuple[str, ...]:
        revision = state.processed_commands[command_id]
        try:
            event = json.loads(
                (
                    self.kernel.events_root / f"r{revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            if event.get("event_type") != event_type:
                raise ValueError("Processed command event type differs")
            values = tuple(str(event["artifact_heads"][slot]) for slot in slots)
            if any(not value for value in values):
                raise ValueError("Processed command receipt is incomplete")
            return values
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise ContractValidationError(
                "Processed content-batch planning receipt is unavailable"
            ) from error

    @staticmethod
    def _advance_batch(
        batch: dict[str, Any], *, predecessor_ref: str, status: str
    ) -> dict[str, Any]:
        candidate = copy.deepcopy(batch)
        candidate["status"] = status
        candidate["supersedes_ref"] = predecessor_ref
        return validate_content_review_batch(candidate, prior_submitted=batch)

    @staticmethod
    def _all_approved(batch: dict[str, Any]) -> bool:
        return batch["counts"]["approved"] == batch["expected_slide_count"]

    @staticmethod
    def _plan_slide_ids(plan: dict[str, Any]) -> set[str]:
        slide_ids: set[str] = set()
        for field in (
            "direct_actions",
            "cross_page_actions",
            "evidence_actions",
            "revised_chapters",
        ):
            for action in plan[field]:
                slide_ids.update(action["slide_ids"])
        for action in plan["merge_delete_actions"]:
            slide_ids.update(action["source_slide_ids"])
            slide_ids.add(action["target_slide_id"])
        return slide_ids

    @staticmethod
    def _require_revision(expected: object, actual: int) -> None:
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
    def _fingerprint(payload: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _workflow(
        code: str, message: str, details: dict[str, object] | None = None
    ) -> None:
        raise ContentWorkflowError(code, f"{code}: {message}", details)
