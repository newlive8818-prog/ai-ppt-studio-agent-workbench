"""Shared exact request helpers for the public Python bridge."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.project_status_projection import (
    ProjectStatusProjectionService,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


@dataclass(frozen=True)
class BridgeContext:
    operation: str
    project_root: Path
    kernel: ProjectKernel
    command_id: str


def is_schema3_project(project_root: Path) -> bool:
    try:
        payload = json.loads(
            (project_root / "kernel" / "state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("schema_version") == "3.0"


def context(request: dict[str, Any]) -> BridgeContext:
    operation = str(request.get("operation") or "").strip()
    project_value = str(request.get("project_root") or "").strip()
    if not operation or not project_value:
        raise ContractValidationError("operation and project_root are required")
    project_root = Path(project_value).resolve()
    state_path = project_root / "kernel" / "state.json"
    try:
        project_id = str(json.loads(state_path.read_text(encoding="utf-8"))["project_id"])
    except (OSError, json.JSONDecodeError, KeyError) as error:
        raise ContractValidationError(
            f"Schema 3.0 project state is invalid: {state_path}"
        ) from error
    supplied = str(request.get("command_id") or "").strip()
    command_id = supplied or "bridge:{}:{}".format(
        operation,
        hashlib.sha256(
            json.dumps(
                request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
    )
    return BridgeContext(
        operation,
        project_root,
        ProjectKernel(project_root, project_id=project_id),
        command_id,
    )


def snapshot(ctx: BridgeContext, state: KernelState | None = None) -> dict[str, Any]:
    state = state or ctx.kernel.load()
    identity = MissionReadinessPolicy(ctx.kernel).projection()
    manifest_ref = state.artifact_heads.get("project/manifest", "")
    project_name = state.project_id
    if manifest_ref:
        manifest = ctx.kernel.artifacts.resolve(ArtifactReference.parse(manifest_ref))[
            "payload"
        ]
        project_name = str(manifest.get("name") or project_name)
    return {
        "schema_version": state.schema_version,
        "revision": state.revision,
        "project": {
            "project_id": state.project_id,
            "name": project_name,
            "project_root": str(ctx.project_root),
        },
        "gate_state": {
            "current_gate": next(
                (
                    gate
                    for gate in ("G0", "G1", "G2", "G3", "G4")
                    if state.gate_status.get(gate) not in {"locked", "passed"}
                ),
                "G4",
            ),
            "gates": dict(state.gate_status),
        },
        "artifacts": dict(state.artifact_heads),
        "missionDraftRef": identity["mission_draft_ref"],
        "missionConfirmationRef": identity["mission_confirmation_ref"],
        "materialMode": identity["material_mode"],
        "contentMode": identity["content_mode"],
        "status": ProjectStatusProjectionService(ctx.kernel).project(),
        "experience": ExperienceService(ctx.kernel).experience_projection(),
        "allowed_next_actions": [],
    }


def response(ctx: BridgeContext, **values: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "operation": ctx.operation,
        "selected_project_root": str(ctx.project_root),
        **values,
    }


def result(
    ctx: BridgeContext, state: KernelState | None = None, **values: Any
) -> dict[str, Any]:
    return response(ctx, result={**values, "snapshot": snapshot(ctx, state)})


def object_value(request: dict[str, Any], field: str) -> dict[str, Any]:
    value = request.get(field)
    if not isinstance(value, dict):
        raise ContractValidationError(f"{field} must be an object")
    return dict(value)


def object_array(request: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = request.get(field)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ContractValidationError(f"{field} must be an object array")
    return [dict(item) for item in value]


def string_array(request: dict[str, Any], field: str) -> list[str]:
    value = request.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ContractValidationError(f"{field} must be an array of strings")
    return list(value)


Handler = Any


__all__ = [
    "BridgeContext",
    "Handler",
    "context",
    "is_schema3_project",
    "object_array",
    "object_value",
    "response",
    "result",
    "snapshot",
    "string_array",
]
