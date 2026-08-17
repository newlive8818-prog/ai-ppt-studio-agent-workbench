"""Minimal shared guards for exact immutable artifact identities."""

from __future__ import annotations

from ai_ppt_studio.errors import ArtifactReferenceError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


class VisualReviewEvidenceError(ArtifactReferenceError):
    """Identify the exact applicable check evidence that broke target lineage."""

    def __init__(self, message: str, *, check_index: int, evidence_index: int):
        self.check_index = check_index
        self.evidence_index = evidence_index
        super().__init__(message)


def resolve_kind(kernel: ProjectKernel, value: str, kind: str) -> dict:
    reference = ArtifactReference.parse(value)
    if reference.kind != kind:
        raise ArtifactReferenceError(
            f"Expected artifact kind {kind}, got {reference.kind}"
        )
    return kernel.artifacts.resolve(reference)


def require_exact_ref(
    kernel: ProjectKernel, value: str, slot: str, kind: str
) -> dict:
    if kernel.load().artifact_heads.get(slot) != value:
        raise ArtifactReferenceError(
            f"Artifact reference is not the current {slot} head: {value}"
        )
    return resolve_kind(kernel, value, kind)


def require_visual_review_target_evidence(
    kernel: ProjectKernel,
    review: dict,
    *,
    expected_target_ref: str,
    expected_target_kind: str,
) -> None:
    """Require each applicable review check to cite its exact current target."""

    if review.get("target_ref") != expected_target_ref:
        raise VisualReviewEvidenceError(
            "Visual review target does not match the current review target",
            check_index=-1,
            evidence_index=-1,
        )
    try:
        resolve_kind(kernel, expected_target_ref, expected_target_kind)
    except Exception as error:
        raise VisualReviewEvidenceError(
            "Visual review target cannot be resolved with its required kind",
            check_index=-1,
            evidence_index=-1,
        ) from error
    for check_index, check in enumerate(review.get("checks") or []):
        if check.get("applicability") != "applicable":
            continue
        evidence_refs = check.get("evidence_refs")
        if evidence_refs != [expected_target_ref]:
            raise VisualReviewEvidenceError(
                "Applicable visual review evidence must exactly bind its current target",
                check_index=check_index,
                evidence_index=0,
            )
        for evidence_index, reference in enumerate(evidence_refs):
            try:
                resolve_kind(kernel, reference, expected_target_kind)
            except Exception as error:
                raise VisualReviewEvidenceError(
                    "Visual review evidence cannot be resolved with the target kind",
                    check_index=check_index,
                    evidence_index=evidence_index,
                ) from error


def require_revision(kernel: ProjectKernel, expected_revision: int) -> KernelState:
    state = kernel.load()
    if state.revision != expected_revision:
        raise RevisionConflictError(expected_revision, state.revision)
    return state


__all__ = [
    "VisualReviewEvidenceError",
    "require_exact_ref",
    "require_revision",
    "require_visual_review_target_evidence",
    "resolve_kind",
]
