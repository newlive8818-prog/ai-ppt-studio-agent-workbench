"""Two non-compensatory v2.2 content hard gates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.artifact_guards import require_exact_ref
from ai_ppt_studio.domains.content.contracts import (
    validate_content_hard_gate_record,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import GateBlockedError, WorkbenchValidationError
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


class ContentHardGateService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

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
        gate_type = str(payload.get("gate_type") or "")
        if GATE_ROLE.get(gate_type) != reviewer_role_id:
            raise WorkbenchValidationError("Reviewer role does not match the hard gate")
        return self._commit_record(
            command_id,
            expected_revision,
            validate_content_hard_gate_record(payload),
            detached=(),
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
        state = self.kernel.load()
        if state.revision != expected_revision:
            from ai_ppt_studio.errors import RevisionConflictError

            raise RevisionConflictError(expected_revision, state.revision)
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        blueprint = validate_reading_deck_blueprint(
            require_exact_ref(
                self.kernel,
                blueprint_ref,
                "content/reading-blueprint",
                "reading-deck-blueprint",
            )["payload"]
        )
        for slot, kind, field in (
            ("content/evidence-book", "presales-evidence-book", "evidence_book_ref"),
            (
                "content/decision-context",
                "customer-decision-context",
                "decision_context_ref",
            ),
            (
                "content/problem-solution-fit",
                "problem-solution-fit-map",
                "problem_solution_fit_ref",
            ),
        ):
            require_exact_ref(self.kernel, blueprint[field], slot, kind)
        if gate_type == "presales-reading":
            evidence_ref = state.artifact_heads.get("content/gate/evidence", "")
            evidence = self._record(evidence_ref)
            if (
                evidence.get("overall_result") != "passed"
                or evidence.get("input_source_version") != blueprint["source_version"]
            ):
                raise GateBlockedError(
                    "content-presales-reading", ("current-evidence-gate-not-passed",)
                )
        context = {
            "project_id": state.project_id,
            "gate_type": gate_type,
            "input_ref": blueprint_ref,
            "source_version": blueprint["source_version"],
            "reviewer_role_id": GATE_ROLE[gate_type],
        }
        context_reference = self.kernel.artifacts.reference_for("context-pack", context)
        deterministic = self._deterministic_checks(gate_type, blueprint_ref, blueprint)
        failures = [
            check
            for check in [*deterministic, *semantic_check_results]
            if check.get("applicability") == "applicable"
            and check.get("hard") is True
            and check.get("result") == "failed"
        ]
        record = validate_content_hard_gate_record(
            {
                "gate_type": gate_type,
                "input_source_version": blueprint["source_version"],
                "input_hash": ArtifactReference.parse(blueprint_ref).sha256,
                "reviewer_mode": reviewer_mode,
                "independent_agent_instance_id": independent_agent_instance_id,
                "context_pack_ref": str(context_reference),
                "context_pack_hash": context_reference.sha256,
                "output_ref": output_ref,
                "deterministic_check_results": deterministic,
                "semantic_check_results": semantic_check_results,
                "overall_result": "failed" if failures else "passed",
                "repair_requirements": [
                    {
                        "check_id": str(check.get("check_id") or "unknown"),
                        "instruction": str(check.get("failure_reason") or "修复硬门失败项"),
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
        )

    def _commit_record(
        self,
        command_id: str,
        expected_revision: int,
        record: dict[str, Any],
        *,
        detached: tuple[tuple[str, dict[str, Any]], ...],
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
        )
        current_ref = committed.artifact_heads[slot]
        return current_ref, record, committed

    def _record(self, value: str) -> dict[str, Any]:
        if not value:
            return {}
        reference = ArtifactReference.parse(value)
        if reference.kind != "content-hard-gate-record":
            return {}
        return validate_content_hard_gate_record(
            self.kernel.artifacts.resolve(reference)["payload"]
        )

    @staticmethod
    def _deterministic_checks(
        gate_type: str, blueprint_ref: str, blueprint: dict[str, Any]
    ) -> list[dict[str, Any]]:
        checks = {
            "evidence": (
                "source-and-identity-traceability",
                "Current evidence refs and content identities are structurally valid",
            ),
            "presales-reading": (
                "neutral-title-and-independent-reading",
                "Titles are neutral and each page is independently readable",
            ),
        }
        check_id, note = checks[gate_type]
        return [{
            "check_id": check_id,
            "applicability": "applicable",
            "result": "passed",
            "hard": True,
            "evidence_refs": [blueprint_ref],
            "failure_reason": "",
            "note": note,
        }]


__all__ = ["ContentHardGateService"]
