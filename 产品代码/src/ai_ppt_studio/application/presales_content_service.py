"""Authoritative v2.2 presales content-chain writes."""

from __future__ import annotations

import hashlib
import json
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
    GateBlockedError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.artifacts import canonical_json
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

    def repair_reading_blueprint(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        source_blueprint_ref: str,
        failed_gate_refs: list[str],
        payload: dict[str, Any],
    ) -> str:
        """Write a new source version from current failed hard-gate facts."""

        fingerprint = hashlib.sha256(
            canonical_json(
                {
                    "expected_revision": expected_revision,
                    "actor_role_id": actor_role_id,
                    "source_blueprint_ref": source_blueprint_ref,
                    "failed_gate_refs": failed_gate_refs,
                    "payload": payload,
                }
            )
        ).hexdigest()
        replayed = self._replay_repaired_blueprint(command_id, fingerprint)
        if replayed:
            return replayed
        self._require_chief(actor_role_id)
        current_ref = self._require_current_ref(
            source_blueprint_ref,
            slot=READING_BLUEPRINT_SLOT,
            kind=READING_BLUEPRINT_KIND,
        )
        if not failed_gate_refs:
            raise GateBlockedError("content-repair", ("missing-failed-gate",))
        state = self.kernel.load()
        current_gate_refs = {
            value
            for value in (
                state.artifact_heads.get("content/gate/evidence", ""),
                state.artifact_heads.get("content/gate/presales-reading", ""),
            )
            if value
        }
        blockers: list[str] = []
        for value in failed_gate_refs:
            if value not in current_gate_refs:
                blockers.append(f"stale-gate:{value}")
                continue
            try:
                reference = ArtifactReference.parse(value)
                if reference.kind != "content-hard-gate-record":
                    raise ArtifactReferenceError("gate kind is invalid")
                record = self.kernel.artifacts.resolve(reference)["payload"]
            except ArtifactReferenceError:
                blockers.append(f"invalid-gate:{value}")
                continue
            if record.get("input_source_version") != current_ref:
                blockers.append(f"stale-gate:{value}")
            if record.get("overall_result") != "failed":
                blockers.append(f"gate-not-failed:{value}")
        if blockers:
            raise GateBlockedError("content-repair", tuple(sorted(blockers)))
        old_payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(current_ref)
        )["payload"]
        if payload.get("hard_gate_refs") != failed_gate_refs:
            raise ContractValidationError(
                "repair hard_gate_refs must equal current failed_gate_refs"
            )
        history = payload.get("repair_history")
        if not isinstance(history, list) or not history:
            raise ContractValidationError("repair_history must record the repair")
        old_history = old_payload.get("repair_history")
        if not isinstance(old_history, list) or history[:-1] != old_history:
            raise ContractValidationError(
                "repair_history must be append-only"
            )
        latest = history[-1]
        if (
            not isinstance(latest, dict)
            or latest.get("source_version") != current_ref
            or latest.get("failed_gate_refs") != failed_gate_refs
            or not str(latest.get("repair_summary") or "").strip()
            or latest.get("new_source_version") != payload.get("source_version")
        ):
            raise ContractValidationError(
                "repair_history must bind source and failed gates"
            )
        used_source_versions = {str(old_payload.get("source_version") or "")}
        for entry in old_history:
            if not isinstance(entry, dict):
                raise ContractValidationError(
                    "repair_history must be append-only"
                )
            previous_ref = str(entry.get("source_version") or "")
            previous_payload = self.kernel.artifacts.resolve(
                ArtifactReference.parse(previous_ref)
            )["payload"]
            used_source_versions.add(
                str(previous_payload.get("source_version") or "")
            )
            used_source_versions.add(str(entry.get("new_source_version") or ""))
        if str(payload.get("source_version") or "") in used_source_versions:
            raise ContractValidationError(
                "repair must create a unique source_version"
            )
        for field, slot in (
            ("evidence_book_ref", EVIDENCE_BOOK_SLOT),
            ("decision_context_ref", DECISION_CONTEXT_SLOT),
            ("problem_solution_fit_ref", FIT_MAP_SLOT),
        ):
            if payload.get(field) != state.artifact_heads.get(slot):
                raise ArtifactReferenceError(
                    f"repair {field} must bind the current upstream head"
                )
        normalized = validate_reading_deck_blueprint(payload)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.reading-deck-blueprint-repaired",
            artifact_updates={
                READING_BLUEPRINT_SLOT: (READING_BLUEPRINT_KIND, normalized)
            },
            artifact_removals=(
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
            ),
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads[READING_BLUEPRINT_SLOT]

    def _replay_repaired_blueprint(
        self, command_id: str, fingerprint: str
    ) -> str:
        state = self.kernel.load()
        revision = state.processed_commands.get(command_id)
        if revision is None:
            return ""
        events_root = getattr(self.kernel, "events_root", None)
        if events_root is None:
            raise ContractValidationError(
                "Processed repair command receipt is unavailable"
            )
        try:
            event = json.loads(
                (events_root / f"r{revision:08d}.json").read_text(
                    encoding="utf-8"
                )
            )
            result_ref = str(
                event.get("artifact_heads", {}).get(READING_BLUEPRINT_SLOT)
                or ""
            )
            reference = ArtifactReference.parse(result_ref)
            if (
                event.get("command_id") != command_id
                or event.get("command_fingerprint") != fingerprint
                or reference.kind != READING_BLUEPRINT_KIND
            ):
                raise ValueError("receipt mismatch")
            self.kernel.artifacts.resolve(reference)
        except (
            ArtifactReferenceError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed repair command has different semantics"
            ) from exc
        return result_ref


__all__ = ["PresalesContentService", "PRESALES_CHIEF_ROLE_ID"]
