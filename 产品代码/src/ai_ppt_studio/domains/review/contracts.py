"""Strict contracts for one source-bound professional review session."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference

REVIEW_TYPES = frozenset({"content-full-deck", "visual-professional"})
OPEN_POLICIES = frozenset({"foreground-if-waiting", "notify-only"})
SESSION_STATUSES = frozenset({"ready", "opened", "submitted", "superseded"})
HOST_OPEN_STATUSES = frozenset({"not-requested", "opened", "failed"})
HOST_NOTIFICATION_STATUSES = frozenset({"not-requested", "sent", "failed"})
AI_RECEIPT_STATUSES = frozenset({"pending", "received", "failed"})
REQUIRED_FIELDS = frozenset(
    {
        "review_session_id",
        "review_type",
        "project_id",
        "target_artifact_ref",
        "source_version",
        "revision",
        "status",
        "open_policy",
        "host_open_status",
        "persistence_status",
        "host_notification_status",
        "ai_receipt_status",
        "created_at",
        "last_opened_at",
        "submitted_at",
    }
)
OPTIONAL_FIELDS = frozenset(
    {
        "host_open_receipt_ref",
        "host_notification_receipt_ref",
        "host_notification_receipts",
        "ai_receipt_ref",
        "ai_receipts",
        "superseded_at",
    }
)
RECEIPT_REQUIREMENTS = {
    "host_open_receipt_ref": ("host_open_status", "opened", "review-host-open-receipt"),
    "host_notification_receipt_ref": (
        "host_notification_status",
        "sent",
        "review-host-notification-receipt",
    ),
    "ai_receipt_ref": ("ai_receipt_status", "received", "review-ai-receipt"),
}
BOUND_RECEIPT_MAPS = {
    "host_notification_receipts": "review-host-notification-receipt",
    "ai_receipts": "review-ai-receipt",
}
BOUND_SAVED_ARTIFACT_KINDS = frozenset(
    {
        "visual-anchor-feedback-batch",
        "visual-contract-review-mark-set",
    }
)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _timestamp(value: object, field: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
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


def validate_review_session(
    payload: dict[str, Any], *, trusted_receipts: bool = False
) -> dict[str, Any]:
    """Validate a session; receipt-derived states require trusted service context."""

    if not isinstance(payload, dict) or not REQUIRED_FIELDS.issubset(payload):
        raise ContractValidationError("ReviewSession is missing required fields")
    if set(payload) - REQUIRED_FIELDS - OPTIONAL_FIELDS:
        raise ContractValidationError("ReviewSession contains unsupported fields")
    normalized = dict(payload)
    normalized["review_session_id"] = _text(payload, "review_session_id")
    normalized["project_id"] = _text(payload, "project_id")
    normalized["source_version"] = _text(payload, "source_version")
    review_type = _text(payload, "review_type")
    if review_type not in REVIEW_TYPES:
        raise ContractValidationError("review_type is not a professional review type")
    normalized["review_type"] = review_type
    target_ref = _text(payload, "target_artifact_ref")
    try:
        normalized["target_artifact_ref"] = str(ArtifactReference.parse(target_ref))
    except ArtifactReferenceError as error:
        raise ContractValidationError(
            "target_artifact_ref must be an artifact reference"
        ) from error
    revision = payload.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ContractValidationError("revision must be a non-negative integer")
    for field, allowed in (
        ("status", SESSION_STATUSES),
        ("open_policy", OPEN_POLICIES),
        ("host_open_status", HOST_OPEN_STATUSES),
        ("host_notification_status", HOST_NOTIFICATION_STATUSES),
        ("ai_receipt_status", AI_RECEIPT_STATUSES),
    ):
        value = _text(payload, field)
        if value not in allowed:
            raise ContractValidationError(f"Invalid ReviewSession {field}")
        normalized[field] = value
    if payload.get("persistence_status") != "saved":
        raise ContractValidationError("persistence_status must be saved")
    if not trusted_receipts and (
        normalized["status"] != "ready"
        or normalized["host_open_status"] != "not-requested"
        or normalized["host_notification_status"] != "not-requested"
        or normalized["ai_receipt_status"] != "pending"
    ):
        raise ContractValidationError("Receipt state must be service-issued")
    normalized["created_at"] = _timestamp(payload.get("created_at"), "created_at")
    normalized["last_opened_at"] = _timestamp(
        payload.get("last_opened_at"), "last_opened_at", optional=True
    )
    normalized["submitted_at"] = _timestamp(
        payload.get("submitted_at"), "submitted_at", optional=True
    )
    for field in OPTIONAL_FIELDS:
        if field not in payload:
            continue
        if field in BOUND_RECEIPT_MAPS:
            if not trusted_receipts or not isinstance(payload[field], dict):
                raise ContractValidationError(
                    f"{field} must be a trusted receipt binding map"
                )
            bindings: dict[str, str] = {}
            for saved_ref, receipt_ref in payload[field].items():
                if not isinstance(saved_ref, str) or not isinstance(receipt_ref, str):
                    raise ContractValidationError(
                        f"{field} must map artifact references to receipt references"
                    )
                try:
                    saved = ArtifactReference.parse(saved_ref.strip())
                    receipt = ArtifactReference.parse(receipt_ref.strip())
                except ArtifactReferenceError as error:
                    raise ContractValidationError(
                        f"{field} contains an invalid artifact reference"
                    ) from error
                if saved.kind not in BOUND_SAVED_ARTIFACT_KINDS:
                    raise ContractValidationError(
                        f"{field} contains an unsupported saved artifact kind"
                    )
                if receipt.kind != BOUND_RECEIPT_MAPS[field]:
                    raise ContractValidationError(
                        f"{field} contains the wrong receipt kind"
                    )
                bindings[str(saved)] = str(receipt)
            normalized[field] = bindings
            continue
        normalized[field] = (
            _timestamp(payload[field], field, optional=True)
            if field == "superseded_at"
            else _text(payload, field)
        )
        if field in RECEIPT_REQUIREMENTS:
            expected_kind = RECEIPT_REQUIREMENTS[field][2]
            try:
                reference = ArtifactReference.parse(normalized[field])
            except ArtifactReferenceError as error:
                raise ContractValidationError(
                    f"{field} must be an artifact reference"
                ) from error
            if reference.kind != expected_kind:
                raise ContractValidationError(
                    f"{field} must reference {expected_kind}"
                )
    for receipt_field, (status_field, advanced_status, _kind) in RECEIPT_REQUIREMENTS.items():
        if normalized[status_field] == advanced_status and receipt_field not in normalized:
            raise ContractValidationError(
                f"{advanced_status} {status_field} requires {receipt_field}"
            )
    if normalized["host_open_status"] == "opened" and not normalized["last_opened_at"]:
        raise ContractValidationError("opened session requires last_opened_at")
    if normalized["status"] == "submitted" and not normalized["submitted_at"]:
        raise ContractValidationError("submitted session requires submitted_at")
    if normalized["status"] == "superseded" and not normalized.get("superseded_at"):
        raise ContractValidationError("superseded session requires superseded_at")
    return normalized
