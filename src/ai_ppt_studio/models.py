"""Stable runtime data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectManifest:
    """Identity and location of one managed presentation project."""

    project_id: str
    name: str
    slug: str
    schema_version: str
    created_at: str
    source_context: str | None
    project_root: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectManifest":
        return cls(
            project_id=str(payload["project_id"]),
            name=str(payload["name"]),
            slug=str(payload["slug"]),
            schema_version=str(payload["schema_version"]),
            created_at=str(payload["created_at"]),
            source_context=(
                str(payload["source_context"])
                if payload.get("source_context") is not None
                else None
            ),
            project_root=str(payload["project_root"]),
        )
