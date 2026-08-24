"""v2.2 source-bound page decisions for ReadingDeckBlueprint review."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


PAGE_DECISIONS = frozenset(
    {"approved", "modify", "evidence", "merge-or-delete"}
)
COMMENT_REQUIRED = PAGE_DECISIONS - {"approved"}
MAX_COMMENT_CODE_POINTS = 1200


def normalize_choice(decision: object, comment: object) -> tuple[str, str]:
    choice = str(decision or "").strip()
    if choice not in PAGE_DECISIONS:
        raise ContractValidationError("PageDecision decision is invalid")
    normalized_comment = str(comment or "").strip()
    if len(normalized_comment) > MAX_COMMENT_CODE_POINTS:
        raise ContractValidationError("PageDecision comment exceeds 1200 code points")
    if choice in COMMENT_REQUIRED and not normalized_comment:
        raise ContractValidationError("PageDecision comment is required")
    if choice == "approved":
        normalized_comment = ""
    return choice, normalized_comment


def validate_page_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecision must be an object")
    choice, comment = normalize_choice(
        payload.get("decision"), payload.get("comment")
    )
    source_version = str(payload.get("source_version") or "").strip()
    source_ref = ArtifactReference.parse(source_version)
    if source_ref.kind != "reading-deck-blueprint":
        raise ContractValidationError(
            "PageDecision source_version must be a ReadingDeckBlueprint"
        )
    snapshot_ref = str(payload.get("visible_copy_snapshot_ref") or "").strip()
    snapshot = ArtifactReference.parse(snapshot_ref)
    if snapshot.kind != "content-visible-copy-snapshot":
        raise ContractValidationError(
            "PageDecision visible_copy_snapshot_ref is invalid"
        )
    required = (
        "page_decision_id",
        "review_batch_id",
        "project_id",
        "slide_id",
        "slide_title_snapshot",
        "saved_at",
    )
    normalized = {field: str(payload.get(field) or "").strip() for field in required}
    if any(not value for value in normalized.values()):
        raise ContractValidationError("PageDecision has an empty required field")
    order = payload.get("slide_order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise ContractValidationError("PageDecision slide_order is invalid")
    supersedes = str(payload.get("supersedes_decision_ref") or "").strip()
    if supersedes and ArtifactReference.parse(supersedes).kind != "content-page-decision":
        raise ContractValidationError("PageDecision supersedes_decision_ref is invalid")
    return {
        **normalized,
        "review_type": "content",
        "source_version": source_version,
        "slide_order": order,
        "visible_copy_snapshot_ref": snapshot_ref,
        "decision": choice,
        "comment": comment,
        "completed": choice == "approved" or bool(comment),
        "supersedes_decision_ref": supersedes,
    }


def validate_page_decision_set(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecisionSet must be an object")
    source_version = str(payload.get("source_version") or "").strip()
    if ArtifactReference.parse(source_version).kind != "reading-deck-blueprint":
        raise ContractValidationError("PageDecisionSet source_version is invalid")
    rows = payload.get("decision_refs")
    if not isinstance(rows, list):
        raise ContractValidationError("PageDecisionSet decision_refs is invalid")
    normalized_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ContractValidationError("PageDecisionSet row is invalid")
        slide_id = str(row.get("slide_id") or "").strip()
        decision_ref = str(row.get("decision_ref") or "").strip()
        order = row.get("slide_order")
        if (
            not slide_id
            or ArtifactReference.parse(decision_ref).kind != "content-page-decision"
            or isinstance(order, bool)
            or not isinstance(order, int)
            or order < 1
            or slide_id in seen_ids
        ):
            raise ContractValidationError("PageDecisionSet row is invalid")
        seen_ids.add(slide_id)
        normalized_rows.append(
            {
                "slide_id": slide_id,
                "slide_order": order,
                "decision_ref": decision_ref,
            }
        )
    if normalized_rows != sorted(normalized_rows, key=lambda row: row["slide_order"]):
        raise ContractValidationError("PageDecisionSet rows must follow slide order")
    status = str(payload.get("status") or "").strip()
    if status not in {"draft", "frozen"}:
        raise ContractValidationError("PageDecisionSet status is invalid")
    expected = payload.get("expected_slide_count")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
        raise ContractValidationError("PageDecisionSet expected_slide_count is invalid")
    required = ("decision_set_id", "review_batch_id", "project_id", "updated_at")
    normalized = {field: str(payload.get(field) or "").strip() for field in required}
    if any(not value for value in normalized.values()):
        raise ContractValidationError("PageDecisionSet has an empty required field")
    return {
        **normalized,
        "review_type": "content",
        "source_version": source_version,
        "expected_slide_count": expected,
        "status": status,
        "decision_refs": normalized_rows,
    }


__all__ = [
    "MAX_COMMENT_CODE_POINTS",
    "PAGE_DECISIONS",
    "normalize_choice",
    "validate_page_decision",
    "validate_page_decision_set",
]
