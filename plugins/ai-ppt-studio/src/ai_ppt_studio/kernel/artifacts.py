"""Immutable, project-bound content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.references import ArtifactReference


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Encode an artifact envelope deterministically for hashing."""

    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class ArtifactRepository:
    """Store immutable artifact envelopes under their SHA-256 identity."""

    def __init__(self, project_root: Path, *, project_id: str) -> None:
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.objects_root = self.project_root / "artifacts" / "objects"

    def put(self, kind: str, payload: dict[str, Any]) -> ArtifactReference:
        reference = self.reference_for(kind, payload)
        envelope = {
            "project_id": self.project_id,
            "kind": kind,
            "payload": payload,
        }
        path = self.path_for(reference)
        if not path.exists():
            atomic_write_json(path, envelope)
        return reference

    def reference_for(
        self, kind: str, payload: dict[str, Any]
    ) -> ArtifactReference:
        """Compute an artifact identity without writing outside a transaction."""

        envelope = {
            "project_id": self.project_id,
            "kind": kind,
            "payload": payload,
        }
        return ArtifactReference(
            kind=kind,
            sha256=hashlib.sha256(canonical_json(envelope)).hexdigest(),
        )

    def path_for(self, reference: ArtifactReference) -> Path:
        return self.objects_root / reference.sha256[:2] / f"{reference.sha256}.json"

    def resolve(self, reference: ArtifactReference) -> dict[str, Any]:
        path = self.path_for(reference)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactReferenceError(
                f"Artifact does not resolve: {reference}"
            ) from exc
        actual = hashlib.sha256(canonical_json(envelope)).hexdigest()
        if actual != reference.sha256:
            raise ArtifactReferenceError(f"Artifact hash mismatch: {reference}")
        if envelope.get("project_id") != self.project_id:
            raise ArtifactReferenceError(
                f"Artifact belongs to another project: {reference}"
            )
        if envelope.get("kind") != reference.kind:
            raise ArtifactReferenceError(f"Artifact kind mismatch: {reference}")
        return envelope
