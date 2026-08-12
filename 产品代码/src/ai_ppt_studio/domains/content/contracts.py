"""Formal v1.6 content artifact contracts."""

from __future__ import annotations

import json
import re
from typing import Any

from ai_ppt_studio.errors import (
    ContractValidationError,
    ProposalOnlyIdentityViolationError,
)

CONTENT_STAGES: dict[str, tuple[str, str]] = {
    "strategy": ("content/strategy", "presales-content-strategy"),
    "claim-map": ("content/claim-map", "claim-evidence-map"),
    "argument-map": ("content/argument-map", "deck-argument-map"),
    "slide-draft-set": ("content/draft", "slide-draft-set"),
}

REQUIRED_CONTENT_REVIEW_ROLES = (
    "presales-reviewer",
    "decision-maker-reviewer",
    "evidence-reviewer",
    "narrative-reviewer",
    "editorial-reviewer",
)
CONTENT_RULE_LEVELS = frozenset(
    {"must-follow", "minimum-content-quality", "reference-implementation"}
)
HARD_CONTENT_RULE_LEVELS = frozenset(
    {"must-follow", "minimum-content-quality"}
)
PROPOSAL_IDENTITY_CLASSES = frozenset(
    {
        "diagnostic-hypothesis",
        "solution-recommendation",
        "joint-validation-required",
    }
)
PROPOSAL_STATUS_BY_CLASS = {
    "diagnostic-hypothesis": "hypothesis",
    "solution-recommendation": "recommended",
    "joint-validation-required": "validation-required",
}
PROHIBITED_PROPOSAL_PATTERNS = (
    (re.compile(r"\d"), "unsourced-number"),
    (re.compile(r"成功案例|客户案例|客户引语"), "unsourced-case"),
    (re.compile(r"客户(?:已经|已|现有|确认|明确|当前)"), "unsourced-customer-fact"),
    (re.compile(r"保证|承诺|必然|一定能够|确保.{0,12}(?:提升|实现|达到)"), "unsupported-promise"),
)


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _objects(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = payload.get(field)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, dict) for item in value
    ):
        raise ContractValidationError(f"{field} must be a non-empty object array")
    return [dict(item) for item in value]


