"""Compile bounded, reproducible context packs for Codex follow-up work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .models import ProjectManifest
from .paths import PathPolicy
from .state_store import StateStore


class ContextCompiler:
    """Summarize project state without embedding material bodies or binaries."""

    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy

    def compile(
        self,
        *,
        action_type: str,
        project_revision: int,
        target_refs: list[str],
        instructions: str,
    ) -> dict[str, Any]:
        manifest = ProjectManifest.from_dict(
            json.loads((self.project_root / "project.json").read_text("utf-8"))
        )
        sources = []
        for path in sorted((self.project_root / "sources").glob("*.json")):
            try:
                item = json.loads(path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            sources.append(
                {
                    "source_id": item.get("source_id"),
                    "kind": item.get("kind"),
                    "mode": item.get("mode"),
                    "source_ref": f"sources/{path.name}",
                    "managed_ref": self._project_ref(item.get("managed_ref")),
                    "sha256": item.get("sha256"),
                    "size_bytes": item.get("size_bytes"),
                }
            )
        artifacts = {
            kind: {
                "kind": artifact.kind,
                "version": artifact.version,
                "path": self._project_ref(artifact.path),
                "sha256": artifact.sha256,
            }
            for kind, artifact in ArtifactStore(
                self.project_root, self.policy
            ).list_latest().items()
        }
        return {
            "schema_version": "1.0",
            "project": {
                "project_id": manifest.project_id,
                "name": manifest.name,
                "project_root": manifest.project_root,
            },
            "project_revision": project_revision,
            "action_type": action_type.strip(),
            "target_refs": [str(item) for item in target_refs],
            "instructions": instructions.strip()[:2000],
            "source_summary": {"count": len(sources), "sources": sources},
            "artifact_summary": artifacts,
            "gate_state": StateStore(self.project_root, self.policy).load().as_dict(),
            "execution_rules": {
                "customer_material_policy": "user-provided-only",
                "visual_concepts": "Image 2 through Codex",
                "pptx_route": "Codex Presentations only",
                "writeback": "commit through AI PPT workbench runtime",
            },
        }

    def _project_ref(self, value: Any) -> str | None:
        if not value:
            return None
        path = Path(str(value))
        try:
            return path.resolve(strict=False).relative_to(self.project_root).as_posix()
        except ValueError:
            return str(value)


__all__ = ["ContextCompiler"]
