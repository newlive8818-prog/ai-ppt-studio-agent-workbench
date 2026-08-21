"""Strict v2.2 contracts for reusable content and visual experience."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any

from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


LAYERS = frozenset({"same-type", "global"})
DOMAINS = frozenset({"content", "visual"})
RESULT_TYPES = frozenset({"mechanism", "anti-pattern", "preference"})
STATUSES = frozenset({"active", "disabled", "retired"})
OUTCOMES = frozenset({"success", "mixed", "failure"})

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{2,127}$")
_FORBIDDEN_FIELDS = frozenset(
    {
        "client_name",
        "customer_name",
        "customer_metric",
        "client_fact",
        "customer_fact",
        "logo_ref",
        "screenshot_ref",
        "image_ref",
        "whole_page_design_ref",
        "gate_override",
        "permission_override",
        "product_policy",
    }
)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperienceValidationError(f"{label} must be an object")
    return dict(value)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ExperienceValidationError(f"{field} must be non-empty text")
    return value.strip()


def _identifier(payload: dict[str, Any], field: str) -> str:
    value = _text(payload, field)
    if not _IDENTIFIER.fullmatch(value):
        raise ExperienceValidationError(f"{field} is invalid")
    return value


def _choice(payload: dict[str, Any], field: str, allowed: frozenset[str]) -> str:
    value = _text(payload, field)
    if value not in allowed:
        raise ExperienceValidationError(
            f"{field} must be one of {', '.join(sorted(allowed))}"
        )
    return value


def _integer(payload: dict[str, Any], field: str, *, minimum: int = 0) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ExperienceValidationError(f"{field} must be an integer >= {minimum}")
    return value


def _strings(
    payload: dict[str, Any], field: str, *, required: bool = False
) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ExperienceValidationError(f"{field} must be a text array")
    normalized = [item.strip() for item in value]
    if required and not normalized:
        raise ExperienceValidationError(f"{field} cannot be empty")
    if len(normalized) != len(set(normalized)):
        raise ExperienceValidationError(f"{field} must contain unique values")
    return normalized


def _artifact_refs(
    payload: dict[str, Any], field: str, *, required: bool = False
) -> list[str]:
    values = _strings(payload, field, required=required)
    try:
        for value in values:
            ArtifactReference.parse(value)
    except Exception as error:
        raise ExperienceValidationError(
            f"{field} must contain artifact references"
        ) from error
    return values


def _artifact_ref(payload: dict[str, Any], field: str) -> str:
    value = _text(payload, field)
    try:
        ArtifactReference.parse(value)
    except Exception as error:
        raise ExperienceValidationError(
            f"{field} must be an artifact reference"
        ) from error
    return value


def _timestamp(payload: dict[str, Any], field: str) -> str:
    value = _text(payload, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExperienceValidationError(f"{field} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise ExperienceValidationError(f"{field} must include a timezone")
    return value


def _reject_forbidden_fields(value: object, path: str = "experience") -> None:
    if isinstance(value, dict):
        forbidden = _FORBIDDEN_FIELDS.intersection(value)
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise ExperienceValidationError(
                f"{path} contains forbidden reusable data: {names}"
            )
        for key, nested in value.items():
            _reject_forbidden_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_fields(nested, f"{path}[{index}]")


def _applicability(payload: dict[str, Any]) -> dict[str, list[str]]:
    value = _object(payload.get("applicability"), "applicability")
    allowed = {"scenes", "audiences", "slide_tasks", "conditions"}
    if set(value) != allowed:
        raise ExperienceValidationError(
            "applicability must contain scenes, audiences, slide_tasks, and conditions"
        )
    return {
        field: _strings(value, field, required=True)
        for field in ("scenes", "audiences", "slide_tasks", "conditions")
    }


def _privacy(payload: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload.get("privacy"), "privacy")
    expected = {
        "contains_client_identifiers": False,
        "contains_client_facts": False,
        "contains_client_assets": False,
        "reuse_scope": "mechanism-only",
    }
    if value != expected:
        raise ExperienceValidationError(
            "privacy must explicitly exclude client identifiers, facts, and assets"
        )
    return expected


def _before_after(payload: dict[str, Any]) -> list[dict[str, str]]:
    values = payload.get("before_after_refs")
    if not isinstance(values, list) or not values:
        raise ExperienceValidationError("before_after_refs cannot be empty")
    normalized: list[dict[str, str]] = []
    for value in values:
        item = _object(value, "before_after_refs item")
        if set(item) != {"before_ref", "after_ref"}:
            raise ExperienceValidationError(
                "before_after_refs items require before_ref and after_ref"
            )
        before_ref = _artifact_ref(item, "before_ref")
        after_ref = _artifact_ref(item, "after_ref")
        if before_ref == after_ref:
            raise ExperienceValidationError(
                "before_ref and after_ref must identify different artifacts"
            )
        normalized.append({"before_ref": before_ref, "after_ref": after_ref})
    return normalized


def _user_outcomes(payload: dict[str, Any]) -> list[dict[str, str]]:
    values = payload.get("user_outcomes")
    if not isinstance(values, list) or not values:
        raise ExperienceValidationError("user_outcomes cannot be empty")
    normalized: list[dict[str, str]] = []
    for value in values:
        item = _object(value, "user_outcomes item")
        outcome = _text(item, "outcome")
        if outcome not in {"accepted", "rejected", "continued-feedback"}:
            raise ExperienceValidationError("user outcome is invalid")
        normalized.append(
            {
                "project_id": _text(item, "project_id"),
                "type_signature": _text(item, "type_signature"),
                "outcome": outcome,
                "evidence_ref": _text(item, "evidence_ref"),
            }
        )
    return normalized


def _optional_version(payload: dict[str, Any], field: str) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ExperienceValidationError(f"{field} must be null or a positive integer")
    return value


def _optional_artifact_ref(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExperienceValidationError(f"{field} must be null or an artifact reference")
    try:
        ArtifactReference.parse(value)
    except Exception as error:
        raise ExperienceValidationError(
            f"{field} must be null or an artifact reference"
        ) from error
    return value


def validate_experience_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the only writable reusable-experience model in v2.2."""

    value = _object(payload, "ExperienceItem")
    _reject_forbidden_fields(value)
    if value.get("sanitized_for_reuse") is not True:
        raise ExperienceValidationError("sanitized_for_reuse must be true")
    previous_version = _optional_version(value, "previous_version")
    previous_ref = _optional_artifact_ref(value, "previous_version_ref")
    if (previous_version is None) != (previous_ref is None):
        raise ExperienceValidationError(
            "previous_version and previous_version_ref must be present together"
        )
    directive_ref = value.get("user_global_directive_ref")
    if directive_ref is not None and (
        not isinstance(directive_ref, str) or not directive_ref.strip()
    ):
        raise ExperienceValidationError(
            "user_global_directive_ref must be null or non-empty text"
        )
    return {
        **deepcopy(value),
        "experience_id": _identifier(value, "experience_id"),
        "version": _integer(value, "version", minimum=1),
        "layer": _choice(value, "layer", LAYERS),
        "domain": _choice(value, "domain", DOMAINS),
        "result_type": _choice(value, "result_type", RESULT_TYPES),
        "mechanism": _text(value, "mechanism"),
        "type_signature": _text(value, "type_signature"),
        "applicability": _applicability(value),
        "counterexamples": _strings(value, "counterexamples"),
        "failure_boundaries": _strings(value, "failure_boundaries", required=True),
        "source_project_ids": _strings(value, "source_project_ids", required=True),
        "source_refs": _artifact_refs(value, "source_refs", required=True),
        "before_after_refs": _before_after(value),
        "hard_gate_refs": _artifact_refs(value, "hard_gate_refs", required=True),
        "user_outcomes": _user_outcomes(value),
        "application_count": _integer(value, "application_count"),
        "success_type_signatures": _strings(
            value, "success_type_signatures"
        ),
        "failure_type_signatures": _strings(
            value, "failure_type_signatures"
        ),
        "excluded_type_signatures": _strings(
            value, "excluded_type_signatures"
        ),
        "sanitized_for_reuse": True,
        "privacy": _privacy(value),
        "status": _choice(value, "status", STATUSES),
        "previous_version": previous_version,
        "previous_version_ref": previous_ref,
        "rollback_from_version": _optional_version(
            value, "rollback_from_version"
        ),
        "user_global_directive_ref": directive_ref,
        "updated_at": _timestamp(value, "updated_at"),
    }


