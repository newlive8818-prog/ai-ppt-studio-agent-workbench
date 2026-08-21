"""Version-bound, one-time confirmation contexts for user Gates."""

from __future__ import annotations

import hashlib
from typing import Any

from ai_ppt_studio.application.scoped_confirmation import (
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContentWorkflowError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


USER_GATES = frozenset({"G0", "G3", "G4"})


class GateConfirmationPolicy:
    """Create and validate one current user-checkpoint challenge."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def context(self, gate: str) -> dict[str, Any]:
        identity = gate.strip()
        if identity not in USER_GATES:
            raise GateBlockedError(identity or "Gate", ("user-gate-invalid",))
        if identity == "G0":
            from ai_ppt_studio.application.presales_content_service import (
                PresalesContentService,
            )

            scoped = PresalesContentService(self.kernel).gate_confirmation_context()
        elif identity == "G3":
            from ai_ppt_studio.application.visual_service import VisualService

            scoped = VisualService(self.kernel).gate_confirmation_context()
        else:
            from ai_ppt_studio.application.delivery_service import DeliveryService

            scoped = DeliveryService(self.kernel).gate_confirmation_context()
        return {
            **scoped,
            "gate": identity,
            "review_summary": "当前 Gate 的可信确认上下文。",
            "confirmation_mode": "confirm-gate",
            "legacy_confirmation_ref": "",
        }

    def confirmation_payload(
        self,
        *,
        gate: str,
        source_version: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
        user_action_ref: str = "",
        user_message_ref: str = "",
    ) -> tuple[dict[str, Any], tuple[object, ...]]:
        current = self.context(gate)
        if user_action_ref.strip() or user_message_ref.strip():
            raise GateBlockedError(
                gate, ("untrusted-raw-confirmation-identity",)
            )
        try:
            scoped, consumptions = self.confirmations.confirmation_payload(
                current=current,
                source_version=source_version,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=host_confirmation_assertion,
            )
        except ContentWorkflowError as error:
            raise GateBlockedError(
                gate, ("trusted-host-assertion-invalid",)
            ) from error
        identity = str(
            scoped.get("user_action_ref")
            or scoped.get("user_message_ref")
            or ""
        )
        if identity and self._was_consumed(identity):
            raise GateBlockedError(
                gate, ("confirmation-identity-already-consumed",)
            )
        payload = {
            **scoped,
            "gate": gate,
            "confirmation_mode": current["confirmation_mode"],
        }
        if current["confirmation_mode"] == "legacy-credential-upgrade":
            payload["supersedes_confirmation_ref"] = current[
                "legacy_confirmation_ref"
            ]
        return payload, consumptions

    def _was_consumed(self, identity: str) -> bool:
        state = self.kernel.load()
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if key in state.consumed_user_confirmations:
            return True
        for slot, reference_value in state.artifact_heads.items():
            if slot != "mission/confirmation" and not (
                slot.startswith("gate/") and slot.endswith("/confirmation")
            ):
                continue
            try:
                payload = self.kernel.artifacts.resolve(
                    ArtifactReference.parse(reference_value)
                )["payload"]
            except (ArtifactReferenceError, KeyError, TypeError, ValueError):
                continue
            if identity in {
                str(payload.get("user_action_ref") or ""),
                str(payload.get("user_message_ref") or ""),
            }:
                return True
        return False
