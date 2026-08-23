"""Pure validation for authoritative content and visual review sessions."""

from __future__ import annotations

import copy
from typing import Any

from ai_ppt_studio.errors import ContractValidationError


REVIEW_TYPES = frozenset({"content-full-deck", "visual-professional"})
SESSION_STATUSES = frozenset(
    {"preparing", "ready", "opened", "submitted", "superseded", "expired"}
)
OPEN_POLICIES = frozenset({"foreground-if-waiting", "notify-only"})
HOST_OPEN_STATUSES = frozenset(
    {"not-requested", "pending", "opened", "failed", "unavailable"}
)
PERSISTENCE_STATUSES = frozenset({"saving", "saved", "failed"})
HOST_NOTIFICATION_STATUSES = frozenset(
    {"not-requested", "pending", "sent", "failed", "unavailable"}
)
AI_RECEIPT_STATUSES = frozenset(
    {"pending", "received", "rejected", "unverified"}
)


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ContractValidationError(f"ReviewSession {field} is required")
    return value


def _enum(
    payload: dict[str, Any], field: str, allowed: frozenset[str]
) -> str:
    value = _required_text(payload, field)
    if value not in allowed:
        raise ContractValidationError(f"ReviewSession {field} is invalid")
    return value


def validate_review_session(
    payload: dict[str, Any], *, current_revision: int | None = None
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ReviewSession must be an object")
    normalized = copy.deepcopy(payload)
    for field in (
        "review_session_id",
        "project_id",
        "target_artifact_ref",
        "source_version",
        "created_at",
    ):
        normalized[field] = _required_text(normalized, field)
    normalized["review_type"] = _enum(
        normalized, "review_type", REVIEW_TYPES
    )
    normalized["status"] = _enum(
        normalized, "status", SESSION_STATUSES
    )
    normalized["open_policy"] = _enum(
        normalized, "open_policy", OPEN_POLICIES
    )
    normalized["host_open_status"] = _enum(
        normalized, "host_open_status", HOST_OPEN_STATUSES
    )
    normalized["persistence_status"] = _enum(
        normalized, "persistence_status", PERSISTENCE_STATUSES
    )
    normalized["host_notification_status"] = _enum(
        normalized,
        "host_notification_status",
        HOST_NOTIFICATION_STATUSES,
    )
    normalized["ai_receipt_status"] = _enum(
        normalized, "ai_receipt_status", AI_RECEIPT_STATUSES
    )
    revision = normalized.get("revision")
    if (
        not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 0
    ):
        raise ContractValidationError(
            "ReviewSession revision must be a non-negative integer"
        )
    if current_revision is not None and revision > current_revision:
        raise ContractValidationError(
            "ReviewSession revision cannot be in the future"
        )
    for field in ("last_opened_at", "submitted_at"):
        if normalized.get(field) is not None and not str(
            normalized[field]
        ).strip():
            raise ContractValidationError(
                f"ReviewSession {field} is invalid"
            )
    return normalized


def review_session_identity(
    payload: dict[str, Any],
) -> tuple[str, str, str, str, int]:
    normalized = validate_review_session(payload)
    return (
        normalized["project_id"],
        normalized["review_type"],
        normalized["target_artifact_ref"],
        normalized["source_version"],
        normalized["revision"],
    )
