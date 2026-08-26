"""Batch-wide revision planning separate from G0 and content editing."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from ai_ppt_studio.application.content_review._shared import (
    decision_lineage,
    fingerprint,
    payload,
    replay_ref,
    review_context,
    stable_id,
)
from ai_ppt_studio.application.review_session_service import (
    authoritative_target_publication_revision,
)
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
from ai_ppt_studio.domains.content.page_decisions import DECISIONS
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from ai_ppt_studio.domains.content.revision_plans import validate_revision_plan
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import ContractValidationError, ReviewSourceStaleError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


PLAN_APPLICATION_SLOT = "content/revision-plan-application"
PLAN_APPLICATION_KIND = "content-batch-revision-plan-application"


class ContentRevisionPlanningService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def save_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        batch_ref: str,
        source_version: str,
        plan: dict[str, Any],
    ):
        values = {"batch_ref": batch_ref, "source_version": source_version, "plan": plan}
        command_fingerprint = fingerprint("save-content-batch-revision-plan", values)
        slot = "content/revision-plan"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, validate_revision_plan(
                payload(self.kernel, reference, "content-batch-revision-plan")
            ), state
        state = self._state(expected_revision)
        batch = self._current_batch(
            state,
            batch_ref,
            source_version,
            require_current_content_authority=True,
        )
        plan_payload = validate_revision_plan(
            {
                "plan_id": stable_id("content-revision-plan", batch_ref, command_id),
                "project_id": state.project_id,
                "batch_ref": batch_ref,
                "source_version": source_version,
                "reading_blueprint_ref": batch["reading_blueprint_ref"],
                "plan": plan,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._require_plan_semantics(plan_payload, batch)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.revision-plan-saved",
            artifact_updates={slot: ("content-batch-revision-plan", plan_payload)},
            artifact_removals=tuple(
                name
                for name in ("content/revision-plan-confirmation", "content/change-set")
                if state.artifact_heads.get(name)
            ),
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], plan_payload, committed

    def confirmation_context(
        self,
        *,
        plan_ref: str,
        source_version: str,
    ) -> dict[str, Any]:
        state = self.kernel.load()
        _plan, batch = self._current_plan_lineage(
            state,
            plan_ref=plan_ref,
            source_version=source_version,
        )
        context = self.confirmations.context(
            scope_kind="content-revision-plan",
            scope_id=plan_ref,
            source_version=source_version,
            evidence_refs=[
                batch["batch_ref"],
                plan_ref,
                batch["reading_blueprint_ref"],
            ],
        )
        if context["challenge_revision"] != state.revision:
            raise RevisionConflictError(
                state.revision, context["challenge_revision"]
            )
        return context

    def confirm_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_ref: str,
        source_version: str,
        challenge_id: str = "",
        challenge_revision: int = -1,
        host_confirmation_assertion: str = "",
        user_action_ref: str = "",
        user_message_ref: str = "",
    ):
        if str(user_action_ref or "").strip() or str(
            user_message_ref or ""
        ).strip():
            raise ContractValidationError(
                "Plan confirmation rejects unverified host confirmation identities"
            )
        values = {
            "plan_ref": plan_ref,
            "source_version": source_version,
            "challenge_id": challenge_id,
            "challenge_revision": challenge_revision,
            "host_assertion_sha256": hashlib.sha256(
                host_confirmation_assertion.encode("utf-8")
            ).hexdigest(),
        }
        command_fingerprint = fingerprint("confirm-content-batch-revision-plan", values)
        slot = "content/revision-plan-confirmation"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, state
        state = self._state(expected_revision)
        plan, batch = self._current_plan_lineage(
            state,
            plan_ref=plan_ref,
            source_version=source_version,
        )
        current = self.confirmation_context(
            plan_ref=plan_ref,
            source_version=source_version,
        )
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=current,
            source_version=source_version,
            challenge_id=challenge_id,
            challenge_revision=challenge_revision,
            host_confirmation_assertion=host_confirmation_assertion,
        )
        confirmation = {
            **scoped,
            "confirmation_id": stable_id("content-plan-confirmation", plan_ref, command_id),
            "plan_ref": plan_ref,
            "batch_ref": plan["batch_ref"],
            "reading_blueprint_ref": batch["reading_blueprint_ref"],
            "status": "confirmed",
            "is_g0": False,
        }
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.revision-plan-confirmed",
            artifact_updates={slot: ("content-batch-revision-plan-confirmation", confirmation)},
            confirmation_consumptions=consumptions,
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], committed

    def create_change_set(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_ref: str,
        confirmation_ref: str,
        source_version: str,
    ):
        values = {
            "plan_ref": plan_ref,
            "confirmation_ref": confirmation_ref,
            "source_version": source_version,
        }
        command_fingerprint = fingerprint("create-content-batch-change-set", values)
        slot = "content/change-set"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, payload(self.kernel, reference, "content-change-set"), state
        state = self._state(expected_revision)
        if state.artifact_heads.get("content/revision-plan") != plan_ref or state.artifact_heads.get("content/revision-plan-confirmation") != confirmation_ref:
            raise ContractValidationError("Plan and confirmation must both be current")
        plan, batch = self._current_plan_lineage(
            state,
            plan_ref=plan_ref,
            source_version=source_version,
        )
        confirmation = payload(
            self.kernel, confirmation_ref, "content-batch-revision-plan-confirmation"
        )
        self._require_trusted_confirmation(
            state,
            confirmation_ref=confirmation_ref,
            confirmation=confirmation,
            plan_ref=plan_ref,
            plan=plan,
            batch=batch,
            source_version=source_version,
        )
        if (
            plan["source_version"] != source_version
            or confirmation.get("source_version") != source_version
            or confirmation.get("plan_ref") != plan_ref
            or confirmation.get("batch_ref") != plan["batch_ref"]
        ):
            raise ReviewSourceStaleError(source_version, plan["source_version"])
        change = {
            "change_set_id": stable_id("content-change-set", plan_ref, command_id),
            "project_id": state.project_id,
            "source_version": source_version,
            "reading_blueprint_ref": batch["reading_blueprint_ref"],
            "batch_ref": plan["batch_ref"],
            "plan_ref": plan_ref,
            "confirmation_ref": confirmation_ref,
            "plan": plan["plan"],
            "status": "ready",
            "is_g0": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.change-set-created",
            artifact_updates={slot: ("content-change-set", change)},
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], change, committed

    def prepare_application(
        self,
        *,
        state,
        change_set_ref: str,
        new_reading_blueprint_ref: str,
        new_source_version: str,
    ) -> dict[str, Any]:
        if state.artifact_heads.get("content/change-set") != change_set_ref:
            raise ContractValidationError("change_set_ref is not current")
        change = payload(self.kernel, change_set_ref, "content-change-set")
        plan_ref = str(change.get("plan_ref") or "")
        confirmation_ref = str(change.get("confirmation_ref") or "")
        source_version = str(change.get("source_version") or "")
        plan, batch = self._current_plan_lineage(
            state,
            plan_ref=plan_ref,
            source_version=source_version,
            require_current_content_authority=False,
        )
        if (
            state.artifact_heads.get("content/revision-plan-confirmation")
            != confirmation_ref
        ):
            raise ContractValidationError(
                "The change set does not bind the current plan confirmation"
            )
        confirmation = payload(
            self.kernel,
            confirmation_ref,
            "content-batch-revision-plan-confirmation",
        )
        self._require_trusted_confirmation(
            state,
            confirmation_ref=confirmation_ref,
            confirmation=confirmation,
            plan_ref=plan_ref,
            plan=plan,
            batch=batch,
            source_version=source_version,
        )
        expected_change = {
            "project_id": state.project_id,
            "source_version": source_version,
            "reading_blueprint_ref": batch["reading_blueprint_ref"],
            "batch_ref": batch["batch_ref"],
            "plan_ref": plan_ref,
            "confirmation_ref": confirmation_ref,
            "plan": plan["plan"],
            "status": "ready",
            "is_g0": False,
        }
        if any(change.get(key) != value for key, value in expected_change.items()):
            raise ContractValidationError(
                "The current change set does not bind the confirmed plan"
            )
        if (
            not isinstance(new_source_version, str)
            or not new_source_version.strip()
            or new_source_version == source_version
        ):
            raise ContractValidationError(
                "Applying a confirmed plan requires a new source version"
            )
        try:
            new_reference = ArtifactReference.parse(new_reading_blueprint_ref)
        except Exception as error:
            raise ContractValidationError(
                "Plan application target must be a reading blueprint reference"
            ) from error
        if new_reference.kind != "reading-deck-blueprint":
            raise ContractValidationError(
                "Plan application target must be a reading blueprint reference"
            )
        return {
            "application_id": stable_id(
                "content-revision-plan-application",
                change_set_ref,
                new_reading_blueprint_ref,
            ),
            "project_id": state.project_id,
            "source_version": source_version,
            "new_source_version": new_source_version,
            "reading_blueprint_ref": batch["reading_blueprint_ref"],
            "new_reading_blueprint_ref": new_reading_blueprint_ref,
            "batch_ref": batch["batch_ref"],
            "plan_ref": plan_ref,
            "confirmation_ref": confirmation_ref,
            "change_set_ref": change_set_ref,
            "rereview_scope": list(plan["plan"]["rereview_scope"]),
            "status": "applied",
            "is_g0": False,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        }

    def _state(self, expected_revision: int):
        state = self.kernel.load()
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        return state

    def _current_batch(
        self,
        state,
        batch_ref: str,
        source_version: str,
        *,
        require_current_content_authority: bool = False,
    ):
        if state.artifact_heads.get("content/review-batch") != batch_ref:
            raise ContractValidationError("batch_ref is not current")
        batch = validate_content_review_batch(
            payload(self.kernel, batch_ref, "content-review-batch")
        )
        if batch["source_version"] != source_version:
            raise ReviewSourceStaleError(source_version, batch["source_version"])
        if batch["status"] != "submitted":
            raise ContractValidationError("Revision plan requires a submitted batch")
        blueprint = validate_reading_deck_blueprint(
            payload(
                self.kernel,
                batch["reading_blueprint_ref"],
                "reading-deck-blueprint",
            )
        )
        session_ref = state.review_session_ref("content-full-deck")
        session = validate_review_session(
            payload(self.kernel, session_ref, "review-session"),
            trusted_receipts=True,
        )
        authoritative_revision = authoritative_target_publication_revision(
            self.kernel,
            state,
            "content-full-deck",
            batch["reading_blueprint_ref"],
        )
        if (
            batch["project_id"] != state.project_id
            or blueprint["project_id"] != state.project_id
            or blueprint["source_version"] != source_version
            or batch["review_session_id"] != session["review_session_id"]
            or session["project_id"] != state.project_id
            or session["review_type"] != "content-full-deck"
            or session["target_artifact_ref"] != batch["reading_blueprint_ref"]
            or session["source_version"] != source_version
            or session["revision"] != authoritative_revision
            or session["status"] != "submitted"
        ):
            raise ContractValidationError(
                "Revision plan requires the exact submitted review authority"
            )
        if require_current_content_authority:
            current = review_context(
                self.kernel,
                batch["review_session_id"],
                source_version=source_version,
            )
            if (
                current.blueprint_ref != batch["reading_blueprint_ref"]
                or current.session_ref != session_ref
            ):
                raise ContractValidationError(
                    "Revision plan requires current content authority"
                )
        slides = blueprint["slides"]
        if batch["slide_ids"] != [slide["slide_id"] for slide in slides]:
            raise ContractValidationError(
                "Revision plan requires the exact current review batch"
            )
        actual_counts: Counter[str] = Counter()
        for slide, decision_ref in zip(slides, batch["decision_refs"], strict=True):
            slot = f"content/review/decision/{slide['slide_id']}"
            if state.artifact_heads.get(slot) != decision_ref:
                raise ContractValidationError(
                    "Revision plan requires current PageDecision heads"
                )
            decision = decision_lineage(
                self.kernel,
                decision_ref,
                {
                    "project_id": state.project_id,
                    "review_session_id": session["review_session_id"],
                    "source_version": source_version,
                    "reading_blueprint_ref": batch["reading_blueprint_ref"],
                    "slide_id": slide["slide_id"],
                    "slide_order": slide["order"],
                    "slide_title_snapshot": slide["neutral_title"],
                    "status": "completed",
                },
            )
            actual_counts[decision["decision"]] += 1
        if batch["counts"] != {
            choice: actual_counts.get(choice, 0) for choice in DECISIONS
        }:
            raise ContractValidationError(
                "Revision plan batch counts do not match current PageDecisions"
            )
        return batch

    def _current_plan_lineage(
        self,
        state,
        *,
        plan_ref: str,
        source_version: str,
        require_current_content_authority: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if state.artifact_heads.get("content/revision-plan") != plan_ref:
            raise ContractValidationError("plan_ref is not current")
        plan = validate_revision_plan(
            payload(self.kernel, plan_ref, "content-batch-revision-plan")
        )
        if plan["project_id"] != state.project_id:
            raise ContractValidationError("Revision plan belongs to another project")
        if plan["source_version"] != source_version:
            raise ReviewSourceStaleError(source_version, plan["source_version"])
        batch = self._current_batch(
            state,
            plan["batch_ref"],
            source_version,
            require_current_content_authority=require_current_content_authority,
        )
        self._require_plan_semantics(plan, batch)
        if (
            batch["project_id"] != state.project_id
            or batch["reading_blueprint_ref"] != plan["reading_blueprint_ref"]
        ):
            raise ContractValidationError(
                "Revision plan does not bind the current review batch"
            )
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        if blueprint_ref != plan["reading_blueprint_ref"]:
            raise ContractValidationError(
                "Revision plan does not bind the current reading blueprint"
            )
        blueprint = validate_reading_deck_blueprint(
            payload(self.kernel, blueprint_ref, "reading-deck-blueprint")
        )
        if (
            blueprint["project_id"] != state.project_id
            or blueprint["source_version"] != source_version
        ):
            raise ReviewSourceStaleError(
                source_version, str(blueprint.get("source_version") or "")
        )
        return plan, {**batch, "batch_ref": plan["batch_ref"]}

    @staticmethod
    def _require_plan_semantics(
        plan: dict[str, Any], batch: dict[str, Any]
    ) -> None:
        requested = sum(
            batch["counts"][choice]
            for choice in ("modify", "evidence", "merge-or-delete")
        )
        if requested == 0:
            raise ContractValidationError(
                "Revision plan requires at least one non-approved PageDecision"
            )
        if plan["plan"]["rereview_scope"] != ["all"]:
            raise ContractValidationError(
                "Revision plan must require complete full-deck rereview"
            )

    def _require_trusted_confirmation(
        self,
        state,
        *,
        confirmation_ref: str,
        confirmation: dict[str, Any],
        plan_ref: str,
        plan: dict[str, Any],
        batch: dict[str, Any],
        source_version: str,
    ) -> None:
        evidence_refs = [
            batch["batch_ref"],
            plan_ref,
            batch["reading_blueprint_ref"],
        ]
        expected = {
            "project_id": state.project_id,
            "scope_kind": "content-revision-plan",
            "scope_id": plan_ref,
            "source_version": source_version,
            "evidence_refs": evidence_refs,
            "plan_ref": plan_ref,
            "batch_ref": plan["batch_ref"],
            "reading_blueprint_ref": batch["reading_blueprint_ref"],
            "status": "confirmed",
            "is_g0": False,
        }
        if any(confirmation.get(key) != value for key, value in expected.items()):
            raise ContractValidationError(
                "Plan confirmation does not bind the current plan lineage"
            )
        challenge_revision = confirmation.get("challenge_revision")
        if (
            isinstance(challenge_revision, bool)
            or not isinstance(challenge_revision, int)
            or challenge_revision < 0
            or challenge_revision >= state.revision
        ):
            raise ContractValidationError(
                "Plan confirmation challenge revision is invalid"
            )
        expected_challenge = ScopedConfirmationPolicy.challenge_id(
            {
                "project_id": state.project_id,
                "project_root": str(self.kernel.project_root),
                "scope_kind": "content-revision-plan",
                "scope_id": plan_ref,
                "source_version": source_version,
                "evidence_refs": evidence_refs,
                "challenge_revision": challenge_revision,
            }
        )
        if confirmation.get("challenge_id") != expected_challenge:
            raise ContractValidationError(
                "Plan confirmation challenge does not match its lineage"
            )
        identity_type = confirmation.get("confirmation_identity_type")
        action_ref = str(confirmation.get("user_action_ref") or "").strip()
        message_ref = str(confirmation.get("user_message_ref") or "").strip()
        if (
            (identity_type == "host-action" and bool(action_ref) and not message_ref)
            or (
                identity_type == "verified-message"
                and bool(message_ref)
                and not action_ref
            )
        ):
            identity_ref = action_ref or message_ref
        else:
            raise ContractValidationError(
                "Plan confirmation identity is not a trusted exclusive identity"
            )
        assertion_digest = str(
            confirmation.get("host_assertion_sha256") or ""
        )
        if len(assertion_digest) != 64 or any(
            character not in "0123456789abcdef"
            for character in assertion_digest
        ):
            raise ContractValidationError(
                "Plan confirmation assertion digest is invalid"
            )
        owner = f"content-revision-plan:{plan_ref}"
        if (
            self.kernel.confirmation_owner(identity_ref) != owner
            or self.kernel.confirmation_artifact_binding(identity_ref)
            != confirmation_ref
        ):
            raise ContractValidationError(
                "Plan confirmation lacks an atomic consumption binding"
            )


__all__ = ["ContentRevisionPlanningService"]
