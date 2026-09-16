"""Pure validators for reading historical v1.6 framework artifacts."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ContractValidationError


_FORBIDDEN = frozenset(
    {"slides", "slide_titles", "visible_copy", "speaker_notes", "materials"}
)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(payload: dict[str, Any], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ContractValidationError(f"{field} must be a non-empty string array")
    return [item.strip() for item in value]


def validate_legacy_framework_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate old data without granting any current write authority."""

    if not isinstance(payload, dict):
        raise ContractValidationError("FrameworkDraft must be an object")
    if _FORBIDDEN.intersection(payload):
        raise ContractValidationError("FrameworkDraft cannot contain slide-level content")
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or not chapters or any(
        not isinstance(chapter, dict) for chapter in chapters
    ):
        raise ContractValidationError("chapters must be a non-empty object array")
    status = _text(payload, "status")
    if status != "discussion":
        raise ContractValidationError("FrameworkDraft status must be discussion")
    return {
        "framework_id": _text(payload, "framework_id"),
        "mission_confirmation_ref": _text(payload, "mission_confirmation_ref"),
        "core_proposition": _text(payload, "core_proposition"),
        "persuasion_path": _strings(payload, "persuasion_path"),
        "chapters": [
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
            for chapter in chapters
        ],
        "structural_risks": _strings(payload, "structural_risks"),
        "highest_impact_question": _text(payload, "highest_impact_question"),
        "status": status,
    }


__all__ = ["validate_legacy_framework_draft"]
