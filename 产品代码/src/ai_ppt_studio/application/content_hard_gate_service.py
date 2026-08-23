"""Non-compensatory v2.2 content hard gates and acceptance."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ai_ppt_studio.domains.content.contracts import (
    V22_CONTENT_GATE_ROLES,
    validate_content_hard_gate_record,
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


GATE_SLOTS = {
    "evidence": "content/gate/evidence",
    "presales-reading": "content/gate/presales-reading",
}
GATE_RECORD_KIND = "content-hard-gate-record"
BLUEPRINT_SLOT = "content/reading-deck-blueprint"
BLUEPRINT_KIND = "reading-deck-blueprint"


class ContentHardGateService:
    """Persist isolated gate facts and derive acceptance from current heads."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def submit_record(
        self,
        *,
        command_id: str,
        expected_revision: int,
        actor_role_id: str,
        agent_task_id: str = "",
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_content_hard_gate_record(payload)
        expected_role = V22_CONTENT_GATE_ROLES[normalized["gate_type"]]
        if actor_role_id != expected_role:
            raise WorkbenchValidationError(
                f"Only the matching hard-gate reviewer {expected_role} may submit this record"
            )
        blueprint_ref = self._require_current(
            normalized["input_source_version"], BLUEPRINT_SLOT, BLUEPRINT_KIND
        )
        normalized["input_source_version"] = blueprint_ref
        task_ref, _task = self._require_queued_reviewer_task(
            task_id=agent_task_id,
            actor_role_id=actor_role_id,
            gate_type=normalized["gate_type"],
            blueprint_ref=blueprint_ref,
            context_pack_ref=normalized["context_pack_ref"],
        )
        normalized["agent_task_id"] = agent_task_id
        normalized["agent_task_ref"] = task_ref
        self._resolve(normalized["context_pack_ref"], "context-pack")
        if normalized["reviewer_mode"] == "independent-agent":
            self._resolve(normalized["review_output_ref"], "review-output")
        for check in (
            normalized["deterministic_check_results"]
            + normalized["semantic_check_results"]
        ):
            for value in check["evidence_refs"]:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        if normalized["gate_type"] == "presales-reading":
            evidence_ref = self._require_evidence_gate_passed(blueprint_ref)
            if normalized.get("evidence_gate_ref") != evidence_ref:
                raise GateBlockedError(
                    "content-presales-reading-gate",
                    ("evidence-gate-lineage-mismatch",),
                )
        slot = GATE_SLOTS[normalized["gate_type"]]
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=f"content.hard-gate.{normalized['gate_type']}.recorded",
            artifact_updates={slot: (GATE_RECORD_KIND, normalized)},
            artifact_removals=("content/acceptance",),
        )
        return state.artifact_heads[slot]

    def accept_current_content(
        self, *, command_id: str, expected_revision: int
    ) -> str:
        fingerprint = hashlib.sha256(
            canonical_json(
                {
                    "operation": "accept-current-content",
                    "expected_revision": expected_revision,
                }
            )
        ).hexdigest()
        replayed = self._replay_artifact_ref(
            command_id,
            "content/acceptance",
            "content-acceptance",
            fingerprint,
        )
        if replayed:
            return replayed
        state = self.kernel.load()
        blueprint_ref = state.artifact_heads.get(BLUEPRINT_SLOT, "")
        blockers: list[str] = []
        gate_refs: dict[str, str] = {}
        gate_records: dict[str, dict[str, Any]] = {}
        for gate_type, slot in GATE_SLOTS.items():
            value = state.artifact_heads.get(slot, "")
            if not value:
                blockers.append(f"missing:{gate_type}")
                continue
            try:
                record = self._resolve(value, GATE_RECORD_KIND)
            except ArtifactReferenceError:
                blockers.append(f"invalid:{gate_type}")
                continue
            if record.get("input_source_version") != blueprint_ref:
                blockers.append(f"stale:{gate_type}")
            if record.get("overall_result") != "passed":
                blockers.append(f"failed:{gate_type}")
            try:
                self._require_completed_reviewer_task(value, record)
            except (ArtifactReferenceError, WorkbenchValidationError):
                blockers.append(f"unverified-task:{gate_type}")
            gate_refs[gate_type] = value
            gate_records[gate_type] = record
        if (
            gate_records.get("presales-reading", {}).get("evidence_gate_ref")
            != gate_refs.get("evidence")
        ):
            blockers.append("evidence-predecessor-mismatch")
        if not blueprint_ref:
            blockers.append("missing:reading-deck-blueprint")
        if blockers:
            raise GateBlockedError(
                "content-acceptance", tuple(sorted(set(blockers)))
            )
        acceptance = {
            "source_version": blueprint_ref,
            "evidence_gate_ref": gate_refs["evidence"],
            "presales_reading_gate_ref": gate_refs["presales-reading"],
            "hard_gate_refs": [
                gate_refs["evidence"],
                gate_refs["presales-reading"],
            ],
            "overall_result": "passed",
        }
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.v22-accepted",
            artifact_updates={
                "content/acceptance": ("content-acceptance", acceptance)
            },
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads["content/acceptance"]

    def _replay_artifact_ref(
        self,
        command_id: str,
        slot: str,
        kind: str,
        fingerprint: str,
    ) -> str:
        state = self.kernel.load()
        revision = state.processed_commands.get(command_id)
        if revision is None:
            return ""
        events_root = getattr(self.kernel, "events_root", None)
        if events_root is None:
            raise WorkbenchValidationError(
                "Processed command receipt is unavailable"
            )
        try:
            event = json.loads(
                (events_root / f"r{revision:08d}.json").read_text(
                    encoding="utf-8"
                )
            )
            value = str(event.get("artifact_heads", {}).get(slot) or "")
            if (
                event.get("command_id") != command_id
                or event.get("event_type") != "content.v22-accepted"
                or event.get("command_fingerprint") != fingerprint
            ):
                raise ValueError("receipt mismatch")
            self._resolve(value, kind)
        except (
            ArtifactReferenceError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ContractValidationError(
                "Processed acceptance command has different semantics"
            ) from exc
        return value

    def _require_evidence_gate_passed(self, blueprint_ref: str) -> str:
        value = self.kernel.load().artifact_heads.get(
            GATE_SLOTS["evidence"], ""
        )
        if not value:
            raise GateBlockedError(
                "content-presales-reading-gate",
                ("evidence-gate-not-passed",),
            )
        record = self._resolve(value, GATE_RECORD_KIND)
        if (
            record.get("input_source_version") != blueprint_ref
            or record.get("overall_result") != "passed"
        ):
            raise GateBlockedError(
                "content-presales-reading-gate",
                ("evidence-gate-not-passed",),
            )
        return value

    def _require_queued_reviewer_task(
        self,
        *,
        task_id: str,
        actor_role_id: str,
        gate_type: str,
        blueprint_ref: str,
        context_pack_ref: str,
    ) -> tuple[str, dict[str, Any]]:
        identity = task_id.strip()
        if not identity:
            raise WorkbenchValidationError(
                "A queued reviewer AgentTask is required"
            )
        state = self.kernel.load()
        task_ref = state.artifact_heads.get(f"agent/task/{identity}", "")
        if not task_ref or task_ref != state.artifact_heads.get(
            "agent/task/active", ""
        ):
            raise WorkbenchValidationError(
                "The reviewer AgentTask must be current and active"
            )
        task = self._resolve(task_ref, "agent-task")
        action = (
            "run-content-evidence-gate"
            if gate_type == "evidence"
            else "run-content-presales-reading-gate"
        )
        expected_targets = [blueprint_ref]
        if gate_type == "presales-reading":
            expected_targets.append(self._require_evidence_gate_passed(blueprint_ref))
        if (
            task.get("task_id") != identity
            or task.get("status") != "queued"
            or task.get("role_id") != actor_role_id
            or task.get("action_type") != action
            or task.get("target_refs") != expected_targets
            or task.get("context_pack_ref") != context_pack_ref
        ):
            raise WorkbenchValidationError(
                "The reviewer AgentTask provenance is inconsistent"
            )
        return task_ref, task

    def _require_completed_reviewer_task(
        self, record_ref: str, record: dict[str, Any]
    ) -> None:
        task_id = str(record.get("agent_task_id") or "")
        queued_task_ref = str(record.get("agent_task_ref") or "")
        queued_task = self._resolve(queued_task_ref, "agent-task")
        completed_ref = self.kernel.load().artifact_heads.get(
            f"agent/task/{task_id}", ""
        )
        completed = self._resolve(completed_ref, "agent-task")
        if (
            queued_task.get("task_id") != task_id
            or queued_task.get("status") != "queued"
            or queued_task.get("context_pack_ref") != record.get("context_pack_ref")
            or completed.get("task_id") != task_id
            or completed.get("status") != "completed"
            or record_ref not in list(completed.get("result_refs") or [])
        ):
            raise WorkbenchValidationError(
                "Content hard-gate record lacks a completed reviewer task"
            )
    def _require_current(self, value: str, slot: str, kind: str) -> str:
        if self.kernel.load().artifact_heads.get(slot) != value:
            raise ArtifactReferenceError(f"{slot} reference is not current")
        self._resolve(value, kind)
        return value

    def _resolve(self, value: str, kind: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"Expected {kind}, received {reference.kind}")
        return dict(self.kernel.artifacts.resolve(reference)["payload"])


__all__ = ["ContentHardGateService"]
