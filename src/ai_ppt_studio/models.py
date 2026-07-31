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


class Gate(str, Enum):
    G0 = "G0"
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"


class GateStatus(str, Enum):
    LOCKED = "locked"
    OPEN = "open"
    PASSED = "passed"


@dataclass(frozen=True)
class ProjectState:
    """Current resumable G0-G4 workflow state."""

    schema_version: str
    revision: int
    gates: dict[str, str]
    current_gate: str
    updated_at: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectState":
        return cls(
            schema_version=str(payload["schema_version"]),
            revision=int(payload["revision"]),
            gates={str(key): str(value) for key, value in payload["gates"].items()},
            current_gate=str(payload["current_gate"]),
            updated_at=str(payload["updated_at"]),
        )


class ArtifactKind(str, Enum):
    MISSION = "mission"
    CONTENT_BLUEPRINT = "content-blueprint"
    VISUAL_BRIEF = "visual-brief"
    CONCEPT_SET = "concept-set"
    VISUAL_CONTRACT = "visual-contract"
    SLIDE_SCENE_GRAPH = "slide-scene-graph"
    FEEDBACK = "feedback"
    PRESENTATION_HANDOFF = "presentation-handoff"
    DELIVERY = "delivery"


@dataclass(frozen=True)
class ArtifactVersion:
    """One immutable, hash-addressed project artifact version."""

    kind: str
    version: int
    path: str
    sha256: str
    created_at: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactVersion":
        return cls(
            kind=str(payload["kind"]),
            version=int(payload["version"]),
            path=str(payload["path"]),
            sha256=str(payload["sha256"]),
            created_at=str(payload["created_at"]),
            payload=dict(payload["payload"]),
        )
