"""Closed v2.2 contract for immutable full-deck review batches."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_ppt_studio.domains.content.page_decisions import DECISIONS
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


BATCH_FIELDS = (
    "batch_id",
    "project_id",
    "review_session_id",
    "source_version",
    "reading_blueprint_ref",
    "slide_ids",
    "decision_refs",
    "counts",
    "status",
    "immutable_after_submit",
    "submitted_at",
    "withdrawn_at",
    "supersedes_ref",
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ContractValidationError(f"{field} must be an array of strings")
    return [item.strip() for item in value]


def _reference(value: object, field: str, kind: str, *, optional: bool = False) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be a string")
    text = value.strip()
    if optional and not text:
        return ""
    try:
        reference = ArtifactReference.parse(text)
    except Exception as error:
        raise ContractValidationError(f"{field} must be an artifact reference") from error
    if reference.kind != kind:
        raise ContractValidationError(f"{field} must reference {kind}")
    return text


def _timestamp(value: object, field: str, *, optional: bool = False) -> str:
    if optional and isinstance(value, str) and not value.strip():
        return ""
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError(f"{field} must be an ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a timezone")
    return text


def validate_content_review_batch(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ContentReviewBatch must be an object")
    if set(payload) != set(BATCH_FIELDS):
        raise ContractValidationError("ContentReviewBatch fields are not closed")
    status = _text(payload.get("status"), "status")
    if status not in {"submitted", "withdrawn"}:
        raise ContractValidationError("ContentReviewBatch status is invalid")
    slide_ids = _strings(payload.get("slide_ids"), "slide_ids")
    decision_refs = _strings(payload.get("decision_refs"), "decision_refs")
    if not slide_ids or len(slide_ids) != len(decision_refs):
        raise ContractValidationError("Batch must bind one decision per slide")
    if len(set(slide_ids)) != len(slide_ids) or len(set(decision_refs)) != len(decision_refs):
        raise ContractValidationError("Batch slide and decision identities must be unique")
    for reference in decision_refs:
        _reference(reference, "decision_refs", "content-page-decision")
    counts = payload.get("counts")
    if not isinstance(counts, dict) or set(counts) != DECISIONS:
        raise ContractValidationError("Batch counts must cover all decisions")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ContractValidationError("Batch counts must be non-negative integers")
    if sum(counts.values()) != len(slide_ids):
        raise ContractValidationError("Batch counts do not match slide count")
    if payload.get("immutable_after_submit") is not True:
        raise ContractValidationError("immutable_after_submit must be true")
    submitted_at = _timestamp(payload.get("submitted_at"), "submitted_at")
    withdrawn_at = _timestamp(
        payload.get("withdrawn_at"), "withdrawn_at", optional=True
    )
    supersedes_ref = _reference(
        payload.get("supersedes_ref"),
        "supersedes_ref",
        "content-review-batch",
        optional=True,
    )
    if status == "submitted" and withdrawn_at:
        raise ContractValidationError("submitted batch cannot have withdrawn_at")
    if status == "withdrawn" and (not withdrawn_at or not supersedes_ref):
        raise ContractValidationError(
            "withdrawn batch requires withdrawn_at and supersedes_ref"
        )
    return {
        "batch_id": _text(payload.get("batch_id"), "batch_id"),
        "project_id": _text(payload.get("project_id"), "project_id"),
        "review_session_id": _text(
            payload.get("review_session_id"), "review_session_id"
        ),
        "source_version": _text(
            payload.get("source_version"), "source_version"
        ),
        "reading_blueprint_ref": _reference(
            payload.get("reading_blueprint_ref"),
            "reading_blueprint_ref",
            "reading-deck-blueprint",
        ),
        "slide_ids": slide_ids,
        "decision_refs": decision_refs,
        "counts": dict(counts),
        "status": status,
        "immutable_after_submit": True,
        "submitted_at": submitted_at,
        "withdrawn_at": withdrawn_at,
        "supersedes_ref": supersedes_ref,
    }


__all__ = ["validate_content_review_batch"]
