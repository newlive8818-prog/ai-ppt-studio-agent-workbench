"""Closed v2.2 contracts for per-slide content-review decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference

DECISIONS = frozenset({"approved", "modify", "evidence", "merge-or-delete"})
MAX_COMMENT_CODEPOINTS = 1200
PAGE_DECISION_FIELDS = (
    "page_decision_id",
    "project_id",
    "review_session_id",
    "source_version",
    "reading_blueprint_ref",
    "slide_id",
    "slide_order",
    "slide_title_snapshot",
    "decision",
    "comment",
    "status",
    "saved_at",
    "supersedes_decision_ref",
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


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


def _timestamp(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError(f"{field} must be an ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a timezone")
    return text


def normalize_decision(decision: object, comment: object) -> tuple[str, str]:
    choice = _text(decision, "decision")
    if choice not in DECISIONS:
        raise ContractValidationError("decision is not a supported PageDecision")
    if not isinstance(comment, str):
        raise ContractValidationError("comment must be a string")
    note = comment.strip()
    if choice != "approved" and not note:
        raise ContractValidationError("Non-approved decisions require a comment")
    if len(note) > MAX_COMMENT_CODEPOINTS:
        raise ContractValidationError("comment exceeds 1200 Unicode code points")
    return choice, "" if choice == "approved" else note


def validate_page_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecision must be an object")
    if set(payload) != set(PAGE_DECISION_FIELDS):
        raise ContractValidationError("PageDecision fields are not closed")
    choice, comment = normalize_decision(
        payload.get("decision"), payload.get("comment")
    )
    order = payload.get("slide_order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise ContractValidationError("slide_order must be a positive integer")
    status = _text(payload.get("status"), "status")
    if status != "completed":
        raise ContractValidationError("PageDecision status must be completed")
    return {
        "page_decision_id": _text(
            payload.get("page_decision_id"), "page_decision_id"
        ),
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
        "slide_id": _text(payload.get("slide_id"), "slide_id"),
        "slide_order": order,
        "slide_title_snapshot": _text(
            payload.get("slide_title_snapshot"), "slide_title_snapshot"
        ),
        "decision": choice,
        "comment": comment,
        "status": status,
        "saved_at": _timestamp(payload.get("saved_at"), "saved_at"),
        "supersedes_decision_ref": _reference(
            payload.get("supersedes_decision_ref"),
            "supersedes_decision_ref",
            "content-page-decision",
            optional=True,
        ),
    }


__all__ = ["DECISIONS", "MAX_COMMENT_CODEPOINTS", "normalize_decision", "validate_page_decision"]
