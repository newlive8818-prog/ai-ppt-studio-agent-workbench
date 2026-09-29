"""Authorized gate mutations for the schema 3.0 kernel."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_ppt_studio.errors import GateMutationError
from ai_ppt_studio.kernel.references import ArtifactReference

_AUTHORITY = object()
_GATES = frozenset({"G0", "G1", "G2", "G3", "G4"})
_STATUSES = frozenset(
    {
        "open",
        "locked",
        "running",
        "failed",
        "delivery-ready",
        "user-reviewable",
        "passed",
    }
)


@dataclass(frozen=True)
class GateMutation:
    """A GateEvaluator-authorized transition plus its formal evidence."""

    updates: dict[str, str]
    evidence_refs: tuple[str, ...]
    authority: object = field(repr=False, compare=False)


def issue_gate_mutation(
    updates: dict[str, str], evidence_refs: tuple[str, ...]
) -> GateMutation:
    """Issue a validated mutation for application GateEvaluator code."""

    if not updates or any(gate not in _GATES for gate in updates):
        raise GateMutationError("Gate mutation contains an unknown or empty gate")
    if any(status not in _STATUSES for status in updates.values()):
        raise GateMutationError("Gate mutation contains an invalid status")
    for value in evidence_refs:
        ArtifactReference.parse(value)
    return GateMutation(dict(updates), tuple(evidence_refs), _AUTHORITY)


def validate_gate_mutation(value: object) -> GateMutation:
    """Reject direct dictionaries and instances not issued by this module."""

    if not isinstance(value, GateMutation) or value.authority is not _AUTHORITY:
        raise GateMutationError("Gate status can only be changed by GateEvaluator")
    return value
