"""Batch-wide revision planning separate from G0 and content editing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.content_review._shared import (
    fingerprint,
    payload,
    replay_ref,
    stable_id,
)
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from ai_ppt_studio.domains.content.revision_plans import validate_revision_plan
from ai_ppt_studio.errors import ContractValidationError, ReviewSourceStaleError, RevisionConflictError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentRevisionPlanningService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

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
        batch = self._current_batch(state, batch_ref, source_version)
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

    def confirm_plan(
        self,
        *,
        command_id: str,
        expected_revision: int,
        plan_ref: str,
        source_version: str,
        user_message_ref: str,
    ):
        if not isinstance(user_message_ref, str) or not user_message_ref.startswith("chat://message/") or len(user_message_ref) <= len("chat://message/"):
            raise ContractValidationError(
                "Plan confirmation requires a trusted chat://message/... reference"
            )
        values = {
            "plan_ref": plan_ref,
            "source_version": source_version,
            "user_message_ref": user_message_ref,
        }
        command_fingerprint = fingerprint("confirm-content-batch-revision-plan", values)
        slot = "content/revision-plan-confirmation"
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, state
        state = self._state(expected_revision)
        if state.artifact_heads.get("content/revision-plan") != plan_ref:
            raise ContractValidationError("plan_ref is not current")
        plan = validate_revision_plan(
            payload(self.kernel, plan_ref, "content-batch-revision-plan")
        )
        if plan["source_version"] != source_version:
            raise ReviewSourceStaleError(source_version, plan["source_version"])
        confirmation = {
            "confirmation_id": stable_id("content-plan-confirmation", plan_ref, command_id),
            "project_id": state.project_id,
            "plan_ref": plan_ref,
            "batch_ref": plan["batch_ref"],
            "source_version": source_version,
            "user_message_ref": user_message_ref,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "status": "confirmed",
            "is_g0": False,
        }
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.revision-plan-confirmed",
            artifact_updates={slot: ("content-batch-revision-plan-confirmation", confirmation)},
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
        plan = validate_revision_plan(
            payload(self.kernel, plan_ref, "content-batch-revision-plan")
        )
        confirmation = payload(
            self.kernel, confirmation_ref, "content-batch-revision-plan-confirmation"
        )
        if (
            plan["source_version"] != source_version
            or confirmation.get("source_version") != source_version
            or confirmation.get("plan_ref") != plan_ref
            or confirmation.get("batch_ref") != plan["batch_ref"]
        ):
            raise ReviewSourceStaleError(source_version, plan["source_version"])
        self._current_batch(state, plan["batch_ref"], source_version)
        change = {
            "change_set_id": stable_id("content-change-set", plan_ref, command_id),
            "project_id": state.project_id,
            "source_version": source_version,
            "reading_blueprint_ref": plan["reading_blueprint_ref"],
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

    def _state(self, expected_revision: int):
        state = self.kernel.load()
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        return state

    def _current_batch(self, state, batch_ref: str, source_version: str):
        if state.artifact_heads.get("content/review-batch") != batch_ref:
            raise ContractValidationError("batch_ref is not current")
        batch = validate_content_review_batch(
            payload(self.kernel, batch_ref, "content-review-batch")
        )
        if batch["source_version"] != source_version:
            raise ReviewSourceStaleError(source_version, batch["source_version"])
        if batch["status"] != "submitted":
            raise ContractValidationError("Revision plan requires a submitted batch")
        return batch


__all__ = ["ContentRevisionPlanningService"]