def validate_content_stage(stage: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the task-specific minimum for one formal content artifact."""

    if stage not in CONTENT_STAGES or not isinstance(payload, dict):
        raise ContractValidationError(f"Unsupported content stage: {stage}")
    normalized = dict(payload)
    if stage == "strategy":
        for field in ("mission_ref", "decision_stage", "core_tension"):
            normalized[field] = _text(payload, field)
        identity_mode = _text(payload, "content_identity_mode")
        if identity_mode == "material-backed":
            normalized["material_inventory_ref"] = _text(
                payload, "material_inventory_ref"
            )
        elif identity_mode == "proposal-only":
            normalized["empty_material_identity"] = _text(
                payload, "empty_material_identity"
            )
        else:
            raise ContractValidationError(
                "content_identity_mode must be material-backed or proposal-only"
            )
    elif stage == "claim-map":
        normalized["strategy_ref"] = _text(payload, "strategy_ref")
        claims = _objects(payload, "claims")
        for claim in claims:
            for field in ("claim_id", "status"):
                claim[field] = _text(claim, field)
            refs = claim.get("evidence_refs")
            proposal_only = (
                payload.get("content_identity_mode") == "proposal-only"
            )
            if not isinstance(refs, list) or (
                not proposal_only and not refs
            ) or any(
                not isinstance(ref, str) or not ref.strip() for ref in refs
            ):
                raise ContractValidationError(
                    "Every material-backed claim requires at least one evidence reference"
                )
            claim["evidence_refs"] = list(refs)
        normalized["claims"] = claims
    elif stage == "argument-map":
        normalized["strategy_ref"] = _text(payload, "strategy_ref")
        normalized["claim_evidence_map_ref"] = _text(
            payload, "claim_evidence_map_ref"
        )
        chapters = _objects(payload, "chapters")
        for chapter in chapters:
            chapter["chapter_id"] = _text(chapter, "chapter_id")
            chapter["task"] = _text(chapter, "task")
        normalized["chapters"] = chapters
    else:
        normalized["argument_map_ref"] = _text(payload, "argument_map_ref")
        slides = _objects(payload, "slides")
        for slide in slides:
            for field in (
                "slide_id",
                "title",
                "communication_goal",
                "core_claim",
                "speaker_notes",
            ):
                slide[field] = _text(slide, field)
            for field in ("visible_copy", "source_refs"):
                values = slide.get(field)
                allow_empty = (
                    field == "source_refs"
                    and payload.get("content_identity_mode") == "proposal-only"
                )
                if not isinstance(values, list) or (
                    not allow_empty and not values
                ) or any(
                    not isinstance(value, str) or not value.strip()
                    for value in values
                ):
                    raise ContractValidationError(
                        f"Every slide requires non-empty {field}"
                    )
        normalized["slides"] = slides
    if normalized.get("content_identity_mode") == "proposal-only":
        validate_proposal_only_identity(stage, normalized)
    return normalized


def validate_proposal_only_identity(
    stage: str, payload: dict[str, Any]
) -> None:
    """Keep no-material content visibly hypothetical and non-committal."""

    labels = payload.get("identity_labels")
    if not isinstance(labels, list) or not PROPOSAL_IDENTITY_CLASSES.issubset(
        {str(value) for value in labels}
    ):
        raise ProposalOnlyIdentityViolationError(
            "PROPOSAL_ONLY_IDENTITY_VIOLATION: all proposal-only identity labels are required"
        )
    semantic = _semantic_proposal_text(stage, payload)
    semantic_for_checks = semantic.replace("不代表客户已确认事实", "")
    for pattern, reason in PROHIBITED_PROPOSAL_PATTERNS:
        if pattern.search(semantic_for_checks):
            raise ProposalOnlyIdentityViolationError(
                f"PROPOSAL_ONLY_IDENTITY_VIOLATION: {reason}"
            )
    if stage == "strategy":
        if not any(
            label in str(payload.get("core_tension") or "")
            for label in ("诊断假设", "方案建议", "待联合验证")
        ):
            raise ProposalOnlyIdentityViolationError(
                "PROPOSAL_ONLY_IDENTITY_VIOLATION: strategy identity is not visible"
            )
    elif stage == "claim-map":
        for claim in payload["claims"]:
            identity_class = str(claim.get("identity_class") or "")
            if identity_class not in PROPOSAL_IDENTITY_CLASSES:
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: claim identity_class is invalid"
                )
            if claim.get("status") != PROPOSAL_STATUS_BY_CLASS[identity_class]:
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: claim status overstates its identity"
                )
            if claim.get("evidence_refs"):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: no-material claim cannot cite project materials"
                )
    elif stage == "argument-map":
        for chapter in payload["chapters"]:
            if not any(
                label in chapter["task"]
                for label in ("诊断假设", "方案建议", "待联合验证")
            ):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: chapter task lacks a visible identity"
                )
    else:
        for slide in payload["slides"]:
            if str(slide.get("identity_class") or "") not in (
                PROPOSAL_IDENTITY_CLASSES
            ):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: slide identity_class is invalid"
                )
            if slide.get("source_refs"):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: no-material slide cannot cite project materials"
                )
            visible = " ".join(
                [
                    slide["core_claim"],
                    *slide["visible_copy"],
                    slide["speaker_notes"],
                ]
            )
            if not any(
                label in visible
                for label in (
                    "诊断假设",
                    "方案建议",
                    "待联合验证",
                    "不代表客户已确认事实",
                )
            ):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: slide identity is not visible"
                )


def _semantic_proposal_text(stage: str, payload: dict[str, Any]) -> str:
    """Serialize user-visible semantic fields while excluding technical IDs."""

    if stage == "strategy":
        values: Any = {
            "decision_stage": payload.get("decision_stage"),
            "core_tension": payload.get("core_tension"),
        }
    elif stage == "claim-map":
        values = [
            {
                "claim": claim.get("claim"),
                "status": claim.get("status"),
                "identity_class": claim.get("identity_class"),
            }
            for claim in payload.get("claims") or []
        ]
    elif stage == "argument-map":
        values = [chapter.get("task") for chapter in payload.get("chapters") or []]
    else:
        values = [
            {
                key: slide.get(key)
                for key in (
                    "title",
                    "communication_goal",
                    "core_claim",
                    "visible_copy",
                    "speaker_notes",
                )
            }
            for slide in payload.get("slides") or []
        ]
    return json.dumps(values, ensure_ascii=False)


def validate_content_review(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one isolated review record and compute its hard result."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ContentReviewRecord must be an object")
    normalized = dict(payload)
    normalized["target_ref"] = _text(payload, "target_ref")
    normalized["input_version"] = _text(payload, "input_version")
    role = _text(payload, "reviewer_role")
    if role not in REQUIRED_CONTENT_REVIEW_ROLES:
        raise ContractValidationError(f"Unknown content review role: {role}")
    normalized["reviewer_role"] = role
    checks = _objects(payload, "checks")
    hard_failed = False
    for check in checks:
        check["criterion_id"] = _text(check, "criterion_id")
        level = _text(check, "level")
        applicability = _text(check, "applicability")
        result = _text(check, "result")
        if level not in CONTENT_RULE_LEVELS:
            raise ContractValidationError(f"Unknown content rule level: {level}")
        if applicability not in {"applicable", "not-applicable"}:
            raise ContractValidationError(
                f"Unknown content check applicability: {applicability}"
            )
        if result not in {"passed", "failed", "not-applicable"}:
            raise ContractValidationError(f"Unknown content check result: {result}")
        if applicability == "not-applicable" and result != "not-applicable":
            raise ContractValidationError(
                "A non-applicable check must have result not-applicable"
            )
        evidence_refs = check.get("evidence_refs")
        if applicability == "applicable" and (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or any(not isinstance(ref, str) or not ref for ref in evidence_refs)
        ):
            raise ContractValidationError(
                "Every applicable content check requires evidence"
            )
        if applicability == "applicable" and result == "failed":
            if not str(check.get("failure_reason") or "").strip():
                raise ContractValidationError("Failed checks require a reason")
            if level in HARD_CONTENT_RULE_LEVELS:
                hard_failed = True
    computed = "failed" if hard_failed else "passed"
    if str(payload.get("overall_result") or "") != computed:
        raise ContractValidationError(
            f"Content review overall_result must be {computed}"
        )
    normalized["checks"] = checks
    normalized["overall_result"] = computed
    return normalized


def aggregate_content_reviews(
    target_ref: str,
    review_records: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Require exactly one passing record from every isolated review role."""

    by_role: dict[str, tuple[str, dict[str, Any]]] = {}
    blockers: list[str] = []
    for reference, raw in review_records:
        review = validate_content_review(raw)
        role = review["reviewer_role"]
        if role in by_role:
            blockers.append(f"duplicate:{role}")
        by_role[role] = (reference, review)
        if review["target_ref"] != target_ref or review["input_version"] != target_ref:
            blockers.append(f"stale:{role}")
        if review["overall_result"] != "passed":
            blockers.append(f"failed:{role}")
    blockers.extend(
        f"missing:{role}"
        for role in REQUIRED_CONTENT_REVIEW_ROLES
        if role not in by_role
    )
    if blockers:
        from ai_ppt_studio.errors import GateBlockedError

        raise GateBlockedError("content-acceptance", tuple(sorted(blockers)))
    ordered_refs = [by_role[role][0] for role in REQUIRED_CONTENT_REVIEW_ROLES]
    return {
        "target_ref": target_ref,
        "review_record_refs": ordered_refs,
        "required_roles": list(REQUIRED_CONTENT_REVIEW_ROLES),
        "all_applicable_checks": [
            check
            for role in REQUIRED_CONTENT_REVIEW_ROLES
            for check in by_role[role][1]["checks"]
        ],
        "overall_result": "passed",
    }
