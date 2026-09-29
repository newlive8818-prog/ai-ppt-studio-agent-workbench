"""Mission and material ownership separated from content production."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.domains.materials.contracts import validate_material_inventory
from ai_ppt_studio.domains.mission.contracts import (
    validate_mission_confirmation,
    validate_mission_draft,
)
from ai_ppt_studio.errors import MaterialModeUnconfirmedError, MissionNotConfirmedError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class MissionMaterialService:
    _DOWNSTREAM_PREFIXES = (
        "agent/",
        "content/",
        "visual/",
        "delivery/",
        "review/session/",
        "chat-delivery/",
    )
    _DOWNSTREAM_SLOTS = {
        "mission/confirmation",
        "gate/G0/confirmation",
        "gate/G3/confirmation",
        "gate/G4/confirmation",
        "project/completion",
        "experience/retrospective/job",
        "experience/project-retrospective",
        "experience/retrospective/error",
    }

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def save_mission_draft(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        state = self.kernel.load()
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.draft-saved",
            artifact_updates={
                "mission/draft": ("mission-draft", validate_mission_draft(payload))
            },
            artifact_removals=self._downstream_removals(state.artifact_heads),
            gate_mutation=GateEvaluator(self.kernel).content_source_replaced(
                self._existing_refs(state, "mission/confirmation")
            ),
        )
        return state.artifact_heads["mission/draft"]

    def register_materials(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        current = self.kernel.load()
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
            artifact_removals=self._downstream_removals(current.artifact_heads),
            gate_mutation=GateEvaluator(self.kernel).content_source_replaced(
                self._existing_refs(current, "materials", "mission/confirmation")
            ),
        )
        return state.artifact_heads["materials"]

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
        state = self.kernel.load()
        draft_ref = state.artifact_heads.get("mission/draft", "")
        if mission_draft_ref != draft_ref:
            raise MissionNotConfirmedError("MISSION_NOT_CONFIRMED: MissionDraft is stale")
        draft = self._payload(draft_ref, "mission-draft")
        if draft.get("status") != "confirmable":
            raise MissionNotConfirmedError("MISSION_NOT_CONFIRMED: MissionDraft is not confirmable")
        policy = MissionReadinessPolicy(self.kernel)
        confirmation: dict[str, Any] = {
            "mission_draft_ref": draft_ref,
            "material_mode": material_mode.strip(),
            "user_action_ref": user_action_ref.strip(),
            "user_message_ref": user_message_ref.strip(),
            "revision": expected_revision,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        current_materials = state.artifact_heads.get("materials", "")
        if confirmation["material_mode"] == "materials-provided":
            if not current_materials or material_inventory_ref != current_materials:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: current material inventory is required"
                )
            self._payload(current_materials, "material-inventory")
            confirmation["material_inventory_ref"] = current_materials
        elif confirmation["material_mode"] == "no-materials-confirmed":
            if current_materials:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: materials already exist"
                )
            confirmation["empty_material_identity"] = policy.empty_material_identity(draft_ref)
        else:
            raise MaterialModeUnconfirmedError(
                "MATERIAL_MODE_UNCONFIRMED: choose materials-provided or no-materials-confirmed"
            )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.confirmed",
            artifact_updates={
                "mission/confirmation": (
                    "mission-confirmation",
                    validate_mission_confirmation(confirmation),
                )
            },
        )
        return committed.artifact_heads["mission/confirmation"]

    def _payload(self, value: str, kind: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise MissionNotConfirmedError(f"MISSION_NOT_CONFIRMED: expected {kind}")
        return dict(self.kernel.artifacts.resolve(reference)["payload"])

    @classmethod
    def _downstream_removals(cls, heads: dict[str, str]) -> tuple[str, ...]:
        return tuple(
            slot
            for slot in heads
            if slot in cls._DOWNSTREAM_SLOTS
            or slot.startswith(cls._DOWNSTREAM_PREFIXES)
        )

    @staticmethod
    def _existing_refs(state, *slots: str) -> tuple[str, ...]:
        return tuple(state.artifact_heads[slot] for slot in slots if slot in state.artifact_heads)


__all__ = ["MissionMaterialService"]
