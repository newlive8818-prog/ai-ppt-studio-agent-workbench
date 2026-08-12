"""Validated v1.6 MissionDraft and MissionConfirmation payloads."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError

REQUIRED_FIELDS = (
    "topic",
    "primary_audience",
    "desired_judgment_or_action",
)


MATERIAL_MODES = frozenset(
    {"materials-provided", "no-materials-confirmed"}
)


def validate_mission_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize an AI-authored draft without ever creating confirmation."""

    if not isinstance(payload, dict):
        raise ContractValidationError("MissionDraft must be an object")
    invalid = [
        field
        for field in REQUIRED_FIELDS
        if field in payload and not isinstance(payload.get(field), str)
    ]
    if invalid:
        raise ContractValidationError(
            f"MissionDraft fields must be strings: {', '.join(invalid)}"
        )
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not isinstance(payload.get(field), str) or not payload[field].strip()
    ]
    normalized = dict(payload)
    for field in REQUIRED_FIELDS:
        if isinstance(payload.get(field), str):
            normalized[field] = str(payload[field]).strip()
    return {
        **normalized,
        "status": "draft" if missing else "confirmable",
        "missing_required_fields": missing,
    }


def validate_mission_confirmation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one explicit, immutable user confirmation record."""

    if not isinstance(payload, dict):
        raise ContractValidationError("MissionConfirmation must be an object")
    draft_ref = str(payload.get("mission_draft_ref") or "").strip()
    material_mode = str(payload.get("material_mode") or "").strip()
    user_action_ref = str(payload.get("user_action_ref") or "").strip()
    user_message_ref = str(payload.get("user_message_ref") or "").strip()
    confirmed_at = str(payload.get("confirmed_at") or "").strip()
    if not draft_ref:
        raise ContractValidationError(
            "MissionConfirmation requires mission_draft_ref"
        )
    if material_mode not in MATERIAL_MODES:
        raise ContractValidationError(
            "MissionConfirmation material_mode is invalid"
        )
    if not user_action_ref and not user_message_ref:
        raise ContractValidationError(
            "MissionConfirmation requires a real user action or message reference"
        )
    try:
        revision = int(payload["revision"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "MissionConfirmation requires a non-negative revision"
        ) from exc
    if revision < 0 or not confirmed_at:
        raise ContractValidationError(
            "MissionConfirmation requires revision and confirmed_at"
        )
    normalized = {
        **payload,
        "mission_draft_ref": draft_ref,
        "material_mode": material_mode,
        "user_action_ref": user_action_ref,
        "user_message_ref": user_message_ref,
        "revision": revision,
        "confirmed_at": confirmed_at,
        "status": "confirmed",
    }
    if material_mode == "materials-provided":
        material_ref = str(payload.get("material_inventory_ref") or "").strip()
        if not material_ref:
            raise ContractValidationError(
                "materials-provided confirmation requires material_inventory_ref"
            )
        normalized["material_inventory_ref"] = material_ref
        normalized.pop("empty_material_identity", None)
    else:
        empty_identity = str(payload.get("empty_material_identity") or "").strip()
        if not empty_identity:
            raise ContractValidationError(
                "no-materials-confirmed requires empty_material_identity"
            )
        normalized["empty_material_identity"] = empty_identity
        normalized.pop("material_inventory_ref", None)
    return normalized


def validate_mission(payload: dict[str, Any]) -> dict[str, Any]:
    """Compatibility alias while callers migrate to MissionDraft naming."""

    return validate_mission_draft(payload)
