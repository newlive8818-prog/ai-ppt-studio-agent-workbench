"""Authoritative readiness policy for formal content production."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


@dataclass(frozen=True)
class MissionReadiness:
    mission_draft_ref: str
    mission_confirmation_ref: str
    material_mode: str
    content_identity_mode: str
    material_inventory_ref: str = ""
    empty_material_identity: str = ""


class MissionReadinessPolicy:
    """Reject every content path that lacks current user-bound identities."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def empty_material_identity(self, mission_draft_ref: str) -> str:
        value = f"{self.kernel.project_id}\0{mission_draft_ref}".encode("utf-8")
        return f"empty-materials:{hashlib.sha256(value).hexdigest()}"

    def require_ready(self) -> MissionReadiness:
        state = self.kernel.load()
        draft_ref = state.artifact_heads.get("mission/draft", "")
        if not draft_ref:
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: current MissionDraft is missing"
            )
        draft = self._resolve(draft_ref, "mission-draft")
        if draft.get("status") != "confirmable":
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: current MissionDraft is not confirmable"
            )
        confirmation_ref = state.artifact_heads.get("mission/confirmation", "")
        if not confirmation_ref:
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: explicit user confirmation is missing"
            )
        confirmation = self._resolve(
            confirmation_ref, "mission-confirmation"
        )
        if confirmation.get("mission_draft_ref") != draft_ref:
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: confirmation targets an obsolete MissionDraft"
            )
        mode = str(confirmation.get("material_mode") or "")
        current_materials = state.artifact_heads.get("materials", "")
        if mode in {
            "material-backed",
            "mixed-evidence",
            "materials-provided",
        }:
            confirmed_materials = str(
                confirmation.get("material_inventory_ref") or ""
            )
            if not current_materials or confirmed_materials != current_materials:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: confirmation does not bind the current material inventory"
                )
            self._resolve(current_materials, "material-inventory")
            return MissionReadiness(
                mission_draft_ref=draft_ref,
                mission_confirmation_ref=confirmation_ref,
                material_mode=mode,
                content_identity_mode=(
                    "material-backed" if mode == "materials-provided" else mode
                ),
                material_inventory_ref=current_materials,
            )
        if mode in {"proposal-led", "no-materials-confirmed"}:
            expected_empty = self.empty_material_identity(draft_ref)
            if current_materials or confirmation.get(
                "empty_material_identity"
            ) != expected_empty:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: empty-material identity is stale or materials now exist"
                )
            return MissionReadiness(
                mission_draft_ref=draft_ref,
                mission_confirmation_ref=confirmation_ref,
                material_mode=mode,
                content_identity_mode=(
                    "proposal-only"
                    if mode == "no-materials-confirmed"
                    else "proposal-led"
                ),
                empty_material_identity=expected_empty,
            )
        raise MaterialModeUnconfirmedError(
            "MATERIAL_MODE_UNCONFIRMED: material mode is not confirmed"
        )

    def projection(self) -> dict[str, str]:
        """Return a non-throwing compact identity projection."""

        state = self.kernel.load()
        draft_ref = state.artifact_heads.get("mission/draft", "")
        confirmation_ref = state.artifact_heads.get("mission/confirmation", "")
        try:
            ready = self.require_ready()
        except MissionNotConfirmedError:
            return {
                "mission_draft_ref": draft_ref,
                "mission_confirmation_ref": confirmation_ref,
                "material_mode": "unconfirmed",
                "content_identity_mode": "blocked",
            }
        except MaterialModeUnconfirmedError:
            return {
                "mission_draft_ref": draft_ref,
                "mission_confirmation_ref": confirmation_ref,
                "material_mode": "unconfirmed",
                "content_identity_mode": "blocked",
            }
        return {
            "mission_draft_ref": ready.mission_draft_ref,
            "mission_confirmation_ref": ready.mission_confirmation_ref,
            "material_mode": ready.material_mode,
            "content_identity_mode": ready.content_identity_mode,
        }

    def _resolve(self, value: str, kind: str) -> dict:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(
                f"Expected {kind} artifact, received {reference.kind}"
            )
        return dict(self.kernel.artifacts.resolve(reference)["payload"])
