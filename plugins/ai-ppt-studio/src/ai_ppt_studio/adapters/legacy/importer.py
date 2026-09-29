"""Read-only import of verifiable legacy payloads into schema 3.0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_ppt_studio.kernel.transactions import ProjectKernel


@dataclass(frozen=True)
class LegacyImportReport:
    project_id: str
    imported_slots: tuple[str, ...]
    warnings: tuple[str, ...]


class LegacyProjectImporter:
    """Import evidence-bearing payloads without copying legacy pass claims."""

    def import_project(
        self, source: Path, destination: Path
    ) -> LegacyImportReport:
        source = source.resolve(strict=True)
        manifest = json.loads(
            (source / "project.json").read_text(encoding="utf-8")
        )
        project_id = str(manifest["project_id"])
        kernel = ProjectKernel.initialize(destination, project_id=project_id)
        updates: dict[str, tuple[str, dict[str, object]]] = {}

        mission_path = source / "mission.json"
        if mission_path.is_file():
            updates["mission"] = (
                "mission-brief",
                json.loads(mission_path.read_text(encoding="utf-8")),
            )
        if updates:
            kernel.commit(
                command_id="legacy-import",
                expected_revision=0,
                event_type="legacy.imported",
                artifact_updates=updates,
            )
        return LegacyImportReport(
            project_id=project_id,
            imported_slots=tuple(sorted(updates)),
            warnings=("legacy pass states were not imported",),
        )
