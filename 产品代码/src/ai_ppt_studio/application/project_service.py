"""Managed schema 3 project discovery and creation."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ProjectNotFoundError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.application.content_action_policy import (
    BATCH_APPLY_ACTIONS,
    BATCH_PLAN_ACTIONS,
    CONTENT_ACTIONS,
    FRAMEWORK_ACTIONS,
    FULL_DECK_CONTENT_ACTIONS,
    CONTENT_ACTION_CONTRACTS,
    validate_content_action_targets,
)


SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

ACTION_ROLES = {
    "build-content-framework": "presales-content-strategist",
    "build-presales-strategy": "presales-content-strategist",
    "build-claim-evidence-map": "claim-evidence-analyst",
    "build-deck-argument-map": "deck-narrative-architect",
    "build-slide-draft-set": "slide-copywriter",
    "repair-content": "content-repair-specialist",
    "review-content-presales": "presales-content-reviewer",
    "review-content-decision-maker": "audience-decision-reviewer",
    "review-content-evidence": "content-fact-checker",
    "review-content-narrative": "argument-logic-reviewer",
    "review-content-editorial": "reading-experience-reviewer",
    "aggregate-content-reviews": "deck-coherence-editor",
    "expand-full-content-blueprint": "deck-narrative-architect",
    "propose-content-batch-revision-plan": "deck-coherence-editor",
    "apply-content-batch-revision": "content-repair-specialist",
    "design-deck-system": "deck-designer",
    "design-slide-visuals": "slide-visual-designer",
    "build-native-first": "native-first-engineer",
    "generate-image-assets": "image-asset-producer",
    "review-visual-aesthetic": "visual-aesthetic-reviewer",
    "review-visual-engineering": "visual-engineering-reviewer",
    "verify-target-render": "target-render-verifier",
    "govern-feedback": "feedback-governance-analyst",
    "curate-experience": "experience-curator",
    "evaluate-experience": "experience-evaluator",
    "coordinate-delivery": "delivery-coordinator",
}

def _normalize_project_id(value: str) -> str:
    identity = unicodedata.normalize("NFC", value.strip())
    if (
        not 1 <= len(identity) <= 96
        or not identity[0].isalnum()
        or any(not (character.isalnum() or character in "._-") for character in identity)
    ):
        raise ContractValidationError(
            "Project ID must use 1-96 Unicode letters/digits, dot, underscore, or dash"
        )
    return identity


class ProjectService:
    """Resolve only managed schema 3 projects below one runtime root."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.policy = PathPolicy(config)
        self.projects_root = self.policy.assert_write_allowed(
            config.runtime_root / "projects"
        )

    def create_project(
        self, name: str, *, project_id: str = ""
    ) -> ProjectKernel:
        display_name = name.strip()
        identity = _normalize_project_id(
            project_id or f"project-{uuid.uuid4().hex[:12]}"
        )
        if not display_name:
            raise ContractValidationError("Project name cannot be empty")
        root = self.policy.assert_write_allowed(self.projects_root / identity)
        if root.exists():
            raise ContractValidationError(f"Project already exists: {identity}")
        root.mkdir(parents=True)
        kernel = ProjectKernel.initialize(root, project_id=identity)
        kernel.commit(
            command_id=f"project:create:{identity}",
            expected_revision=0,
            event_type="project.created",
            artifact_updates={
                "project/manifest": (
                    "project-manifest",
                    {
                        "project_id": identity,
                        "name": display_name,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "scenario_pack": "reading-first-presales",
                    },
                )
            },
        )
        return kernel

    def list_projects(self) -> list[dict[str, Any]]:
        if not self.projects_root.is_dir():
            return []
        rows: list[tuple[int, dict[str, Any]]] = []
        for root in self.projects_root.iterdir():
            if root.is_symlink() or not root.is_dir():
                continue
            state_path = root / "kernel" / "state.json"
            try:
                raw = json.loads(state_path.read_text(encoding="utf-8"))
                if str(raw.get("schema_version")) != "3.0":
                    continue
                project_id = str(raw["project_id"])
                kernel = ProjectKernel(root, project_id=project_id)
                state = kernel.load()
                name = self._project_name(kernel, state.artifact_heads)
                modified = state_path.stat().st_mtime_ns
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            rows.append(
                (
                    modified,
                    {
                        "project_id": project_id,
                        "name": name,
                        "project_root": str(root.resolve()),
                        "schema_version": "3.0",
                        "revision": state.revision,
                    },
                )
            )
        rows.sort(key=lambda item: (item[0], item[1]["project_id"]), reverse=True)
        return [row for _modified, row in rows]

    def latest_project(self) -> Path:
        projects = self.list_projects()
        if not projects:
            raise ProjectNotFoundError("No managed schema 3 AI PPT project is available")
        return Path(str(projects[0]["project_root"]))

    def resolve_project(self, project_root: Path | None = None) -> Path:
        if project_root is None:
            candidate = self.latest_project()
        else:
            requested = project_root.expanduser()
            if requested.is_symlink():
                raise ProjectNotFoundError(
                    f"Project cannot be a symlink: {requested}"
                )
            candidate = requested.resolve()
        try:
            candidate.relative_to(self.projects_root)
        except ValueError as exc:
            raise ProjectNotFoundError(
                f"Project is outside the managed schema 3 workspace: {candidate}"
            ) from exc
        state_path = candidate / "kernel" / "state.json"
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectNotFoundError(
                f"Schema 3 project state is missing: {candidate}"
            ) from exc
        if str(state.get("schema_version")) != "3.0":
            raise ProjectNotFoundError(
                f"Project is not a schema 3 project: {candidate}"
            )
        return candidate

    @staticmethod
    def _project_name(
        kernel: ProjectKernel, heads: dict[str, str]
    ) -> str:
        value = heads.get("project/manifest")
        if value:
            try:
                payload = kernel.artifacts.resolve(
                    ArtifactReference.parse(value)
                )["payload"]
                name = str(payload.get("name") or "").strip()
                if name:
                    return name
            except (KeyError, TypeError, ValueError):
                pass
        return kernel.project_id


