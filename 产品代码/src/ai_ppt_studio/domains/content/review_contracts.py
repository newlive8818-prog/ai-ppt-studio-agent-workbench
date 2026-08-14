"""Strict contracts for independent content-page review decisions."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ContentWorkflowError,
)
from ai_ppt_studio.kernel.references import ArtifactReference


CONTENT_PAGE_DECISIONS = (
    "approved",
    "modify",
    "evidence",
    "merge-or-delete",
)
COMMENT_REQUIRED_DECISIONS = frozenset(CONTENT_PAGE_DECISIONS[1:])
MAX_PAGE_DECISION_COMMENT_CODE_POINTS = 1200

_CONTENT_BLUEPRINT_FIELDS = frozenset(
    {
        "strategy_ref",
        "claim_evidence_map_ref",
        "argument_map_ref",
        "draft_ref",
        "framework_ref",
        "framework_confirmation_ref",
        "full_deck_expansion_authorization_ref",
        "acceptance_ref",
        "strategy",
        "claim_evidence_map",
        "argument_map",
        "slides",
        "status",
    }
)
_CONTENT_BLUEPRINT_REFERENCE_KINDS = {
    "strategy_ref": "presales-content-strategy",
    "claim_evidence_map_ref": "claim-evidence-map",
    "argument_map_ref": "deck-argument-map",
    "draft_ref": "slide-draft-set",
    "framework_ref": "content-framework-draft",
    "framework_confirmation_ref": "content-framework-confirmation",
    "full_deck_expansion_authorization_ref": (
        "full-deck-expansion-authorization"
    ),
    "acceptance_ref": "content-acceptance",
}

_PAGE_DECISION_FIELDS = frozenset(
    {
        "page_decision_id",
        "review_batch_id",
        "project_id",
        "review_type",
        "source_version",
        "slide_id",
        "slide_order",
        "slide_title_snapshot",
        "visible_copy_snapshot_ref",
        "decision",
        "comment",
        "completed",
        "saved_at",
        "supersedes_decision_ref",
    }
)
_PAGE_DECISION_SET_FIELDS = frozenset(
    {
        "decision_set_id",
        "review_batch_id",
        "project_id",
        "review_type",
        "source_version",
        "expected_slide_count",
        "status",
        "decision_refs",
        "updated_at",
    }
)
_CONTENT_REVIEW_BATCH_FIELDS = frozenset(
    {
        "review_batch_id",
        "project_id",
        "review_type",
        "source_version",
        "decision_set_ref",
        "page_snapshot_refs",
        "decision_refs",
        "expected_slide_count",
        "counts",
        "status",
        "submitted_at",
        "submitted_by",
        "supersedes_ref",
        "scope_kind",
        "scope_id",
        "evidence_refs",
        "challenge_id",
        "challenge_revision",
        "user_action_ref",
        "user_message_ref",
        "confirmation_identity_type",
        "host_assertion_sha256",
        "confirmed_at",
    }
)
_CONTENT_REVIEW_BATCH_COUNTS = frozenset(
    {"approved", "modify", "evidence", "merge_or_delete"}
)
_CONTENT_REVIEW_BATCH_WITHDRAWAL_FIELDS = frozenset(
    {
        "withdrawal_id",
        "project_id",
        "review_batch_id",
        "source_version",
        "submitted_batch_ref",
        "superseded_batch_ref",
        "replacement_review_batch_id",
        "reason",
        "withdrawn_at",
        "withdrawn_by",
        "scope_kind",
        "scope_id",
        "evidence_refs",
        "challenge_id",
        "challenge_revision",
        "user_action_ref",
        "user_message_ref",
        "confirmation_identity_type",
        "host_assertion_sha256",
        "confirmed_at",
    }
)
CONTENT_REVIEW_BATCH_STATUSES = frozenset(
    {
        "draft",
        "ready",
        "submitted",
        "plan-proposed",
        "plan-confirmed",
        "applied",
        "superseded",
    }
)
_SUBMITTED_CONTENT_REVIEW_BATCH_STATUSES = CONTENT_REVIEW_BATCH_STATUSES - {
    "draft",
    "ready",
}
_VISIBLE_COPY_SNAPSHOT_FIELDS = frozenset(
    {
        "project_id",
        "source_version",
        "slide_id",
        "slide_order",
        "slide_title_snapshot",
        "visible_copy",
    }
)
_VISIBLE_COPY_ITEM_FIELDS = frozenset({"copy_id", "role", "text"})


def _nonempty_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field, "")
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be a string")
    return value.strip()


def _positive_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractValidationError(f"{field} must be a positive integer")
    return value


def _artifact_ref(value: str, *, field: str, kind: str) -> str:
    try:
        reference = ArtifactReference.parse(value)
    except ArtifactReferenceError as error:
        raise ContractValidationError(
            f"{field} must be a valid {kind} artifact reference"
        ) from error
    if reference.kind != kind:
        raise ContractValidationError(
            f"{field} must reference artifact kind {kind}"
        )
    return str(reference)


def _timestamp(value: object, *, field: str) -> str:
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


def normalize_page_decision_choice(
    decision: object,
    comment: object,
) -> tuple[str, str]:
    """Normalize the only four choices and their exact comment semantics."""

    if not isinstance(decision, str) or decision not in CONTENT_PAGE_DECISIONS:
        raise ContractValidationError(
            "decision must be one of approved, modify, evidence, "
            "merge-or-delete"
        )
    if decision == "approved":
        return decision, ""
    if not isinstance(comment, str):
        raise ContractValidationError("comment must be a string")
    normalized_comment = comment.strip()
    if decision in COMMENT_REQUIRED_DECISIONS and not normalized_comment:
        raise ContentWorkflowError(
            "CONTENT_PAGE_COMMENT_REQUIRED",
            "CONTENT_PAGE_COMMENT_REQUIRED: "
            f"{decision} requires a non-empty saved comment",
            {"decision": decision},
        )
    if len(normalized_comment) > MAX_PAGE_DECISION_COMMENT_CODE_POINTS:
        raise ContractValidationError(
            "comment cannot exceed 1200 Unicode code points"
        )
    return decision, normalized_comment


def validate_content_blueprint(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the one closed envelope accepted for formal review."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ContentBlueprint must be an object")
    if set(payload) != _CONTENT_BLUEPRINT_FIELDS:
        raise ContractValidationError(
            "ContentBlueprint must contain exactly the formal content-chain "
            "references, embedded content, slides, and status"
        )
    normalized = {
        field: _artifact_ref(
            _nonempty_text(payload, field),
            field=field,
            kind=kind,
        )
        for field, kind in _CONTENT_BLUEPRINT_REFERENCE_KINDS.items()
    }
    for field in ("strategy", "claim_evidence_map", "argument_map"):
        value = payload.get(field)
        if not isinstance(value, dict) or not value:
            raise ContractValidationError(f"{field} must be a non-empty object")
        normalized[field] = copy.deepcopy(value)
    slides = payload.get("slides")
    if (
        not isinstance(slides, list)
        or not slides
        or any(not isinstance(slide, dict) for slide in slides)
    ):
        raise ContractValidationError("slides must be a non-empty object array")
    normalized["slides"] = copy.deepcopy(slides)
    if payload.get("status") != "user-reviewable":
        raise ContractValidationError(
            "ContentBlueprint status must be user-reviewable"
        )
    normalized["status"] = "user-reviewable"
    return normalized


def validate_visible_copy_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact immutable copy snapshot captured from one slide."""

    if not isinstance(payload, dict):
        raise ContractValidationError("VisibleCopySnapshot must be an object")
    if set(payload) != _VISIBLE_COPY_SNAPSHOT_FIELDS:
        raise ContractValidationError(
            "VisibleCopySnapshot must contain exactly project_id, "
            "source_version, slide_id, slide_order, slide_title_snapshot, "
            "and visible_copy"
        )
    visible_copy = payload.get("visible_copy")
    if not isinstance(visible_copy, list) or not visible_copy:
        raise ContractValidationError("visible_copy must be a non-empty list")
    normalized_visible_copy: list[dict[str, str]] = []
    for index, item in enumerate(visible_copy):
        if not isinstance(item, dict):
            raise ContractValidationError(
                f"visible_copy[{index}] must be an object"
            )
        if set(item) != _VISIBLE_COPY_ITEM_FIELDS:
            raise ContractValidationError(
                f"visible_copy[{index}] must contain exactly copy_id, role, "
                "and text"
            )
        normalized_visible_copy.append(
            {
                "copy_id": _nonempty_text(item, "copy_id"),
                "role": _nonempty_text(item, "role"),
                "text": _nonempty_text(item, "text"),
            }
        )
    return {
        "project_id": _nonempty_text(payload, "project_id"),
        "source_version": _artifact_ref(
            _nonempty_text(payload, "source_version"),
            field="source_version",
            kind="content-blueprint",
        ),
        "slide_id": _nonempty_text(payload, "slide_id"),
        "slide_order": _positive_int(payload, "slide_order"),
        "slide_title_snapshot": _nonempty_text(
            payload, "slide_title_snapshot"
        ),
        "visible_copy": copy.deepcopy(normalized_visible_copy),
    }


