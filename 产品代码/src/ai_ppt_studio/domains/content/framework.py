"""Contracts for framework-first content discussion and deck expansion."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError


FRAMEWORK_FORBIDDEN_FIELDS = frozenset(
    {"slides", "slide_titles", "visible_copy", "speaker_notes", "materials"}
)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractValidationError(f"{field} must be a positive integer")
    return value


def _strings(
    payload: dict[str, Any], field: str, *, allow_empty: bool = False
) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or (not allow_empty and not value) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        qualifier = "" if allow_empty else "non-empty "
        raise ContractValidationError(f"{field} must be a {qualifier}string array")
    return [item.strip() for item in value]


def validate_framework_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate discussion-level structure without permitting page content."""

    if not isinstance(payload, dict):
        raise ContractValidationError("FrameworkDraft must be an object")
    if FRAMEWORK_FORBIDDEN_FIELDS.intersection(payload):
        raise ContractValidationError(
            "FrameworkDraft cannot contain slide-level content"
        )
    normalized = {
        "framework_id": _text(payload, "framework_id"),
        "mission_confirmation_ref": _text(payload, "mission_confirmation_ref"),
        "core_proposition": _text(payload, "core_proposition"),
        "persuasion_path": _strings(payload, "persuasion_path"),
    }
    raw_chapters = payload.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters or any(
        not isinstance(chapter, dict) for chapter in raw_chapters
    ):
        raise ContractValidationError("chapters must be a non-empty object array")
    normalized["chapters"] = [
        {
            field: _text(chapter, field)
            for field in (
                "chapter_id",
                "title",
                "task",
                "expected_judgment",
                "transition",
            )
        }
        for chapter in raw_chapters
    ]
    normalized["structural_risks"] = _strings(payload, "structural_risks")
    normalized["highest_impact_question"] = _text(
        payload, "highest_impact_question"
    )
    status = _text(payload, "status")
    if status != "discussion":
        raise ContractValidationError("FrameworkDraft status must be discussion")
    normalized["status"] = status
    return normalized


def _validate_binding(
    payload: dict[str, Any],
    *,
    name: str,
    extra: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError(f"{name} must be an object")
    normalized = {
        "project_id": _text(payload, "project_id"),
        "framework_ref": _text(payload, "framework_ref"),
    }
    for field in extra:
        normalized[field] = _text(payload, field)
    normalized["framework_revision"] = _positive_int(
        payload, "framework_revision"
    )
    normalized["challenge_identity"] = _text(payload, "challenge_identity")
    normalized["confirmed_at"] = _text(payload, "confirmed_at")
    return normalized


def validate_framework_confirmation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a confirmation bound to one exact project framework revision."""

    return _validate_binding(payload, name="FrameworkConfirmation")


def validate_full_deck_expansion_authorization(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate expansion consent bound to its exact confirmed framework."""

    return _validate_binding(
        payload,
        name="FullDeckExpansionAuthorization",
        extra=("framework_confirmation_ref",),
    )
