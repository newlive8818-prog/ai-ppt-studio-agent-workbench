"""Small exact-source guards shared only by content-review services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_content_hard_gate_record,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.domains.content.page_decisions import validate_page_decision
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.application.artifact_guards import require_exact_ref
from ai_ppt_studio.application.review_commands import fingerprint, replay_ref, stable_id
from ai_ppt_studio.application.review_session_service import (
    authoritative_target_publication_revision,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


@dataclass(frozen=True)
class ContentReviewContext:
    state: KernelState
    blueprint_ref: str
    blueprint: dict[str, Any]
    acceptance_ref: str
    acceptance: dict[str, Any]
    session_ref: str
    session: dict[str, Any]


class DecisionLineageMismatchError(ContractValidationError):
    """A valid PageDecision belongs to a different authoritative slide."""


CONTENT_ACCEPTANCE_FIELDS = {
    "source_version",
    "reading_blueprint_ref",
    "evidence_gate_ref",
    "presales_reading_gate_ref",
    "overall_result",
    "accepted_at",
}


def validate_content_acceptance(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the closed current acceptance authority used by review paths."""

    if not isinstance(value, dict) or set(value) != CONTENT_ACCEPTANCE_FIELDS:
        raise ContractValidationError("Content acceptance fields are not closed")
    normalized = dict(value)
    for field in ("source_version", "accepted_at"):
        if not isinstance(normalized.get(field), str) or not normalized[field].strip():
            raise ContractValidationError(f"Content acceptance {field} is invalid")
        normalized[field] = normalized[field].strip()
    reference_kinds = {
        "reading_blueprint_ref": "reading-deck-blueprint",
        "evidence_gate_ref": "content-hard-gate-record",
        "presales_reading_gate_ref": "content-hard-gate-record",
    }
    for field, kind in reference_kinds.items():
        try:
            reference = ArtifactReference.parse(str(normalized.get(field) or ""))
        except Exception as error:
            raise ContractValidationError(
                f"Content acceptance {field} is invalid"
            ) from error
        if reference.kind != kind:
            raise ContractValidationError(
                f"Content acceptance {field} must reference {kind}"
            )
        normalized[field] = str(reference)
    if normalized.get("overall_result") != "passed":
        raise ContractValidationError("Content acceptance must be passed")
    try:
        accepted_at = datetime.fromisoformat(
            normalized["accepted_at"].replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ContractValidationError(
            "Content acceptance accepted_at must be an ISO timestamp"
        ) from error
    if accepted_at.tzinfo is None or accepted_at.utcoffset() is None:
        raise ContractValidationError(
            "Content acceptance accepted_at must include a timezone"
        )
    return normalized


def payload(kernel: ProjectKernel, reference: str, kind: str) -> dict[str, Any]:
    try:
        parsed = ArtifactReference.parse(reference)
        if parsed.kind != kind:
            raise ContractValidationError(f"Expected artifact kind {kind}")
        value = kernel.artifacts.resolve(parsed).get("payload")
    except Exception as error:
        if isinstance(error, ContractValidationError):
            raise
        raise ContractValidationError(f"Cannot resolve current {kind}") from error
    if not isinstance(value, dict):
        raise ContractValidationError(f"{kind} payload must be an object")
    return dict(value)


def decision_lineage(
    kernel: ProjectKernel,
    reference: str,
    expected_identity: dict[str, Any],
) -> dict[str, Any]:
    """Validate the current PageDecision and every immutable predecessor."""

    seen: set[str] = set()
    head: dict[str, Any] | None = None
    while reference:
        if reference in seen:
            raise ContractValidationError("PageDecision lineage contains a cycle")
        seen.add(reference)
        decision = validate_page_decision(
            payload(kernel, reference, "content-page-decision")
        )
        if any(
            decision.get(field) != value
            for field, value in expected_identity.items()
        ):
            raise DecisionLineageMismatchError(
                "PageDecision lineage does not match its authoritative slide"
            )
        head = head or decision
        reference = decision["supersedes_decision_ref"]
    if head is None:
        raise ContractValidationError("PageDecision lineage is empty")
    return head


def review_context(
    kernel: ProjectKernel,
    review_session_id: str,
    *,
    source_version: str | None = None,
    expected_revision: int | None = None,
) -> ContentReviewContext:
    state = kernel.load()
    if expected_revision is not None and state.revision != expected_revision:
        raise RevisionConflictError(expected_revision, state.revision)
    blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
    blueprint = validate_reading_deck_blueprint(
        payload(kernel, blueprint_ref, "reading-deck-blueprint")
    )
    if source_version is not None and source_version != blueprint["source_version"]:
        raise ReviewSourceStaleError(source_version, blueprint["source_version"])

    upstream = (
        (
            "evidence_book_ref",
            "content/evidence-book",
            "presales-evidence-book",
            validate_presales_evidence_book,
        ),
        (
            "decision_context_ref",
            "content/decision-context",
            "customer-decision-context",
            validate_customer_decision_context,
        ),
        (
            "problem_solution_fit_ref",
            "content/problem-solution-fit",
            "problem-solution-fit-map",
            validate_problem_solution_fit_map,
        ),
    )
    validated_upstream = {}
    try:
        for field, slot, kind, validator in upstream:
            envelope = require_exact_ref(kernel, blueprint[field], slot, kind)
            validated_upstream[field] = validator(envelope.get("payload"))
    except ArtifactReferenceError as error:
        raise ContractValidationError(
            "ReadingDeckBlueprint does not bind the current content chain"
        ) from error
    evidence = validated_upstream["evidence_book_ref"]
    decision_context = validated_upstream["decision_context_ref"]
    fit_map = validated_upstream["problem_solution_fit_ref"]
    if (
        evidence["material_mode"] != blueprint["material_mode"]
        or decision_context["evidence_book_ref"] != blueprint["evidence_book_ref"]
        or fit_map["evidence_book_ref"] != blueprint["evidence_book_ref"]
        or fit_map["decision_context_ref"] != blueprint["decision_context_ref"]
    ):
        raise ContractValidationError(
            "ReadingDeckBlueprint upstream lineage is inconsistent"
        )

    gate_refs = {
        "evidence": state.artifact_heads.get("content/gate/evidence", ""),
        "presales-reading": state.artifact_heads.get(
            "content/gate/presales-reading", ""
        ),
    }
    gates = {}
    for gate_type, reference in gate_refs.items():
        if not reference:
            raise GateBlockedError(
                "content-review", (f"current-{gate_type}-gate-not-passed",)
            )
        gate = validate_content_hard_gate_record(
            payload(kernel, reference, "content-hard-gate-record")
        )
        if (
            gate["gate_type"] != gate_type
            or gate["overall_result"] != "passed"
            or gate["input_source_version"] != blueprint["source_version"]
            or gate["input_hash"] != ArtifactReference.parse(blueprint_ref).sha256
        ):
            raise GateBlockedError(
                "content-review", (f"current-{gate_type}-gate-not-passed",)
            )
        gates[gate_type] = gate

    acceptance_ref = state.artifact_heads.get("content/acceptance", "")
    if not acceptance_ref:
        raise GateBlockedError("content-review", ("current-content-acceptance",))
    acceptance = validate_content_acceptance(
        payload(kernel, acceptance_ref, "content-acceptance")
    )
    expected_acceptance = {
        "source_version": blueprint["source_version"],
        "reading_blueprint_ref": blueprint_ref,
        "evidence_gate_ref": gate_refs["evidence"],
        "presales_reading_gate_ref": gate_refs["presales-reading"],
        "overall_result": "passed",
    }
    if any(acceptance.get(key) != value for key, value in expected_acceptance.items()):
        raise GateBlockedError("content-review", ("current-content-acceptance",))

    session_ref = state.review_session_ref("content-full-deck")
    session = validate_review_session(
        payload(kernel, session_ref, "review-session"), trusted_receipts=True
    )
    if (
        session["review_session_id"] != review_session_id
        or session["review_type"] != "content-full-deck"
        or session["target_artifact_ref"] != blueprint_ref
        or session["source_version"] != blueprint["source_version"]
        or session["status"] in {"superseded", "expired"}
    ):
        raise ReviewSourceStaleError(
            str(review_session_id), str(session.get("review_session_id") or "")
        )
    authoritative_revision = authoritative_target_publication_revision(
        kernel, state, "content-full-deck", blueprint_ref
    )
    if session["revision"] != authoritative_revision:
        raise ReviewSourceStaleError(
            str(session["revision"]), str(authoritative_revision)
        )
    return ContentReviewContext(
        state, blueprint_ref, blueprint, acceptance_ref, acceptance, session_ref, session
    )


__all__ = [
    "ContentReviewContext",
    "DecisionLineageMismatchError",
    "decision_lineage",
    "fingerprint",
    "payload",
    "replay_ref",
    "review_context",
    "stable_id",
    "validate_content_acceptance",
]
