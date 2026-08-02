"""Single-request JSON bridge used by the Node MCP server."""

from __future__ import annotations

import json
import os
import sys
import base64
import binascii
from pathlib import Path
from typing import Any

from .config import RuntimeConfig
from .errors import (
    ArtifactValidationError,
    GateBlockedError,
    InvalidTransitionError,
    MaterialImportError,
    ProjectNotFoundError,
    ProtectedPathError,
    RevisionConflictError,
    WorkbenchValidationError,
)
from .models import ArtifactKind, Gate, ProjectManifest
from .paths import PathPolicy
from .workbench_store import WorkbenchStore


def _config(request: dict[str, Any]) -> RuntimeConfig:
    configured = request.get("workspace_config") or os.environ.get(
        "AI_PPT_WORKSPACE_CONFIG"
    )
    path = (
        Path(str(configured))
        if configured
        else Path.home() / "Documents" / "AI-PPT-Workspace" / "workspace.json"
    )
    return RuntimeConfig.from_workspace_file(path)


def _list_projects(config: RuntimeConfig) -> list[dict[str, object]]:
    projects_root = config.runtime_root / "projects"
    if not projects_root.is_dir():
        return []
    items: list[tuple[float, dict[str, object]]] = []
    for path in projects_root.iterdir():
        manifest_path = path / "project.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = ProjectManifest.from_dict(
                json.loads(manifest_path.read_text("utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            continue
        if Path(manifest.project_root).resolve(strict=False) != path.resolve(
            strict=False
        ):
            continue
        items.append((manifest_path.stat().st_mtime, manifest.as_dict()))
    items.sort(key=lambda item: item[0], reverse=True)
    return [payload for _, payload in items]


def _project_root(request: dict[str, Any], config: RuntimeConfig) -> Path:
    explicit = request.get("project_root")
    if explicit:
        return Path(str(explicit))
    projects = _list_projects(config)
    if not projects:
        raise ProjectNotFoundError("No managed AI PPT project is available")
    return Path(str(projects[0]["project_root"]))


def dispatch(request: dict[str, Any]) -> dict[str, object]:
    operation = request.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        raise WorkbenchValidationError("operation is required")
    config = _config(request)
    policy = PathPolicy(config)
    if operation == "list-projects":
        return {"ok": True, "operation": operation, "projects": _list_projects(config)}
    project_root = _project_root(request, config)
    store = WorkbenchStore(project_root, policy)
    if operation == "get-project-snapshot":
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(store.project_root),
            "snapshot": store.ensure().as_dict(),
        }
    if operation == "submit-human-decision":
        expected_revision = _expected_revision(request)
        result = store.submit_decision(
            expected_revision=expected_revision,
            target_ref=str(request.get("target_ref") or ""),
            choice=str(request.get("choice") or ""),
            feedback=str(request.get("feedback") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(store.project_root),
            "result": result.as_dict(),
        }
    if operation == "add-material":
        material_type = str(request.get("material_type") or "")
        value: Any = request.get("value")
        if material_type == "bytes":
            encoded = request.get("data_base64")
            if not isinstance(encoded, str) or not encoded:
                raise WorkbenchValidationError("data_base64 is required for byte material")
            try:
                value = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise WorkbenchValidationError("data_base64 is invalid") from exc
        result = store.add_material(
            expected_revision=_expected_revision(request),
            material_type=material_type,
            value=value,
            label=str(request.get("label") or ""),
            filename=str(request.get("filename") or ""),
            mime_type=str(request.get("mime_type") or ""),
        )
        return _result_payload(operation, store, result)
    if operation == "request-agent-action":
        target_refs = request.get("target_refs")
        if not isinstance(target_refs, list):
            raise WorkbenchValidationError("target_refs must be an array")
        result = store.request_agent_action(
            expected_revision=_expected_revision(request),
            action_type=str(request.get("action_type") or ""),
            target_refs=[str(item) for item in target_refs],
            instructions=str(request.get("instructions") or ""),
        )
        return _result_payload(operation, store, result)
    if operation == "commit-artifact":
        payload = request.get("payload")
        if not isinstance(payload, dict):
            raise WorkbenchValidationError("payload must be a JSON object")
        try:
            artifact_kind = ArtifactKind(str(request.get("kind") or ""))
        except ValueError as exc:
            raise WorkbenchValidationError("kind is not a supported artifact") from exc
        result = store.commit_artifact(
            expected_revision=_expected_revision(request),
            kind=artifact_kind,
            payload=payload,
            task_id=(str(request["task_id"]) if request.get("task_id") else None),
        )
        return _result_payload(operation, store, result)
    if operation == "confirm-gate":
        result = store.confirm_gate(
            expected_revision=_expected_revision(request),
            gate=_gate(request),
        )
        return _result_payload(operation, store, result)
    if operation == "reopen-scope":
        result = store.reopen_scope(
            expected_revision=_expected_revision(request),
            gate=_gate(request),
            reason=str(request.get("reason") or ""),
        )
        return _result_payload(operation, store, result)
    raise WorkbenchValidationError(f"Unsupported operation: {operation}")


def _expected_revision(request: dict[str, Any]) -> int:
    try:
        return int(request["expected_revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkbenchValidationError(
            "expected_revision must be an integer"
        ) from exc


def _gate(request: dict[str, Any]) -> Gate:
    try:
        return Gate(str(request.get("gate") or ""))
    except ValueError as exc:
        raise WorkbenchValidationError("gate must be one of G0-G4") from exc


def _result_payload(
    operation: str, store: WorkbenchStore, result: Any
) -> dict[str, object]:
    return {
        "ok": True,
        "operation": operation,
        "selected_project_root": str(store.project_root),
        "result": result.as_dict(),
    }


def _error_payload(exc: Exception) -> tuple[int, dict[str, object]]:
    if isinstance(exc, RevisionConflictError):
        return 2, {
            "ok": False,
            "error": {
                "code": "REVISION_CONFLICT",
                "message": str(exc),
                "details": {
                    "expected_revision": exc.expected_revision,
                    "actual_revision": exc.actual_revision,
                },
            },
        }
    if isinstance(exc, GateBlockedError):
        return 2, {
            "ok": False,
            "error": {
                "code": "GATE_BLOCKED",
                "message": str(exc),
                "details": {
                    "gate": exc.gate,
                    "missing_evidence": list(exc.missing_evidence),
                },
            },
        }
    if isinstance(exc, ProjectNotFoundError):
        code = "PROJECT_NOT_FOUND"
    elif isinstance(exc, ProtectedPathError):
        code = "PATH_PROTECTED"
    elif isinstance(exc, MaterialImportError):
        code = "SOURCE_UNREADABLE"
    elif isinstance(exc, InvalidTransitionError):
        code = "GATE_BLOCKED"
    elif isinstance(
        exc,
        (
            ArtifactValidationError,
            WorkbenchValidationError,
            json.JSONDecodeError,
            TypeError,
        ),
    ):
        code = "VALIDATION_ERROR"
    else:
        code = "INTERNAL_ERROR"
    return 2 if code != "INTERNAL_ERROR" else 3, {
        "ok": False,
        "error": {"code": code, "message": str(exc), "details": {}},
    }


def main() -> int:
    try:
        raw = sys.stdin.read()
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise WorkbenchValidationError("Bridge request must be a JSON object")
        payload = dispatch(request)
        status = 0
    except Exception as exc:  # Stable process boundary: never leak a traceback to stdout.
        status, payload = _error_payload(exc)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
