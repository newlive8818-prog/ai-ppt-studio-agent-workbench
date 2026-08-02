"""Single-request JSON bridge used by the Node MCP server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import RuntimeConfig
from .errors import (
    ProjectNotFoundError,
    ProtectedPathError,
    RevisionConflictError,
    WorkbenchValidationError,
)
from .models import ProjectManifest
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
        try:
            expected_revision = int(request["expected_revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkbenchValidationError(
                "expected_revision must be an integer"
            ) from exc
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
    raise WorkbenchValidationError(f"Unsupported operation: {operation}")


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
    if isinstance(exc, ProjectNotFoundError):
        code = "PROJECT_NOT_FOUND"
    elif isinstance(exc, ProtectedPathError):
        code = "PATH_PROTECTED"
    elif isinstance(exc, (WorkbenchValidationError, json.JSONDecodeError, TypeError)):
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
