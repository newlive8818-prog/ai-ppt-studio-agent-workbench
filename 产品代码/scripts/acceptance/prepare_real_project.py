#!/usr/bin/env python3
"""Create or resume one managed schema 3 real acceptance project."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.project_service import ProjectCommandService, ProjectService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ContractValidationError, ProjectNotFoundError
from ai_ppt_studio.kernel.references import ArtifactReference


def _matches(current: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(current.get(key) == value for key, value in expected.items())


def prepare_real_project(
    config: RuntimeConfig,
    *,
    project_id: str,
    name: str,
    mission: dict[str, Any],
    text_materials: list[tuple[str, str]] | None = None,
    file_materials: list[Path] | None = None,
) -> dict[str, Any]:
    projects = ProjectService(config)
    target = projects.projects_root / project_id
    try:
        project_root = projects.resolve_project(target)
        state_payload = json.loads(
            (project_root / "kernel" / "state.json").read_text(encoding="utf-8")
        )
        from ai_ppt_studio.kernel.transactions import ProjectKernel

        kernel = ProjectKernel(project_root, project_id=str(state_payload["project_id"]))
    except ProjectNotFoundError:
        kernel = projects.create_project(name, project_id=project_id)
    state = kernel.load()
    if state.artifact_heads.get("mission"):
        raise ContractValidationError(
            "Legacy mission projects cannot be migrated in place; create a new "
            "MissionDraft version through the formal recovery workflow"
        )
    mission_ref = state.artifact_heads.get("mission/draft")
    if mission_ref:
        current = kernel.artifacts.resolve(ArtifactReference.parse(mission_ref))["payload"]
        if not _matches(current, mission):
            raise ContractValidationError(
                "Existing real-project MissionDraft differs from the requested draft"
            )
    else:
        ContentService(kernel).save_mission_draft(
            "acceptance:mission", state.revision, mission
        )

    requested: list[tuple[str, str, bytes, str]] = []
    for label, text in text_materials or []:
        requested.append((label, "text", text.encode("utf-8"), text))
    for source in file_materials or []:
        resolved = source.expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise ContractValidationError(f"Material is not a file: {resolved}")
        requested.append((resolved.name, "bytes", resolved.read_bytes(), ""))

    commands = ProjectCommandService(kernel)
    for label, material_type, raw, value in requested:
        source_id = f"source-{hashlib.sha256(raw).hexdigest()[:16]}"
        state = kernel.load()
        existing = state.artifact_heads.get("materials")
        if existing:
            inventory = kernel.artifacts.resolve(
                ArtifactReference.parse(existing)
            )["payload"]
            if any(item.get("source_id") == source_id for item in inventory.get("sources", [])):
                continue
        commands.add_material(
            f"acceptance:material:{source_id}",
            state.revision,
            material_type=material_type,
            value=value,
            data_base64=(
                base64.b64encode(raw).decode("ascii")
                if material_type == "bytes"
                else ""
            ),
            label=label,
            filename=label,
            mime_type=("application/octet-stream" if material_type == "bytes" else "text/plain"),
        )
    final = kernel.load()
    return {
        "ok": True,
        "project_id": final.project_id,
        "project_root": str(kernel.project_root),
        "schema_version": final.schema_version,
        "revision": final.revision,
        "artifact_heads": dict(final.artifact_heads),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--mission-json", type=Path, required=True)
    parser.add_argument("--material-file", type=Path, action="append", default=[])
    args = parser.parse_args()
    result = prepare_real_project(
        RuntimeConfig.from_workspace_file(args.workspace_config),
        project_id=args.project_id,
        name=args.name,
        mission=json.loads(args.mission_json.read_text(encoding="utf-8")),
        file_materials=args.material_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