def validate_page_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical immutable PageDecision payload."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecision must be an object")
    unknown = set(payload) - _PAGE_DECISION_FIELDS
    if unknown:
        raise ContractValidationError(
            "PageDecision contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    decision, comment = normalize_page_decision_choice(
        payload.get("decision"), payload.get("comment", "")
    )
    review_type = _nonempty_text(payload, "review_type")
    if review_type != "content":
        raise ContractValidationError("review_type must be content")
    source_version = _artifact_ref(
        _nonempty_text(payload, "source_version"),
        field="source_version",
        kind="content-blueprint",
    )
    snapshot_ref = _artifact_ref(
        _nonempty_text(payload, "visible_copy_snapshot_ref"),
        field="visible_copy_snapshot_ref",
        kind="content-visible-copy-snapshot",
    )
    supersedes = _optional_text(payload, "supersedes_decision_ref")
    if supersedes:
        supersedes = _artifact_ref(
            supersedes,
            field="supersedes_decision_ref",
            kind="content-page-decision",
        )
    completed = decision == "approved" or bool(comment)
    supplied_completed = payload.get("completed", completed)
    if not isinstance(supplied_completed, bool) or supplied_completed != completed:
        raise ContractValidationError(
            "completed must exactly match the normalized decision and comment"
        )
    return {
        "page_decision_id": _nonempty_text(payload, "page_decision_id"),
        "review_batch_id": _nonempty_text(payload, "review_batch_id"),
        "project_id": _nonempty_text(payload, "project_id"),
        "review_type": "content",
        "source_version": source_version,
        "slide_id": _nonempty_text(payload, "slide_id"),
        "slide_order": _positive_int(payload, "slide_order"),
        "slide_title_snapshot": _nonempty_text(
            payload, "slide_title_snapshot"
        ),
        "visible_copy_snapshot_ref": snapshot_ref,
        "decision": decision,
        "comment": comment,
        "completed": completed,
        "saved_at": _timestamp(payload.get("saved_at"), field="saved_at"),
        "supersedes_decision_ref": supersedes,
    }


