"""Immutable version storage for AI PPT project decisions and deliverables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import ArtifactValidationError, ProjectNotFoundError
from .event_store import EventStore, utc_now
from .json_io import atomic_write_json
from .models import ArtifactKind, ArtifactVersion
from .paths import PathPolicy

ARTIFACT_DIRECTORIES = {
    ArtifactKind.MATERIAL_FINDINGS: Path("cognition/material-findings"),
    ArtifactKind.MISSION: Path("blueprint/mission"),
    ArtifactKind.CONTENT_BLUEPRINT: Path("blueprint/content-blueprint"),
    ArtifactKind.VISUAL_BRIEF: Path("visual/visual-brief"),
    ArtifactKind.CONCEPT_SET: Path("visual/concept-set"),
    ArtifactKind.ENGINEERING_SAMPLES: Path("visual/engineering-samples"),
    ArtifactKind.VISUAL_CONTRACT: Path("visual/visual-contract"),
    ArtifactKind.SLIDE_SCENE_GRAPH: Path("scene-graph/slide-scene-graph"),
    ArtifactKind.FEEDBACK: Path("reviews/feedback"),
    ArtifactKind.PRESENTATION_HANDOFF: Path("ppt/presentation-handoff"),
    ArtifactKind.DELIVERY: Path("reviews/delivery"),
}


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_non_empty(payload: dict[str, object], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not payload.get(field)]
    if missing:
        raise ArtifactValidationError(
            f"Artifact is missing required fields: {', '.join(missing)}"
        )


def validate_artifact(kind: ArtifactKind, payload: dict[str, object]) -> None:
    if not isinstance(payload, dict):
        raise ArtifactValidationError("Artifact payload must be a JSON object")
    if kind is ArtifactKind.MATERIAL_FINDINGS:
        _require_non_empty(payload, ("summary", "findings", "source_assignments"))
        findings = payload.get("findings")
        if not isinstance(findings, list) or not findings:
            raise ArtifactValidationError(
                "Material findings requires at least one finding"
            )
        required = (
            "finding_id",
            "finding_type",
            "content",
            "source_ref",
            "locator",
            "fact_status",
            "purposes",
        )
        for index, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                raise ArtifactValidationError(f"Finding {index} must be an object")
            missing = [field for field in required if field not in finding]
            if missing:
                raise ArtifactValidationError(
                    f"Finding {index} is missing fields: {', '.join(missing)}"
                )
            if not str(finding.get("source_ref", "")).startswith("sources/"):
                raise ArtifactValidationError(
                    f"Finding {index} source_ref must reference sources/"
                )
        assignments = payload.get("source_assignments")
        if not isinstance(assignments, list) or not assignments:
            raise ArtifactValidationError(
                "Material findings requires at least one source assignment"
            )
    elif kind is ArtifactKind.MISSION:
        _require_non_empty(payload, ("title", "audience", "goal", "context"))
    elif kind is ArtifactKind.CONTENT_BLUEPRINT:
        _require_non_empty(payload, ("title", "audience", "goal", "slides"))
        slides = payload.get("slides")
        if not isinstance(slides, list) or not slides:
            raise ArtifactValidationError(
                "Content blueprint requires at least one slide"
            )
        required = (
            "slide_id",
            "title",
            "purpose",
            "claim",
            "visible_content",
            "speaker_notes",
            "source_refs",
            "material_refs",
        )
        for index, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                raise ArtifactValidationError(f"Slide {index} must be an object")
            missing = [field for field in required if field not in slide]
            if missing:
                raise ArtifactValidationError(
                    f"Slide {index} is missing fields: {', '.join(missing)}"
                )
    elif kind is ArtifactKind.VISUAL_BRIEF:
        _require_non_empty(
            payload,
            ("design_challenge", "audience", "desired_response", "constraints"),
        )
    elif kind is ArtifactKind.CONCEPT_SET:
        _require_non_empty(payload, ("directions",))
        directions = payload.get("directions")
        if not isinstance(directions, list) or len(directions) < 2:
            raise ArtifactValidationError(
                "Concept set requires at least two distinct directions"
            )
    elif kind is ArtifactKind.ENGINEERING_SAMPLES:
        _require_non_empty(payload, ("summary", "samples", "native_coverage", "qa_status"))
        samples = payload.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ArtifactValidationError(
                "Engineering samples requires at least one sample"
            )
        required = (
            "sample_id",
            "slide_refs",
            "render_ref",
            "native_element_ratio",
            "editable",
            "notes",
        )
        for index, sample in enumerate(samples, start=1):
            if not isinstance(sample, dict):
                raise ArtifactValidationError(
                    f"Engineering sample {index} must be an object"
                )
            missing = [field for field in required if field not in sample]
            if missing:
                raise ArtifactValidationError(
                    f"Engineering sample {index} is missing fields: {', '.join(missing)}"
                )
            ratio = sample.get("native_element_ratio")
            if not isinstance(ratio, (int, float)) or not 0 <= float(ratio) <= 1:
                raise ArtifactValidationError(
                    f"Engineering sample {index} native_element_ratio must be between 0 and 1"
                )
        coverage = payload.get("native_coverage")
        if not isinstance(coverage, dict) or "whole_slide_bitmap" not in coverage:
            raise ArtifactValidationError(
                "Engineering samples requires native_coverage.whole_slide_bitmap"
            )
    elif kind is ArtifactKind.VISUAL_CONTRACT:
        _require_non_empty(
            payload,
            (
                "design_thesis",
                "palette",
                "typography",
                "layout_rules",
                "image_language",
                "editability_rules",
            ),
        )
    elif kind is ArtifactKind.SLIDE_SCENE_GRAPH:
        slides_value = payload.get("slides")
        graphs = slides_value if isinstance(slides_value, list) else [payload]
        if not graphs:
            raise ArtifactValidationError("Scene graph cannot be empty")
        for index, graph in enumerate(graphs, start=1):
            if not isinstance(graph, dict):
                raise ArtifactValidationError(
                    f"Scene graph slide {index} must be an object"
                )
            missing = [
                field
                for field in ("slide_id", "width", "height", "elements")
                if field not in graph
            ]
            if missing:
                raise ArtifactValidationError(
                    f"Scene graph slide {index} is missing fields: {', '.join(missing)}"
                )
    elif kind is ArtifactKind.FEEDBACK:
        _require_non_empty(payload, ("raw_feedback", "scope", "decision"))
    elif kind is ArtifactKind.PRESENTATION_HANDOFF:
        _require_non_empty(
            payload,
            (
                "content_blueprint_ref",
                "visual_contract_ref",
                "scene_graph_ref",
                "output_pptx",
                "render_directory",
                "source_notes_ref",
            ),
        )
    elif kind is ArtifactKind.DELIVERY:
        _require_non_empty(payload, ("pptx", "renders", "qa_status", "sources"))


class ArtifactStore:
    """Save and retrieve immutable artifact versions inside one project."""

    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.events = EventStore(self.project_root, policy)

    def save(
        self, kind: ArtifactKind, payload: dict[str, object]
    ) -> ArtifactVersion:
        validate_artifact(kind, payload)
        directory = self.policy.assert_write_allowed(
            self.project_root / ARTIFACT_DIRECTORIES[kind]
        )
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        version = self._next_version(directory)
        path = self.policy.assert_write_allowed(directory / f"v{version:04d}.json")
        if path.exists():
            raise ArtifactValidationError(
                f"Artifact version already exists and cannot be overwritten: {path}"
            )
        artifact = ArtifactVersion(
            kind=kind.value,
            version=version,
            path=str(path),
            sha256=_payload_hash(payload),
            created_at=utc_now(),
            payload=dict(payload),
        )
        atomic_write_json(path, artifact.as_dict())
        latest_path = self.policy.assert_write_allowed(directory / "latest.json")
        atomic_write_json(
            latest_path,
            {
                "kind": kind.value,
                "version": version,
                "path": str(path),
                "sha256": artifact.sha256,
                "created_at": artifact.created_at,
            },
        )
        self.events.append(
            "project.artifact.saved",
            {
                "kind": kind.value,
                "version": version,
                "path": str(path),
                "sha256": artifact.sha256,
            },
        )
        return artifact

    def latest(self, kind: ArtifactKind) -> ArtifactVersion:
        directory = self.project_root / ARTIFACT_DIRECTORIES[kind]
        pointer = directory / "latest.json"
        if not pointer.is_file():
            raise ProjectNotFoundError(f"Artifact has no saved version: {kind.value}")
        try:
            metadata = json.loads(pointer.read_text(encoding="utf-8"))
            version_path = self.policy.assert_write_allowed(Path(metadata["path"]))
            artifact = ArtifactVersion.from_dict(
                json.loads(version_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProjectNotFoundError(
                f"Artifact pointer is invalid: {pointer}"
            ) from exc
        if artifact.kind != kind.value:
            raise ProjectNotFoundError(f"Artifact kind mismatch: {pointer}")
        return artifact

    def list_latest(self) -> dict[str, ArtifactVersion]:
        result: dict[str, ArtifactVersion] = {}
        for kind in ArtifactKind:
            try:
                result[kind.value] = self.latest(kind)
            except ProjectNotFoundError:
                continue
        return result

    @staticmethod
    def _next_version(directory: Path) -> int:
        versions = []
        for path in directory.glob("v[0-9][0-9][0-9][0-9].json"):
            try:
                versions.append(int(path.stem[1:]))
            except ValueError:
                continue
        return max(versions, default=0) + 1
