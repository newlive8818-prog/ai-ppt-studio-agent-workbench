"""Deterministic production orchestration owned by the presales chief."""

from __future__ import annotations

import re
from typing import Any, Callable

from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_content_hard_gate_record,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class PresalesChiefOrchestrator:
    """Select the only legal next write in the v2.2 content chain."""

    _STEPS = (
        (
            "content/evidence-book",
            "reconstructing-evidence",
            "build-presales-evidence-book",
        ),
        (
            "content/decision-context",
            "building-decision-context",
            "build-customer-decision-context",
        ),
        (
            "content/problem-solution-fit",
            "diagnosing-problem-solution-fit",
            "build-problem-solution-fit",
        ),
        (
            "content/reading-blueprint",
            "drafting-reading-deck",
            "build-reading-deck-blueprint",
        ),
    )
    _CURRENT_SLOTS = {
        "mission_confirmation": "mission/confirmation",
        "material_inventory": "materials",
        "evidence_book": "content/evidence-book",
        "decision_context": "content/decision-context",
        "problem_solution_fit": "content/problem-solution-fit",
        "reading_blueprint": "content/reading-blueprint",
    }
    _VALIDATORS: tuple[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]], ...] = (
        ("build-presales-evidence-book", validate_presales_evidence_book),
        ("build-customer-decision-context", validate_customer_decision_context),
        ("build-problem-solution-fit", validate_problem_solution_fit_map),
        ("build-reading-deck-blueprint", validate_reading_deck_blueprint),
    )
    _WRITERS = {
        "build-presales-evidence-book": "build_evidence_book",
        "build-customer-decision-context": "build_decision_context",
        "build-problem-solution-fit": "build_problem_solution_fit",
        "build-reading-deck-blueprint": "build_reading_deck_blueprint",
    }
    _FAILED_GATE_SLOTS = (
        "content/gate/evidence",
        "content/gate/presales-reading",
    )
    _MAX_REPAIR_ATTEMPTS = 3
    _RISK_AREA = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.content = PresalesContentService(kernel)
        self.readiness = MissionReadinessPolicy(kernel)

    def inspect(self) -> dict[str, Any]:
        state = self.kernel.load()
        current_refs = {
            key: state.artifact_heads.get(slot, "")
            for key, slot in self._CURRENT_SLOTS.items()
        }
        projection: dict[str, Any] = {
            "project_id": self.kernel.project_id,
            "revision": state.revision,
            "state": "mission-not-ready",
            "material_mode": "",
            "current_refs": current_refs,
            "next_operation": "",
            "target_refs": [],
            "repair": {
                "applicable": False,
                "attempts_used": 0,
                "attempts_remaining": 3,
                "failure_refs": [],
            },
            "stop": {"code": "", "message": "", "resumable": False},
        }
        try:
            self.readiness.require_ready()
        except MissionNotConfirmedError:
            projection["stop"] = {
                "code": "MISSION_NOT_CONFIRMED",
                "message": "Current Mission is not explicitly confirmed",
                "resumable": True,
            }
            return projection
        except MaterialModeUnconfirmedError:
            projection["stop"] = {
                "code": "MATERIAL_MODE_UNCONFIRMED",
                "message": "Current material identity is not confirmed",
                "resumable": True,
            }
            return projection

        try:
            chain = self.content.get_current_content_chain()["objects"]
        except (ArtifactReferenceError, ContractValidationError):
            projection["state"] = "governed-stop"
            projection["stop"] = {
                "code": "CONTENT_CHAIN_INCONSISTENT",
                "message": "Current content chain is inconsistent",
                "resumable": True,
            }
            return projection

        evidence = chain["evidence_book"]
        if evidence is None:
            mode = self.readiness.v22_material_mode(has_evidence_gaps=False)
        else:
            mode = str(evidence["payload"].get("material_mode") or "")
        projection["material_mode"] = mode

        for index, (_slot, stage, operation) in enumerate(self._STEPS):
            key = tuple(self._CURRENT_SLOTS)[index + 2]
            if not current_refs[key]:
                projection["state"] = stage
                projection["next_operation"] = operation
                projection["target_refs"] = [
                    value
                    for value in current_refs.values()
                    if value
                ]
                return projection

        try:
            failure_refs = self._failed_gate_refs()
            attempts = self._repair_history(chain["reading_blueprint"]["payload"])
        except ContractValidationError:
            projection["state"] = "governed-stop"
            projection["stop"] = {
                "code": "CONTENT_CHAIN_INCONSISTENT",
                "message": "Current repair or hard-gate identity is inconsistent",
                "resumable": True,
            }
            return projection
        projection["repair"] = {
            "applicable": bool(failure_refs) and attempts < self._MAX_REPAIR_ATTEMPTS,
            "attempts_used": attempts,
            "attempts_remaining": max(0, self._MAX_REPAIR_ATTEMPTS - attempts),
            "failure_refs": failure_refs,
        }
        if failure_refs and attempts >= self._MAX_REPAIR_ATTEMPTS:
            projection["state"] = "governed-stop"
            projection["stop"] = {
                "code": "REPAIR_ATTEMPTS_EXHAUSTED",
                "message": "Presales chief repair attempts are exhausted",
                "resumable": False,
            }
            return projection
        if failure_refs:
            projection["state"] = "chief-repair"
            projection["next_operation"] = "repair-reading-deck-blueprint"
            projection["target_refs"] = failure_refs
            return projection
        projection["state"] = "ready-for-independent-gates"
        return projection

    def advance(
        self,
        *,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        operation = self._payload_operation(payload)
        state = self.kernel.load()
        if command_id not in state.processed_commands:
            if expected_revision != state.revision:
                raise RevisionConflictError(expected_revision, state.revision)
            projection = self.inspect()
            if not projection["next_operation"]:
                raise ContractValidationError(
                    "Presales chief has no legal production operation"
                )
            if operation != projection["next_operation"]:
                raise ContractValidationError(
                    "Payload does not match the next presales chief operation"
                )
            if operation == "build-presales-evidence-book":
                expected_mode = self.readiness.v22_material_mode(
                    has_evidence_gaps=bool(payload["evidence_gaps"])
                )
                if payload["material_mode"] != expected_mode:
                    raise ContractValidationError(
                        "PresalesEvidenceBook material_mode conflicts with Mission readiness"
                    )

        writer = getattr(self.content, self._WRITERS[operation])
        created_ref = writer(command_id, expected_revision, payload)
        return {
            "operation": operation,
            "created_ref": created_ref,
            "projection": self.inspect(),
        }

    def repair_blueprint(
        self,
        *,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = validate_reading_deck_blueprint(payload)
        state = self.kernel.load()
        if command_id in state.processed_commands:
            created_ref = self.content.build_reading_deck_blueprint(
                command_id, expected_revision, normalized
            )
            return {
                "operation": "repair-reading-deck-blueprint",
                "created_ref": created_ref,
                "projection": self.inspect(),
            }
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        projection = self.inspect()
        if projection["stop"]["code"] == "REPAIR_ATTEMPTS_EXHAUSTED":
            raise ContractValidationError("Presales chief repair attempts are exhausted")
        if projection["state"] != "chief-repair":
            raise ContractValidationError(
                "Blueprint repair requires a current failed hard gate"
            )

        current_ref = state.artifact_heads["content/reading-blueprint"]
        current = self.kernel.artifacts.resolve(
            self._reference(current_ref)
        )["payload"]
        old_history = list(current.get("repair_history") or [])
        new_history = normalized["repair_history"]
        if len(new_history) != len(old_history) + 1 or new_history[:-1] != old_history:
            raise ContractValidationError(
                "Repair history must append exactly one new attempt"
            )
        self._repair_history(normalized)
        current_failures = projection["repair"]["failure_refs"]
        latest = new_history[-1]
        if set(latest["failure_refs"]) != set(current_failures):
            raise ContractValidationError(
                "Repair attempt must bind every current failed hard gate"
            )
        if set(normalized["hard_gate_refs"]) != set(current_failures):
            raise ContractValidationError(
                "Blueprint hard_gate_refs must bind the current failures"
            )
        created_ref = self.content.repair_reading_deck_blueprint(
            command_id, expected_revision, normalized
        )
        return {
            "operation": "repair-reading-deck-blueprint",
            "created_ref": created_ref,
            "projection": self.inspect(),
        }

    def consultant_capability(
        self,
        *,
        risk_area: str,
        question: str,
        target_refs: list[str],
    ) -> dict[str, Any]:
        if not isinstance(risk_area, str) or self._RISK_AREA.fullmatch(risk_area) is None:
            raise ContractValidationError("risk_area must use lowercase ASCII kebab-case")
        if not isinstance(question, str) or not question.strip() or len(question.strip()) > 500:
            raise ContractValidationError("question must contain 1 to 500 characters")
        if (
            not isinstance(target_refs, list)
            or not target_refs
            or any(not isinstance(value, str) for value in target_refs)
            or len(set(target_refs)) != len(target_refs)
        ):
            raise ContractValidationError("target_refs must be a non-empty unique array")
        current = set(self.kernel.load().artifact_heads.values())
        for value in target_refs:
            try:
                reference = self._reference(value)
                self.kernel.artifacts.resolve(reference)
            except (ArtifactReferenceError, OSError) as error:
                raise ContractValidationError("target_refs must be resolvable artifacts") from error
            if value not in current:
                raise ContractValidationError("target_refs must reference current artifacts")
        return {
            "status": "unavailable",
            "code": "CONSULTANT_RUNTIME_UNAVAILABLE",
            "requested_role": f"presales-risk-specialist/{risk_area}",
            "write_authority": "none",
            "target_refs": list(target_refs),
        }

    def _payload_operation(self, payload: dict[str, Any]) -> str:
        matches: list[str] = []
        for operation, validator in self._VALIDATORS:
            try:
                validator(payload)
            except ContractValidationError:
                continue
            matches.append(operation)
        if len(matches) != 1:
            raise ContractValidationError(
                "Payload must match exactly one presales content contract"
            )
        return matches[0]

    def _failed_gate_refs(self) -> list[str]:
        state = self.kernel.load()
        failures: list[str] = []
        for slot in self._FAILED_GATE_SLOTS:
            value = state.artifact_heads.get(slot, "")
            if not value:
                continue
            reference = self._reference(value)
            if reference.kind != "content-hard-gate-record":
                raise ContractValidationError(
                    f"{slot} must reference content-hard-gate-record"
                )
            record = validate_content_hard_gate_record(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
            if record["overall_result"] == "failed":
                failures.append(value)
        return failures

    def _repair_history(self, blueprint: dict[str, Any]) -> int:
        history = list(blueprint.get("repair_history") or [])
        attempt_ids: list[str] = []
        for entry in history:
            if not isinstance(entry, dict) or set(entry) != {
                "attempt_id",
                "failure_refs",
            }:
                raise ContractValidationError("Repair history entries are not closed")
            attempt_id = entry["attempt_id"]
            failures = entry["failure_refs"]
            if (
                not isinstance(attempt_id, str)
                or not attempt_id.strip()
                or len(attempt_id) > 100
                or not isinstance(failures, list)
                or not failures
                or any(not isinstance(value, str) for value in failures)
                or len(set(failures)) != len(failures)
            ):
                raise ContractValidationError("Repair history entry is invalid")
            for value in failures:
                reference = self._reference(value)
                if reference.kind != "content-hard-gate-record":
                    raise ContractValidationError(
                        "Repair history must reference content hard-gate records"
                    )
                self.kernel.artifacts.resolve(reference)
            attempt_ids.append(attempt_id)
        if len(set(attempt_ids)) != len(attempt_ids):
            raise ContractValidationError("Repair attempt identities must be unique")
        return len(history)

    @staticmethod
    def _reference(value: str):
        try:
            return ArtifactReference.parse(value)
        except (ArtifactReferenceError, ValueError, TypeError) as error:
            raise ContractValidationError("Artifact reference is malformed") from error


__all__ = ["PresalesChiefOrchestrator"]
