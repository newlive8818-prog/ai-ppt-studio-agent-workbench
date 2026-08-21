"""Capture and govern feedback without owning content production."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.feedback.contracts import (
    decide_feedback as apply_feedback_decision,
    validate_feedback_governance,
    validate_raw_feedback,
)
from ai_ppt_studio.errors import ArtifactReferenceError, FeedbackGovernanceError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class FeedbackService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def capture(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_raw_feedback(payload)
        for reference in normalized["target_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(reference))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.captured",
            artifact_updates={"feedback/raw": ("raw-feedback", normalized)},
        )
        return state.artifact_heads["feedback/raw"]

    def govern(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_feedback_governance(payload)
        self._require_current(
            normalized["raw_feedback_ref"], "feedback/raw", "raw-feedback"
        )
        for reference in normalized["preserve_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(reference))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.governed",
            artifact_updates={
                "feedback/governance": ("feedback-governance-record", normalized)
            },
        )
        return state.artifact_heads["feedback/governance"]

    def decide(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        choice: str,
    ) -> str:
        self._require_current(
            governance_ref, "feedback/governance", "feedback-governance-record"
        )
        payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.decision-recorded",
            artifact_updates={
                "feedback/governance": (
                    "feedback-governance-record",
                    apply_feedback_decision(payload, choice),
                )
            },
        )
        return state.artifact_heads["feedback/governance"]

    def create_content_change_set(
        self, command_id: str, expected_revision: int, governance_ref: str
    ) -> str:
        try:
            self._require_current(
                governance_ref,
                "feedback/governance",
                "feedback-governance-record",
            )
        except ArtifactReferenceError as error:
            raise FeedbackGovernanceError(
                "ContentChangeSet requires the current governed feedback record"
            ) from error
        governance = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        if governance.get("status") != "executable":
            raise FeedbackGovernanceError(
                "Feedback requires governance and any mandatory user decision"
            )
        raw = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance["raw_feedback_ref"])
        )["payload"]
        intent = (
            raw["raw_feedback"]
            if governance.get("user_decision") == "follow-user-instruction"
            else governance["ai_recommendation"]
        )
        change = {
            "feedback_governance_record_ref": governance_ref,
            "governed_intent": intent,
            "target_refs": raw["target_refs"],
            "preserve_refs": governance["preserve_refs"],
            "scope": governance["scope"],
            "required_role_runs": ["presales-solution-chief"],
            "review_route": [
                "content-evidence-gate-reviewer",
                "content-presales-reading-gate-reviewer",
            ],
            "status": "ready",
        }
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.change-set-created",
            artifact_updates={"content/change-set": ("content-change-set", change)},
        )
        return state.artifact_heads["content/change-set"]

    def _require_current(self, value: str, slot: str, kind: str) -> None:
        if self.kernel.load().artifact_heads.get(slot, "") != value:
            raise ArtifactReferenceError(f"{slot} is stale")
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"{slot} must reference {kind}")
        self.kernel.artifacts.resolve(reference)


__all__ = ["FeedbackService"]
