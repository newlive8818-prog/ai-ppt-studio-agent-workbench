"""F0–F3 feedback governance before any content or visual change set."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError, FeedbackGovernanceError
from ai_ppt_studio.kernel.references import ArtifactReference

FEEDBACK_LEVELS = frozenset({"F0", "F1", "F2", "F3"})
FEEDBACK_DECISIONS = frozenset(
    {"follow-ai-recommendation", "follow-user-instruction", "supplement"}
)
_BATCH_PLAN_GOVERNANCE_FIELDS = frozenset(
    {
        "review_batch_ref",
        "revision_plan_ref",
        "plan_confirmation_ref",
        "affected_refs",
        "full_deck_re_review_route",
    }
)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FeedbackGovernanceError(f"{field} must be a non-empty string")
    return value.strip()


def _strings(payload: dict[str, Any], field: str) -> list[str]:
    values = payload.get(field)
    if not isinstance(values, list) or not values or any(
        not isinstance(item, str) or not item.strip() for item in values
    ):
        raise FeedbackGovernanceError(f"{field} must be a non-empty string array")
    return [item.strip() for item in values]


def _artifact_ref(payload: dict[str, Any], field: str, kind: str) -> str:
    value = _text(payload, field)
    try:
        reference = ArtifactReference.parse(value)
    except ArtifactReferenceError as error:
        raise FeedbackGovernanceError(
            f"{field} must be a valid {kind} artifact reference"
        ) from error
    if reference.kind != kind:
        raise FeedbackGovernanceError(
            f"{field} must reference artifact kind {kind}"
        )
    return str(reference)


def validate_raw_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise FeedbackGovernanceError("RawFeedback must be an object")
    return {
        **payload,
        "raw_feedback": _text(payload, "raw_feedback"),
        "target_refs": _strings(payload, "target_refs"),
        "status": "captured",
    }


def validate_feedback_governance(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise FeedbackGovernanceError(
            "FeedbackGovernanceRecord must be an object"
        )
    level = _text(payload, "feedback_level")
    if level not in FEEDBACK_LEVELS:
        raise FeedbackGovernanceError(f"Unknown feedback level: {level}")
    normalized = {
        **payload,
        "raw_feedback_ref": _text(payload, "raw_feedback_ref"),
        "feedback_level": level,
        "diagnosis": _text(payload, "diagnosis"),
        "scope": _text(payload, "scope"),
        "counterexamples": _strings(payload, "counterexamples"),
        "ai_recommendation": _text(payload, "ai_recommendation"),
        "preserve_refs": _strings(payload, "preserve_refs"),
        "status": "needs-user" if level in {"F2", "F3"} else "executable",
        "requires_user_decision": level in {"F2", "F3"},
    }
    supplied_batch_fields = set(payload).intersection(
        _BATCH_PLAN_GOVERNANCE_FIELDS
    )
    if supplied_batch_fields:
        if supplied_batch_fields != _BATCH_PLAN_GOVERNANCE_FIELDS:
            raise FeedbackGovernanceError(
                "Batch feedback governance requires complete review-batch, "
                "revision-plan, confirmation, affected-ref, and full-deck "
                "re-review lineage"
            )
        if normalized["scope"] != "whole-deck-confirmed-plan":
            raise FeedbackGovernanceError(
                "Batch feedback governance scope must be whole-deck-confirmed-plan"
            )
        if payload.get("full_deck_re_review_route") != "new-blueprint-full-deck":
            raise FeedbackGovernanceError(
                "Batch feedback governance must require full-deck re-review"
            )
        normalized.update(
            {
                "review_batch_ref": _artifact_ref(
                    payload, "review_batch_ref", "content-review-batch"
                ),
                "revision_plan_ref": _artifact_ref(
                    payload,
                    "revision_plan_ref",
                    "content-batch-revision-plan",
                ),
                "plan_confirmation_ref": _artifact_ref(
                    payload,
                    "plan_confirmation_ref",
                    "content-batch-plan-confirmation",
                ),
                "affected_refs": _strings(payload, "affected_refs"),
                "full_deck_re_review_route": "new-blueprint-full-deck",
            }
        )
    return normalized


def decide_feedback(payload: dict[str, Any], choice: str) -> dict[str, Any]:
    if payload.get("status") != "needs-user":
        raise FeedbackGovernanceError("Feedback record does not need a decision")
    if choice not in FEEDBACK_DECISIONS:
        raise FeedbackGovernanceError(f"Unknown feedback decision: {choice}")
    return {
        **payload,
        "user_decision": choice,
        "status": "needs-user" if choice == "supplement" else "executable",
    }
