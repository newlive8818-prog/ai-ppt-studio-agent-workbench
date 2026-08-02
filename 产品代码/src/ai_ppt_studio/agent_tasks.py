"""Immutable Agent task requests with resumable active-task state."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .errors import ProjectNotFoundError, WorkbenchValidationError
from .event_store import EventStore, utc_now
from .json_io import atomic_write_json
from .paths import PathPolicy


SUPPORTED_AGENT_ACTIONS = {
    "classify-materials",
    "generate-blueprint",
    "revise-blueprint",
    "explore-concepts",
    "build-engineering-samples",
    "freeze-visual-contract",
    "build-pptx",
    "qa-render",
    "repair-pptx",
}


class AgentTaskStore:
    """Persist a request and context without mutating either after creation."""

    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.events = EventStore(self.project_root, policy)

    @property
    def active_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "state" / "active-task.json"
        )

    def request(
        self,
        *,
        action_type: str,
        target_refs: list[str],
        instructions: str,
        project_revision: int,
        context_payload: dict[str, Any],
    ) -> dict[str, Any]:
        action = action_type.strip()
        if action not in SUPPORTED_AGENT_ACTIONS:
            raise WorkbenchValidationError(f"Unsupported Agent action: {action}")
        if project_revision < 0:
            raise WorkbenchValidationError("project_revision cannot be negative")
        targets = [str(item).strip() for item in target_refs if str(item).strip()]
        if not targets:
            raise WorkbenchValidationError("Agent task requires target_refs")
        task_id = str(uuid.uuid4())
        created_at = utc_now()
        task_ref = f"tasks/{task_id}.json"
        context_ref = f"context/{task_id}.json"
        task = {
            "schema_version": "1.0",
            "task_id": task_id,
            "action_type": action,
            "target_refs": targets,
            "instructions": instructions.strip(),
            "project_revision": project_revision,
            "status": "requested",
            "context_ref": context_ref,
            "created_at": created_at,
            "created_by": "user",
        }
        context = dict(context_payload)
        context.update(
            {
                "task_id": task_id,
                "action_type": action,
                "project_revision": project_revision,
                "created_at": created_at,
            }
        )
        task_path = self.policy.assert_write_allowed(self.project_root / task_ref)
        context_path = self.policy.assert_write_allowed(self.project_root / context_ref)
        if task_path.exists() or context_path.exists():
            raise WorkbenchValidationError(f"Agent task already exists: {task_id}")
        atomic_write_json(context_path, context)
        atomic_write_json(task_path, task)
        pointer = {
            "schema_version": "1.0",
            "task_id": task_id,
            "task_ref": task_ref,
            "context_ref": context_ref,
            "action_type": action,
            "status": "requested",
            "project_revision": project_revision,
            "updated_at": created_at,
        }
        atomic_write_json(self.active_path, pointer)
        self.events.append(
            "workbench.agent-task.requested",
            {
                "task_id": task_id,
                "action_type": action,
                "project_revision": project_revision,
                "target_refs": targets,
            },
        )
        return task

    def complete(
        self,
        task_id: str,
        *,
        artifact_refs: list[str],
        result_revision: int,
    ) -> dict[str, Any]:
        request = self._read_request(task_id)
        result_path = self.policy.assert_write_allowed(
            self.project_root / "tasks" / f"{task_id}.result.json"
        )
        if result_path.exists():
            raise WorkbenchValidationError(f"Agent task already completed: {task_id}")
        completed_at = utc_now()
        result = {
            "schema_version": "1.0",
            "task_id": task_id,
            "action_type": request["action_type"],
            "status": "completed",
            "artifact_refs": [str(item) for item in artifact_refs],
            "result_revision": result_revision,
            "completed_at": completed_at,
        }
        atomic_write_json(result_path, result)
        pointer = {
            "schema_version": "1.0",
            "task_id": task_id,
            "task_ref": f"tasks/{task_id}.json",
            "context_ref": request["context_ref"],
            "result_ref": f"tasks/{task_id}.result.json",
            "action_type": request["action_type"],
            "status": "completed",
            "project_revision": result_revision,
            "updated_at": completed_at,
        }
        atomic_write_json(self.active_path, pointer)
        self.events.append(
            "workbench.agent-task.completed",
            {
                "task_id": task_id,
                "artifact_refs": result["artifact_refs"],
                "result_revision": result_revision,
            },
        )
        return result

    def active(self) -> dict[str, Any] | None:
        if not self.active_path.is_file():
            return None
        try:
            pointer = json.loads(self.active_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectNotFoundError(
                f"Active Agent task is invalid: {self.active_path}"
            ) from exc
        return dict(pointer)

    def _read_request(self, task_id: str) -> dict[str, Any]:
        clean = task_id.strip()
        if not clean or "/" in clean or ".." in clean:
            raise WorkbenchValidationError("Invalid Agent task id")
        path = self.policy.assert_write_allowed(
            self.project_root / "tasks" / f"{clean}.json"
        )
        if not path.is_file():
            raise ProjectNotFoundError(f"Agent task not found: {clean}")
        try:
            return dict(json.loads(path.read_text("utf-8")))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ProjectNotFoundError(f"Agent task is invalid: {path}") from exc


__all__ = ["AgentTaskStore", "SUPPORTED_AGENT_ACTIONS"]
