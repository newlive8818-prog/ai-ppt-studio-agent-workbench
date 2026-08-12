"""Strict contracts for schema 3 experience intake and learning results."""

from __future__ import annotations

import re
from typing import Any

from ai_ppt_studio.errors import ExperienceValidationError

INTAKE_SOURCE_TYPES = frozenset(
    {
        "governed-feedback",
        "preferred-example",
        "reference-example",
        "accepted-delivery",
        "rejected-delivery",
        "internal-review-failure",
        "engineering-degradation",
    }
)
RESULT_TYPES = frozenset(
    {
        "preference-signal",
        "professional-mechanism-candidate",
        "anti-pattern-candidate",
    }
)
FORBIDDEN_SCORE_FIELDS = frozenset(
    {
        "score",
        "rating",
        "average",
        "weight",
        "weighted_score",
        "vote",
        "conditional_pass",
    }
)
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{2,79}$")


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ExperienceValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _identifier(payload: dict[str, Any], field: str) -> str:
    value = _text(payload, field)
    if not IDENTIFIER.fullmatch(value):
        raise ExperienceValidationError(
            f"{field} must be a lowercase stable identifier"
        )
    return value


def _strings(payload: dict[str, Any], field: str) -> list[str]:
    values = payload.get(field)
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ExperienceValidationError(
            f"{field} must be a non-empty string array"
        )
    normalized = [value.strip() for value in values]
    if len(set(normalized)) != len(normalized):
        raise ExperienceValidationError(f"{field} cannot contain duplicates")
    return normalized


def _version(payload: dict[str, Any]) -> int:
    value = payload.get("version")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ExperienceValidationError("version must be a positive integer")
    return value


def _reject_scores(payload: dict[str, Any]) -> None:
    forbidden = FORBIDDEN_SCORE_FIELDS.intersection(payload)
    if forbidden:
        raise ExperienceValidationError(
            "Experience artifacts cannot contain score fields: "
            + ", ".join(sorted(forbidden))
        )


def _sanitized_privacy_boundary(payload: dict[str, Any]) -> str:
    value = _text(payload, "privacy_boundary")
    if not value.startswith("sanitized-no-client-identifiers"):
        raise ExperienceValidationError(
            "Learning results require a sanitized privacy boundary without client identifiers"
        )
    return value


