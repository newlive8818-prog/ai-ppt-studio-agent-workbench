"""Contracts for batch-wide revision plans, confirmations, and change sets."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError

PLAN_FIELDS = (
    "direct_changes",
    "cross_slide_changes",
    "merge_or_delete",
    "evidence_downgrades",
    "sequence_changes",
    "preserved",
    "conflicts",
    "rereview_scope",
)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def validate_revision_plan_payload(value: object) -> dict[str, list[Any]]:
    if not isinstance(value, dict) or set(value) != set(PLAN_FIELDS):
        raise ContractValidationError("Revision plan fields are incomplete or unknown")
    normalized = {}
    for field in PLAN_FIELDS:
        items = value[field]
        if not isinstance(items, list):
            raise ContractValidationError(f"{field} must be an array")
        normalized[field] = list(items)
    if not normalized["rereview_scope"]:
        raise ContractValidationError("rereview_scope must not be empty")
    return normalized


def validate_revision_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ContentBatchRevisionPlan must be an object")
    return {
        "plan_id": _text(payload.get("plan_id"), "plan_id"),
        "project_id": _text(payload.get("project_id"), "project_id"),
        "batch_ref": _text(payload.get("batch_ref"), "batch_ref"),
        "source_version": _text(payload.get("source_version"), "source_version"),
        "reading_blueprint_ref": _text(
            payload.get("reading_blueprint_ref"), "reading_blueprint_ref"
        ),
        "plan": validate_revision_plan_payload(payload.get("plan")),
        "status": "proposed",
        "saved_at": _text(payload.get("saved_at"), "saved_at"),
    }


__all__ = ["PLAN_FIELDS", "validate_revision_plan", "validate_revision_plan_payload"]
