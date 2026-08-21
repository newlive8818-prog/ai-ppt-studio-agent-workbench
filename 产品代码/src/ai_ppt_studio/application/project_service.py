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
from dataclasses import dataclass, replace
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
from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.kernel.artifacts import canonical_json
from ai_ppt_studio.application.content_action_policy import (
    BATCH_APPLY_ACTIONS,
    BATCH_PLAN_ACTIONS,
    CONTENT_ACTIONS,
    FRAMEWORK_ACTIONS,
    FULL_DECK_CONTENT_ACTIONS,
    CONTENT_ACTION_CONTRACTS,
    CONTENT_ACTION_ROLES,
    CONTENT_RESULT_CONTRACTS,
    validate_content_action_targets,
)


SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

ACTION_ROLES = {
    **CONTENT_ACTION_ROLES,
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

NONCONTENT_RESULT_CONTRACTS = {
    "design-deck-system": frozenset({
        ("visual-brief", ""),
        ("visual-contract", "deck-design-system"),
    }),
    "design-slide-visuals": frozenset({
        ("concept-set", ""),
        ("visual-contract", "visual-contract-set"),
    }),
    "build-native-first": frozenset({
        ("native-anchor-set", ""),
    }),
    "generate-image-assets": frozenset({
        ("visual-contract", "image-asset-pack"),
    }),
    "review-visual-aesthetic": frozenset({
        ("visual-contract", "visual-review-record"),
    }),
    "review-visual-engineering": frozenset({
        ("visual-contract", "visual-review-record"),
    }),
    "verify-target-render": frozenset({("target-render-evidence", "")}),
    "govern-feedback": frozenset({("feedback", "feedback-governance-record")}),
    "curate-experience": frozenset({
        ("experience", "experience-candidate"),
        ("experience", "qualified-experience-selection"),
        ("experience", "experience-application"),
    }),
    "evaluate-experience": frozenset({
        ("experience", "experience-application-evaluation"),
        ("experience", "experience-evolution-decision"),
    }),
    "coordinate-delivery": frozenset({
        ("delivery", "delivery-package"),
        ("target-render-evidence", ""),
    }),
}

VISUAL_ACTIONS = frozenset(
    {
        "design-deck-system",
        "design-slide-visuals",
        "build-native-first",
        "generate-image-assets",
        "review-visual-aesthetic",
        "review-visual-engineering",
        "verify-target-render",
    }
)


@dataclass(frozen=True)
class PreparedArtifactTransaction:
    """A fully validated service transaction that has not written anything."""

    event_type: str
    artifact_updates: dict[str, tuple[str, dict[str, Any]]]
    artifact_removals: tuple[str, ...] = ()
    gate_mutation: object | None = None
    result_ref: str = ""


class _ReadOnlyPreparationArtifacts:
    """Allow validation and deterministic references, but forbid object writes."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def resolve(self, reference: ArtifactReference) -> dict[str, Any]:
        return self._repository.resolve(reference)

    def reference_for(
        self, kind: str, payload: dict[str, Any]
    ) -> ArtifactReference:
        return self._repository.reference_for(kind, payload)

    def put(self, kind: str, payload: dict[str, Any]) -> ArtifactReference:
        raise ContractValidationError(
            "Prepared Agent results cannot persist objects before atomic commit"
        )


class _PreparationKernel:
    """Capture one existing service commit as a side-effect-free transaction."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self._kernel = kernel
        self.project_id = kernel.project_id
        self.artifacts = _ReadOnlyPreparationArtifacts(kernel.artifacts)
        self.prepared: PreparedArtifactTransaction | None = None

    def load(self) -> KernelState:
        return self._kernel.load()

    def commit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        artifact_removals: tuple[str, ...] = (),
        confirmation_consumptions: tuple[object, ...] = (),
        content_framework_reset: object | None = None,
        gate_mutation: object | None = None,
        command_fingerprint: str = "",
    ) -> KernelState:
        state = self.load()
        if state.revision != expected_revision:
            from ai_ppt_studio.errors import RevisionConflictError

            raise RevisionConflictError(expected_revision, state.revision)
        if self.prepared is not None:
            raise ContractValidationError(
                "A prepared Agent result must contain exactly one service transaction"
            )
        if confirmation_consumptions or content_framework_reset is not None:
            raise ContractValidationError(
                "Non-content Agent results cannot consume content confirmations"
            )
        if set(artifact_updates).intersection(artifact_removals):
            raise ContractValidationError(
                "Prepared transaction cannot update and remove the same head"
            )
        prepared = PreparedArtifactTransaction(
            event_type=event_type,
            artifact_updates={
                slot: (kind, dict(payload))
                for slot, (kind, payload) in artifact_updates.items()
            },
            artifact_removals=tuple(artifact_removals),
            gate_mutation=gate_mutation,
        )
        self.prepared = prepared
        heads = dict(state.artifact_heads)
        for slot in artifact_removals:
            heads.pop(slot, None)
        for slot, (kind, payload) in artifact_updates.items():
            heads[slot] = str(self.artifacts.reference_for(kind, payload))
        gate_status = dict(state.gate_status)
        if gate_mutation is not None:
            from ai_ppt_studio.kernel.gates import validate_gate_mutation

            gate_status.update(validate_gate_mutation(gate_mutation).updates)
        return replace(
            state,
            revision=state.revision + 1,
            artifact_heads=heads,
            gate_status=gate_status,
        )

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
                ),
                "release/target-policy": (
                    "release-target-policy",
                    ReleaseTargetPolicy.from_payload(
                        CURRENT_RELEASE_TARGET_POLICY
                    ).as_payload(),
                ),
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
        if action in VISUAL_ACTIONS:
            from ai_ppt_studio.application.visual_service import VisualService

            VisualService(self.kernel).require_visual_production_open()
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
        exact_ref = state.artifact_heads.get(f"agent/task/{identity}", "")
        if exact_ref != task_ref:
            raise ContractValidationError(
                "Artifact result task_id must match the active Agent task"
            )
        return self.resolve_agent_task(identity)

    def resolve_agent_task(self, task_id: str) -> dict[str, Any]:
        """Resolve an immutable exact task receipt without requiring it is active."""

        identity = task_id.strip()
        if not identity:
            raise ContractValidationError("Agent task ID cannot be empty")
        task_ref = self.kernel.load().artifact_heads.get(
            f"agent/task/{identity}", ""
        )
        if not task_ref:
            raise ContractValidationError("Exact Agent task receipt is unavailable")
        reference = ArtifactReference.parse(task_ref)
        if reference.kind != "agent-task":
            raise ContractValidationError("Agent task reference has the wrong kind")
        task = self.kernel.artifacts.resolve(reference)["payload"]
        if task.get("task_id") != identity:
            raise ContractValidationError("Agent task receipt identity is invalid")
        return dict(task)

    def preflight_content_agent_result(
        self,
        *,
        task_id: str,
        request_kind: str,
        payload: dict[str, Any],
        expected_revision: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate task, context, targets, and lineage before result writes."""

        from ai_ppt_studio.application.content_service import (
            require_full_deck_expansion_authorization,
        )
        from ai_ppt_studio.errors import ContentWorkflowError

        state = self.kernel.load()
        task = self.require_active_agent_task(task_id)
        expected_action = str(task.get("action_type") or "")
        try:
            if state.revision != expected_revision:
                raise ValueError("result revision is stale")
            if task.get("status") != "queued":
                raise ValueError("Agent task is not active")
            result_contract = CONTENT_RESULT_CONTRACTS.get(expected_action)
            if result_contract is None:
                raise ValueError("Agent task does not allow a formal content result")
            if (
                request_kind != result_contract.request_kind
                or payload.get("artifact_type") != result_contract.artifact_type
                or (
                    result_contract.reviewer_role
                    and payload.get("reviewer_role")
                    != result_contract.reviewer_role
                )
            ):
                raise ValueError("Agent result does not match its task contract")
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

    def replay_content_agent_result(
        self,
        *,
        command_id: str,
        task_id: str,
        request_kind: str,
        payload: dict[str, Any],
        expected_revision: int,
    ) -> tuple[str, KernelState] | None:
        """Return an exact completed result replay or reject command collision."""

        from ai_ppt_studio.application.content_action_policy import (
            CONTENT_RESULT_CONTRACTS,
        )
        from ai_ppt_studio.errors import ContentWorkflowError

        state = self.kernel.load()
        revision = state.processed_commands.get(command_id)
        if revision is None:
            return None
        task_ref = state.artifact_heads.get(f"agent/task/{task_id}", "")
        try:
            task_reference = ArtifactReference.parse(task_ref)
            task = self.kernel.artifacts.resolve(task_reference)["payload"]
            action = str(task.get("action_type") or "")
            contract = CONTENT_RESULT_CONTRACTS[action]
            completion = task.get("completion_result")
            request_fingerprint = hashlib.sha256(
                canonical_json({
                    "request_kind": request_kind,
                    "payload": payload,
                    "expected_revision": expected_revision,
                })
            ).hexdigest()
            event = json.loads(
                (
                    self.kernel.events_root / f"r{revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            context_ref = str(task.get("context_pack_ref") or "")
            context_reference = ArtifactReference.parse(context_ref)
            context = self.kernel.artifacts.resolve(context_reference)["payload"]
            if (
                task_reference.kind != "agent-task"
                or task.get("task_id") != task_id
                or task.get("status") != "completed"
                or task.get("completion_command_id") != command_id
                or request_kind != contract.request_kind
                or payload.get("artifact_type") != contract.artifact_type
                or not isinstance(completion, dict)
                or completion.get("action_type") != action
                or completion.get("artifact_slot") != contract.artifact_slot
                or completion.get("artifact_kind") != contract.artifact_kind
                or completion.get("request_fingerprint")
                != request_fingerprint
                or event.get("command_id") != command_id
                or event.get("command_fingerprint") != request_fingerprint
                or event.get("revision") != revision
                or event.get("artifact_heads", {}).get(contract.artifact_slot)
                != completion.get("result_ref")
                or event.get("artifact_heads", {}).get(
                    f"agent/task/{task_id}"
                ) != task_ref
                or context_reference.kind != "context-pack"
                or state.artifact_heads.get(f"agent/context/{task_id}")
                != context_ref
                or context.get("project_id") != state.project_id
                or context.get("project_revision") != task.get("input_revision")
                or context.get("artifact_version_refs") != task.get("target_refs")
                or context.get("layers", {}).get("role_contract", {}).get(
                    "role_id"
                ) != task.get("role_id")
                or context.get("layers", {}).get("task_contract", {}).get(
                    "task_type"
                ) != action
                or context.get("layers", {}).get("task_contract", {}).get(
                    "target_refs"
                ) != task.get("target_refs")
                or (
                    contract.reviewer_role
                    and payload.get("reviewer_role") != contract.reviewer_role
                )
            ):
                raise ValueError("Processed command does not match completed task")
            result_ref = str(completion.get("result_ref") or "")
            result_reference = ArtifactReference.parse(result_ref)
            self.kernel.artifacts.resolve(result_reference)
            if (
                result_reference.kind != contract.artifact_kind
            ):
                raise ValueError("Processed command result payload differs")
            return result_ref, state
        except (
            ArtifactReferenceError,
            KeyError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Processed content result command has different semantics",
                {"command_id": command_id, "task_id": task_id, "revision": revision},
            ) from None

    @staticmethod
    def _result_request_fingerprint(
        request_kind: str,
        payload: dict[str, Any],
        expected_revision: int,
    ) -> str:
        return hashlib.sha256(
            canonical_json({
                "request_kind": request_kind,
                "payload": payload,
                "expected_revision": expected_revision,
            })
        ).hexdigest()

    def replay_noncontent_agent_result(
        self,
        *,
        command_id: str,
        task_id: str,
        request_kind: str,
        payload: dict[str, Any],
        expected_revision: int,
    ) -> tuple[str, KernelState] | None:
        """Return an exact generic result replay or reject command collision."""

        state = self.kernel.load()
        if command_id not in state.processed_commands:
            return None
        task = self.resolve_agent_task(task_id)
        completion = task.get("completion_result")
        fingerprint = self._result_request_fingerprint(
            request_kind, payload, expected_revision
        )
        try:
            completion_dict = completion if isinstance(completion, dict) else {}
            result_ref = str(completion_dict.get("result_ref") or "")
            result_reference = ArtifactReference.parse(result_ref)
            artifact_slot = str(completion_dict.get("artifact_slot") or "")
            processed_revision = state.processed_commands[command_id]
            event = json.loads(
                (
                    self.kernel.events_root
                    / f"r{processed_revision:08d}.json"
                ).read_text(encoding="utf-8")
            )
            exact_task_ref = state.artifact_heads.get(
                f"agent/task/{task_id}", ""
            )
            context_ref = str(task.get("context_pack_ref") or "")
            context_reference = ArtifactReference.parse(context_ref)
            context = self.kernel.artifacts.resolve(context_reference)["payload"]
            if (
                task.get("status") != "completed"
                or task.get("completion_command_id") != command_id
                or not isinstance(completion, dict)
                or completion.get("action_type") != task.get("action_type")
                or completion.get("artifact_kind") != result_reference.kind
                or completion.get("request_fingerprint") != fingerprint
                or event.get("command_id") != command_id
                or event.get("command_fingerprint") != fingerprint
                or event.get("revision") != processed_revision
                or event.get("artifact_heads", {}).get(artifact_slot)
                != result_ref
                or event.get("artifact_heads", {}).get(
                    f"agent/task/{task_id}"
                ) != exact_task_ref
                or context_reference.kind != "context-pack"
                or state.artifact_heads.get(f"agent/context/{task_id}")
                != context_ref
                or context.get("project_id") != state.project_id
                or context.get("project_revision") != task.get("input_revision")
                or context.get("artifact_version_refs") != task.get("target_refs")
                or context.get("layers", {}).get("role_contract", {}).get(
                    "role_id"
                ) != task.get("role_id")
                or context.get("layers", {}).get("task_contract", {}).get(
                    "task_type"
                ) != task.get("action_type")
                or context.get("layers", {}).get("task_contract", {}).get(
                    "target_refs"
                ) != task.get("target_refs")
            ):
                raise ValueError("Processed command has different semantics")
            self.kernel.artifacts.resolve(result_reference)
            if task.get("result_refs") != [result_ref]:
                raise ValueError("Completed task result binding differs")
            return result_ref, state
        except (
            ArtifactReferenceError,
            KeyError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            raise ContractValidationError(
                "Processed Agent result command has different semantics"
            ) from None

    def validate_noncontent_agent_result_kind(
        self,
        task: dict[str, Any],
        request_kind: str,
        payload: dict[str, Any],
    ) -> None:
        action = str(task.get("action_type") or "")
        allowed = NONCONTENT_RESULT_CONTRACTS.get(action, frozenset())
        discriminator = str(payload.get("artifact_type") or "")
        if (request_kind, discriminator) not in allowed:
            raise ContractValidationError(
                "Agent result kind or artifact_type does not match its task action"
            )
        reviewer_contracts = {
            "review-visual-aesthetic": (
                "aesthetic", "visual-aesthetic-reviewer"
            ),
            "review-visual-engineering": (
                "engineering", "visual-engineering-reviewer"
            ),
        }
        reviewer_contract = reviewer_contracts.get(action)
        if reviewer_contract is not None and (
            str(payload.get("reviewer_kind") or "") != reviewer_contract[0]
            or str(payload.get("reviewer_role") or "") != reviewer_contract[1]
        ):
            raise ContractValidationError(
                "Visual review result does not match its reviewer task identity"
            )

    def preflight_noncontent_agent_result(
        self,
        *,
        task_id: str,
        request_kind: str,
        payload: dict[str, Any],
        expected_revision: int,
    ) -> dict[str, Any]:
        """Validate exact queued task and immutable ContextPack provenance."""

        state = self.kernel.load()
        task = self.require_active_agent_task(task_id)
        try:
            if state.revision != expected_revision or task.get("status") != "queued":
                raise ValueError("Agent task is not current and queued")
            action = str(task.get("action_type") or "")
            if action not in NONCONTENT_RESULT_CONTRACTS:
                raise ValueError("Agent task has no non-content result contract")
            if task.get("role_id") != ACTION_ROLES.get(action):
                raise ValueError("Agent task role does not match its action")
            input_revision = task.get("input_revision")
            if isinstance(input_revision, bool) or not isinstance(input_revision, int):
                raise ValueError("Agent task input revision is invalid")
            context_ref = str(task.get("context_pack_ref") or "")
            context_reference = ArtifactReference.parse(context_ref)
            if context_reference.kind != "context-pack":
                raise ValueError("Agent ContextPack kind is invalid")
            if state.artifact_heads.get(f"agent/context/{task_id}") != context_ref:
                raise ValueError("Agent ContextPack is not the exact task context")
            context = self.kernel.artifacts.resolve(context_reference)["payload"]
            layers = context.get("layers", {})
            if (
                context.get("project_id") != state.project_id
                or context.get("project_revision") != input_revision
                or context.get("artifact_version_refs") != task.get("target_refs")
                or layers.get("role_contract", {}).get("role_id")
                != task.get("role_id")
                or layers.get("task_contract", {}).get("task_type") != action
                or layers.get("task_contract", {}).get("target_refs")
                != task.get("target_refs")
            ):
                raise ValueError("Agent ContextPack provenance is inconsistent")
            for value in list(task.get("target_refs") or []):
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
            self.validate_noncontent_agent_result_kind(task, request_kind, payload)
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ContractValidationError(
                "Agent result provenance is stale or inconsistent"
            ) from error
        return task

    def _prepare_noncontent_agent_result(
        self,
        *,
        command_id: str,
        expected_revision: int,
        request_kind: str,
        payload: dict[str, Any],
    ) -> PreparedArtifactTransaction:
        """Run the established public route against a no-write kernel."""

        preparation = _PreparationKernel(self.kernel)
        from ai_ppt_studio.application.content_service import ContentService
        from ai_ppt_studio.application.visual_service import VisualService

        if request_kind in {
            "material-findings",
            "content-blueprint",
            "content-acceptance",
            "feedback",
        }:
            result_ref = ContentService(preparation).commit_public_artifact(
                command_id,
                expected_revision,
                kind=request_kind,
                payload=payload,
            )
        else:
            result_ref = VisualService(preparation).commit_public_artifact(
                command_id,
                expected_revision,
                kind=request_kind,
                payload=payload,
            )
        if preparation.prepared is None:
            raise ContractValidationError(
                "Agent result route did not prepare a formal transaction"
            )
        return replace(preparation.prepared, result_ref=result_ref)

    def commit_noncontent_agent_result(
        self,
        *,
        command_id: str,
        expected_revision: int,
        task_id: str,
        request_kind: str,
        raw_request_payload: dict[str, Any],
    ) -> tuple[str, KernelState]:
        """Publish a non-content result and complete its task in one commit."""

        replay = self.replay_noncontent_agent_result(
            command_id=command_id,
            task_id=task_id,
            request_kind=request_kind,
            payload=raw_request_payload,
            expected_revision=expected_revision,
        )
        if replay is not None:
            return replay
        task = self.preflight_noncontent_agent_result(
            task_id=task_id,
            request_kind=request_kind,
            payload=raw_request_payload,
            expected_revision=expected_revision,
        )
        prepared = self._prepare_noncontent_agent_result(
            command_id=command_id,
            expected_revision=expected_revision,
            request_kind=request_kind,
            payload=raw_request_payload,
        )
        task_slots = {"agent/task/active", f"agent/task/{task_id}"}
        if task_slots.intersection(prepared.artifact_updates) or task_slots.intersection(
            prepared.artifact_removals
        ):
            raise ContractValidationError(
                "Domain result transaction cannot mutate Agent task heads"
            )
        candidates = [
            (slot, kind, artifact_payload)
            for slot, (kind, artifact_payload) in prepared.artifact_updates.items()
            if str(
                self.kernel.artifacts.reference_for(kind, artifact_payload)
            ) == prepared.result_ref
        ]
        if len(candidates) != 1:
            raise ContractValidationError(
                "Prepared Agent result does not identify one formal result artifact"
            )
        artifact_slot, artifact_kind, _artifact_payload = candidates[0]
        result_ref = prepared.result_ref
        completed = {
            **task,
            "status": "completed",
            "progress": {"stage": "completed", "done": 1, "total": 1},
            "result_refs": [result_ref],
            "error": None,
            "completion_command_id": command_id,
            "completion_result": {
                "action_type": str(task.get("action_type") or ""),
                "artifact_slot": artifact_slot,
                "artifact_kind": artifact_kind,
                "result_ref": result_ref,
                "request_fingerprint": self._result_request_fingerprint(
                    request_kind, raw_request_payload, expected_revision
                ),
            },
        }
        fingerprint = self._result_request_fingerprint(
            request_kind, raw_request_payload, expected_revision
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=prepared.event_type,
            artifact_updates={
                **prepared.artifact_updates,
                "agent/task/active": ("agent-task", completed),
                f"agent/task/{task_id}": ("agent-task", completed),
            },
            artifact_removals=prepared.artifact_removals,
            gate_mutation=prepared.gate_mutation,
            command_fingerprint=fingerprint,
        )
        return committed.artifact_heads[artifact_slot], committed

    def complete_agent_task(
        self,
        command_id: str,
        expected_revision: int,
        *,
        task_id: str,
        result_ref: str,
        completion_command_id: str = "",
        request_kind: str = "",
        request_payload: dict[str, Any] | None = None,
        result_expected_revision: int | None = None,
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
        if completion_command_id:
            completed["completion_command_id"] = completion_command_id
            completed["completion_result"] = {
                "result_ref": result_ref,
                "request_fingerprint": hashlib.sha256(
                    canonical_json({
                        "request_kind": request_kind,
                        "payload": request_payload or {},
                        "expected_revision": result_expected_revision,
                    })
                ).hexdigest(),
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

    def commit_content_agent_result(
        self,
        *,
        command_id: str,
        expected_revision: int,
        task_id: str,
        request_kind: str,
        raw_request_payload: dict[str, Any],
    ) -> tuple[str, KernelState]:
        """Publish a validated content result and complete its task atomically."""

        from ai_ppt_studio.application.content_action_policy import (
            CONTENT_RESULT_CONTRACTS,
        )
        from ai_ppt_studio.errors import ContentWorkflowError

        replay = self.replay_content_agent_result(
            command_id=command_id,
            task_id=task_id,
            request_kind=request_kind,
            payload=raw_request_payload,
            expected_revision=expected_revision,
        )
        if replay is not None:
            return replay
        task, _context = self.preflight_content_agent_result(
            task_id=task_id,
            request_kind=request_kind,
            payload=raw_request_payload,
            expected_revision=expected_revision,
        )
        action = str(task.get("action_type") or "")
        contract = CONTENT_RESULT_CONTRACTS.get(action)
        if (
            contract is None
            or request_kind != contract.request_kind
            or raw_request_payload.get("artifact_type") != contract.artifact_type
            or (
                contract.reviewer_role
                and raw_request_payload.get("reviewer_role") != contract.reviewer_role
            )
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Prepared content result does not match the active task contract",
                {"task_id": task_id, "action_type": action},
            )
        from ai_ppt_studio.application.content_service import ContentService

        content = ContentService(self.kernel)
        if contract.stage:
            artifact_slot, artifact_kind, normalized = (
                content._prepare_content_stage_update(
                    contract.stage, raw_request_payload
                )
            )
        else:
            artifact_slot, artifact_kind, normalized = (
                content._prepare_review_update(raw_request_payload)
            )
        if (
            artifact_slot != contract.artifact_slot
            or artifact_kind != contract.artifact_kind
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Prepared content result violates the active task contract",
                {"task_id": task_id, "action_type": action},
            )
        artifact_payload = normalized
        result_ref = str(
            self.kernel.artifacts.reference_for(
                artifact_kind, artifact_payload
            )
        )
        result_refs = list(task.get("result_refs") or [])
        if result_ref not in result_refs:
            result_refs.append(result_ref)
        completed = {
            **task,
            "status": "completed",
            "progress": {"stage": "completed", "done": 1, "total": 1},
            "result_refs": result_refs,
            "error": None,
            "completion_command_id": command_id,
            "completion_result": {
                "action_type": action,
                "artifact_slot": artifact_slot,
                "artifact_kind": artifact_kind,
                "result_ref": result_ref,
                "request_fingerprint": self._result_request_fingerprint(
                    request_kind, raw_request_payload, expected_revision
                ),
            },
        }
        request_fingerprint = self._result_request_fingerprint(
            request_kind, raw_request_payload, expected_revision
        )
        try:
            state = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="agent.content-result-committed",
                artifact_updates={
                    artifact_slot: (artifact_kind, artifact_payload),
                    "agent/task/active": ("agent-task", completed),
                    f"agent/task/{task_id}": ("agent-task", completed),
                },
                command_fingerprint=request_fingerprint,
            )
        except ContractValidationError:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Processed content result command has different semantics",
                {"command_id": command_id, "task_id": task_id},
            ) from None
        return state.artifact_heads[artifact_slot], state

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
