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
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
    ProjectNotFoundError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.kernel.artifacts import canonical_json
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

ACTION_ROLES = {
    "design-deck-system": "deck-designer",
    "design-slide-visuals": "slide-visual-designer",
    "build-native-first": "native-first-engineer",
    "build-native-diagnostic": "native-first-engineer",
    "generate-image-assets": "image-asset-producer",
    "generate-slide-images": "image-asset-producer",
    "review-visual-aesthetic": "visual-aesthetic-reviewer",
    "review-visual-engineering": "visual-engineering-reviewer",
    "verify-target-render": "target-render-verifier",
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
        ("native-anchor-set", "image-led-anchor-set"),
        ("visual-contract", "image-led-build-result"),
    }),
    "build-native-diagnostic": frozenset({
        ("visual-contract", "image-led-native-diagnostic-result"),
    }),
    "generate-image-assets": frozenset({
        ("visual-contract", "image-asset-pack"),
    }),
    "generate-slide-images": frozenset({
        ("visual-contract", "image-led-candidate"),
    }),
    "review-visual-aesthetic": frozenset({
        ("visual-contract", "visual-review-record"),
    }),
    "review-visual-engineering": frozenset({
        ("visual-contract", "visual-review-record"),
        ("visual-contract", "image-led-review"),
        ("visual-contract", "image-led-region-review"),
        ("visual-contract", "image-led-result-review"),
        ("visual-contract", "image-led-content-diagnostic"),
    }),
    "verify-target-render": frozenset({("target-render-evidence", "")}),
    "coordinate-delivery": frozenset({
        ("delivery", "delivery-package"),
        ("target-render-evidence", ""),
    }),
}


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

    def __init__(self, kernel: ProjectKernel, *, agent_task: dict | None = None) -> None:
        self._kernel = kernel
        self.project_id = kernel.project_id
        self.project_root = kernel.project_root
        self.events_root = kernel.events_root
        self.prepared_agent_task = deepcopy(agent_task)
        self.artifacts = _ReadOnlyPreparationArtifacts(kernel.artifacts)
        self.prepared: PreparedArtifactTransaction | None = None

    def load(self) -> KernelState:
        return self._kernel.load()

    def confirmation_owner(self, identity: str) -> str:
        return self._kernel.confirmation_owner(identity)

    def confirmation_artifact_binding(self, identity: str) -> str:
        return self._kernel.confirmation_artifact_binding(identity)

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

    def close_project(
        self,
        *,
        command_id: str,
        expected_revision: int,
        user_message_ref: str,
        completed_at: str,
    ) -> KernelState:
        if not user_message_ref.startswith("chat://message/"):
            raise ContractValidationError(
                "Project close requires an explicit chat message"
            )
        from ai_ppt_studio.application.retrospective_service import (
            RetrospectiveService,
        )
        from ai_ppt_studio.application.review_commands import stable_id

        return RetrospectiveService(self.kernel).queue_project_completion(
            command_id=command_id,
            expected_revision=expected_revision,
            completion_kind="closed",
            completion_identity=stable_id(
                "project-completion", "closed", user_message_ref
            ),
            completion_ref=user_message_ref,
            completed_at=completed_at,
        )

    def abort_project(
        self,
        *,
        command_id: str,
        expected_revision: int,
        user_message_ref: str,
        reason: str,
        completed_at: str,
    ) -> KernelState:
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not user_message_ref.startswith("chat://message/") or not clean_reason:
            raise ContractValidationError(
                "Project abort requires an explicit chat message and reason"
            )
        from ai_ppt_studio.application.retrospective_service import (
            RetrospectiveService,
        )
        from ai_ppt_studio.application.review_commands import stable_id

        return RetrospectiveService(self.kernel).queue_project_completion(
            command_id=command_id,
            expected_revision=expected_revision,
            completion_kind="aborted",
            completion_identity=stable_id(
                "project-completion", "aborted", user_message_ref
            ),
            completion_ref=user_message_ref,
            completed_at=completed_at,
            completion_details={"reason": clean_reason},
        )

    def add_material(
        self,
        command_id: str,
        expected_revision: int,
        *,
        material_type: str,
        **fields: Any,
    ) -> tuple[str, KernelState]:
        from ai_ppt_studio.application.mission_material_service import MissionMaterialService
        from ai_ppt_studio.application.material_finding_service import MaterialFindingService

        if material_type == "finding":
            reference = MaterialFindingService(self.kernel).register(command_id, expected_revision, fields)
            return reference, self.kernel.load()
        allowed = {"value", "data_base64", "label", "filename", "mime_type"}
        if set(fields) - allowed:
            raise ContractValidationError("Import material contains unknown or finding-only fields")
        if any(not isinstance(value, str) for value in fields.values()):
            raise ContractValidationError("Import material fields must be strings")
        value, data_base64, label, filename, mime_type = (fields.get(key, "") for key in
            ("value", "data_base64", "label", "filename", "mime_type"))
        kind = material_type.strip() if isinstance(material_type, str) else None
        if kind not in {"text", "url", "bytes"}:
            raise ContractValidationError("material_type must be text, url, bytes, or finding")
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
        reference = MissionMaterialService(self.kernel).register_materials(
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
        generation_request_id: str = "",
    ) -> tuple[str, dict[str, Any], KernelState]:
        action = action_type.strip()
        role_id = ACTION_ROLES.get(action)
        if role_id is None:
            raise ContractValidationError(
                f"Unsupported schema 3 Agent action: {action}"
            )
        if len(set(target_refs)) != len(target_refs):
            raise ContractValidationError("Agent task target_refs must be unique")
        if (action == 'generate-slide-images' and not generation_request_id
                and any(ArtifactReference.parse(ref).kind == 'image-led-content-diagnostic' for ref in target_refs)):
            raise ContractValidationError('Image-led repair requires an explicit generation request ID')
        state = self.kernel.load()
        if action in {'design-deck-system', 'design-slide-visuals', 'generate-image-assets'}:
            from ai_ppt_studio.application.image_led_service import reject_legacy_production
            reject_legacy_production(self.kernel)
        if state.revision != expected_revision:
            from ai_ppt_studio.errors import RevisionConflictError

            raise RevisionConflictError(expected_revision, state.revision)
        if action in {
            "design-deck-system",
            "design-slide-visuals",
            "build-native-first",
            "build-native-diagnostic",
            "generate-image-assets",
            "generate-slide-images",
            "review-visual-aesthetic",
            "review-visual-engineering",
            "verify-target-render",
        } and state.gate_status.get("G2") == "passed":
            blocker = (
                "G2-visual-lineage-frozen-until-G3-publication"
                if state.gate_status.get("G3") == "locked"
                else "G3-visual-production-frozen-until-formal-reopen"
            )
            raise GateBlockedError("visual-production", (blocker,))
        if action == "build-native-first":
            current_plan_ref = state.artifact_heads.get("visual/compilation-plan", "")
            if target_refs != [current_plan_ref] or not current_plan_ref:
                raise ContractValidationError(
                    "build-native-first requires the exact current visual compilation plan"
                )
        elif action == "build-native-diagnostic":
            current_selection_ref = state.artifact_heads.get("visual/image-led/selection", "")
            current_regions_ref = state.artifact_heads.get("visual/image-led/regions", "")
            if target_refs != [current_selection_ref, current_regions_ref] or not current_selection_ref or not current_regions_ref:
                raise ContractValidationError("build-native-diagnostic requires exact current selection and regions")
        elif not target_refs:
            raise ContractValidationError("Agent task requires target_refs")
        current_refs = set(state.artifact_heads.values())
        for value in target_refs:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
            if value not in current_refs:
                raise ArtifactReferenceError(
                    "Agent task target must be an exact current artifact head"
                )
        required_gate = {
            "design-deck-system": ("G0", "passed"),
            "design-slide-visuals": ("G0", "passed"),
            "build-native-first": ("G1", "passed"),
            "generate-image-assets": ("G1", "passed"),
            "generate-slide-images": ("G0", "passed"),
            "coordinate-delivery": ("G3", "passed"),
        }.get(action)
        if required_gate and state.gate_status.get(required_gate[0]) != required_gate[1]:
            raise ContractValidationError(
                f"{action} requires {required_gate[0]} {required_gate[1]}"
            )
        from ai_ppt_studio.context_compiler import ContextCompiler

        task_id = hashlib.sha256(command_id.encode("utf-8")).hexdigest()
        if generation_request_id:
            if action != 'generate-slide-images' or not re.fullmatch(r'(?!active$)[A-Za-z0-9_-]{1,128}', generation_request_id):
                raise ContractValidationError('Invalid generation request identity')
            task_id = generation_request_id
            command_id = 'image-led-task-' + task_id
        context = ContextCompiler(self.kernel).compile_role_task(
            role_id=role_id,
            task_type=action,
            project_revision=expected_revision,
            target_refs=target_refs,
            instructions=instructions,
            task_id=task_id,
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
        artifact_updates = {
            f"agent/context/{task_id}": ("context-pack", context),
            "agent/task/active": ("agent-task", task),
            f"agent/task/{task_id}": ("agent-task", task),
        }
        if action == "build-native-diagnostic":
            diagnostic_input = context.get("layers", {}).get("image_led_diagnostic_input")
            if not isinstance(diagnostic_input, dict) or not diagnostic_input.get("diagnostic_ref"):
                raise ContractValidationError("Diagnostic ContextPack lacks its persisted input identity")
            diagnostic_payload = dict(diagnostic_input)
            diagnostic_payload.pop("diagnostic_ref", None)
            from ai_ppt_studio.application.image_led_diagnostic import ImageLedDiagnosticService
            slot = ImageLedDiagnosticService.input_slot(task_id)
            artifact_updates[slot] = ("image-led-native-diagnostic-input", diagnostic_payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="agent.task-requested",
            artifact_updates=artifact_updates,
            command_fingerprint=(hashlib.sha256(json.dumps({
                "action": action, "request_id": task_id, "target_refs": target_refs,
                "instructions": instructions.strip()}, sort_keys=True).encode()).hexdigest()
                if generation_request_id else ""),
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
            if action == "build-native-first":
                current_plan_ref = state.artifact_heads.get(
                    "visual/compilation-plan", ""
                )
                if task.get("target_refs") != [current_plan_ref] or not current_plan_ref:
                    raise ValueError(
                        "build-native-first task is not bound to the exact current visual compilation plan"
                    )
                from ai_ppt_studio.application.image_led_service import is_image_led
                if is_image_led(self.kernel):
                    artifact_type = str(payload.get('artifact_type') or '')
                    if (
                        request_kind == 'visual-contract'
                        and artifact_type == 'image-led-build-result'
                    ):
                        result_plan_ref = (payload.get('output') or {}).get(
                            'plan_ref'
                        )
                    elif (
                        request_kind == 'native-anchor-set'
                        and artifact_type == 'image-led-anchor-set'
                    ):
                        build_result_ref = str(
                            payload.get('build_result_ref') or ''
                        )
                        review_ref = str(
                            payload.get('four_dimension_review_ref') or ''
                        )
                        result_reference = ArtifactReference.parse(
                            build_result_ref
                        )
                        review_reference = ArtifactReference.parse(review_ref)
                        if result_reference.kind != 'image-led-build-result':
                            raise ValueError(
                                'Image-led anchors require an exact build result'
                            )
                        if review_reference.kind != 'image-led-result-review':
                            raise ValueError(
                                'Image-led anchors require an exact four-dimension review'
                            )
                        if state.artifact_heads.get(
                            'visual/image-led/build-result'
                        ) != build_result_ref:
                            raise ValueError(
                                'Image-led anchors require the current build result head'
                            )
                        review_slot = (
                            'visual/image-led/result-review/'
                            + result_reference.sha256
                        )
                        if state.artifact_heads.get(review_slot) != review_ref:
                            raise ValueError(
                                'Image-led anchors require the current result review head'
                            )
                        result_payload = self.kernel.artifacts.resolve(
                            result_reference
                        ).get('payload')
                        if not isinstance(result_payload, dict):
                            raise ValueError(
                                'Image-led anchor build result payload is invalid'
                            )
                        result_plan_ref = (
                            result_payload.get('output') or {}
                        ).get('plan_ref')
                    else:
                        raise ValueError(
                            'Image-led native task result kind is invalid'
                        )
                else:
                    if payload.get('artifact_type') == 'image-led-build-result':
                        raise ValueError('Legacy tasks cannot submit Image-led native results')
                    result_plan_ref = payload.get('visual_compilation_plan_ref')
                if result_plan_ref != current_plan_ref:
                    raise ValueError(
                        "build-native-first result is not bound to the exact current visual compilation plan"
                    )
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
            if action == "build-native-diagnostic":
                from ai_ppt_studio.application.image_led_diagnostic import ImageLedDiagnosticService
                selection_ref = state.artifact_heads.get("visual/image-led/selection", "")
                regions_ref = state.artifact_heads.get("visual/image-led/regions", "")
                if task.get("target_refs") != [selection_ref, regions_ref] or not selection_ref or not regions_ref:
                    raise ValueError("diagnostic task targets are stale")
                input_layer = layers.get("image_led_diagnostic_input")
                if not isinstance(input_layer, dict) or input_layer.get("diagnostic_ref") is None:
                    raise ValueError("diagnostic ContextPack lacks input identity")
                input_ref = input_layer["diagnostic_ref"]
                slot = ImageLedDiagnosticService.input_slot(task_id)
                if state.artifact_heads.get(slot) != input_ref:
                    raise ValueError("diagnostic input is not the exact persisted task input")
                input_payload = self.kernel.artifacts.resolve(ArtifactReference.parse(input_ref))["payload"]
                expected_input = dict(input_layer); expected_input.pop("diagnostic_ref", None)
                if input_payload != expected_input:
                    raise ValueError("diagnostic input differs from ContextPack projection")
                from ai_ppt_studio.domains.visual.diagnostic import validate_diagnostic_handoff
                handoff = layers.get("visual_handoff")
                validate_diagnostic_handoff(handoff)
                if handoff.get("diagnostic_ref") != input_ref or handoff.get("task_id") != task_id:
                    raise ValueError("diagnostic handoff identity is stale")
            if action == "build-native-first":
                handoff = layers.get("visual_handoff")
                if not isinstance(handoff, dict):
                    raise ValueError(
                        "Agent visual handoff provenance is stale or inconsistent"
                    )
                from ai_ppt_studio.context_compiler import ContextCompiler

                ContextCompiler(self.kernel).validate_visual_handoff_for_result(
                    handoff,
                    project_revision=input_revision,
                    expected_revision=expected_revision,
                    target_refs=list(task.get("target_refs") or []),
                    task_id=task_id,
                )
            for value in list(task.get("target_refs") or []):
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
            self.validate_noncontent_agent_result_kind(task, request_kind, payload)
        except (
            ArtifactReferenceError,
            KeyError,
            TypeError,
            ValueError,
            WorkbenchValidationError,
        ) as error:
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
        agent_task: dict | None = None,
    ) -> PreparedArtifactTransaction:
        """Run the established public route against a no-write kernel."""

        preparation = _PreparationKernel(self.kernel, agent_task=agent_task)
        from ai_ppt_studio.application.visual_service import VisualService

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
            agent_task=task,
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

    def cancel_unstarted_native_task(
        self, command_id: str, expected_revision: int, *, task_id: str, reason: str,
    ) -> KernelState:
        """Cancel only a queued native build with no output; preserve visual Gates."""
        from ai_ppt_studio.application.artifact_guards import require_revision
        from ai_ppt_studio.application.review_commands import fingerprint, replay_state

        reason = reason.strip()
        if not reason:
            raise ContractValidationError("Cancellation reason is required")
        semantic = fingerprint("cancel-unstarted-native-task", {"task_id": task_id, "reason": reason})
        replay = replay_state(self.kernel, command_id, semantic)
        if replay is not None:
            return replay
        require_revision(self.kernel, expected_revision)
        task = self.require_active_agent_task(task_id)
        if task.get("action_type") != "build-native-first" or task.get("status") != "queued" or task.get("result_refs"):
            raise ContractValidationError("Only an unstarted native task can be cancelled")
        context = self.kernel.artifacts.resolve(ArtifactReference.parse(task["context_pack_ref"]))["payload"]
        handoff = context["layers"]["visual_handoff"]
        paths = handoff.get("renderer_handoff", handoff)["output_paths"]
        for value in paths.values():
            target = Path(value)
            if not target.is_absolute() or not target.resolve().is_relative_to(self.kernel.project_root):
                raise ContractValidationError("Native task output is outside the project")
            if task_id not in target.parts or target.exists() or target.is_symlink():
                raise ContractValidationError("Native task has output or an invalid output path")
        cancelled = {**task, "status": "cancelled",
            "progress": {"stage": "cancelled", "done": 0, "total": 1},
            "cancellation_reason": reason,
            "cancelled_at": datetime.now(timezone.utc).isoformat()}
        return self.kernel.commit(
            command_id=command_id, expected_revision=expected_revision,
            event_type="agent.native-task-cancelled",
            artifact_updates={f"agent/task/{task_id}": ("agent-task", cancelled)},
            artifact_removals=("agent/task/active",), command_fingerprint=semantic,
        )

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

    def submit_human_decision(
        self,
        command_id: str,
        expected_revision: int,
        *,
        target_ref: str,
        choice: str,
        feedback: str,
        image_led_confirmation: dict[str, Any] | None = None,
    ) -> tuple[str, str, KernelState]:
        target = ArtifactReference.parse(target_ref)
        if target.kind.startswith("image-led-"):
            from ai_ppt_studio.application.image_led_service import ImageLedService
            if image_led_confirmation is None:
                raise ContractValidationError("IMAGE_LED_CONFIRMATION: trusted host assertion required")
            ref = ImageLedService(self.kernel).confirm(
                command_id, expected_revision, target_ref=target_ref, choice=choice,
                **image_led_confirmation)
            return ref, "当前 Image-led 决定已记录；此决定不等于 G3。", self.kernel.load()
        self.kernel.artifacts.resolve(target)
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
