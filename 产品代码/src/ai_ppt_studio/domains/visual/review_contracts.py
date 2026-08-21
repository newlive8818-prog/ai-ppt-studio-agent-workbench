"""v2.2 contracts for visual professional-review feedback."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import ContractValidationError

MIN_REGION_SIZE = 0.02


def _text(value: object, field: str, *, optional: bool = False) -> str:
    if optional and (value is None or value == ""):
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _revision(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractValidationError("revision must be a non-negative integer")
    return value


def _timestamp(value: object, field: str) -> tuple[str, datetime]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError(
            f"{field} must be an ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a timezone")
    return text, parsed


def _rectangle(value: object) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise ContractValidationError("normalized_region must be a closed rectangle")
    result = {}
    for field in ("x", "y", "width", "height"):
        coordinate = value[field]
        if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
            raise ContractValidationError("normalized_region values must be numbers")
        if not math.isfinite(coordinate):
            raise ContractValidationError("normalized_region values must be finite")
        result[field] = float(coordinate)
    if (
        result["x"] < 0
        or result["y"] < 0
        or result["width"] < MIN_REGION_SIZE
        or result["height"] < MIN_REGION_SIZE
        or result["x"] + result["width"] > 1
        or result["y"] + result["height"] > 1
    ):
        raise ContractValidationError("normalized_region is outside perceptible bounds")
    return result


def validate_anchor_region_feedback(
    payload: dict[str, Any],
    *,
    created_not_after: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("AnchorRegionFeedback must be an object")
    order = payload.get("order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        raise ContractValidationError("order must be a positive integer")
    created_at, created_at_value = _timestamp(payload.get("created_at"), "created_at")
    created_by = _text(payload.get("created_by"), "created_by")
    if created_by != "user":
        raise ContractValidationError("created_by must be user")
    if created_not_after is not None:
        if (
            created_not_after.tzinfo is None
            or created_not_after.utcoffset() is None
        ):
            raise ContractValidationError("created_not_after must include a timezone")
        if created_at_value > created_not_after:
            raise ContractValidationError("created_at cannot be in the future")
    return {
        "feedback_id": _text(payload.get("feedback_id"), "feedback_id"),
        "anchor_slide_id": _text(payload.get("anchor_slide_id"), "anchor_slide_id"),
        "anchor_artifact_ref": _text(payload.get("anchor_artifact_ref"), "anchor_artifact_ref"),
        "normalized_region": _rectangle(payload.get("normalized_region")),
        "comment": _text(payload.get("comment"), "comment"),
        "order": order,
        "visual_source_version": _text(payload.get("visual_source_version"), "visual_source_version"),
        "revision": _revision(payload.get("revision")),
        "created_at": created_at,
        "created_by": created_by,
    }


def validate_anchor_feedback_batch(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("AnchorFeedbackBatch must be an object")
    submitted_at, submitted_at_value = _timestamp(
        payload.get("submitted_at"), "submitted_at"
    )
    submitted_by = _text(payload.get("submitted_by"), "submitted_by")
    if submitted_by != "user":
        raise ContractValidationError("submitted_by must be user")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ContractValidationError("AnchorFeedbackBatch cannot be empty")
    items = [
        validate_anchor_region_feedback(
            item,
            created_not_after=submitted_at_value,
        )
        for item in raw_items
    ]
    orders = [item["order"] for item in items]
    if orders != list(range(1, len(items) + 1)):
        raise ContractValidationError("Anchor feedback order must be contiguous")
    if len({item["feedback_id"] for item in items}) != len(items):
        raise ContractValidationError("Anchor feedback ids must be unique")
    if payload.get("immutable_after_submit") is not True:
        raise ContractValidationError("Submitted AnchorFeedbackBatch must be immutable")
    return {
        "batch_id": _text(payload.get("batch_id"), "batch_id"),
        "project_id": _text(payload.get("project_id"), "project_id"),
        "review_session_id": _text(payload.get("review_session_id"), "review_session_id"),
        "visual_contract_ref": _text(payload.get("visual_contract_ref"), "visual_contract_ref"),
        "deck_design_system_ref": _text(payload.get("deck_design_system_ref"), "deck_design_system_ref"),
        "anchor_slide_set_ref": _text(payload.get("anchor_slide_set_ref"), "anchor_slide_set_ref"),
        "items": items,
        "source_version": _text(payload.get("source_version"), "source_version"),
        "revision": _revision(payload.get("revision")),
        "persistence_status": _status(payload.get("persistence_status"), "persistence_status", {"saved"}),
        "host_notification_status": _status(payload.get("host_notification_status"), "host_notification_status", {"not-requested", "pending", "sent", "failed", "unavailable"}),
        "ai_receipt_status": _status(payload.get("ai_receipt_status"), "ai_receipt_status", {"pending", "received", "rejected", "unverified"}),
        "immutable_after_submit": True,
        "submitted_at": submitted_at,
        "submitted_by": submitted_by,
    }


def _status(value: object, field: str, allowed: set[str]) -> str:
    status = _text(value, field)
    if status not in allowed:
        raise ContractValidationError(f"{field} is invalid")
    return status


def validate_visual_contract_review_mark(
    payload: dict[str, Any],
    *,
    created_not_after: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("VisualContractReviewMark must be an object")
    target_type = _status(payload.get("target_type"), "target_type", {"contract-field", "text-range"})
    target_key = _text(payload.get("target_key"), "target_key")
    selected_text = _text(payload.get("selected_text"), "selected_text", optional=True)
    if target_type == "text-range" and not selected_text:
        raise ContractValidationError("text-range marks require selected_text")
    slide_id = _text(payload.get("slide_id"), "slide_id", optional=True)
    deck_section_id = _text(payload.get("deck_section_id"), "deck_section_id", optional=True)
    if bool(slide_id) == bool(deck_section_id):
        raise ContractValidationError(
            "A contract mark needs exactly one slide or deck section"
        )
    created_at, created_at_value = _timestamp(payload.get("created_at"), "created_at")
    created_by = _text(payload.get("created_by"), "created_by")
    if created_by != "user":
        raise ContractValidationError("created_by must be user")
    if created_not_after is not None:
        if (
            created_not_after.tzinfo is None
            or created_not_after.utcoffset() is None
        ):
            raise ContractValidationError("created_not_after must include a timezone")
        if created_at_value > created_not_after:
            raise ContractValidationError("created_at cannot be in the future")
    return {
        "mark_id": _text(payload.get("mark_id"), "mark_id"),
        "target_type": target_type,
        "slide_id": slide_id,
        "deck_section_id": deck_section_id,
        "target_key": target_key,
        "selected_text": selected_text,
        "context_before": _text(payload.get("context_before"), "context_before", optional=True),
        "context_after": _text(payload.get("context_after"), "context_after", optional=True),
        "comment": _text(payload.get("comment"), "comment"),
        "visual_contract_ref": _text(payload.get("visual_contract_ref"), "visual_contract_ref"),
        "source_version": _text(payload.get("source_version"), "source_version"),
        "revision": _revision(payload.get("revision")),
        "created_at": created_at,
        "created_by": created_by,
    }


def validate_visual_contract_review_mark_set(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("VisualContractReviewMarkSet must be an object")
    raw_marks = payload.get("marks")
    if not isinstance(raw_marks, list) or not raw_marks:
        raise ContractValidationError("VisualContractReviewMarkSet cannot be empty")
    saved_at, saved_at_value = _timestamp(payload.get("saved_at"), "saved_at")
    marks = [
        validate_visual_contract_review_mark(
            mark,
            created_not_after=saved_at_value,
        )
        for mark in raw_marks
    ]
    if len({mark["mark_id"] for mark in marks}) != len(marks):
        raise ContractValidationError("Visual contract mark ids must be unique")
    return {
        "mark_set_id": _text(payload.get("mark_set_id"), "mark_set_id"),
        "project_id": _text(payload.get("project_id"), "project_id"),
        "review_session_id": _text(payload.get("review_session_id"), "review_session_id"),
        "visual_contract_ref": _text(payload.get("visual_contract_ref"), "visual_contract_ref"),
        "source_version": _text(payload.get("source_version"), "source_version"),
        "revision": _revision(payload.get("revision")),
        "marks": marks,
        "persistence_status": _status(payload.get("persistence_status"), "persistence_status", {"saved"}),
        "host_notification_status": _status(payload.get("host_notification_status"), "host_notification_status", {"not-requested", "pending", "sent", "failed", "unavailable"}),
        "ai_receipt_status": _status(payload.get("ai_receipt_status"), "ai_receipt_status", {"pending", "received", "rejected", "unverified"}),
        "saved_at": saved_at,
    }


__all__ = [
    "MIN_REGION_SIZE",
    "validate_anchor_feedback_batch",
    "validate_anchor_region_feedback",
    "validate_visual_contract_review_mark",
    "validate_visual_contract_review_mark_set",
]