class ProjectCommandService:
    """Formal schema 3 commands that belong to the project boundary."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def add_material(
        self,
        command_id: str,
        expected_revision: int,
        *,
        material_type: str,
        value: str,
        data_base64: str,
        label: str,
        filename: str,
        mime_type: str,
    ) -> tuple[str, KernelState]:
        from ai_ppt_studio.application.content_service import ContentService

        kind = material_type.strip()
        if kind not in {"text", "url", "bytes"}:
            raise ContractValidationError(
                "material_type must be text, url, or bytes"
            )
        if kind == "bytes":
            try:
                raw = base64.b64decode(data_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ContractValidationError("data_base64 is invalid") from exc
            if not raw:
                raise ContractValidationError("Byte material cannot be empty")
            source_kind = "file"
        else:
            clean = value.strip()
            if not clean:
                raise ContractValidationError(
                    f"{kind} material cannot be empty"
                )
            raw = clean.encode("utf-8")
            source_kind = kind
        digest = hashlib.sha256(raw).hexdigest()
        source_id = f"source-{digest[:16]}"
        if kind == "url":
            locator = value.strip()
            project_copy = ""
        elif kind == "text":
            locator = f"inline://user-provided/{source_id}"
            project_copy = ""
        else:
            clean_name = SAFE_FILENAME.sub("-", Path(filename).name).strip("-.")
            clean_name = clean_name or f"material-{digest[:12]}.bin"
            relative = Path("materials") / "files" / f"{digest[:12]}-{clean_name}"
            target = (self.kernel.project_root / relative).resolve()
            try:
                target.relative_to(self.kernel.project_root)
            except ValueError as exc:
                raise ContractValidationError(
                    "Material copy escaped the project root"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                staged = target.with_name(f".{target.name}.stage-{os.getpid()}")
                try:
                    staged.write_bytes(raw)
                    os.replace(staged, target)
                finally:
                    if staged.exists():
                        staged.unlink()
            locator = f"project://{relative.as_posix()}"
            project_copy = relative.as_posix()

        state = self.kernel.load()
        sources: list[dict[str, Any]] = []
        current = state.artifact_heads.get("materials")
        if current:
            envelope = self.kernel.artifacts.resolve(
                ArtifactReference.parse(current)
            )
            sources = [dict(item) for item in envelope["payload"]["sources"]]
        if not any(item.get("source_id") == source_id for item in sources):
            sources.append(
                {
                    "source_id": source_id,
                    "origin": "user-provided",
                    "kind": source_kind,
                    "locator": locator,
                    "sha256": digest,
                    "label": label.strip() or "用户提供材料",
                    **({"project_copy": project_copy} if project_copy else {}),
                    **({"mime_type": mime_type.strip()} if mime_type.strip() else {}),
                }
            )
        reference = ContentService(self.kernel).register_materials(
            command_id,
            expected_revision,
            {"sources": sources},
        )
        return reference, self.kernel.load()

    def request_agent_action(
        self,
        command_id: str,
        expected_revision: int,
        *,
        action_type: str,
        target_refs: list[str],
        instructions: str,
    ) -> tuple[str, dict[str, Any], KernelState]:
        action = action_type.strip()
        role_id = ACTION_ROLES.get(action)
        if role_id is None:
            raise ContractValidationError(
                f"Unsupported schema 3 Agent action: {action}"
            )
        if not target_refs:
            raise ContractValidationError("Agent task requires target_refs")
        content_contract = CONTENT_ACTION_CONTRACTS.get(action)
        if content_contract is not None and role_id != content_contract.role_id:
            raise ContractValidationError(
                "Content action role registry conflicts with the action policy"
            )
        if action in FRAMEWORK_ACTIONS:
            from ai_ppt_studio.application.mission_readiness import (
                MissionReadinessPolicy,
            )

            MissionReadinessPolicy(self.kernel).require_ready()
            validate_content_action_targets(
                action, target_refs, self.kernel.load().artifact_heads
            )
        elif action in CONTENT_ACTIONS:
            from ai_ppt_studio.application.mission_readiness import (
                MissionReadinessPolicy,
            )
            from ai_ppt_studio.application.content_service import (
                require_full_deck_expansion_authorization,
            )

            MissionReadinessPolicy(self.kernel).require_ready()
            require_full_deck_expansion_authorization(self.kernel)
            validate_content_action_targets(
                action, target_refs, self.kernel.load().artifact_heads
            )
        for value in target_refs:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        from ai_ppt_studio.context_compiler import ContextCompiler

        task_id = hashlib.sha256(command_id.encode("utf-8")).hexdigest()
        context = ContextCompiler(self.kernel).compile_role_task(
            role_id=role_id,
            task_type=action,
            project_revision=expected_revision,
            target_refs=target_refs,
            instructions=instructions,
        )
        context_ref = str(
            self.kernel.artifacts.reference_for("context-pack", context)
        )
        task = {
            "task_id": task_id,
            "action_type": action,
            "role_id": role_id,
            "target_refs": list(target_refs),
            "instructions": instructions.strip(),
            "input_revision": expected_revision,
            "context_pack_ref": context_ref,
            "status": "queued",
            "progress": {"stage": "queued", "done": 0, "total": 1},
            "result_refs": [],
            "error": None,
            "retry_count": 0,
        }
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="agent.task-requested",
            artifact_updates={
                f"agent/context/{task_id}": ("context-pack", context),
                "agent/task/active": ("agent-task", task),
                f"agent/task/{task_id}": ("agent-task", task),
            },
        )
        return state.artifact_heads["agent/task/active"], task, state

    def require_active_agent_task(self, task_id: str) -> dict[str, Any]:
        """Resolve one exact active task before accepting its result."""

        identity = task_id.strip()
        if not identity:
            raise ContractValidationError("Agent task ID cannot be empty")
        state = self.kernel.load()
        task_ref = state.artifact_heads.get("agent/task/active", "")
        if not task_ref:
            raise ContractValidationError("No active Agent task is available")
        reference = ArtifactReference.parse(task_ref)
        if reference.kind != "agent-task":
            raise ContractValidationError("Active Agent task reference has the wrong kind")
        task = self.kernel.artifacts.resolve(reference)["payload"]
        if task.get("task_id") != identity:
            raise ContractValidationError(
                "Artifact result task_id must match the active Agent task"
            )
        return dict(task)

    def preflight_content_agent_result(
        self,
        *,
        task_id: str,
        expected_action: str,
        expected_revision: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate task, context, targets, and lineage before result writes."""

        from ai_ppt_studio.application.content_service import (
            require_full_deck_expansion_authorization,
        )
        from ai_ppt_studio.errors import ContentWorkflowError

        state = self.kernel.load()
        task = self.require_active_agent_task(task_id)
        try:
            if state.revision != expected_revision:
                raise ValueError("result revision is stale")
            if task.get("status") != "queued":
                raise ValueError("Agent task is not active")
            if task.get("action_type") != expected_action:
                raise ValueError("Agent task action does not match result")
            input_revision = task.get("input_revision")
            if isinstance(input_revision, bool) or not isinstance(input_revision, int):
                raise ValueError("Agent task input revision is invalid")
            context_ref = str(task.get("context_pack_ref") or "")
            context_reference = ArtifactReference.parse(context_ref)
            if context_reference.kind != "context-pack":
                raise ValueError("Agent ContextPack kind is invalid")
            exact_context_ref = state.artifact_heads.get(
                f"agent/context/{task_id}", ""
            )
            if exact_context_ref != context_ref:
                raise ValueError("Agent ContextPack is not the exact task context")
            context = dict(
                self.kernel.artifacts.resolve(context_reference)["payload"]
            )
            if (
                context.get("project_id") != state.project_id
                or context.get("project_revision") != input_revision
                or context.get("layers", {}).get("task_contract", {}).get(
                    "task_type"
                )
                != expected_action
                or context.get("layers", {}).get("task_contract", {}).get(
                    "target_refs"
                )
                != task.get("target_refs")
                or context.get("artifact_version_refs") != task.get("target_refs")
            ):
                raise ValueError("Agent ContextPack task contract is invalid")
            lineage = require_full_deck_expansion_authorization(self.kernel)
            workflow = context.get("layers", {}).get("content_workflow")
            if not isinstance(workflow, dict) or any(
                workflow.get(field) != value
                for field, value in lineage.items()
            ):
                raise ValueError("Agent ContextPack framework lineage is stale")
            validate_content_action_targets(
                expected_action,
                list(task.get("target_refs") or []),
                state.artifact_heads,
            )
        except (
            ArtifactReferenceError,
            KeyError,
            TypeError,
            ValueError,
            ContentWorkflowError,
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Agent result provenance is stale or inconsistent",
                {
                    "task_id": task_id,
                    "expected_action": expected_action,
                    "revision": state.revision,
                },
            ) from None
        return task, context

    def complete_agent_task(
        self,
        command_id: str,
        expected_revision: int,
        *,
        task_id: str,
        result_ref: str,
    ) -> KernelState:
        """Bind a validated immutable result and complete the active task."""

        task = self.require_active_agent_task(task_id)
        self.kernel.artifacts.resolve(ArtifactReference.parse(result_ref))
        result_refs = list(task.get("result_refs") or [])
        if result_ref not in result_refs:
            result_refs.append(result_ref)
        completed = {
            **task,
            "status": "completed",
            "progress": {"stage": "completed", "done": 1, "total": 1},
            "result_refs": result_refs,
            "error": None,
        }
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="agent.task-completed",
            artifact_updates={
                "agent/task/active": ("agent-task", completed),
                f"agent/task/{task_id}": ("agent-task", completed),
            },
        )

    def submit_human_decision(
        self,
        command_id: str,
        expected_revision: int,
        *,
        target_ref: str,
        choice: str,
        feedback: str,
    ) -> tuple[str, str, KernelState]:
        self.kernel.artifacts.resolve(ArtifactReference.parse(target_ref))
        selected = choice.strip()
        if not selected:
            raise ContractValidationError("Human decision choice cannot be empty")
        decision = {
            "target_ref": target_ref,
            "choice": selected,
            "feedback": feedback.strip(),
            "input_revision": expected_revision,
        }
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="human.decision-recorded",
            artifact_updates={
                "human/decision/latest": ("human-decision", decision)
            },
        )
        follow_up = f"已记录“{selected}”，Codex 将按当前决定继续推进。"
        return state.artifact_heads["human/decision/latest"], follow_up, state
