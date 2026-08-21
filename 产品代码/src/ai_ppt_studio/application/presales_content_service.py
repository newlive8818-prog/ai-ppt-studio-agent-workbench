"""Authoritative v2.2 evidence-first content object writer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.review_commands import fingerprint, replay_state
from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class PresalesContentService:
    """Write the four current content objects in exact upstream order."""

    _CONTENT_OBJECT_SLOTS = {
        "content/evidence-book",
        "content/decision-context",
        "content/problem-solution-fit",
        "content/reading-blueprint",
    }
    _DOWNSTREAM_PREFIXES = (
        "agent/",
        "visual/",
        "delivery/",
        "review/session/",
        "chat-delivery/",
    )
    _DOWNSTREAM_SLOTS = {
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

    def build_evidence_book(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_presales_evidence_book(payload)
        self._require_current(
            "mission/confirmation",
            "mission-confirmation",
            normalized["mission_confirmation_ref"],
        )
        material_ref = normalized["material_inventory_ref"]
        if normalized["material_mode"] == "proposal-led":
            if self.kernel.load().artifact_heads.get("materials"):
                raise ContractValidationError(
                    "proposal-led cannot be used while current materials exist"
                )
        else:
            self._require_current("materials", "material-inventory", material_ref)
        return self._commit(
            command_id,
            expected_revision,
            "content.evidence-book-built",
            "content/evidence-book",
            "presales-evidence-book",
            normalized,
        )

    def build_decision_context(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_customer_decision_context(payload)
        self._require_current(
            "content/evidence-book",
            "presales-evidence-book",
            normalized["evidence_book_ref"],
        )
        return self._commit(
            command_id,
            expected_revision,
            "content.decision-context-built",
            "content/decision-context",
            "customer-decision-context",
            normalized,
        )

    def build_problem_solution_fit(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_problem_solution_fit_map(payload)
        self._require_current(
            "content/evidence-book",
            "presales-evidence-book",
            normalized["evidence_book_ref"],
        )
        self._require_current(
            "content/decision-context",
            "customer-decision-context",
            normalized["decision_context_ref"],
        )
        return self._commit(
            command_id,
            expected_revision,
            "content.problem-solution-fit-built",
            "content/problem-solution-fit",
            "problem-solution-fit-map",
            normalized,
        )

    def build_reading_deck_blueprint(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_reading_deck_blueprint(payload)
        if normalized["project_id"] != self.kernel.project_id:
            raise ContractValidationError("ReadingDeckBlueprint project_id is stale")
        upstream = (
            ("content/evidence-book", "presales-evidence-book", "evidence_book_ref"),
            ("content/decision-context", "customer-decision-context", "decision_context_ref"),
            ("content/problem-solution-fit", "problem-solution-fit-map", "problem_solution_fit_ref"),
        )
        for slot, kind, field in upstream:
            self._require_current(slot, kind, normalized[field])
        evidence = self._payload(normalized["evidence_book_ref"])
        if evidence.get("material_mode") != normalized["material_mode"]:
            raise ContractValidationError("ReadingDeckBlueprint material_mode is stale")
        state = self.kernel.load()
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.reading-blueprint-built",
            artifact_updates={
                "content/reading-blueprint": ("reading-deck-blueprint", normalized)
            },
            artifact_removals=self._replacement_removals(state.artifact_heads),
            gate_mutation=GateEvaluator(self.kernel).content_source_replaced(
                tuple(
                    reference
                    for reference in dict.fromkeys(
                        (
                            *(state.artifact_heads[slot] for slot, _kind, _field in upstream),
                            state.artifact_heads.get("content/reading-blueprint", ""),
                        )
                    )
                    if reference
                )
            ),
        )
        return committed.artifact_heads["content/reading-blueprint"]

    def repair_reading_deck_blueprint(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        state = self.kernel.load()
        failed = False
        for slot in ("content/gate/evidence", "content/gate/presales-reading"):
            value = state.artifact_heads.get(slot, "")
            if value and self._payload(value).get("overall_result") == "failed":
                failed = True
        if not failed:
            raise ContractValidationError(
                "ReadingDeckBlueprint repair requires a current failed hard gate"
            )
        if not payload.get("repair_history"):
            raise ContractValidationError("Repair must preserve the applied requirements")
        return self.build_reading_deck_blueprint(
            command_id, expected_revision, payload
        )

    def open_g0_review(
        self, *, command_id: str, expected_revision: int
    ):
        command_fingerprint = fingerprint("open-g0-review", {})
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            return replay
        state = self.kernel.load()
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        review_batch_ref = state.artifact_heads.get("content/review-batch", "")
        if not acceptance_ref or not blueprint_ref or not review_batch_ref:
            raise GateBlockedError("G0", ("content-review-evidence-missing",))
        mutation = GateEvaluator(self.kernel).content_user_reviewable(
            acceptance_ref, blueprint_ref, review_batch_ref
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.user-reviewable",
            artifact_updates={},
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
        )

    def confirm_g0(
        self,
        *,
        command_id: str,
        expected_revision: int,
        user_message_ref: str,
    ):
        if not user_message_ref.startswith("chat://message/") or not user_message_ref.removeprefix(
            "chat://message/"
        ):
            raise GateBlockedError("G0", ("explicit-chat-message-required",))
        command_fingerprint = fingerprint(
            "confirm-g0", {"user_message_ref": user_message_ref}
        )
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            return replay
        state = self.kernel.load()
        confirmation = {
            "gate": "G0",
            "user_message_ref": user_message_ref,
            "content_acceptance_ref": state.artifact_heads.get(
                "content/acceptance", ""
            ),
            "reading_blueprint_ref": state.artifact_heads.get(
                "content/reading-blueprint", ""
            ),
            "content_review_batch_ref": state.artifact_heads.get(
                "content/review-batch", ""
            ),
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        confirmation_ref = str(
            self.kernel.artifacts.put("g0-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g0(
            confirmation_ref=confirmation_ref,
            user_message_ref=user_message_ref,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.confirmed",
            artifact_updates={
                "gate/G0/confirmation": ("g0-confirmation", confirmation)
            },
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
        )

    def _commit(
        self,
        command_id: str,
        expected_revision: int,
        event_type: str,
        slot: str,
        kind: str,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=event_type,
            artifact_updates={slot: (kind, payload)},
        )
        return state.artifact_heads[slot]

    def _require_current(self, slot: str, kind: str, supplied_ref: str) -> None:
        current = self.kernel.load().artifact_heads.get(slot, "")
        if supplied_ref != current:
            raise ArtifactReferenceError(f"{slot} must bind the current {kind}")
        reference = ArtifactReference.parse(supplied_ref)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"{slot} must reference {kind}")
        self.kernel.artifacts.resolve(reference)

    @classmethod
    def _replacement_removals(cls, heads: dict[str, str]) -> tuple[str, ...]:
        return tuple(
            slot
            for slot in heads
            if (
                slot.startswith("content/")
                and slot not in cls._CONTENT_OBJECT_SLOTS
            )
            or slot in cls._DOWNSTREAM_SLOTS
            or slot.startswith(cls._DOWNSTREAM_PREFIXES)
        )
    def _payload(self, reference: str) -> dict[str, Any]:
        return dict(
            self.kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]
        )


__all__ = ["PresalesContentService"]
