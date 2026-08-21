"""Schema 3-only single-request JSON bridge used by the Node MCP server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ArtifactValidationError,
    ChatDeliveryError,
    ConfigurationError,
    ContractValidationError,
    FeedbackGovernanceError,
    GateBlockedError,
    GateMutationError,
    MaterialImportError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
    ProjectIdentityError,
    ProjectNotFoundError,
    ProtectedPathError,
    ReviewMarkSaveError,
    ReviewSourceStaleError,
    RevisionConflictError,
    WorkbenchValidationError,
)


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


def dispatch(request: dict[str, Any]) -> dict[str, object]:
    """Resolve one managed schema 3 project and invoke the formal bridge."""

    operation = request.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        raise WorkbenchValidationError("operation is required")
    projects = ProjectService(_config(request))
    if operation == "list-projects":
        return {
            "ok": True,
            "operation": operation,
            "projects": projects.list_projects(),
        }
    if operation == "create-project":
        kernel = projects.create_project(
            str(request.get("name") or ""),
            project_id=str(request.get("project_id") or ""),
        )
        return dispatch_v16(
            {
                "operation": "get-project-snapshot",
                "project_root": str(kernel.project_root),
            }
        )
    explicit = request.get("project_root")
    project_root = projects.resolve_project(
        Path(str(explicit)) if explicit else None
    )
    return dispatch_v16({**request, "project_root": str(project_root)})


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
    if isinstance(exc, ReviewSourceStaleError):
        return 2, {
            "ok": False,
            "error": {
                "code": "REVIEW_SOURCE_STALE",
                "message": str(exc),
                "details": {
                    "expected_source": exc.expected_source,
                    "actual_source": exc.actual_source,
                },
            },
        }
    if isinstance(exc, MissionNotConfirmedError):
        code = "MISSION_NOT_CONFIRMED"
    elif isinstance(exc, MaterialModeUnconfirmedError):
        code = "MATERIAL_MODE_UNCONFIRMED"
    elif isinstance(exc, ProjectNotFoundError):
        code = "PROJECT_NOT_FOUND"
    elif isinstance(exc, ProtectedPathError):
        code = "PATH_PROTECTED"
    elif isinstance(exc, MaterialImportError):
        code = "SOURCE_UNREADABLE"
    elif isinstance(exc, ReviewMarkSaveError):
        code = "REVIEW_MARK_SAVE_FAILED"
    elif isinstance(exc, ChatDeliveryError):
        code = "CHAT_DELIVERY_FAILED"
    elif isinstance(
        exc,
        (
            ArtifactReferenceError,
            ArtifactValidationError,
            ConfigurationError,
            ContractValidationError,
            FeedbackGovernanceError,
            GateMutationError,
            ProjectIdentityError,
            WorkbenchValidationError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
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
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise WorkbenchValidationError(
                "Bridge request must be a JSON object"
            )
        payload = dispatch(request)
        status = 0
    except Exception as exc:  # Stable process boundary; stdout remains JSON-only.
        status, payload = _error_payload(exc)
    sys.stdout.write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
