"""Immutable v2.2 contracts for a whole-deck content revision plan."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


REVISION_PLAN_KIND = "content-batch-revision-plan"
REVISION_PLAN_CONFIRMATION_KIND = "content-batch-plan-confirmation"
PLAN_ACTIONS = frozenset({"keep", "revise", "merge-or-delete"})
PLAN_STATUSES = frozenset({"proposed", "confirmed", "applied", "superseded"})


def validate_revision_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a chief-authored plan and its immutable source lineage."""

    if not isinstance(payload, dict):
        raise ContractValidationError("Revision plan must be an object")
    plan = dict(payload)
    _required_text(plan, "plan_id")
    _required_text(plan, "project_id")
    _exact_ref(plan, "review_batch_ref", "content-review-batch")
    _exact_ref(plan, "source_version", "reading-deck-blueprint")
    if plan.get("producer_id") != "presales-solution-chief":
        raise ContractValidationError("Revision plan producer is invalid")
    _required_text(plan, "summary")
    _timestamp(plan, "created_at")
    status = str(plan.get("status") or "")
    if status not in PLAN_STATUSES:
        raise ContractValidationError("Revision plan status is invalid")
    supersedes_ref = str(plan.get("supersedes_ref") or "")
    if supersedes_ref:
        _exact_ref(plan, "supersedes_ref", REVISION_PLAN_KIND)
    elif status != "proposed":
        raise ContractValidationError("Confirmed revision plan must preserve predecessor")
    actions = plan.get("page_actions")
    if not isinstance(actions, list) or not actions:
        raise ContractValidationError("Revision plan must include page actions")
    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for action in actions:
        if not isinstance(action, dict):
            raise ContractValidationError("Revision plan page action is invalid")
        slide_id = _value(action, "slide_id")
        if slide_id in seen or _value(action, "action") not in PLAN_ACTIONS:
            raise ContractValidationError("Revision plan page action is invalid")
        seen.add(slide_id)
        normalized.append(
            {
                "slide_id": slide_id,
                "action": _value(action, "action"),
                "rationale": _value(action, "rationale"),
            }
        )
    plan["page_actions"] = normalized
    return plan


def validate_revision_plan_confirmation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the receipt for one trusted plan-confirmation action."""

    if not isinstance(payload, dict):
        raise ContractValidationError("Revision plan confirmation must be an object")
    confirmation = dict(payload)
    _required_text(confirmation, "project_id")
    _exact_ref(confirmation, "revision_plan_ref", REVISION_PLAN_KIND)
    _exact_ref(confirmation, "review_batch_ref", "content-review-batch")
    _exact_ref(confirmation, "source_version", "reading-deck-blueprint")
    _required_text(confirmation, "scope_kind")
    _required_text(confirmation, "scope_id")
    _required_text(confirmation, "challenge_id")
    _timestamp(confirmation, "confirmed_at")
    challenge_revision = confirmation.get("challenge_revision")
    if (
        isinstance(challenge_revision, bool)
        or not isinstance(challenge_revision, int)
        or challenge_revision < 0
    ):
        raise ContractValidationError("Revision plan confirmation revision is invalid")
    confirmation["challenge_revision"] = challenge_revision
    return confirmation


def _exact_ref(payload: dict[str, Any], field: str, kind: str) -> None:
    try:
        reference = ArtifactReference.parse(_required_text(payload, field))
    except (TypeError, ValueError) as error:
        raise ContractValidationError(f"{field} is invalid") from error
    if reference.kind != kind:
        raise ContractValidationError(f"{field} has the wrong kind")


def _timestamp(payload: dict[str, Any], field: str) -> None:
    value = _required_text(payload, field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ContractValidationError(f"{field} is invalid") from error
    if "T" not in value or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a timezone")


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ContractValidationError(f"{field} is required")
    return value


def _value(payload: dict[str, Any], field: str) -> str:
    return _required_text(payload, field)


__all__ = [
    "PLAN_ACTIONS",
    "PLAN_STATUSES",
    "REVISION_PLAN_CONFIRMATION_KIND",
    "REVISION_PLAN_KIND",
    "validate_revision_plan",
    "validate_revision_plan_confirmation",
]
