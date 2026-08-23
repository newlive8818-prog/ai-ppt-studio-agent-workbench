"""Authoritative v2.2 presales content-chain writes."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


PRESALES_CHIEF_ROLE_ID = "presales-solution-chief"

EVIDENCE_BOOK_SLOT = "content/presales-evidence-book"
DECISION_CONTEXT_SLOT = "content/customer-decision-context"
FIT_MAP_SLOT = "content/problem-solution-fit-map"
READING_BLUEPRINT_SLOT = "content/reading-deck-blueprint"

EVIDENCE_BOOK_KIND = "presales-evidence-book"
DECISION_CONTEXT_KIND = "customer-decision-context"
FIT_MAP_KIND = "problem-solution-fit-map"
READING_BLUEPRINT_KIND = "reading-deck-blueprint"


class PresalesContentService:
    """Persist the four v2.2 objects under one bounded producer authority."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    @staticmethod
    def _require_chief(actor_role_id: str) -> None:
        if actor_role_id != PRESALES_CHIEF_ROLE_ID:
            raise WorkbenchValidationError(
                f"Only {PRESALES_CHIEF_ROLE_ID} may write v2.2 content objects"
            )

    def _require_current_ref(
        self, value: str, *, slot: str, kind: str
    ) -> str:
        current = self.kernel.load().artifact_heads.get(slot, "")
        if not value or value != current:
            raise ArtifactReferenceError(
                f"{slot} must bind its exact current artifact reference"
            )
        try:
            reference = ArtifactReference.parse(value)
            if reference.kind != kind:
                raise ValueError("unexpected artifact kind")
            self.kernel.artifacts.resolve(reference)
        except (ArtifactReferenceError, ValueError) as exc:
            raise ArtifactReferenceError(
                f"{slot} must identify a resolvable {kind} artifact"
            ) from exc
        return value

    @staticmethod
    def _require_mode(payload: dict[str, Any], material_mode: str) -> None:
        if payload.get("material_mode") != material_mode:
            raise ContractValidationError(
                "material_mode argument must equal the artifact material_mode"
            )

    def build_presales_evidence_book(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        material_mode: str,
        payload: dict[str, Any],
    ) -> str:
        self._require_chief(actor_role_id)
        self._require_mode(payload, material_mode)
        normalized = validate_presales_evidence_book(payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.presales-evidence-book-built",
            artifact_updates={
                EVIDENCE_BOOK_SLOT: (EVIDENCE_BOOK_KIND, normalized)
            },
            artifact_removals=(
                DECISION_CONTEXT_SLOT,
                FIT_MAP_SLOT,
                READING_BLUEPRINT_SLOT,
            ),
        )
        return state.artifact_heads[EVIDENCE_BOOK_SLOT]

    def build_customer_decision_context(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        evidence_book_ref: str,
        payload: dict[str, Any],
    ) -> str:
        self._require_chief(actor_role_id)
        exact_book_ref = self._require_current_ref(
            evidence_book_ref,
            slot=EVIDENCE_BOOK_SLOT,
            kind=EVIDENCE_BOOK_KIND,
        )
        if payload.get("evidence_book_ref") != exact_book_ref:
            raise ArtifactReferenceError(
                "CustomerDecisionContext evidence_book_ref is not current"
            )
        normalized = validate_customer_decision_context(payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.customer-decision-context-built",
            artifact_updates={
                DECISION_CONTEXT_SLOT: (DECISION_CONTEXT_KIND, normalized)
            },
            artifact_removals=(FIT_MAP_SLOT, READING_BLUEPRINT_SLOT),
        )
        return state.artifact_heads[DECISION_CONTEXT_SLOT]

    def build_problem_solution_fit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        evidence_book_ref: str,
        decision_context_ref: str,
        payload: dict[str, Any],
    ) -> str:
        self._require_chief(actor_role_id)
        exact_book_ref = self._require_current_ref(
            evidence_book_ref,
            slot=EVIDENCE_BOOK_SLOT,
            kind=EVIDENCE_BOOK_KIND,
        )
        exact_context_ref = self._require_current_ref(
            decision_context_ref,
            slot=DECISION_CONTEXT_SLOT,
            kind=DECISION_CONTEXT_KIND,
        )
        normalized = validate_problem_solution_fit_map(payload)
        normalized.update(
            {
                "evidence_book_ref": exact_book_ref,
                "decision_context_ref": exact_context_ref,
            }
        )
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.problem-solution-fit-built",
            artifact_updates={FIT_MAP_SLOT: (FIT_MAP_KIND, normalized)},
            artifact_removals=(READING_BLUEPRINT_SLOT,),
        )
        return state.artifact_heads[FIT_MAP_SLOT]

    def build_reading_blueprint(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        material_mode: str,
        evidence_book_ref: str,
        decision_context_ref: str,
        problem_solution_fit_ref: str,
        payload: dict[str, Any],
    ) -> str:
        self._require_chief(actor_role_id)
        self._require_mode(payload, material_mode)
        exact_refs = {
            "evidence_book_ref": self._require_current_ref(
                evidence_book_ref,
                slot=EVIDENCE_BOOK_SLOT,
                kind=EVIDENCE_BOOK_KIND,
            ),
            "decision_context_ref": self._require_current_ref(
                decision_context_ref,
                slot=DECISION_CONTEXT_SLOT,
                kind=DECISION_CONTEXT_KIND,
            ),
            "problem_solution_fit_ref": self._require_current_ref(
                problem_solution_fit_ref,
                slot=FIT_MAP_SLOT,
                kind=FIT_MAP_KIND,
            ),
        }
        for field, current in exact_refs.items():
            if payload.get(field) != current:
                raise ArtifactReferenceError(
                    f"ReadingDeckBlueprint {field} is not current"
                )
        if payload.get("project_id") != self.kernel.project_id:
            raise ContractValidationError(
                "ReadingDeckBlueprint project_id does not match the kernel"
            )
        normalized = validate_reading_deck_blueprint(payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.reading-deck-blueprint-built",
            artifact_updates={
                READING_BLUEPRINT_SLOT: (READING_BLUEPRINT_KIND, normalized)
            },
        )
        return state.artifact_heads[READING_BLUEPRINT_SLOT]


__all__ = ["PresalesContentService", "PRESALES_CHIEF_ROLE_ID"]
