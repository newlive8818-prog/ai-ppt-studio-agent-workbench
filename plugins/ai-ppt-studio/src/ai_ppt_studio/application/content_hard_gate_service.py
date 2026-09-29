"""Two non-compensatory v2.2 content hard gates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.material_finding_service import MaterialFindingService
from ai_ppt_studio.application.review_commands import fingerprint, replay_ref
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.domains.content.contracts import (
    validate_content_hard_gate_record,
    validate_customer_decision_context,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
    RevisionConflictError,
    WorkbenchValidationError,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel

GATE_ROLE = {
    "evidence": "content-evidence-gate-reviewer",
    "presales-reading": "content-presales-reading-gate-reviewer",
}
GATE_SLOT = {
    "evidence": "content/gate/evidence",
    "presales-reading": "content/gate/presales-reading",
}
GATE_OPERATION = {
    "evidence": "run-content-evidence-gate",
    "presales-reading": "run-content-presales-reading-gate",
}
SEMANTIC_CHECK_IDS = {
    "evidence": (
        "selective-evidence-risk",
        "unsupported-causality",
        "unsupported-capability-result-commitment",
    ),
    "presales-reading": (
        "customer-decision-position",
        "problem-completeness",
        "whole-deck-coherence-and-repetition",
        "boundary-risk-validation-next-step",
    ),
}
DETERMINISTIC_CHECK_IDS = {
    "evidence": (
        "current-content-lineage",
        "source-and-exclusion-identity",
        "formal-identity-and-material-mode",
        "problem-requirement-solution-traceability",
    ),
    "presales-reading": (
        "neutral-title-contract",
        "independent-reading-contract",
        "page-and-section-order",
        "solution-mapping-contract",
    ),
}


class ContentHardGateService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def inspect(self) -> dict[str, Any]:
        state = self.kernel.load()
        projection: dict[str, Any] = {
            "project_id": self.kernel.project_id,
            "revision": state.revision,
            "state": "content-not-ready",
            "source_version": "",
            "blueprint_ref": state.artifact_heads.get("content/reading-blueprint", ""),
            "evidence_gate_ref": state.artifact_heads.get("content/gate/evidence", ""),
            "presales_reading_gate_ref": state.artifact_heads.get("content/gate/presales-reading", ""),
            "acceptance_ref": state.artifact_heads.get("content/acceptance", ""),
            "next_operation": "",
            "failure_refs": [],
            "repair_requirements": [],
            "stop": {"code": "", "message": "", "resumable": False},
        }
        try:
            chain = self._validated_content_chain()["objects"]
        except (ArtifactReferenceError, ContractValidationError):
            return self._stopped(projection, "CONTENT_CHAIN_INCONSISTENT", "Current content chain is inconsistent")
        blueprint = chain["reading_blueprint"]
        if blueprint is None:
            projection["stop"] = {
                "code": "CONTENT_BLUEPRINT_NOT_READY",
                "message": "Current ReadingDeckBlueprint is not ready",
                "resumable": True,
            }
            return projection
        projection["source_version"] = blueprint["payload"]["source_version"]
        try:
            evidence = self._current_record("evidence", projection["evidence_gate_ref"], blueprint)
            reading = self._current_record("presales-reading", projection["presales_reading_gate_ref"], blueprint)
        except (ArtifactReferenceError, ContractValidationError):
            return self._stopped(projection, "CONTENT_GATE_INCONSISTENT", "Current content hard-gate identity is inconsistent")
        if not evidence:
            if reading or projection["acceptance_ref"]:
                return self._stopped(projection, "CONTENT_GATE_ORDER_INCONSISTENT", "Reading or acceptance exists without the evidence gate")
            projection["state"] = "evidence-gate-review"
            projection["next_operation"] = GATE_OPERATION["evidence"]
            return projection
        if evidence["overall_result"] == "failed":
            if reading or projection["acceptance_ref"]:
                return self._stopped(
                    projection,
                    "CONTENT_GATE_ORDER_INCONSISTENT",
                    "Failed evidence cannot coexist with reading or acceptance",
                )
            return self._repair_projection(projection, projection["evidence_gate_ref"], evidence)
        if not reading:
            if projection["acceptance_ref"]:
                return self._stopped(projection, "CONTENT_ACCEPTANCE_INCONSISTENT", "Acceptance exists without both passed gates")
            projection["state"] = "presales-reading-gate-review"
            projection["next_operation"] = GATE_OPERATION["presales-reading"]
            return projection
        if reading["overall_result"] == "failed":
            if projection["acceptance_ref"]:
                return self._stopped(
                    projection,
                    "CONTENT_ACCEPTANCE_INCONSISTENT",
                    "Failed reading cannot coexist with acceptance",
                )
            return self._repair_projection(projection, projection["presales_reading_gate_ref"], reading)
        try:
            self._require_current_acceptance(
                projection["acceptance_ref"], blueprint,
                projection["evidence_gate_ref"], projection["presales_reading_gate_ref"],
            )
        except (ArtifactReferenceError, ContractValidationError):
            return self._stopped(projection, "CONTENT_ACCEPTANCE_INCONSISTENT", "Current content acceptance does not bind both current gates")
        projection["state"] = "content-user-reviewable"
        return projection

    def run_evidence_gate(self, **kwargs: Any):
        return self._run_gate("evidence", **kwargs)

    def run_presales_reading_gate(self, **kwargs: Any):
        return self._run_gate("presales-reading", **kwargs)

    def commit_reviewer_output(
        self,
        *,
        command_id: str,
        expected_revision: int,
        reviewer_role_id: str,
        artifact_kind: str,
        payload: dict[str, Any],
    ):
        if artifact_kind != "content-hard-gate-record":
            raise WorkbenchValidationError(
                "Content hard-gate reviewers may write content-hard-gate-record only"
            )
        normalized = validate_content_hard_gate_record(payload)
        gate_type = normalized["gate_type"]
        if GATE_ROLE.get(gate_type) != reviewer_role_id:
            raise WorkbenchValidationError("Reviewer role does not match the hard gate")
        if normalized["reviewer_mode"] != "isolated-review-task":
            raise WorkbenchValidationError(
                "INDEPENDENT_REVIEW_RUNTIME_UNAVAILABLE: no attested independent reviewer adapter"
            )
        command_fingerprint = fingerprint(
            f"commit-{GATE_OPERATION[gate_type]}", normalized
        )
        replay = replay_ref(
            self.kernel, command_id, command_fingerprint, GATE_SLOT[gate_type]
        )
        if replay is not None:
            reference, replay_state = replay
            return reference, self._payload(reference), replay_state
        state, chain, blueprint = self._require_new_command(expected_revision)
        self._require_record_current(normalized, gate_type, blueprint)
        self._require_check_coverage(normalized, gate_type, blueprint["ref"])
        self._require_context_pack(normalized, gate_type, chain)
        self._require_gate_order(gate_type, state, blueprint)
        return self._commit_record(
            command_id,
            state.revision,
            normalized,
            detached=(),
            command_fingerprint=command_fingerprint,
        )

    def _run_gate(
        self,
        gate_type: str,
        *,
        command_id: str,
        expected_revision: int,
        semantic_check_results: list[dict[str, Any]],
        reviewer_mode: str,
        independent_agent_instance_id: str = "",
        output_ref: str = "",
    ) -> tuple[str, dict[str, Any], KernelState]:
        if reviewer_mode != "isolated-review-task":
            raise WorkbenchValidationError(
                "INDEPENDENT_REVIEW_RUNTIME_UNAVAILABLE: no attested independent reviewer adapter"
            )
        if independent_agent_instance_id.strip() or output_ref.strip():
            raise WorkbenchValidationError(
                "isolated-review-task cannot claim independent reviewer evidence"
            )
        state = self.kernel.load()
        chain, blueprint = self._current_complete_chain()
        semantic = self._semantic_checks(
            gate_type, semantic_check_results, blueprint["ref"]
        )
        command_fingerprint = fingerprint(
            GATE_OPERATION[gate_type],
            {
                "reviewer_mode": reviewer_mode,
                "semantic_check_results": semantic,
                "blueprint_ref": blueprint["ref"],
            },
        )
        replay = replay_ref(
            self.kernel, command_id, command_fingerprint, GATE_SLOT[gate_type]
        )
        if replay is not None:
            reference, replay_state = replay
            return reference, self._payload(reference), replay_state
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        self._require_gate_order(gate_type, state, blueprint)
        context = ContextCompiler(self.kernel).compile_role_task(
            role_id=GATE_ROLE[gate_type],
            task_type=GATE_OPERATION[gate_type],
            project_revision=state.revision,
            target_refs=[value["ref"] for value in chain.values() if value is not None],
            instructions="只审查当前内容并提交 pass/fail 与修复要求；禁止编辑内容。",
        )
        context_reference = self.kernel.artifacts.reference_for("context-pack", context)
        deterministic = self._deterministic_checks(
            gate_type, blueprint["ref"], chain
        )
        failures = [
            check
            for check in [*deterministic, *semantic]
            if check["applicability"] == "applicable"
            and check["result"] == "failed"
        ]
        record = validate_content_hard_gate_record(
            {
                "gate_type": gate_type,
                "input_source_version": blueprint["payload"]["source_version"],
                "input_hash": ArtifactReference.parse(blueprint["ref"]).sha256,
                "reviewer_mode": "isolated-review-task",
                "independent_agent_instance_id": "",
                "context_pack_ref": str(context_reference),
                "context_pack_hash": context_reference.sha256,
                "output_ref": "",
                "deterministic_check_results": deterministic,
                "semantic_check_results": semantic,
                "overall_result": "failed" if failures else "passed",
                "repair_requirements": [
                    {
                        "check_id": check["check_id"],
                        "instruction": check["failure_reason"],
                    }
                    for check in failures
                ],
                "reviewer_cannot_edit": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return self._commit_record(
            command_id,
            expected_revision,
            record,
            detached=(("context-pack", context),),
            command_fingerprint=command_fingerprint,
        )

    def _commit_record(
        self,
        command_id: str,
        expected_revision: int,
        record: dict[str, Any],
        *,
        detached: tuple[tuple[str, dict[str, Any]], ...],
        command_fingerprint: str,
    ) -> tuple[str, dict[str, Any], KernelState]:
        gate_type = record["gate_type"]
        slot = GATE_SLOT[gate_type]
        reference = self.kernel.artifacts.reference_for(
            "content-hard-gate-record", record
        )
        updates: dict[str, tuple[str, dict[str, Any]]] = {
            slot: ("content-hard-gate-record", record)
        }
        gate_mutation = None
        removals = []
        if gate_type == "evidence":
            removals.extend(("content/gate/presales-reading", "content/acceptance"))
        else:
            removals.append("content/acceptance")
        if record["overall_result"] == "passed" and gate_type == "presales-reading":
            state = self.kernel.load()
            _chain, blueprint = self._current_complete_chain()
            self._require_gate_order(gate_type, state, blueprint)
            evidence_ref = state.artifact_heads["content/gate/evidence"]
            blueprint_ref = state.artifact_heads["content/reading-blueprint"]
            acceptance = {
                "source_version": record["input_source_version"],
                "reading_blueprint_ref": blueprint_ref,
                "evidence_gate_ref": evidence_ref,
                "presales_reading_gate_ref": str(reference),
                "overall_result": "passed",
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
            updates["content/acceptance"] = ("content-acceptance", acceptance)
            acceptance_ref = str(
                self.kernel.artifacts.reference_for("content-acceptance", acceptance)
            )
            gate_mutation = GateEvaluator(self.kernel).await_content_review_v22(
                blueprint_ref=blueprint_ref,
                evidence_gate_ref=evidence_ref,
                presales_reading_gate_ref=str(reference),
                acceptance_ref=acceptance_ref,
            )
            removals.remove("content/acceptance")
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=f"content.hard-gate-{gate_type}",
            artifact_updates=updates,
            artifact_removals=tuple(
                item for item in removals if self.kernel.load().artifact_heads.get(item)
            ),
            detached_artifacts=detached,
            gate_mutation=gate_mutation,
            command_fingerprint=command_fingerprint,
        )
        current_ref = committed.artifact_heads[slot]
        return current_ref, record, committed

    def _current_complete_chain(self):
        objects = self._validated_content_chain()["objects"]
        if any(value is None for value in objects.values()):
            raise ArtifactReferenceError("Complete current content chain is required")
        return objects, objects["reading_blueprint"]

    def _validated_content_chain(self) -> dict[str, Any]:
        content = PresalesContentService(self.kernel)
        chain = content.get_current_content_chain()
        objects = chain["objects"]
        validators = {
            "evidence_book": validate_presales_evidence_book,
            "decision_context": validate_customer_decision_context,
            "problem_solution_fit": validate_problem_solution_fit_map,
            "reading_blueprint": validate_reading_deck_blueprint,
        }
        for key, validator in validators.items():
            current = objects[key]
            if current is not None:
                current["payload"] = validator(current["payload"])

        evidence = objects["evidence_book"]
        fit = objects["problem_solution_fit"]
        blueprint = objects["reading_blueprint"]
        if evidence is not None:
            payload = evidence["payload"]
            MaterialFindingService(self.kernel).validate_evidence(payload)
            content._require_current(
                "mission/confirmation",
                "mission-confirmation",
                payload["mission_confirmation_ref"],
            )
            if payload["material_mode"] == "proposal-led":
                if self.kernel.load().artifact_heads.get("materials"):
                    raise ContractValidationError(
                        "proposal-led cannot be current while materials exist"
                    )
            else:
                content._require_current(
                    "materials",
                    "material-inventory",
                    payload["material_inventory_ref"],
                )
        if evidence is not None and fit is not None:
            content._validate_fit_evidence(
                fit["payload"], evidence=evidence["payload"]
            )
        if evidence is not None and fit is not None and blueprint is not None:
            if blueprint["payload"]["project_id"] != self.kernel.project_id:
                raise ContractValidationError(
                    "ReadingDeckBlueprint project_id is stale"
                )
            content._validate_blueprint_evidence(
                blueprint["payload"],
                evidence=evidence["payload"],
                fit=fit["payload"],
            )
        return chain

    def _require_new_command(self, expected_revision: int):
        state = self.kernel.load()
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        chain, blueprint = self._current_complete_chain()
        return state, chain, blueprint

    def _require_gate_order(
        self,
        gate_type: str,
        state: KernelState,
        blueprint: dict[str, Any],
    ) -> None:
        if gate_type != "presales-reading":
            return
        evidence_ref = state.artifact_heads.get("content/gate/evidence", "")
        try:
            evidence = self._current_record("evidence", evidence_ref, blueprint)
        except ArtifactReferenceError as error:
            raise GateBlockedError(
                "content-presales-reading",
                ("current-evidence-gate-invalid",),
            ) from error
        if not evidence or evidence["overall_result"] != "passed":
            raise GateBlockedError(
                "content-presales-reading", ("current-evidence-gate-not-passed",)
            )

    def _current_record(
        self, gate_type: str, value: str, blueprint: dict[str, Any]
    ) -> dict[str, Any]:
        if not value:
            return {}
        reference = ArtifactReference.parse(value)
        if reference.kind != "content-hard-gate-record":
            raise ArtifactReferenceError(
                f"{GATE_SLOT[gate_type]} must reference content-hard-gate-record"
            )
        record = validate_content_hard_gate_record(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        self._require_record_current(record, gate_type, blueprint)
        self._require_check_coverage(record, gate_type, blueprint["ref"])
        return record

    @staticmethod
    def _require_record_current(
        record: dict[str, Any], gate_type: str, blueprint: dict[str, Any]
    ) -> None:
        reference = ArtifactReference.parse(blueprint["ref"])
        if (
            record["gate_type"] != gate_type
            or record["input_source_version"] != blueprint["payload"]["source_version"]
            or record["input_hash"] != reference.sha256
        ):
            raise ContractValidationError(
                "Content hard-gate record is stale for the current Blueprint"
            )

    @staticmethod
    def _require_check_coverage(
        record: dict[str, Any], gate_type: str, blueprint_ref: str
    ) -> None:
        if tuple(
            row["check_id"] for row in record["deterministic_check_results"]
        ) != DETERMINISTIC_CHECK_IDS[gate_type]:
            raise ContractValidationError("Deterministic hard-gate coverage is incomplete")
        if tuple(
            row["check_id"] for row in record["semantic_check_results"]
        ) != SEMANTIC_CHECK_IDS[gate_type]:
            raise ContractValidationError("Semantic hard-gate coverage is incomplete")
        for row in record["deterministic_check_results"] + record["semantic_check_results"]:
            expected = [blueprint_ref] if row["applicability"] == "applicable" else []
            if row["evidence_refs"] != expected:
                raise ContractValidationError(
                    "Hard-gate checks must cite the exact current Blueprint"
                )

    @staticmethod
    def _semantic_checks(
        gate_type: str, values: list[dict[str, Any]], blueprint_ref: str
    ) -> list[dict[str, Any]]:
        if not isinstance(values, list) or tuple(
            row.get("check_id") if isinstance(row, dict) else None for row in values
        ) != SEMANTIC_CHECK_IDS[gate_type]:
            raise ContractValidationError("Semantic hard-gate coverage is incomplete")
        failures = [
            row for row in values
            if isinstance(row, dict) and row.get("result") == "failed"
        ]
        normalized = validate_content_hard_gate_record(
            {
                "gate_type": gate_type,
                "input_source_version": "validation-only",
                "input_hash": "a" * 64,
                "reviewer_mode": "isolated-review-task",
                "independent_agent_instance_id": "",
                "context_pack_ref": "artifact://context-pack/" + "b" * 64,
                "context_pack_hash": "b" * 64,
                "output_ref": "",
                "deterministic_check_results": [],
                "semantic_check_results": values,
                "overall_result": "failed" if failures else "passed",
                "repair_requirements": [
                    {
                        "check_id": str(row.get("check_id") or ""),
                        "instruction": str(row.get("failure_reason") or ""),
                    }
                    for row in failures
                ],
                "reviewer_cannot_edit": True,
                "created_at": "2026-08-26T00:00:00+00:00",
            }
        )["semantic_check_results"]
        for row in normalized:
            expected = [blueprint_ref] if row["applicability"] == "applicable" else []
            if row["evidence_refs"] != expected:
                raise ContractValidationError(
                    "Semantic checks must cite the exact current Blueprint"
                )
        return normalized

    @staticmethod
    def _deterministic_checks(
        gate_type: str,
        blueprint_ref: str,
        chain: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if any(value is None for value in chain.values()):
            raise ArtifactReferenceError(
                "Deterministic checks require a validated complete content chain"
            )
        return [
            {
                "check_id": check_id,
                "applicability": "applicable",
                "result": "passed",
                "hard": True,
                "evidence_refs": [blueprint_ref],
                "failure_reason": "",
            }
            for check_id in DETERMINISTIC_CHECK_IDS[gate_type]
        ]

    def _require_context_pack(
        self,
        record: dict[str, Any],
        gate_type: str,
        chain: dict[str, dict[str, Any]],
    ) -> None:
        reference = ArtifactReference.parse(record["context_pack_ref"])
        if reference.kind != "context-pack" or reference.sha256 != record["context_pack_hash"]:
            raise ContractValidationError("Context Pack identity is inconsistent")
        context = self.kernel.artifacts.resolve(reference)["payload"]
        if (
            context.get("project_id") != self.kernel.project_id
            or context.get("layers", {}).get("role_contract", {}).get("role_id") != GATE_ROLE[gate_type]
            or context.get("layers", {}).get("task_contract", {}).get("task_type") != GATE_OPERATION[gate_type]
            or context.get("artifact_version_refs") != [value["ref"] for value in chain.values()]
        ):
            raise ContractValidationError(
                "Context Pack does not bind the current hard-gate task"
            )

    def _require_current_acceptance(
        self,
        value: str,
        blueprint: dict[str, Any],
        evidence_ref: str,
        reading_ref: str,
    ) -> None:
        if not value:
            raise ContractValidationError("Current content acceptance is missing")
        reference = ArtifactReference.parse(value)
        if reference.kind != "content-acceptance":
            raise ArtifactReferenceError("content/acceptance has the wrong kind")
        payload = self.kernel.artifacts.resolve(reference)["payload"]
        if set(payload) != {
            "source_version",
            "reading_blueprint_ref",
            "evidence_gate_ref",
            "presales_reading_gate_ref",
            "overall_result",
            "accepted_at",
        } or (
            payload["source_version"] != blueprint["payload"]["source_version"]
            or payload["reading_blueprint_ref"] != blueprint["ref"]
            or payload["evidence_gate_ref"] != evidence_ref
            or payload["presales_reading_gate_ref"] != reading_ref
            or payload["overall_result"] != "passed"
        ):
            raise ContractValidationError(
                "Content acceptance does not bind current passed gates"
            )

    @staticmethod
    def _repair_projection(
        projection: dict[str, Any], failure_ref: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        projection["state"] = "chief-repair"
        projection["failure_refs"] = [failure_ref]
        projection["repair_requirements"] = list(record["repair_requirements"])
        return projection

    @staticmethod
    def _stopped(
        projection: dict[str, Any], code: str, message: str
    ) -> dict[str, Any]:
        projection["state"] = "governed-stop"
        projection["stop"] = {"code": code, "message": message, "resumable": True}
        return projection

    def _payload(self, reference: str) -> dict[str, Any]:
        return validate_content_hard_gate_record(
            self.kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]
        )


__all__ = ["ContentHardGateService"]
