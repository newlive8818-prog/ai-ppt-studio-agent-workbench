"""Mission and material-boundary writes, separated from content production."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.domains.materials.contracts import validate_material_inventory
from ai_ppt_studio.domains.mission.contracts import (
    validate_mission_confirmation,
    validate_mission_draft,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


V22_MATERIAL_MODES = frozenset(
    {"material-backed", "mixed-evidence", "proposal-led"}
)
LEGACY_MATERIAL_MODES = frozenset(
    {"materials-provided", "no-materials-confirmed"}
)
MATERIAL_BOUND_MODES = frozenset(
    {"material-backed", "mixed-evidence", "materials-provided"}
)
EMPTY_MATERIAL_MODES = frozenset(
    {"proposal-led", "no-materials-confirmed"}
)


class MissionMaterialService:
    """Own MissionDraft, MissionConfirmation and material inventory writes."""

    def __init__(
        self, kernel: ProjectKernel, *, allow_legacy_modes: bool = False
    ) -> None:
        self.kernel = kernel
        self.allow_legacy_modes = allow_legacy_modes

    def save_mission_draft(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.draft-saved",
            artifact_updates={
                "mission/draft": (
                    "mission-draft",
                    validate_mission_draft(payload),
                )
            },
        )
        return state.artifact_heads["mission/draft"]

    def register_mission(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        return self.save_mission_draft(command_id, expected_revision, payload)

    def confirm_mission(
        self,
        command_id: str,
        expected_revision: int,
        *,
        mission_draft_ref: str,
        material_mode: str,
        material_inventory_ref: str,
        user_action_ref: str,
        user_message_ref: str,
    ) -> str:
        mode = material_mode.strip()
        allowed = set(V22_MATERIAL_MODES)
        if self.allow_legacy_modes:
            allowed.update(LEGACY_MATERIAL_MODES)
        if mode not in allowed:
            raise MaterialModeUnconfirmedError(
                "MATERIAL_MODE_UNCONFIRMED: choose a v2.2 material mode"
            )
        draft_ref = self._require_exact_ref(
            mission_draft_ref, "mission/draft", "mission-draft"
        )
        draft = self.kernel.artifacts.resolve(
            ArtifactReference.parse(draft_ref)
        )["payload"]
        if draft.get("status") != "confirmable":
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: MissionDraft is not confirmable"
            )
        policy = MissionReadinessPolicy(self.kernel)
        payload: dict[str, Any] = {
            "mission_draft_ref": draft_ref,
            "material_mode": mode,
            "user_action_ref": user_action_ref.strip(),
            "user_message_ref": user_message_ref.strip(),
            "revision": expected_revision,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        if mode in MATERIAL_BOUND_MODES:
            current = self.kernel.load().artifact_heads.get("materials", "")
            if not current or material_inventory_ref != current:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: current material inventory is required"
                )
            self._require_exact_ref(current, "materials", "material-inventory")
            payload["material_inventory_ref"] = current
        elif mode in EMPTY_MATERIAL_MODES:
            if self.kernel.load().artifact_heads.get("materials"):
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: proposal-led requires an empty material boundary"
                )
            payload["empty_material_identity"] = policy.empty_material_identity(
                draft_ref
            )
        normalized = validate_mission_confirmation(payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.confirmed",
            artifact_updates={
                "mission/confirmation": ("mission-confirmation", normalized)
            },
        )
        return state.artifact_heads["mission/confirmation"]

    def register_materials(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="materials.registered",
            artifact_updates={
                "materials": (
                    "material-inventory",
                    validate_material_inventory(payload),
                )
            },
        )
        return state.artifact_heads["materials"]

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


__all__ = ["MissionMaterialService", "V22_MATERIAL_MODES"]
