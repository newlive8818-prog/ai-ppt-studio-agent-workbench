"""Read-only projections for historical v1.6 content artifacts."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


LEGACY_CONTENT_KINDS = frozenset(
    {
        "content-framework",
        "content-blueprint",
        "content-review-record",
        "full-deck-expansion-authorization",
    }
)


def read_legacy_content(kernel: ProjectKernel, reference: str) -> dict[str, Any]:
    """Resolve one historical artifact without creating a current head."""

    parsed = ArtifactReference.parse(reference)
    if parsed.kind not in LEGACY_CONTENT_KINDS:
        raise ContractValidationError("Artifact is not a supported legacy content kind")
    return {
        "identity": "legacy-read-only",
        "legacy_ref": reference,
        "legacy_kind": parsed.kind,
        "payload": dict(kernel.artifacts.resolve(parsed)["payload"]),
        "requires_v22_migration_and_hard_gates": True,
    }


__all__ = ["LEGACY_CONTENT_KINDS", "read_legacy_content"]
