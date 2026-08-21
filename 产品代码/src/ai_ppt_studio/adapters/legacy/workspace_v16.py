"""Read-only historical workspace projection adapter."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def project_legacy_workspace(kernel: ProjectKernel) -> dict[str, Any]:
    """Expose legacy heads for history screens without restoring five spaces."""

    state = kernel.load()
    heads = {
        slot: reference
        for slot, reference in state.artifact_heads.items()
        if slot.startswith("content/")
        and ArtifactReference.parse(reference).kind
        in {"content-framework", "content-blueprint", "content-review-record"}
    }
    return {
        "identity": "legacy-read-only",
        "project_id": state.project_id,
        "revision": state.revision,
        "historical_heads": heads,
    }


__all__ = ["project_legacy_workspace"]