def validate_experience_intake(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceIntake must be an object")
    _reject_scores(payload)
    source_type = _text(payload, "source_type")
    if source_type not in INTAKE_SOURCE_TYPES:
        raise ExperienceValidationError(f"Unsupported intake source type: {source_type}")
    if payload.get("execution_status") != "source-registered":
        raise ExperienceValidationError(
            "ExperienceIntake execution_status must be source-registered"
        )
    if payload.get("learning_status") != "intake-only":
        raise ExperienceValidationError(
            "ExperienceIntake cannot claim candidate, personal, or stable learning status"
        )
    return {
        **payload,
        "intake_id": _identifier(payload, "intake_id"),
        "source_type": source_type,
        "source_project_id": _text(payload, "source_project_id"),
        "source_version": _text(payload, "source_version"),
        "source_refs": _strings(payload, "source_refs"),
        "target_refs": _strings(payload, "target_refs"),
        "evidence_refs": _strings(payload, "evidence_refs"),
        "privacy_boundary": _text(payload, "privacy_boundary"),
        "user_label": _text(payload, "user_label"),
        "execution_status": "source-registered",
        "learning_status": "intake-only",
    }


def _learning_result_common(
    payload: dict[str, Any], expected_type: str
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("Learning result must be an object")
    _reject_scores(payload)
    if payload.get("result_type") != expected_type:
        raise ExperienceValidationError(
            f"result_type must be {expected_type}"
        )
    if payload.get("whole_case_copy") is True:
        raise ExperienceValidationError(
            "A whole case cannot be copied as one experience rule"
        )
    if payload.get("status") in {"personal", "stable", "published"}:
        raise ExperienceValidationError(
            "A learning result cannot claim personal or stable status"
        )
    return {
        **payload,
        "result_type": expected_type,
        "result_id": _identifier(payload, "result_id"),
        "intake_ref": _text(payload, "intake_ref"),
        "source_refs": _strings(payload, "source_refs"),
        "version": _version(payload),
        "status": "candidate",
    }


def validate_preference_signal(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _learning_result_common(payload, "preference-signal")
    direction = _text(payload, "positive_or_negative")
    if direction not in {"positive", "negative"}:
        raise ExperienceValidationError(
            "positive_or_negative must be positive or negative"
        )
    normalized.update(
        {
            "positive_or_negative": direction,
            "preference_statement": _text(payload, "preference_statement"),
            "scope": _text(payload, "scope"),
            "conditions": _strings(payload, "conditions"),
            "counterexamples": _strings(payload, "counterexamples"),
            "confidence_inputs": _strings(payload, "confidence_inputs"),
        }
    )
    return normalized


def validate_professional_mechanism_candidate(
    payload: dict[str, Any]
) -> dict[str, Any]:
    normalized = _learning_result_common(
        payload, "professional-mechanism-candidate"
    )
    normalized.update(
        {
            "mechanism": _text(payload, "mechanism"),
            "scenes": _strings(payload, "scenes"),
            "audiences": _strings(payload, "audiences"),
            "slide_tasks": _strings(payload, "slide_tasks"),
            "conditions": _strings(payload, "conditions"),
            "evidence_refs": _strings(payload, "evidence_refs"),
            "counterexamples": _strings(payload, "counterexamples"),
            "failure_conditions": _strings(payload, "failure_conditions"),
            "privacy_boundary": _sanitized_privacy_boundary(payload),
            "whole_case_copy": False,
        }
    )
    return normalized


def validate_anti_pattern_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _learning_result_common(payload, "anti-pattern-candidate")
    normalized.update(
        {
            "pattern": _text(payload, "pattern"),
            "symptoms": _strings(payload, "symptoms"),
            "root_causes": _strings(payload, "root_causes"),
            "scopes": _strings(payload, "scopes"),
            "negative_evidence_refs": _strings(
                payload, "negative_evidence_refs"
            ),
            "repair_mechanisms": _strings(payload, "repair_mechanisms"),
            "exceptions": _strings(payload, "exceptions"),
            "privacy_boundary": _sanitized_privacy_boundary(payload),
            "whole_case_copy": False,
        }
    )
    return normalized


def validate_learning_result(payload: dict[str, Any]) -> dict[str, Any]:
    result_type = str(payload.get("result_type") or "") if isinstance(payload, dict) else ""
    validators = {
        "preference-signal": validate_preference_signal,
        "professional-mechanism-candidate": validate_professional_mechanism_candidate,
        "anti-pattern-candidate": validate_anti_pattern_candidate,
    }
    validator = validators.get(result_type)
    if validator is None:
        raise ExperienceValidationError(f"Unsupported learning result type: {result_type}")
    return validator(payload)


def validate_qualified_selection(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError(
            "QualifiedExperienceSelection must be an object"
        )
    _reject_scores(payload)
    option_refs = _strings(payload, "option_refs")
    results = payload.get("qualification_results")
    if not isinstance(results, list) or len(results) != len(option_refs):
        raise ExperienceValidationError(
            "qualification_results must cover every option once in order"
        )
    normalized_results: list[dict[str, str]] = []
    gates = (
        "fact_result",
        "content_result",
        "aesthetic_result",
        "engineering_result",
    )
    for option_ref, item in zip(option_refs, results, strict=True):
        if not isinstance(item, dict):
            raise ExperienceValidationError(
                "Each qualification result must be an object"
            )
        _reject_scores(item)
        if item.get("option_ref") != option_ref:
            raise ExperienceValidationError(
                "Qualification result order must match option_refs"
            )
        normalized = {"option_ref": option_ref}
        for gate in gates:
            if item.get(gate) != "passed":
                raise ExperienceValidationError(
                    "Preference selection requires every applicable professional gate to pass"
                )
            normalized[gate] = "passed"
        normalized_results.append(normalized)
    preference_refs = _strings(payload, "preference_signal_refs")
    selected = _text(payload, "selected_option_ref")
    if selected not in option_refs:
        raise ExperienceValidationError(
            "selected_option_ref must be one of the qualified options"
        )
    return {
        **payload,
        "option_refs": option_refs,
        "qualification_results": normalized_results,
        "preference_signal_refs": preference_refs,
        "selected_option_ref": selected,
        "selection_reason": _text(payload, "selection_reason"),
        "qualification_status": "passed",
    }


def validate_role_specific_slice(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError(
            "RoleSpecificExperienceSlice must be an object"
        )
    _reject_scores(payload)
    entries = payload.get("experience_entries")
    if not isinstance(entries, list):
        raise ExperienceValidationError("experience_entries must be an array")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ExperienceValidationError(
                "Role slice entries must be objects"
            )
        for field in (
            "experience_ref",
            "result_type",
            "scope",
        ):
            _text(entry, field)
        _strings(entry, "source_refs")
        _strings(entry, "match_reasons")
        if not isinstance(entry.get("application_outcomes"), list):
            raise ExperienceValidationError(
                "application_outcomes must be an array"
            )
        _version(entry)
    target_context = payload.get("target_context")
    if not isinstance(target_context, dict):
        raise ExperienceValidationError("target_context must be an object")
    for field in ("scene", "audience", "slide_task"):
        _text(target_context, field)
    _strings(target_context, "conditions")
    excluded = payload.get("excluded_experience_refs")
    if not isinstance(excluded, list) or any(
        not isinstance(value, str) or not value for value in excluded
    ):
        raise ExperienceValidationError(
            "excluded_experience_refs must be an artifact reference array"
        )
    return {
        **payload,
        "target_role_id": _text(payload, "target_role_id"),
        "target_role_display_name": _text(
            payload, "target_role_display_name"
        ),
        "task_type": _text(payload, "task_type"),
        "target_context": dict(target_context),
        "experience_entries": list(entries),
        "excluded_experience_refs": list(excluded),
        "compiled_at": _text(payload, "compiled_at"),
    }


def _target_context(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("target_context")
    if not isinstance(value, dict):
        raise ExperienceValidationError("target_context must be an object")
    return {
        "scene": _text(value, "scene"),
        "audience": _text(value, "audience"),
        "slide_task": _text(value, "slide_task"),
        "conditions": _strings(value, "conditions"),
    }


def validate_experience_candidate(
    payload: dict[str, Any], learning_result: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceCandidate must be an object")
    _reject_scores(payload)
    result_type = learning_result.get("result_type")
    if result_type not in {
        "professional-mechanism-candidate",
        "anti-pattern-candidate",
    }:
        raise ExperienceValidationError(
            "Only a professional mechanism or anti-pattern can become an experience candidate"
        )
    if payload.get("level") != "candidate" or payload.get("version") != 1:
        raise ExperienceValidationError(
            "New experience candidates start at candidate level and version 1"
        )
    applicability = {
        "scenes": list(learning_result.get("scenes") or []),
        "audiences": list(learning_result.get("audiences") or []),
        "slide_tasks": list(learning_result.get("slide_tasks") or []),
        "conditions": list(learning_result.get("conditions") or []),
        "scopes": list(learning_result.get("scopes") or []),
    }
    return {
        **payload,
        "candidate_id": _identifier(payload, "candidate_id"),
        "learning_result_ref": _text(payload, "learning_result_ref"),
        "result_type": result_type,
        "source_refs": list(learning_result.get("source_refs") or []),
        "applicability": applicability,
        "counterexamples": list(learning_result.get("counterexamples") or []),
        "failure_conditions": list(
            learning_result.get("failure_conditions") or []
        ),
        "version": 1,
        "level": "candidate",
        "enabled": True,
    }


def validate_experience_application(
    payload: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceApplication must be an object")
    _reject_scores(payload)
    if payload.get("candidate_ref") is None:
        raise ExperienceValidationError("candidate_ref is required")
    context = _target_context(payload)
    applicability = candidate.get("applicability") or {}
    required_fields = {
        "scene": applicability.get("scenes") or [],
        "audience": applicability.get("audiences") or [],
        "slide_task": applicability.get("slide_tasks") or [],
    }
    for field, allowed in required_fields.items():
        if allowed and context[field] not in allowed:
            raise ExperienceValidationError(
                f"Experience application {field} does not match candidate scope"
            )
    if not set(applicability.get("conditions") or []).issubset(
        set(context["conditions"])
    ):
        raise ExperienceValidationError(
            "Experience application conditions do not match candidate scope"
        )
    if payload.get("match_result") != "matched":
        raise ExperienceValidationError(
            "Only a matched application can be recorded as valid"
        )
    reasons = _strings(payload, "match_reasons")
    if set(reasons) != {"scene", "audience", "slide-task", "conditions"}:
        raise ExperienceValidationError(
            "match_reasons must cover scene, audience, slide-task, and conditions"
        )
    return {
        **payload,
        "application_id": _identifier(payload, "application_id"),
        "candidate_ref": _text(payload, "candidate_ref"),
        "candidate_id": str(candidate["candidate_id"]),
        "candidate_version": int(candidate["version"]),
        "application_project_id": _text(payload, "application_project_id"),
        "target_context": context,
        "match_reasons": reasons,
        "match_result": "matched",
        "runtime_evidence_ref": _text(payload, "runtime_evidence_ref"),
        "status": "applied",
    }


def validate_experience_evaluation(
    payload: dict[str, Any], application: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceEvaluation must be an object")
    _reject_scores(payload)
    if payload.get("application_ref") is None:
        raise ExperienceValidationError("application_ref is required")
    professional_result = _text(payload, "professional_result")
    user_outcome = _text(payload, "user_outcome")
    application_result = _text(payload, "application_result")
    if professional_result not in {"passed", "failed"}:
        raise ExperienceValidationError(
            "professional_result must be passed or failed"
        )
    if user_outcome not in {"accepted", "rejected", "continued-feedback"}:
        raise ExperienceValidationError(
            "Evaluation requires an explicit evaluated user outcome"
        )
    if application_result not in {"success", "failure", "mixed"}:
        raise ExperienceValidationError(
            "application_result must be success, failure, or mixed"
        )
    if application_result == "success" and (
        professional_result != "passed" or user_outcome != "accepted"
    ):
        raise ExperienceValidationError(
            "A successful application requires professional pass and user acceptance"
        )
    if payload.get("context_match_result") != "matched":
        raise ExperienceValidationError(
            "Wrong-context evaluations cannot be recorded as valid evidence"
        )
    return {
        **payload,
        "application_ref": _text(payload, "application_ref"),
        "application_id": str(application["application_id"]),
        "candidate_ref": str(application["candidate_ref"]),
        "candidate_id": str(application["candidate_id"]),
        "application_project_id": str(application["application_project_id"]),
        "professional_review_refs": _strings(
            payload, "professional_review_refs"
        ),
        "professional_result": professional_result,
        "user_outcome": user_outcome,
        "evidence_refs": _strings(payload, "evidence_refs"),
        "application_result": application_result,
        "context_match_result": "matched",
    }


def validate_evolution_policy(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceEvolutionPolicy must be an object")
    _reject_scores(payload)
    if payload.get("threshold_status") != "configurable-pending-real-validation":
        raise ExperienceValidationError(
            "Evolution thresholds must remain configurable and pending real validation"
        )
    normalized = {
        **payload,
        "policy_version": _text(payload, "policy_version"),
        "threshold_status": "configurable-pending-real-validation",
    }
    for field in (
        "minimum_distinct_accepted_projects",
        "minimum_failure_projects_for_demotion",
    ):
        value = payload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 2:
            raise ExperienceValidationError(
                f"{field} must be a configurable integer of at least two distinct projects"
            )
        normalized[field] = value
    for field in (
        "requires_professional_review",
        "requires_user_acceptance",
        "simulation_evidence_forbidden",
    ):
        if payload.get(field) is not True:
            raise ExperienceValidationError(f"{field} must be true")
        normalized[field] = True
    return normalized


def validate_evolution_decision(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError("ExperienceEvolutionDecision must be an object")
    _reject_scores(payload)
    action = _text(payload, "action")
    if action not in {"promote", "demote", "disable"}:
        raise ExperienceValidationError(
            "Experience evolution action must be promote, demote, or disable"
        )
    if _text(payload, "decided_by") != "经验进化治理智能体":
        raise ExperienceValidationError(
            "Experience evolution requires the formal governance role"
        )
    return {
        **payload,
        "decision_id": _identifier(payload, "decision_id"),
        "action": action,
        "candidate_ref": _text(payload, "candidate_ref"),
        "policy_ref": _text(payload, "policy_ref"),
        "evaluation_refs": _strings(payload, "evaluation_refs"),
        "reason": _text(payload, "reason"),
        "decided_by": "经验进化治理智能体",
    }


def validate_stable_release_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ExperienceValidationError(
            "StableCapabilityReleaseCandidate must be an object"
        )
    forbidden = {
        "publish",
        "released_version",
        "rewrite_prompt",
        "rewrite_role_contract",
        "rewrite_scenario_pack",
    }.intersection(payload)
    if forbidden:
        raise ExperienceValidationError(
            "Runtime cannot publish or rewrite stable capabilities: "
            + ", ".join(sorted(forbidden))
        )
    versions = payload.get("proposed_versions")
    if not isinstance(versions, dict):
        raise ExperienceValidationError("proposed_versions must be an object")
    normalized_versions = {
        field: _text(versions, field)
        for field in ("stable_prompt", "role_contract", "scenario_pack")
    }
    return {
        **payload,
        "release_candidate_id": _identifier(payload, "release_candidate_id"),
        "source_experience_refs": _strings(payload, "source_experience_refs"),
        "positive_regression_refs": _strings(payload, "positive_regression_refs"),
        "negative_regression_refs": _strings(payload, "negative_regression_refs"),
        "cross_role_review_refs": _strings(payload, "cross_role_review_refs"),
        "scope": _text(payload, "scope"),
        "counterexamples": _strings(payload, "counterexamples"),
        "failure_boundaries": _strings(payload, "failure_boundaries"),
        "proposed_versions": normalized_versions,
        "status": "release-candidate",
        "runtime_publish_allowed": False,
    }
