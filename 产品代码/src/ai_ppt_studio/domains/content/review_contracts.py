"""Strict contracts for independent content-page review decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ContentWorkflowError,
)
from ai_ppt_studio.kernel.references import ArtifactReference


CONTENT_PAGE_DECISIONS = (
    "approved",
    "modify",
    "evidence",
    "merge-or-delete",
)
COMMENT_REQUIRED_DECISIONS = frozenset(CONTENT_PAGE_DECISIONS[1:])
MAX_PAGE_DECISION_COMMENT_CODE_POINTS = 1200

_PAGE_DECISION_FIELDS = frozenset(
    {
        "page_decision_id",
        "review_batch_id",
        "project_id",
        "review_type",
        "source_version",
        "slide_id",
        "slide_order",
        "slide_title_snapshot",
        "visible_copy_snapshot_ref",
        "decision",
        "comment",
        "completed",
        "saved_at",
        "supersedes_decision_ref",
    }
)
_PAGE_DECISION_SET_FIELDS = frozenset(
    {
        "decision_set_id",
        "review_batch_id",
        "project_id",
        "review_type",
        "source_version",
        "expected_slide_count",
        "status",
        "decision_refs",
        "updated_at",
    }
)


def _nonempty_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field, "")
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be a string")
    return value.strip()


def _positive_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractValidationError(f"{field} must be a positive integer")
    return value


def _artifact_ref(value: str, *, field: str, kind: str) -> str:
    try:
        reference = ArtifactReference.parse(value)
    except ArtifactReferenceError as error:
        raise ContractValidationError(
            f"{field} must be a valid {kind} artifact reference"
        ) from error
    if reference.kind != kind:
        raise ContractValidationError(
            f"{field} must reference artifact kind {kind}"
        )
    return str(reference)


def _timestamp(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be an ISO-8601 timestamp")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError(
            f"{field} must be an ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a timezone")
    return text


def normalize_page_decision_choice(
    decision: object,
    comment: object,
) -> tuple[str, str]:
    """Normalize the only four choices and their exact comment semantics."""

    if not isinstance(decision, str) or decision not in CONTENT_PAGE_DECISIONS:
        raise ContractValidationError(
            "decision must be one of approved, modify, evidence, "
            "merge-or-delete"
        )
    if decision == "approved":
        return decision, ""
    if not isinstance(comment, str):
        raise ContractValidationError("comment must be a string")
    normalized_comment = comment.strip()
    if decision in COMMENT_REQUIRED_DECISIONS and not normalized_comment:
        raise ContentWorkflowError(
            "CONTENT_PAGE_COMMENT_REQUIRED",
            "CONTENT_PAGE_COMMENT_REQUIRED: "
            f"{decision} requires a non-empty saved comment",
            {"decision": decision},
        )
    if len(normalized_comment) > MAX_PAGE_DECISION_COMMENT_CODE_POINTS:
        raise ContractValidationError(
            "comment cannot exceed 1200 Unicode code points"
        )
    return decision, normalized_comment


def validate_page_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical immutable PageDecision payload."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecision must be an object")
    unknown = set(payload) - _PAGE_DECISION_FIELDS
    if unknown:
        raise ContractValidationError(
            "PageDecision contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    decision, comment = normalize_page_decision_choice(
        payload.get("decision"), payload.get("comment", "")
    )
    review_type = _nonempty_text(payload, "review_type")
    if review_type != "content":
        raise ContractValidationError("review_type must be content")
    source_version = _artifact_ref(
        _nonempty_text(payload, "source_version"),
        field="source_version",
        kind="content-blueprint",
    )
    snapshot_ref = _artifact_ref(
        _nonempty_text(payload, "visible_copy_snapshot_ref"),
        field="visible_copy_snapshot_ref",
        kind="content-visible-copy-snapshot",
    )
    supersedes = _optional_text(payload, "supersedes_decision_ref")
    if supersedes:
        supersedes = _artifact_ref(
            supersedes,
            field="supersedes_decision_ref",
            kind="content-page-decision",
        )
    completed = decision == "approved" or bool(comment)
    supplied_completed = payload.get("completed", completed)
    if not isinstance(supplied_completed, bool) or supplied_completed != completed:
        raise ContractValidationError(
            "completed must exactly match the normalized decision and comment"
        )
    return {
        "page_decision_id": _nonempty_text(payload, "page_decision_id"),
        "review_batch_id": _nonempty_text(payload, "review_batch_id"),
        "project_id": _nonempty_text(payload, "project_id"),
        "review_type": "content",
        "source_version": source_version,
        "slide_id": _nonempty_text(payload, "slide_id"),
        "slide_order": _positive_int(payload, "slide_order"),
        "slide_title_snapshot": _nonempty_text(
            payload, "slide_title_snapshot"
        ),
        "visible_copy_snapshot_ref": snapshot_ref,
        "decision": decision,
        "comment": comment,
        "completed": completed,
        "saved_at": _timestamp(payload.get("saved_at"), field="saved_at"),
        "supersedes_decision_ref": supersedes,
    }


def validate_page_decision_set(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the source-bound aggregate of current page decisions."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecisionSet must be an object")
    unknown = set(payload) - _PAGE_DECISION_SET_FIELDS
    if unknown:
        raise ContractValidationError(
            "PageDecisionSet contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    review_type = _nonempty_text(payload, "review_type")
    if review_type != "content":
        raise ContractValidationError("review_type must be content")
    status = _nonempty_text(payload, "status")
    if status not in {"draft", "frozen"}:
        raise ContractValidationError(
            "PageDecisionSet status must be draft or frozen"
        )
    expected_slide_count = _positive_int(payload, "expected_slide_count")
    raw_refs = payload.get("decision_refs")
    if not isinstance(raw_refs, list):
        raise ContractValidationError("decision_refs must be a list")
    decision_refs: list[dict[str, Any]] = []
    seen_slides: set[str] = set()
    seen_orders: set[int] = set()
    seen_refs: set[str] = set()
    previous_order = 0
    for raw in raw_refs:
        if not isinstance(raw, dict) or set(raw) != {
            "slide_id",
            "slide_order",
            "decision_ref",
        }:
            raise ContractValidationError(
                "Each decision_refs item must contain only slide_id, "
                "slide_order, and decision_ref"
            )
        slide_id = _nonempty_text(raw, "slide_id")
        slide_order = _positive_int(raw, "slide_order")
        decision_ref = _artifact_ref(
            _nonempty_text(raw, "decision_ref"),
            field="decision_ref",
            kind="content-page-decision",
        )
        if (
            slide_id in seen_slides
            or slide_order in seen_orders
            or decision_ref in seen_refs
        ):
            raise ContractValidationError(
                "PageDecisionSet decision refs must be unique"
            )
        if slide_order <= previous_order:
            raise ContractValidationError(
                "PageDecisionSet decision refs must follow slide order"
            )
        seen_slides.add(slide_id)
        seen_orders.add(slide_order)
        seen_refs.add(decision_ref)
        previous_order = slide_order
        decision_refs.append(
            {
                "slide_id": slide_id,
                "slide_order": slide_order,
                "decision_ref": decision_ref,
            }
        )
    if len(decision_refs) > expected_slide_count:
        raise ContractValidationError(
            "decision_refs cannot exceed expected_slide_count"
        )
    return {
        "decision_set_id": _nonempty_text(payload, "decision_set_id"),
        "review_batch_id": _nonempty_text(payload, "review_batch_id"),
        "project_id": _nonempty_text(payload, "project_id"),
        "review_type": "content",
        "source_version": _artifact_ref(
            _nonempty_text(payload, "source_version"),
            field="source_version",
            kind="content-blueprint",
        ),
        "expected_slide_count": expected_slide_count,
        "status": status,
        "decision_refs": decision_refs,
        "updated_at": _timestamp(
            payload.get("updated_at"), field="updated_at"
        ),
    }
