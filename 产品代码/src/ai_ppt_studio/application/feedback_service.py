"""Feedback capture, governance, decision and change-set writes."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.feedback.contracts import (
    decide_feedback as apply_feedback_decision,
    validate_feedback_governance,
    validate_raw_feedback,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContentWorkflowError,
    FeedbackGovernanceError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class FeedbackService:
    """Own governed feedback without acquiring content-producer authority."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def capture_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_raw_feedback(payload)
        for value in normalized["target_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.captured",
            artifact_updates={"feedback/raw": ("raw-feedback", normalized)},
        )
        return state.artifact_heads["feedback/raw"]

    def govern_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_feedback_governance(payload)
        raw_ref = normalized["raw_feedback_ref"]
        self._require_exact_ref(raw_ref, "feedback/raw", "raw-feedback")
        for value in normalized["preserve_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.governed",
            artifact_updates={
                "feedback/governance": (
                    "feedback-governance-record",
                    normalized,
                )
            },
        )
        return state.artifact_heads["feedback/governance"]

    def decide_feedback(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        choice: str,
    ) -> str:
        self._require_exact_ref(
            governance_ref,
            "feedback/governance",
            "feedback-governance-record",
        )
        current = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        decided = apply_feedback_decision(current, choice)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.decision-recorded",
            artifact_updates={
                "feedback/governance": (
                    "feedback-governance-record",
                    decided,
                )
            },
        )
        return state.artifact_heads["feedback/governance"]

    def create_content_change_set(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        plan_confirmation_ref: str = "",
    ) -> str:
        current_confirmation = self.kernel.load().artifact_heads.get(
            "content/batch-plan-confirmation", ""
        )
        if not plan_confirmation_ref or plan_confirmation_ref != current_confirmation:
            raise ContentWorkflowError(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED: ContentChangeSet requires "
                "the current exact whole-deck plan confirmation",
                {
                    "current_plan_confirmation_ref": current_confirmation,
                    "provided_plan_confirmation_ref": plan_confirmation_ref,
                },
            )
        try:
            self._require_exact_ref(
                governance_ref,
                "feedback/governance",
                "feedback-governance-record",
            )
        except ArtifactReferenceError as exc:
            raise FeedbackGovernanceError(
                "ContentChangeSet requires the current governed feedback record"
            ) from exc
        governance = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        if governance.get("plan_confirmation_ref") != plan_confirmation_ref:
            raise ContentWorkflowError(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED: governance is not bound "
                "to the current exact plan confirmation",
                {"governance_ref": governance_ref},
            )
        from ai_ppt_studio.application.content_batch_planning_service import (
            ContentBatchPlanningService,
        )

        confirmation = ContentBatchPlanningService(
            self.kernel
        ).require_current_plan_confirmation(plan_confirmation_ref)
        plan_ref = str(governance.get("revision_plan_ref") or "")
        if (
            confirmation.get("revision_plan_ref") != plan_ref
            or self.kernel.load().artifact_heads.get("content/batch-revision-plan")
            != plan_ref
        ):
            raise ContentWorkflowError(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED: governance and current "
                "confirmation do not bind the same revision plan",
                {"governance_ref": governance_ref},
            )
        plan = self.kernel.artifacts.resolve(
            ArtifactReference.parse(plan_ref)
        )["payload"]
        if governance.get("status") != "executable":
            raise FeedbackGovernanceError(
                "Feedback requires governance and any mandatory user decision"
            )
        raw = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance["raw_feedback_ref"])
        )["payload"]
        choice = governance.get("user_decision")
        governed_intent = (
            raw["raw_feedback"]
            if choice == "follow-user-instruction"
            else governance["ai_recommendation"]
        )
        change = {
            "feedback_governance_record_ref": governance_ref,
            "governed_intent": governed_intent,
            "target_refs": raw["target_refs"],
            "preserve_refs": governance["preserve_refs"],
            "scope": governance["scope"],
            "required_role_runs": ["presales-solution-chief"],
            "review_route": governance["full_deck_re_review_route"],
            "affected_refs": list(governance["affected_refs"]),
            "review_batch_ref": governance["review_batch_ref"],
            "revision_plan_ref": plan_ref,
            "plan_confirmation_ref": plan_confirmation_ref,
            "source_blueprint_ref": plan["source_version"],
            "status": "ready",
        }
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.change-set-created",
            artifact_updates={
                "content/change-set": ("content-change-set", change)
            },
        )
        return state.artifact_heads["content/change-set"]

    def _require_exact_ref(self, value: str, slot: str, kind: str) -> str:
        reference = ArtifactReference.parse(value)
        if (
            self.kernel.load().artifact_heads.get(slot) != value
            or reference.kind != kind
        ):
            raise ArtifactReferenceError(
                f"Artifact reference is not the current {slot} head: {value}"
            )
        self.kernel.artifacts.resolve(reference)
        return value


__all__ = ["FeedbackService"]