def validate_persisted_page_decision(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Require every persisted PageDecision field in canonical form."""

    if not isinstance(payload, dict) or set(payload) != _PAGE_DECISION_FIELDS:
        raise ContractValidationError(
            "Persisted PageDecision must contain every exact formal field"
        )
    normalized = validate_page_decision(payload)
    if normalized != payload:
        raise ContractValidationError(
            "Persisted PageDecision payload is not canonical"
        )
    return normalized


def validate_page_decision_set(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the source-bound aggregate of current page decisions."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PageDecisionSet must be an object")
    unknown = set(payload) - _PAGE_DECISION_SET_FIELDS
    if unknown:
        raise ContractValidationError(
            "PageDecisionSet contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    review_type = _nonempty_text(payload, "review_type")
    if review_type != "content":
        raise ContractValidationError("review_type must be content")
    status = _nonempty_text(payload, "status")
    if status not in {"draft", "frozen"}:
        raise ContractValidationError(
            "PageDecisionSet status must be draft or frozen"
        )
    expected_slide_count = _positive_int(payload, "expected_slide_count")
    raw_refs = payload.get("decision_refs")
    if not isinstance(raw_refs, list):
        raise ContractValidationError("decision_refs must be a list")
    decision_refs: list[dict[str, Any]] = []
    seen_slides: set[str] = set()
    seen_orders: set[int] = set()
    seen_refs: set[str] = set()
    previous_order = 0
    for raw in raw_refs:
        if not isinstance(raw, dict) or set(raw) != {
            "slide_id",
            "slide_order",
            "decision_ref",
        }:
            raise ContractValidationError(
                "Each decision_refs item must contain only slide_id, "
                "slide_order, and decision_ref"
            )
        slide_id = _nonempty_text(raw, "slide_id")
        slide_order = _positive_int(raw, "slide_order")
        decision_ref = _artifact_ref(
            _nonempty_text(raw, "decision_ref"),
            field="decision_ref",
            kind="content-page-decision",
        )
        if (
            slide_id in seen_slides
            or slide_order in seen_orders
            or decision_ref in seen_refs
        ):
            raise ContractValidationError(
                "PageDecisionSet decision refs must be unique"
            )
        if slide_order <= previous_order:
            raise ContractValidationError(
                "PageDecisionSet decision refs must follow slide order"
            )
        seen_slides.add(slide_id)
        seen_orders.add(slide_order)
        seen_refs.add(decision_ref)
        previous_order = slide_order
        decision_refs.append(
            {
                "slide_id": slide_id,
                "slide_order": slide_order,
                "decision_ref": decision_ref,
            }
        )
    if len(decision_refs) > expected_slide_count:
        raise ContractValidationError(
            "decision_refs cannot exceed expected_slide_count"
        )
    return {
        "decision_set_id": _nonempty_text(payload, "decision_set_id"),
        "review_batch_id": _nonempty_text(payload, "review_batch_id"),
        "project_id": _nonempty_text(payload, "project_id"),
        "review_type": "content",
        "source_version": _artifact_ref(
            _nonempty_text(payload, "source_version"),
            field="source_version",
            kind="content-blueprint",
        ),
        "expected_slide_count": expected_slide_count,
        "status": status,
        "decision_refs": decision_refs,
        "updated_at": _timestamp(
            payload.get("updated_at"), field="updated_at"
        ),
    }


def validate_persisted_page_decision_set(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Require the persisted decision-set aggregate to be byte-canonical."""

    if not isinstance(payload, dict) or set(payload) != _PAGE_DECISION_SET_FIELDS:
        raise ContractValidationError(
            "Persisted PageDecisionSet must contain every exact formal field"
        )
    normalized = validate_page_decision_set(payload)
    if normalized != payload:
        raise ContractValidationError(
            "Persisted PageDecisionSet payload is not canonical"
        )
    return normalized


def _reference_list(
    value: object,
    *,
    field: str,
    kind: str,
    expected_count: int,
) -> list[str]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise ContractValidationError(
            f"{field} must contain exactly expected_slide_count references"
        )
    normalized = [
        _artifact_ref(
            _nonempty_text({field: item}, field),
            field=field,
            kind=kind,
        )
        for item in value
    ]
    if len(set(normalized)) != len(normalized):
        raise ContractValidationError(f"{field} references must be unique")
    return normalized


def _batch_counts(value: object, *, expected_total: int) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != _CONTENT_REVIEW_BATCH_COUNTS:
        raise ContractValidationError(
            "counts must contain exactly approved, modify, evidence, and "
            "merge_or_delete"
        )
    counts: dict[str, int] = {}
    for key in ("approved", "modify", "evidence", "merge_or_delete"):
        count = value[key]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ContractValidationError(f"counts.{key} must be non-negative")
        counts[key] = count
    if sum(counts.values()) != expected_total:
        raise ContractValidationError(
            "The four-way counts must equal expected_slide_count"
        )
    return counts


def _empty_submission_fields(payload: dict[str, Any]) -> dict[str, Any]:
    empty_text_fields = (
        "submitted_at",
        "submitted_by",
        "scope_kind",
        "scope_id",
        "challenge_id",
        "user_action_ref",
        "user_message_ref",
        "confirmation_identity_type",
        "host_assertion_sha256",
        "confirmed_at",
    )
    if any(payload.get(field) != "" for field in empty_text_fields):
        raise ContractValidationError(
            "Draft review batches cannot carry submission confirmation fields"
        )
    if payload.get("challenge_revision") != 0 or payload.get("evidence_refs") != []:
        raise ContractValidationError(
            "Draft review batches cannot carry a submission challenge"
        )
    return {
        **{field: "" for field in empty_text_fields},
        "evidence_refs": [],
        "challenge_revision": 0,
    }


def _submitted_confirmation_fields(
    payload: dict[str, Any],
    *,
    source_version: str,
    review_batch_id: str,
    decision_set_ref: str,
    decision_refs: list[str],
) -> dict[str, Any]:
    scope_kind = _nonempty_text(payload, "scope_kind")
    scope_id = _nonempty_text(payload, "scope_id")
    expected_scope_id = f"{review_batch_id}:{source_version}"
    if scope_kind != "content-review-batch-submission":
        raise ContractValidationError(
            "Submitted review batch scope_kind must be "
            "content-review-batch-submission"
        )
    if scope_id != expected_scope_id:
        raise ContractValidationError(
            "Submitted review batch scope_id must bind batch and source"
        )
    evidence_refs = payload.get("evidence_refs")
    expected_evidence = [source_version, decision_set_ref, *decision_refs]
    if evidence_refs != expected_evidence:
        raise ContractValidationError(
            "Submitted review batch evidence_refs are not canonical"
        )
    challenge_id = _nonempty_text(payload, "challenge_id")
    assertion_digest = _nonempty_text(payload, "host_assertion_sha256")
    if (
        len(challenge_id) != 64
        or any(character not in "0123456789abcdef" for character in challenge_id)
        or len(assertion_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in assertion_digest
        )
    ):
        raise ContractValidationError(
            "Submission challenge and assertion digests must be SHA-256 hex"
        )
    challenge_revision = _positive_int(payload, "challenge_revision")
    identity_type = _nonempty_text(payload, "confirmation_identity_type")
    action_ref = _optional_text(payload, "user_action_ref")
    message_ref = _optional_text(payload, "user_message_ref")
    if (
        identity_type not in {"host-action", "verified-message"}
        or (identity_type == "host-action" and (not action_ref or message_ref))
        or (identity_type == "verified-message" and (not message_ref or action_ref))
    ):
        raise ContractValidationError(
            "Submitted review batch must bind exactly one trusted identity"
        )
    identity = action_ref or message_ref
    submitted_by = _nonempty_text(payload, "submitted_by")
    submitted_at = _timestamp(payload.get("submitted_at"), field="submitted_at")
    confirmed_at = _timestamp(payload.get("confirmed_at"), field="confirmed_at")
    if submitted_by != identity or submitted_at != confirmed_at:
        raise ContractValidationError(
            "Submission identity and timestamp must match confirmation"
        )
    return {
        "submitted_at": submitted_at,
        "submitted_by": submitted_by,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "evidence_refs": list(expected_evidence),
        "challenge_id": challenge_id,
        "challenge_revision": challenge_revision,
        "user_action_ref": action_ref,
        "user_message_ref": message_ref,
        "confirmation_identity_type": identity_type,
        "host_assertion_sha256": assertion_digest,
        "confirmed_at": confirmed_at,
    }


def validate_content_review_batch(
    payload: dict[str, Any],
    *,
    authoritative_slides: list[dict[str, Any]] | None = None,
    decisions_by_ref: dict[str, dict[str, Any]] | None = None,
    prior_submitted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one exact immutable full-deck review-batch lifecycle artifact."""

    if not isinstance(payload, dict) or set(payload) != _CONTENT_REVIEW_BATCH_FIELDS:
        raise ContractValidationError(
            "ContentReviewBatch must contain every exact formal field"
        )
    review_type = _nonempty_text(payload, "review_type")
    if review_type != "content":
        raise ContractValidationError("review_type must be content")
    source_version = _artifact_ref(
        _nonempty_text(payload, "source_version"),
        field="source_version",
        kind="content-blueprint",
    )
    decision_set_ref = _artifact_ref(
        _nonempty_text(payload, "decision_set_ref"),
        field="decision_set_ref",
        kind="content-page-decision-set",
    )
    expected_slide_count = _positive_int(payload, "expected_slide_count")
    decision_refs = _reference_list(
        payload.get("decision_refs"),
        field="decision_refs",
        kind="content-page-decision",
        expected_count=expected_slide_count,
    )
    page_snapshot_refs = _reference_list(
        payload.get("page_snapshot_refs"),
        field="page_snapshot_refs",
        kind="content-visible-copy-snapshot",
        expected_count=expected_slide_count,
    )
    counts = _batch_counts(
        payload.get("counts"), expected_total=expected_slide_count
    )
    status = _nonempty_text(payload, "status")
    if status not in CONTENT_REVIEW_BATCH_STATUSES:
        raise ContractValidationError("ContentReviewBatch status is invalid")
    review_batch_id = _nonempty_text(payload, "review_batch_id")
    supersedes = _optional_text(payload, "supersedes_ref")
    if supersedes:
        supersedes = _artifact_ref(
            supersedes,
            field="supersedes_ref",
            kind="content-review-batch",
        )
    if status == "superseded" and not supersedes:
        raise ContractValidationError(
            "A superseded batch lifecycle must reference its predecessor"
        )
    if status in _SUBMITTED_CONTENT_REVIEW_BATCH_STATUSES:
        submission = _submitted_confirmation_fields(
            payload,
            source_version=source_version,
            review_batch_id=review_batch_id,
            decision_set_ref=decision_set_ref,
            decision_refs=decision_refs,
        )
    else:
        submission = _empty_submission_fields(payload)

    normalized = {
        "review_batch_id": review_batch_id,
        "project_id": _nonempty_text(payload, "project_id"),
        "review_type": "content",
        "source_version": source_version,
        "decision_set_ref": decision_set_ref,
        "page_snapshot_refs": page_snapshot_refs,
        "decision_refs": decision_refs,
        "expected_slide_count": expected_slide_count,
        "counts": counts,
        "status": status,
        "submitted_at": submission["submitted_at"],
        "submitted_by": submission["submitted_by"],
        "supersedes_ref": supersedes,
        "scope_kind": submission["scope_kind"],
        "scope_id": submission["scope_id"],
        "evidence_refs": submission["evidence_refs"],
        "challenge_id": submission["challenge_id"],
        "challenge_revision": submission["challenge_revision"],
        "user_action_ref": submission["user_action_ref"],
        "user_message_ref": submission["user_message_ref"],
        "confirmation_identity_type": submission[
            "confirmation_identity_type"
        ],
        "host_assertion_sha256": submission["host_assertion_sha256"],
        "confirmed_at": submission["confirmed_at"],
    }
    if normalized != payload:
        raise ContractValidationError(
            "ContentReviewBatch payload is not canonical"
        )

    if authoritative_slides is not None or decisions_by_ref is not None:
        if not isinstance(authoritative_slides, list) or not isinstance(
            decisions_by_ref, dict
        ):
            raise ContractValidationError(
                "Authoritative slides and decisions must be validated together"
            )
        if len(authoritative_slides) != expected_slide_count:
            raise ContractValidationError(
                "Review batch page count differs from the blueprint"
            )
        remaining = 0
        next_incomplete = ""
        observed_counts = {key: 0 for key in _CONTENT_REVIEW_BATCH_COUNTS}
        observed_snapshots: list[str] = []
        for index, (slide, decision_ref) in enumerate(
            zip(authoritative_slides, decision_refs), start=1
        ):
            if not isinstance(slide, dict):
                raise ContractValidationError("Authoritative slide is invalid")
            slide_id = slide.get("slide_id")
            slide_order = slide.get("order")
            decision = decisions_by_ref.get(decision_ref)
            if (
                not isinstance(slide_id, str)
                or not slide_id
                or slide_order != index
                or not isinstance(decision, dict)
                or decision.get("project_id") != normalized["project_id"]
                or decision.get("review_type") != "content"
                or decision.get("slide_id") != slide_id
                or decision.get("slide_order") != index
                or decision.get("review_batch_id") != review_batch_id
                or decision.get("source_version") != source_version
            ):
                raise ContractValidationError(
                    "Review batch decisions do not match authoritative page order"
                )
            if not decision.get("completed"):
                remaining += 1
                if not next_incomplete:
                    next_incomplete = slide_id
                continue
            choice = decision.get("decision")
            count_key = (
                "merge_or_delete" if choice == "merge-or-delete" else choice
            )
            if count_key not in observed_counts:
                raise ContractValidationError(
                    "Review batch decision choice is invalid"
                )
            observed_counts[str(count_key)] += 1
            observed_snapshots.append(
                _artifact_ref(
                    _nonempty_text(
                        decision, "visible_copy_snapshot_ref"
                    ),
                    field="visible_copy_snapshot_ref",
                    kind="content-visible-copy-snapshot",
                )
            )
        if remaining:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_INCOMPLETE",
                "CONTENT_REVIEW_BATCH_INCOMPLETE: all pages need a completed decision",
                {
                    "total": expected_slide_count,
                    "completed": expected_slide_count - remaining,
                    "remaining": remaining,
                    "next_incomplete_slide_id": next_incomplete,
                },
            )
        if observed_counts != counts or observed_snapshots != page_snapshot_refs:
            raise ContractValidationError(
                "Review batch counts or page snapshots differ from decisions"
            )

    if prior_submitted is not None:
        if not isinstance(prior_submitted, dict):
            raise ContractValidationError("prior_submitted must be an object")
        immutable_fields = (
            "review_batch_id",
            "project_id",
            "review_type",
            "source_version",
            "decision_set_ref",
            "page_snapshot_refs",
            "decision_refs",
            "expected_slide_count",
            "counts",
            "submitted_at",
            "submitted_by",
            "scope_kind",
            "scope_id",
            "evidence_refs",
            "challenge_id",
            "challenge_revision",
            "user_action_ref",
            "user_message_ref",
            "confirmation_identity_type",
            "host_assertion_sha256",
            "confirmed_at",
        )
        if any(
            normalized.get(field) != prior_submitted.get(field)
            for field in immutable_fields
        ):
            raise ContractValidationError(
                "Submitted review-batch content cannot be mutated"
            )
    return normalized


def validate_content_review_batch_withdrawal(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate one exact pre-plan review-batch withdrawal receipt."""

    if (
        not isinstance(payload, dict)
        or set(payload) != _CONTENT_REVIEW_BATCH_WITHDRAWAL_FIELDS
    ):
        raise ContractValidationError(
            "ContentReviewBatchWithdrawal must contain every exact formal field"
        )
    source_version = _artifact_ref(
        _nonempty_text(payload, "source_version"),
        field="source_version",
        kind="content-blueprint",
    )
    submitted_batch_ref = _artifact_ref(
        _nonempty_text(payload, "submitted_batch_ref"),
        field="submitted_batch_ref",
        kind="content-review-batch",
    )
    superseded_batch_ref = _artifact_ref(
        _nonempty_text(payload, "superseded_batch_ref"),
        field="superseded_batch_ref",
        kind="content-review-batch",
    )
    if superseded_batch_ref == submitted_batch_ref:
        raise ContractValidationError(
            "Withdrawal must preserve submitted bytes in a new superseded artifact"
        )
    review_batch_id = _nonempty_text(payload, "review_batch_id")
    replacement_batch_id = _nonempty_text(
        payload, "replacement_review_batch_id"
    )
    if replacement_batch_id == review_batch_id:
        raise ContractValidationError(
            "Withdrawal replacement batch must have a new identity"
        )
    reason = _nonempty_text(payload, "reason")
    if payload.get("scope_kind") != "content-review-batch-withdrawal":
        raise ContractValidationError(
            "Withdrawal scope_kind must be content-review-batch-withdrawal"
        )
    if payload.get("scope_id") != review_batch_id:
        raise ContractValidationError(
            "Withdrawal scope_id must be the exact submitted batch id"
        )
    evidence_refs = payload.get("evidence_refs")
    if (
        not isinstance(evidence_refs, list)
        or len(evidence_refs) < 4
        or evidence_refs[0] != source_version
        or evidence_refs[1] != submitted_batch_ref
        or any(not isinstance(item, str) or not item for item in evidence_refs)
    ):
        raise ContractValidationError(
            "Withdrawal evidence_refs must bind source, submitted batch, and decisions"
        )
    _artifact_ref(
        evidence_refs[2],
        field="evidence_refs[2]",
        kind="content-page-decision-set",
    )
    ordered_decision_refs = [
        _artifact_ref(
            value,
            field="evidence_refs decision",
            kind="content-page-decision",
        )
        for value in evidence_refs[3:]
    ]
    if len(set(ordered_decision_refs)) != len(ordered_decision_refs):
        raise ContractValidationError(
            "Withdrawal decision evidence references must be unique"
        )
    challenge_id = _nonempty_text(payload, "challenge_id")
    assertion_digest = _nonempty_text(payload, "host_assertion_sha256")
    if (
        len(challenge_id) != 64
        or any(character not in "0123456789abcdef" for character in challenge_id)
        or len(assertion_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in assertion_digest
        )
    ):
        raise ContractValidationError(
            "Withdrawal challenge and assertion digests must be SHA-256 hex"
        )
    challenge_revision = _positive_int(payload, "challenge_revision")
    identity_type = _nonempty_text(payload, "confirmation_identity_type")
    action_ref = _optional_text(payload, "user_action_ref")
    message_ref = _optional_text(payload, "user_message_ref")
    if (
        identity_type not in {"host-action", "verified-message"}
        or (identity_type == "host-action" and (not action_ref or message_ref))
        or (identity_type == "verified-message" and (not message_ref or action_ref))
    ):
        raise ContractValidationError(
            "Withdrawal must bind exactly one trusted identity"
        )
    identity = action_ref or message_ref
    withdrawn_by = _nonempty_text(payload, "withdrawn_by")
    withdrawn_at = _timestamp(payload.get("withdrawn_at"), field="withdrawn_at")
    confirmed_at = _timestamp(payload.get("confirmed_at"), field="confirmed_at")
    if withdrawn_by != identity or withdrawn_at != confirmed_at:
        raise ContractValidationError(
            "Withdrawal identity and timestamp must match confirmation"
        )
    normalized = {
        "withdrawal_id": _nonempty_text(payload, "withdrawal_id"),
        "project_id": _nonempty_text(payload, "project_id"),
        "review_batch_id": review_batch_id,
        "source_version": source_version,
        "submitted_batch_ref": submitted_batch_ref,
        "superseded_batch_ref": superseded_batch_ref,
        "replacement_review_batch_id": replacement_batch_id,
        "reason": reason,
        "withdrawn_at": withdrawn_at,
        "withdrawn_by": withdrawn_by,
        "scope_kind": "content-review-batch-withdrawal",
        "scope_id": review_batch_id,
        "evidence_refs": list(evidence_refs),
        "challenge_id": challenge_id,
        "challenge_revision": challenge_revision,
        "user_action_ref": action_ref,
        "user_message_ref": message_ref,
        "confirmation_identity_type": identity_type,
        "host_assertion_sha256": assertion_digest,
        "confirmed_at": confirmed_at,
    }
    if normalized != payload:
        raise ContractValidationError(
            "ContentReviewBatchWithdrawal payload is not canonical"
        )
    return normalized
