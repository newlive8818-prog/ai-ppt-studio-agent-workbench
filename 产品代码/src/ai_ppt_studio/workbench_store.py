"""Additive project projection and revision-safe human decision persistence."""

from __future__ import annotations

import fcntl
import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .artifact_store import ArtifactStore
from .agent_tasks import AgentTaskStore
from .context_compiler import ContextCompiler
from .errors import (
    ProjectNotFoundError,
    RevisionConflictError,
    WorkbenchValidationError,
)
from .event_store import EventStore, utc_now
from .json_io import append_jsonl, atomic_write_json
from .gate_evidence import GateEvidenceChecker
from .materials import MaterialIntake
from .models import ArtifactKind, Gate, ProjectManifest
from .paths import PathPolicy
from .state_store import StateStore
from .space_projection import SpaceProjectionBuilder
from .workbench_models import DecisionResult, ProjectSnapshot


WORKBENCH_SCHEMA_VERSION = "2.0"


class WorkbenchStore:
    """Project-backed Native Widget state without duplicating domain artifacts."""

    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.events = EventStore(self.project_root, policy)

    @property
    def workbench_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "state" / "workbench.json"
        )

    @property
    def cognition_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "cognition" / "map.json"
        )

    @property
    def decisions_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "cognition" / "decisions.jsonl"
        )

    @property
    def lock_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "state" / ".workbench.lock"
        )

    def ensure(self) -> ProjectSnapshot:
        """Create additive v2 files when needed and return a fresh projection."""

        with self._locked():
            self._load_manifest()
            state = self._load_or_initialize_workbench()
            cognition = self._build_cognition_map()
            atomic_write_json(self.cognition_path, cognition)
            return self._snapshot(state, cognition)

    def submit_decision(
        self,
        *,
        expected_revision: int,
        target_ref: str,
        choice: str,
        feedback: str = "",
    ) -> DecisionResult:
        """Persist one human decision if and only if the revision is current."""

        target = target_ref.strip()
        selected = choice.strip()
        note = feedback.strip()
        if not target:
            raise WorkbenchValidationError("Decision target_ref is required")
        if not selected:
            raise WorkbenchValidationError("Decision choice is required")
        if expected_revision < 0:
            raise WorkbenchValidationError("expected_revision cannot be negative")

        with self._locked():
            self._load_manifest()
            state = self._load_or_initialize_workbench()
            actual_revision = int(state["revision"])
            if expected_revision != actual_revision:
                raise RevisionConflictError(expected_revision, actual_revision)

            decision_id = str(uuid.uuid4())
            created_at = utc_now()
            affected = self._affected_artifacts(target)
            decision = {
                "decision_id": decision_id,
                "target_ref": target,
                "choice": selected,
                "feedback": note,
                "expected_revision": expected_revision,
                "result_revision": actual_revision + 1,
                "affected_artifacts": list(affected),
                "created_at": created_at,
                "created_by": "user",
            }
            updated = dict(state)
            updated.update(
                {
                    "revision": actual_revision + 1,
                    "updated_at": created_at,
                    "last_human_decision_id": decision_id,
                    "current_decision": {
                        "target_ref": target,
                        "status": "resolved",
                        "choice": selected,
                        "feedback": note,
                        "decision_id": decision_id,
                    },
                }
            )

            # Revision validation happens before any append. All writes remain under
            # one project lock so two Widget instances cannot interleave decisions.
            append_jsonl(self.decisions_path, decision)
            self.events.append(
                "workbench.human-decision.submitted",
                {
                    "decision_id": decision_id,
                    "target_ref": target,
                    "choice": selected,
                    "revision": actual_revision + 1,
                    "affected_artifacts": list(affected),
                },
            )
            atomic_write_json(self.workbench_path, updated)

            cognition = self._build_cognition_map()
            cognition["confirmed_decisions"] = self._decision_summaries()
            atomic_write_json(self.cognition_path, cognition)
            snapshot = self._snapshot(updated, cognition)

        follow_up = (
            f"用户已提交判断：{selected}。目标：{target}。"
            f"当前项目 revision={snapshot.revision}。"
        )
        if note:
            follow_up += f" 用户补充：{note}"
        follow_up += " 请读取最新项目快照，说明影响范围，并继续下一项最有价值的工作。"
        model_context = {
            "project_id": snapshot.project["project_id"],
            "project_root": snapshot.project["project_root"],
            "project_revision": snapshot.revision,
            "active_space": snapshot.active_space,
            "decision_id": decision_id,
            "target_ref": target,
            "choice": selected,
            "affected_artifacts": list(affected),
        }
        return DecisionResult(
            decision=decision,
            snapshot=snapshot,
            follow_up_message=follow_up,
            model_context=model_context,
            affected_artifacts=affected,
        )

    def add_material(
        self,
        *,
        expected_revision: int,
        material_type: str,
        value: Any,
        label: str = "",
        filename: str = "",
        mime_type: str = "",
    ) -> DecisionResult:
        """Add one user-supplied material and refresh the shared project revision."""

        kind = material_type.strip()
        if kind not in {"text", "url", "bytes"}:
            raise WorkbenchValidationError(f"Unsupported material type: {kind}")
        with self._locked():
            state = self._checked_state(expected_revision)
            intake = MaterialIntake(self.policy)
            if kind == "text":
                records = (intake.add_text(self.project_root, str(value), label or "补充材料"),)
            elif kind == "url":
                records = (intake.add_url(self.project_root, str(value)),)
            else:
                if not isinstance(value, bytes):
                    raise WorkbenchValidationError("Byte material requires bytes value")
                records = (
                    intake.add_bytes(
                        self.project_root,
                        filename or label or "upload.bin",
                        value,
                        mime_type or "application/octet-stream",
                    ),
                )
            revision = int(state["revision"]) + 1
            operation = {
                "operation": "add-material",
                "material_type": kind,
                "source_ids": [record.source_id for record in records],
                "source_refs": [f"sources/{record.source_id}.json" for record in records],
                "status": "received",
            }
            snapshot = self._complete_write(state, revision, operation)
            self.events.append(
                "workbench.material.added",
                {**operation, "revision": revision},
            )
        return self._operation_result(
            operation,
            snapshot,
            "用户材料已安全写入项目。请先运行 classify-materials，自动提炼用途、事实、案例、冲突和缺口。",
            tuple(operation["source_refs"]),
        )

    def request_agent_action(
        self,
        *,
        expected_revision: int,
        action_type: str,
        target_refs: list[str],
        instructions: str = "",
    ) -> DecisionResult:
        """Persist intent and bounded context before asking Codex to continue."""

        with self._locked():
            state = self._checked_state(expected_revision)
            revision = int(state["revision"]) + 1
            context = ContextCompiler(self.project_root, self.policy).compile(
                action_type=action_type,
                project_revision=revision,
                target_refs=target_refs,
                instructions=instructions,
            )
            task = AgentTaskStore(self.project_root, self.policy).request(
                action_type=action_type,
                target_refs=target_refs,
                instructions=instructions,
                project_revision=revision,
                context_payload=context,
            )
            snapshot = self._complete_write(state, revision, task)
        context_ref = f"context/{task['task_id']}.json"
        follow_up = (
            f"继续 AI PPT Studio 任务 {task['task_id']}：{action_type}。"
            f"项目 revision={revision}，先读取 {context_ref}，严格使用用户提供材料。"
            "视觉构想仅通过 Image 2，PPTX 制作/编辑/渲染/检查仅通过 Codex Presentations；"
            "完成后用 commit_ai_ppt_artifact 回写结构化结果。"
        )
        return self._operation_result(
            task,
            snapshot,
            follow_up,
            tuple(target_refs),
            {"task_id": task["task_id"], "context_ref": context_ref},
        )

    def commit_artifact(
        self,
        *,
        expected_revision: int,
        kind: ArtifactKind,
        payload: dict[str, object],
        task_id: str | None = None,
    ) -> DecisionResult:
        """Commit one validated immutable Agent result and optionally complete its task."""

        with self._locked():
            state = self._checked_state(expected_revision)
            active = AgentTaskStore(self.project_root, self.policy).active()
            if task_id and (not active or active.get("task_id") != task_id):
                raise WorkbenchValidationError(
                    f"Agent task is not active or does not match: {task_id}"
                )
            artifact = ArtifactStore(self.project_root, self.policy).save(kind, payload)
            revision = int(state["revision"]) + 1
            artifact_ref = self._project_ref(artifact.path)
            if task_id:
                AgentTaskStore(self.project_root, self.policy).complete(
                    task_id,
                    artifact_refs=[artifact_ref],
                    result_revision=revision,
                )
            operation = {
                "operation": "commit-artifact",
                "kind": kind.value,
                "version": artifact.version,
                "artifact_ref": artifact_ref,
                "task_id": task_id,
                "status": "committed",
            }
            snapshot = self._complete_write(state, revision, operation)
        return self._operation_result(
            operation,
            snapshot,
            f"{kind.value} v{artifact.version} 已回写项目；请根据最新投影继续当前质量门。",
            (artifact_ref,),
        )

    def confirm_gate(
        self, *, expected_revision: int, gate: Gate
    ) -> DecisionResult:
        """Pass one open gate only after runtime evidence validation."""

        with self._locked():
            state = self._checked_state(expected_revision)
            evidence = GateEvidenceChecker(self.project_root, self.policy).require(gate)
            gate_state = StateStore(self.project_root, self.policy).pass_gate(gate, evidence)
            revision = int(state["revision"]) + 1
            operation = {
                "operation": "confirm-gate",
                "gate": gate.value,
                "status": "passed",
                "evidence_refs": list(evidence),
                "gate_revision": gate_state.revision,
            }
            snapshot = self._complete_write(state, revision, operation)
        return self._operation_result(
            operation,
            snapshot,
            f"用户已确认 {gate.value}，系统已开放下一质量门。请读取最新项目投影继续。",
            evidence,
        )

    def reopen_scope(
        self,
        *,
        expected_revision: int,
        gate: Gate,
        reason: str,
    ) -> DecisionResult:
        """Reopen one gate without deleting downstream artifacts or history."""

        explanation = reason.strip()
        if not explanation:
            raise WorkbenchValidationError("Reopening scope requires a reason")
        with self._locked():
            state = self._checked_state(expected_revision)
            gate_state = StateStore(self.project_root, self.policy).reopen_from(
                gate, explanation
            )
            revision = int(state["revision"]) + 1
            affected = self._gate_affected(gate)
            operation = {
                "operation": "reopen-scope",
                "gate": gate.value,
                "status": "reopened",
                "reason": explanation,
                "affected_artifacts": list(affected),
                "gate_revision": gate_state.revision,
            }
            snapshot = self._complete_write(state, revision, operation)
            self.events.append(
                "workbench.scope.reopened",
                {**operation, "revision": revision},
            )
        return self._operation_result(
            operation,
            snapshot,
            f"{gate.value} 已按用户反馈重新打开，历史成果保留但下游状态已标记受影响。",
            affected,
        )

    def _load_manifest(self) -> ProjectManifest:
        path = self.project_root / "project.json"
        if not path.is_file():
            raise ProjectNotFoundError(f"Managed project not found: {self.project_root}")
        try:
            manifest = ProjectManifest.from_dict(json.loads(path.read_text("utf-8")))
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProjectNotFoundError(f"Managed project manifest is invalid: {path}") from exc
        if Path(manifest.project_root).resolve(strict=False) != self.project_root:
            raise ProjectNotFoundError(f"Managed project manifest root mismatch: {path}")
        return manifest

    def _checked_state(self, expected_revision: int) -> dict[str, Any]:
        if expected_revision < 0:
            raise WorkbenchValidationError("expected_revision cannot be negative")
        self._load_manifest()
        state = self._load_or_initialize_workbench()
        actual_revision = int(state["revision"])
        if expected_revision != actual_revision:
            raise RevisionConflictError(expected_revision, actual_revision)
        return state

    def _complete_write(
        self,
        state: dict[str, Any],
        revision: int,
        operation: dict[str, Any],
    ) -> ProjectSnapshot:
        updated = dict(state)
        updated.update(
            {
                "revision": revision,
                "updated_at": utc_now(),
                "current_decision": {
                    "target_ref": f"operation://{operation.get('operation', 'agent-task')}",
                    "status": "resolved",
                    "choice": operation.get("status", "saved"),
                },
            }
        )
        atomic_write_json(self.workbench_path, updated)
        cognition = self._build_cognition_map()
        cognition["confirmed_decisions"] = self._decision_summaries()
        atomic_write_json(self.cognition_path, cognition)
        return self._snapshot(updated, cognition)

    def _operation_result(
        self,
        operation: dict[str, Any],
        snapshot: ProjectSnapshot,
        follow_up_message: str,
        affected: tuple[str, ...],
        extra_context: dict[str, Any] | None = None,
    ) -> DecisionResult:
        model_context = {
            "project_id": snapshot.project["project_id"],
            "project_root": snapshot.project["project_root"],
            "project_revision": snapshot.revision,
            "active_space": snapshot.active_space,
            **(extra_context or {}),
        }
        return DecisionResult(
            decision=operation,
            snapshot=snapshot,
            follow_up_message=follow_up_message,
            model_context=model_context,
            affected_artifacts=affected,
        )

    def _project_ref(self, value: str) -> str:
        path = Path(value)
        try:
            return path.resolve(strict=False).relative_to(self.project_root).as_posix()
        except ValueError:
            return str(value)

    @staticmethod
    def _gate_affected(gate: Gate) -> tuple[str, ...]:
        ordered = {
            Gate.G0: ("mission", "content-blueprint", "visual", "presentation", "delivery"),
            Gate.G1: ("concept-set", "engineering-samples", "visual-contract", "presentation", "delivery"),
            Gate.G2: ("engineering-samples", "visual-contract", "presentation", "delivery"),
            Gate.G3: ("visual-contract", "slide-scene-graph", "presentation", "delivery"),
            Gate.G4: ("presentation", "delivery"),
        }
        return ordered[gate]

    def _load_or_initialize_workbench(self) -> dict[str, Any]:
        if self.workbench_path.is_file():
            try:
                payload = json.loads(self.workbench_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProjectNotFoundError(
                    f"Workbench state is invalid: {self.workbench_path}"
                ) from exc
            if payload.get("schema_version") != WORKBENCH_SCHEMA_VERSION:
                raise ProjectNotFoundError(
                    f"Unsupported workbench schema: {payload.get('schema_version')}"
                )
            return payload
        created_at = utc_now()
        payload: dict[str, Any] = {
            "schema_version": WORKBENCH_SCHEMA_VERSION,
            "revision": 0,
            "active_space": "overview",
            "updated_at": created_at,
            "last_human_decision_id": None,
            "current_decision": self._default_decision(),
        }
        atomic_write_json(self.workbench_path, payload)
        return payload

    def _build_cognition_map(self) -> dict[str, Any]:
        mission = self._artifact_payload(ArtifactKind.MISSION)
        blueprint = self._artifact_payload(ArtifactKind.CONTENT_BLUEPRINT)
        delivery = self._artifact_payload(ArtifactKind.DELIVERY)
        goal = self._string(mission, "goal") or self._string(blueprint, "goal")
        audience = self._string(mission, "audience") or self._string(
            blueprint, "audience"
        )
        judgment = self._string(blueprint, "narrative_thesis")
        if not judgment and mission:
            judgment = self._string(mission, "decision_start")
        if not judgment:
            judgment = "尚未形成可确认的内容蓝图，AI 将先澄清任务书。"

        uncertainties: list[str] = []
        if not goal:
            uncertainties.append("汇报目标和期望促成的判断尚未确认")
        if not audience:
            uncertainties.append("主要汇报对象尚未确认")
        if not blueprint:
            uncertainties.append("逐页内容蓝图尚未形成")
        if not uncertainties and not delivery:
            uncertainties.append("当前成果仍需继续通过后续质量门")

        return {
            "delivery_goal": goal or "尚未确认交付目标",
            "audiences": [audience] if audience else [],
            "problem": self._string(mission, "context")
            or "需要先建立汇报任务书，再组织解决方案内容。",
            "ai_judgment": judgment,
            "facts": self._material_summary(),
            "confirmed_decisions": self._decision_summaries(),
            "uncertainty": "；".join(uncertainties) if uncertainties else "当前无阻断性不确定项",
            "affected_artifacts": sorted(self._artifact_summaries()),
            "outcome_status": "已形成可交付成果" if delivery else "成果正在形成中",
            "dialogue_focus": uncertainties[0] if uncertainties else "确认当前成果是否需要继续修改",
        }

    def _snapshot(
        self, state: dict[str, Any], cognition: dict[str, Any]
    ) -> ProjectSnapshot:
        manifest = self._load_manifest()
        gate = StateStore(self.project_root, self.policy).load()
        current_decision = dict(state.get("current_decision") or {})
        if current_decision.get("status") == "resolved":
            current_decision = self._default_decision()
        return ProjectSnapshot(
            schema_version=WORKBENCH_SCHEMA_VERSION,
            revision=int(state["revision"]),
            updated_at=str(state["updated_at"]),
            active_space=str(state.get("active_space", "overview")),
            project=manifest.as_dict(),
            gate_state=gate.as_dict(),
            cognition_map=cognition,
            artifacts=self._artifact_summaries(),
            space_projections=SpaceProjectionBuilder(
                self.project_root, self.policy
            ).build(),
            current_decision=current_decision,
            last_human_decision_id=(
                str(state["last_human_decision_id"])
                if state.get("last_human_decision_id")
                else None
            ),
            allowed_next_actions=(
                "submit-human-decision",
                "continue-in-codex",
                "request-fullscreen",
                "refresh-snapshot",
            ),
        )

    def _default_decision(self) -> dict[str, Any]:
        mission = self._artifact_payload(ArtifactKind.MISSION)
        delivery = self._artifact_payload(ArtifactKind.DELIVERY)
        if not mission:
            return {
                "target_ref": "mission://goal",
                "status": "needs-user",
                "question": "这份 PPT 要给谁看，并希望促成什么判断或行动？",
                "why_now": "任务目标决定后续材料提炼、内容叙事和视觉方向。",
                "options": ["在 Codex 中补充任务", "暂存为草稿"],
                "recommended_choice": "在 Codex 中补充任务",
                "reversible": True,
            }
        if delivery:
            return {
                "target_ref": "delivery://current",
                "status": "available",
                "question": "当前交付是否需要继续修改？",
                "why_now": "当前项目已形成交付成果，可以接受、提出修改或暂不处理。",
                "options": ["接受当前成果", "提出修改", "暂不处理"],
                "recommended_choice": "接受当前成果",
                "reversible": True,
            }
        return {
            "target_ref": "project://next-focus",
            "status": "available",
            "question": "是否按 AI 当前判断继续推进？",
            "why_now": "继续前需要确认当前主线没有偏离汇报目标。",
            "options": ["继续推进", "提出修改", "暂不处理"],
            "recommended_choice": "继续推进",
            "reversible": True,
        }

    def _artifact_payload(self, kind: ArtifactKind) -> dict[str, Any] | None:
        try:
            return ArtifactStore(self.project_root, self.policy).latest(kind).payload
        except ProjectNotFoundError:
            return None

    def _artifact_summaries(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for kind, artifact in ArtifactStore(
            self.project_root, self.policy
        ).list_latest().items():
            result[kind] = {
                "kind": artifact.kind,
                "version": artifact.version,
                "path": artifact.path,
                "sha256": artifact.sha256,
                "created_at": artifact.created_at,
            }
        return result

    def _material_summary(self) -> list[dict[str, Any]]:
        sources = sorted((self.project_root / "sources").glob("*.json"))
        return [
            {
                "summary": f"用户已提供 {len(sources)} 份可追溯材料",
                "source_count": len(sources),
                "source": "project://sources",
            }
        ]

    def _decision_summaries(self) -> list[dict[str, Any]]:
        if not self.decisions_path.is_file():
            return []
        result: list[dict[str, Any]] = []
        for line in self.decisions_path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            result.append(
                {
                    "decision_id": item.get("decision_id"),
                    "target_ref": item.get("target_ref"),
                    "choice": item.get("choice"),
                    "feedback": item.get("feedback"),
                    "created_at": item.get("created_at"),
                }
            )
        return result[-5:]

    @staticmethod
    def _string(payload: dict[str, Any] | None, key: str) -> str:
        if not payload:
            return ""
        value = payload.get(key)
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _affected_artifacts(target_ref: str) -> tuple[str, ...]:
        if target_ref.startswith("mission://"):
            return ("mission", "content-blueprint", "visual-brief", "presentation")
        if target_ref.startswith("delivery://"):
            return ("delivery",)
        return ("project",)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
