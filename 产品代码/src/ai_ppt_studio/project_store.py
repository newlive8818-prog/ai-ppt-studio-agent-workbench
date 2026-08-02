"""Creation and recovery of managed AI PPT projects."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .config import RuntimeConfig
from .errors import ProjectNotFoundError
from .json_io import atomic_write_json
from .models import ProjectManifest
from .paths import PathPolicy

PROJECT_DIRECTORIES = (
    "sources",
    "managed-assets",
    "cognition",
    "blueprint",
    "visual",
    "scene-graph",
    "ppt",
    "renders",
    "reviews",
    "state",
    "events",
    "logs",
    "tasks",
    "context",
)


def normalize_slug(value: str) -> str:
    """Create a readable filesystem-safe slug while preserving Unicode letters."""

    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^\w\-]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"[-_]{2,}", "-", normalized).strip("-_")
    return normalized[:72] or "project"


class ProjectStore:
    """Persist projects only below the configured managed projects directory."""

    def __init__(self, config: RuntimeConfig, policy: PathPolicy) -> None:
        self.config = config
        self.policy = policy

    def create(
        self, name: str, source_context: Path | None = None
    ) -> ProjectManifest:
        clean_name = name.strip()
        if not clean_name:
            clean_name = "Untitled presentation"
        project_id = str(uuid.uuid4())
        slug = normalize_slug(clean_name)
        projects_root = self.policy.assert_write_allowed(
            self.config.runtime_root / "projects"
        )
        projects_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        project_root = self.policy.assert_write_allowed(
            projects_root / f"{slug}-{project_id[:8]}"
        )
        project_root.mkdir(mode=0o700)
        for directory_name in PROJECT_DIRECTORIES:
            directory = self.policy.assert_write_allowed(
                project_root / directory_name
            )
            directory.mkdir(mode=0o700)
        manifest = ProjectManifest(
            project_id=project_id,
            name=clean_name,
            slug=slug,
            schema_version="1.0",
            created_at=datetime.now(UTC).isoformat(),
            source_context=(
                str(source_context.expanduser().resolve(strict=False))
                if source_context is not None
                else None
            ),
            project_root=str(project_root),
        )
        manifest_path = self.policy.assert_write_allowed(
            project_root / "project.json"
        )
        atomic_write_json(manifest_path, manifest.as_dict())
        return manifest

    def load(self, project_root: Path) -> ProjectManifest:
        managed_root = self.policy.assert_write_allowed(project_root)
        manifest_path = managed_root / "project.json"
        if not manifest_path.is_file():
            raise ProjectNotFoundError(f"Managed project not found: {managed_root}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = ProjectManifest.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProjectNotFoundError(
                f"Managed project manifest is invalid: {manifest_path}"
            ) from exc
        if Path(manifest.project_root).resolve(strict=False) != managed_root:
            raise ProjectNotFoundError(
                f"Managed project manifest root mismatch: {manifest_path}"
            )
        return manifest
