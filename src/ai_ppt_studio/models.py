"""Stable runtime data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
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


class SourceKind(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"
    URL = "url"
    TEXT = "text"


class ImportMode(str, Enum):
    REFERENCE = "reference"
    COPY = "copy"


@dataclass(frozen=True)
class MaterialSource:
    """One immutable record of user-provided source material."""

    source_id: str
    kind: SourceKind
    mode: ImportMode
    original_ref: str
    managed_ref: str | None
    sha256: str | None
    size_bytes: int | None
    created_at: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["mode"] = self.mode.value
        return payload
