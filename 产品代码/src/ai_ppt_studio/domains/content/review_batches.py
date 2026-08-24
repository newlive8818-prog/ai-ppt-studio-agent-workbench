"""Pure v2.2 contracts for immutable ReadingDeckBlueprint review batches."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


REVIEW_BATCH_KIND = "content-review-batch"
REVIEW_BATCH_STATUS = "submitted"
SUBMISSION_SCOPE = "content-review-batch-submission"


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ContractValidationError(f"ContentReviewBatch {field} is required")
    return value


def _reference(payload: dict[str, Any], field: str, kind: str) -> str:
    value = _required_text(payload, field)
    if ArtifactReference.parse(value).kind != kind:
        raise ContractValidationError(
            f"ContentReviewBatch {field} must be a {kind} reference"
        )
    return value


def _refs(payload: dict[str, Any], field: str, kind: str) -> list[str]:
    values = payload.get(field)
    if not isinstance(values, list) or not values:
        raise ContractValidationError(f"ContentReviewBatch {field} is invalid")
    normalized: list[str] = []
    for value in values:
        reference = str(value or "").strip()
        if ArtifactReference.parse(reference).kind != kind:
            raise ContractValidationError(
                f"ContentReviewBatch {field} contains an invalid reference"
            )
        normalized.append(reference)
    if len(set(normalized)) != len(normalized):
        raise ContractValidationError(
            f"ContentReviewBatch {field} cannot contain duplicates"
        )
    return normalized


def validate_content_review_batch(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one submitted v2.2 whole-deck decision batch."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ContentReviewBatch must be an object")
    source_version = _reference(
        payload, "source_version", "reading-deck-blueprint"
    )
    decision_set_ref = _reference(
        payload, "decision_set_ref", "content-page-decision-set"
    )
    decision_refs = _refs(payload, "decision_refs", "content-page-decision")
    page_snapshot_refs = _refs(
        payload, "page_snapshot_refs", "content-visible-copy-snapshot"
    )
    expected_slide_count = payload.get("expected_slide_count")
    if (
        isinstance(expected_slide_count, bool)
        or not isinstance(expected_slide_count, int)
        or expected_slide_count < 1
        or expected_slide_count != len(decision_refs)
        or expected_slide_count != len(page_snapshot_refs)
    ):
        raise ContractValidationError(
            "ContentReviewBatch expected_slide_count is inconsistent"
        )
    counts = payload.get("counts")
    required_counts = {
        "approved",
        "modify",
        "evidence",
        "merge_or_delete",
    }
    if (
        not isinstance(counts, dict)
        or set(counts) != required_counts
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts.values()
        )
        or sum(counts.values()) != expected_slide_count
    ):
        raise ContractValidationError("ContentReviewBatch counts are invalid")
    if _required_text(payload, "review_type") != "content":
        raise ContractValidationError("ContentReviewBatch review_type is invalid")
    if _required_text(payload, "status") != REVIEW_BATCH_STATUS:
        raise ContractValidationError("ContentReviewBatch status is invalid")
    batch_id = _required_text(payload, "review_batch_id")
    scope_kind = _required_text(payload, "scope_kind")
    scope_id = _required_text(payload, "scope_id")
    if scope_kind != SUBMISSION_SCOPE or scope_id != f"{batch_id}:{source_version}":
        raise ContractValidationError("ContentReviewBatch submission scope is invalid")
    identity_type = _required_text(payload, "confirmation_identity_type")
    action_ref = str(payload.get("user_action_ref") or "").strip()
    message_ref = str(payload.get("user_message_ref") or "").strip()
    if (
        identity_type not in {"host-action", "verified-message"}
        or (identity_type == "host-action" and (not action_ref or message_ref))
        or (identity_type == "verified-message" and (not message_ref or action_ref))
    ):
        raise ContractValidationError("ContentReviewBatch confirmation identity is invalid")
    submitted_by = _required_text(payload, "submitted_by")
    if submitted_by != action_ref and submitted_by != message_ref:
        raise ContractValidationError("ContentReviewBatch submitted_by is invalid")
    for field in (
        "project_id",
        "submitted_at",
        "challenge_id",
        "host_assertion_sha256",
        "confirmed_at",
    ):
        _required_text(payload, field)
    challenge_revision = payload.get("challenge_revision")
    if (
        isinstance(challenge_revision, bool)
        or not isinstance(challenge_revision, int)
        or challenge_revision < 0
    ):
        raise ContractValidationError(
            "ContentReviewBatch challenge_revision is invalid"
        )
    supersedes_ref = str(payload.get("supersedes_ref") or "").strip()
    if supersedes_ref and ArtifactReference.parse(supersedes_ref).kind != REVIEW_BATCH_KIND:
        raise ContractValidationError("ContentReviewBatch supersedes_ref is invalid")
    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise ContractValidationError("ContentReviewBatch evidence_refs are invalid")
    if str(evidence_refs[0] or "").strip() != source_version:
        raise ContractValidationError(
            "ContentReviewBatch evidence_refs must start with source_version"
        )
    return {
        "review_batch_id": batch_id,
        "project_id": _required_text(payload, "project_id"),
        "review_type": "content",
        "source_version": source_version,
        "decision_set_ref": decision_set_ref,
        "page_snapshot_refs": page_snapshot_refs,
        "decision_refs": decision_refs,
        "expected_slide_count": expected_slide_count,
        "counts": dict(counts),
        "status": REVIEW_BATCH_STATUS,
        "submitted_at": _required_text(payload, "submitted_at"),
        "submitted_by": submitted_by,
        "supersedes_ref": supersedes_ref,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "evidence_refs": [str(value).strip() for value in evidence_refs],
        "challenge_id": _required_text(payload, "challenge_id"),
        "challenge_revision": challenge_revision,
        "user_action_ref": action_ref,
        "user_message_ref": message_ref,
        "confirmation_identity_type": identity_type,
        "host_assertion_sha256": _required_text(
            payload, "host_assertion_sha256"
        ),
        "confirmed_at": _required_text(payload, "confirmed_at"),
    }


__all__ = [
    "REVIEW_BATCH_KIND",
    "REVIEW_BATCH_STATUS",
    "SUBMISSION_SCOPE",
    "validate_content_review_batch",
]
