"""Framework-first discussion, confirmation, and expansion authorization."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.scoped_confirmation import (
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.domains.content.framework import (
    validate_framework_confirmation,
    validate_framework_draft,
    validate_full_deck_expansion_authorization,
)
from ai_ppt_studio.errors import ContentWorkflowError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


FRAMEWORK_CONFIRMATION_SCOPE = "content-framework-confirmation"
FULL_DECK_EXPANSION_SCOPE = (
    "content-full-deck-expansion-authorization"
)


class FrameworkDiscussionService:
    """Persist only chapter-level discussion until two user actions exist."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def save_draft(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> tuple[str, KernelState]:
        normalized = validate_framework_draft(payload)
        readiness = MissionReadinessPolicy(self.kernel).require_ready()
        if (
            normalized["mission_confirmation_ref"]
            != readiness.mission_confirmation_ref
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "FrameworkDraft does not bind the current MissionConfirmation",
                {
                    "expected_confirmation_ref": (
                        readiness.mission_confirmation_ref
                    ),
                    "actual_confirmation_ref": normalized[
                        "mission_confirmation_ref"
                    ],
                },
            )
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.framework-draft-saved",
            artifact_updates={
                "content/framework-draft": (
                    "content-framework-draft",
                    normalized,
                )
            },
            artifact_removals=(
                "content/framework-confirmation",
                "content/full-deck-expansion-authorization",
            ),
        )
        return state.artifact_heads["content/framework-draft"], state

    def confirmation_context(self) -> dict[str, Any]:
        state = self.kernel.load()
        framework_ref = self._current_framework_ref(state)
        mission_confirmation_ref = self._current_mission_confirmation(
            framework_ref
        )
        return self.confirmations.context(
            scope_kind=FRAMEWORK_CONFIRMATION_SCOPE,
            scope_id=framework_ref,
            source_version=framework_ref,
            evidence_refs=[framework_ref, mission_confirmation_ref],
        )

    def confirm_framework(
        self,
        command_id: str,
        expected_revision: int,
        source_version: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, KernelState]:
        current = self.confirmation_context()
        self._require_current_source(source_version, current["source_version"])
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=current,
            source_version=source_version,
            challenge_id=challenge_id,
            challenge_revision=challenge_revision,
            host_confirmation_assertion=host_confirmation_assertion,
        )
        binding = validate_framework_confirmation(
            {
                "project_id": current["project_id"],
                "framework_ref": current["source_version"],
                "framework_revision": current["challenge_revision"],
                "challenge_identity": current["challenge_id"],
                "confirmed_at": scoped["confirmed_at"],
            }
        )
        payload = {**scoped, **binding}
        state = self._commit_confirmed(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.framework-confirmed",
            slot="content/framework-confirmation",
            kind="content-framework-confirmation",
            payload=payload,
            consumptions=consumptions,
        )
        return state.artifact_heads["content/framework-confirmation"], state

    def expansion_authorization_context(self) -> dict[str, Any]:
        state = self.kernel.load()
        framework_ref = self._current_framework_ref(state)
        mission_confirmation_ref = self._current_mission_confirmation(
            framework_ref
        )
        confirmation_ref = state.artifact_heads.get(
            "content/framework-confirmation", ""
        )
        if not confirmation_ref:
            raise ContentWorkflowError(
                "CONTENT_FRAMEWORK_NOT_CONFIRMED",
                "The current content framework is not confirmed",
                {
                    "framework_ref": framework_ref,
                    "revision": state.revision,
                },
            )
        confirmation = self._resolve(
            confirmation_ref,
            "content-framework-confirmation",
        )
        if confirmation.get("framework_ref") != framework_ref:
            raise ContentWorkflowError(
                "CONTENT_FRAMEWORK_NOT_CONFIRMED",
                "The current content framework confirmation is stale",
                {
                    "framework_ref": framework_ref,
                    "confirmation_ref": confirmation_ref,
                    "revision": state.revision,
                },
            )
        return self.confirmations.context(
            scope_kind=FULL_DECK_EXPANSION_SCOPE,
            scope_id=confirmation_ref,
            source_version=framework_ref,
            evidence_refs=[
                framework_ref,
                confirmation_ref,
                mission_confirmation_ref,
            ],
        )

    def authorize_full_deck_expansion(
        self,
        command_id: str,
        expected_revision: int,
        source_version: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[str, KernelState]:
        current = self.expansion_authorization_context()
        self._require_current_source(source_version, current["source_version"])
        scoped, consumptions = self.confirmations.confirmation_payload(
            current=current,
            source_version=source_version,
            challenge_id=challenge_id,
            challenge_revision=challenge_revision,
            host_confirmation_assertion=host_confirmation_assertion,
        )
        confirmation_ref = str(current["scope_id"])
        binding = validate_full_deck_expansion_authorization(
            {
                "project_id": current["project_id"],
                "framework_ref": current["source_version"],
                "framework_confirmation_ref": confirmation_ref,
                "framework_revision": current["challenge_revision"],
                "challenge_identity": current["challenge_id"],
                "confirmed_at": scoped["confirmed_at"],
            }
        )
        payload = {**scoped, **binding}
        state = self._commit_confirmed(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.full-deck-expansion-authorized",
            slot="content/full-deck-expansion-authorization",
            kind="full-deck-expansion-authorization",
            payload=payload,
            consumptions=consumptions,
        )
        return (
            state.artifact_heads[
                "content/full-deck-expansion-authorization"
            ],
            state,
        )

    def _commit_confirmed(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        slot: str,
        kind: str,
        payload: dict[str, Any],
        consumptions: tuple[tuple[str, str], ...],
    ) -> KernelState:
        try:
            return self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type=event_type,
                artifact_updates={slot: (kind, payload)},
                confirmation_consumptions=consumptions,
            )
        except ValueError as error:
            if "Confirmation identity" not in str(error):
                raise
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The trusted confirmation identity was already consumed",
                {
                    "scope_kind": payload["scope_kind"],
                    "scope_id": payload["scope_id"],
                    "revision": self.kernel.load().revision,
                },
            ) from None

    def _current_framework_ref(self, state: KernelState) -> str:
        framework_ref = state.artifact_heads.get("content/framework-draft", "")
        if not framework_ref:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "A current content framework draft is required",
                {"revision": state.revision},
            )
        self._resolve(framework_ref, "content-framework-draft")
        return framework_ref

    def _current_mission_confirmation(self, framework_ref: str) -> str:
        readiness = MissionReadinessPolicy(self.kernel).require_ready()
        framework = self._resolve(framework_ref, "content-framework-draft")
        if (
            framework.get("mission_confirmation_ref")
            != readiness.mission_confirmation_ref
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The content framework binds a stale MissionConfirmation",
                {
                    "framework_ref": framework_ref,
                    "expected_confirmation_ref": (
                        readiness.mission_confirmation_ref
                    ),
                    "actual_confirmation_ref": framework.get(
                        "mission_confirmation_ref", ""
                    ),
                },
            )
        return readiness.mission_confirmation_ref

    @staticmethod
    def _require_current_source(actual: str, expected: str) -> None:
        if actual != expected:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The content framework source is stale",
                {
                    "expected_source_version": expected,
                    "actual_source_version": actual,
                },
            )

    def _resolve(self, value: str, kind: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Content workflow artifact kind is invalid",
                {"expected_kind": kind, "actual_kind": reference.kind},
            )
        return dict(self.kernel.artifacts.resolve(reference)["payload"])