def validate_experience_application(payload: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "ExperienceApplication")
    _reject_forbidden_fields(value)
    context = _object(value.get("context"), "context")
    conditions = _strings(context, "conditions", required=True)
    return {
        **deepcopy(value),
        "application_id": _identifier(value, "application_id"),
        "experience_ref": _artifact_ref(value, "experience_ref"),
        "experience_id": _identifier(value, "experience_id"),
        "experience_version": _integer(value, "experience_version", minimum=1),
        "domain": _choice(value, "domain", DOMAINS),
        "experience_layer": _choice(value, "experience_layer", LAYERS),
        "source_type_signature": _text(value, "source_type_signature"),
        "target_project_id": _text(value, "target_project_id"),
        "target_type_signature": _text(value, "target_type_signature"),
        "context": {**deepcopy(context), "conditions": conditions},
        "evidence_refs": _artifact_refs(value, "evidence_refs", required=True),
        "explicit_validation": bool(value.get("explicit_validation", False)),
        "status": "applied"
        if value.get("status") == "applied"
        else _raise("status must be applied"),
        "applied_at": _timestamp(value, "applied_at"),
    }


def validate_experience_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    value = _object(payload, "ExperienceOutcome")
    _reject_forbidden_fields(value)
    return {
        **deepcopy(value),
        "outcome_id": _identifier(value, "outcome_id"),
        "application_ref": _artifact_ref(value, "application_ref"),
        "application_id": _identifier(value, "application_id"),
        "experience_ref": _artifact_ref(value, "experience_ref"),
        "experience_id": _identifier(value, "experience_id"),
        "experience_version": _integer(value, "experience_version", minimum=1),
        "domain": _choice(value, "domain", DOMAINS),
        "experience_layer": _choice(value, "experience_layer", LAYERS),
        "target_project_id": _text(value, "target_project_id"),
        "target_type_signature": _text(value, "target_type_signature"),
        "outcome": _choice(value, "outcome", OUTCOMES),
        "user_outcome_ref": _text(value, "user_outcome_ref"),
        "hard_gate_refs": _artifact_refs(value, "hard_gate_refs", required=True),
        "evidence_refs": _artifact_refs(value, "evidence_refs", required=True),
        "evaluated_at": _timestamp(value, "evaluated_at"),
    }


def _raise(message: str) -> Any:
    raise ExperienceValidationError(message)


__all__ = [
    "DOMAINS",
    "LAYERS",
    "OUTCOMES",
    "RESULT_TYPES",
    "STATUSES",
    "validate_experience_application",
    "validate_experience_item",
    "validate_experience_outcome",
]
