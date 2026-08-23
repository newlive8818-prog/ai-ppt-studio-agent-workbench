"""Formal v1.6 content artifact contracts."""

from __future__ import annotations

import copy
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
GATE_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z0-9])G[0-4](?![A-Za-z0-9])")
READING_DENSITY_LEVELS = frozenset({"low", "moderate", "high"})
EVIDENCE_KINDS = frozenset({"material", "planned-gap"})

V22_MATERIAL_MODES = frozenset(
    {"material-backed", "mixed-evidence", "proposal-led"}
)
V22_CONTENT_IDENTITIES = frozenset(
    {
        "来源事实",
        "材料推断",
        "用户已确认",
        "诊断假设",
        "方案建议",
        "待联合验证",
        "证据缺口",
        "禁止使用",
    }
)
V22_PROHIBITED_PERSUASION_FIELDS = frozenset(
    {
        "desiredCustomerJudgment",
        "desired_customer_judgment",
        "coreClaim",
        "core_claim",
    }
)
V22_UNSUPPORTED_TITLE_PATTERN = re.compile(
    r"(?:唯一(?:正确|选择|方案)?|必须|必然|最佳|领先|显著提升|确保|保证|证明)"
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


def _string_array(
    payload: dict[str, Any], field: str, *, allow_empty: bool = False
) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or (not allow_empty and not value) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ContractValidationError(f"{field} must be a string array")
    return [item.strip() for item in value]


def _boundary_text(payload: dict[str, Any], field: str) -> str:
    if field not in payload or not isinstance(payload[field], str):
        raise ContractValidationError(f"{field} must be a string")
    return payload[field].strip()


def _validate_visible_copy(slide: dict[str, Any]) -> list[dict[str, str]]:
    items = _objects(slide, "visible_copy")
    return [
        {
            "copy_id": _text(item, "copy_id"),
            "role": _text(item, "role"),
            "text": _text(item, "text"),
        }
        for item in items
    ]


def _validate_evidence_items(slide: dict[str, Any]) -> list[dict[str, str]]:
    items = _objects(slide, "evidence_items")
    normalized: list[dict[str, str]] = []
    fields = (
        "evidence_id",
        "source_file",
        "source_page_or_region",
        "used_region",
        "supports_claim",
        "treatment",
        "fact_identity",
        "evidence_gap",
    )
    for item in items:
        evidence = {field: _text(item, field) for field in fields}
        evidence_kind = _text(item, "evidence_kind")
        if evidence_kind not in EVIDENCE_KINDS:
            raise ContractValidationError(
                "evidence_kind must be material or planned-gap"
            )
        evidence["evidence_kind"] = evidence_kind
        if evidence_kind == "material":
            evidence["material_ref"] = _text(item, "material_ref")
            evidence["asset_ref"] = _text(item, "asset_ref")
        else:
            evidence["material_ref"] = _boundary_text(item, "material_ref")
            evidence["asset_ref"] = _boundary_text(item, "asset_ref")
            if evidence["treatment"] != "to-supply":
                raise ContractValidationError(
                    "planned-gap treatment must be to-supply"
                )
            if evidence["fact_identity"] != "joint-validation-required":
                raise ContractValidationError(
                    "planned-gap fact_identity must be joint-validation-required"
                )
        normalized.append(
            {
                field: evidence[field]
                for field in (
                    "evidence_id",
                    "evidence_kind",
                    "material_ref",
                    "asset_ref",
                    "source_file",
                    "source_page_or_region",
                    "used_region",
                    "supports_claim",
                    "treatment",
                    "fact_identity",
                    "evidence_gap",
                )
            }
        )
    return normalized


def _validate_reading_quality(slide: dict[str, Any]) -> dict[str, Any]:
    quality = slide.get("reading_quality")
    if not isinstance(quality, dict):
        raise ContractValidationError("reading_quality must be an object")
    if quality.get("independently_readable") is not True:
        raise ContractValidationError("independently_readable must be true")
    density = _text(quality, "information_density")
    if density not in READING_DENSITY_LEVELS:
        raise ContractValidationError(
            "information_density must be low, moderate, or high"
        )
    if quality.get("claim_reason_evidence_boundary_complete") is not True:
        raise ContractValidationError(
            "claim_reason_evidence_boundary_complete must be true"
        )
    return {
        "independently_readable": True,
        "information_density": density,
        "claim_reason_evidence_boundary_complete": True,
        "review_note": _text(quality, "review_note"),
    }


def _validate_sequence(slide: dict[str, Any]) -> dict[str, str]:
    sequence = slide.get("sequence")
    if not isinstance(sequence, dict):
        raise ContractValidationError("sequence must be an object")
    return {
        "previous_slide_id": _boundary_text(sequence, "previous_slide_id"),
        "next_slide_id": _boundary_text(sequence, "next_slide_id"),
        "transition_from_previous": _text(
            sequence, "transition_from_previous"
        ),
        "transition_to_next": _text(sequence, "transition_to_next"),
    }


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
                "chapter_id",
                "title",
                "page_purpose",
                "customer_judgment",
                "communication_goal",
                "core_claim",
                "speaker_notes",
                "user_judgment_prompt",
            ):
                slide[field] = _text(slide, field)
            order = slide.get("order")
            if (
                isinstance(order, bool)
                or not isinstance(order, int)
                or order < 1
            ):
                raise ContractValidationError("order must be a positive integer")
            slide["order"] = order
            slide["visible_copy"] = _validate_visible_copy(slide)
            slide["evidence_items"] = _validate_evidence_items(slide)
            slide["reading_quality"] = _validate_reading_quality(slide)
            slide["sequence"] = _validate_sequence(slide)
            slide["source_refs"] = _string_array(
                slide,
                "source_refs",
                allow_empty=(
                    payload.get("content_identity_mode") == "proposal-only"
                ),
            )
        orders = [slide["order"] for slide in slides]
        if len(set(orders)) != len(orders) or sorted(orders) != list(
            range(1, len(slides) + 1)
        ):
            raise ContractValidationError(
                "slide order must be unique and contiguous from 1"
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
        pattern_input = (
            GATE_TOKEN_PATTERN.sub("GATE", semantic_for_checks)
            if reason == "unsourced-number"
            else semantic_for_checks
        )
        if pattern.search(pattern_input):
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
            for evidence in slide["evidence_items"]:
                if (
                    evidence.get("evidence_kind") != "planned-gap"
                    or evidence.get("material_ref") != ""
                    or evidence.get("asset_ref") != ""
                ):
                    raise ProposalOnlyIdentityViolationError(
                        "PROPOSAL_ONLY_IDENTITY_VIOLATION: proposal-only evidence must be an unbound planned-gap"
                    )
            visible = " ".join(
                [
                    slide["core_claim"],
                    *[item["text"] for item in slide["visible_copy"]],
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
                "title": slide.get("title"),
                "page_purpose": slide.get("page_purpose"),
                "customer_judgment": slide.get("customer_judgment"),
                "communication_goal": slide.get("communication_goal"),
                "core_claim": slide.get("core_claim"),
                "visible_copy": [
                    {
                        "role": item.get("role"),
                        "text": item.get("text"),
                    }
                    for item in slide.get("visible_copy") or []
                ],
                "speaker_notes": slide.get("speaker_notes"),
                "user_judgment_prompt": slide.get("user_judgment_prompt"),
                "evidence_items": [
                    {
                        key: evidence.get(key)
                        for key in (
                            "source_file",
                            "source_page_or_region",
                            "used_region",
                            "supports_claim",
                            "treatment",
                            "fact_identity",
                            "evidence_gap",
                        )
                    }
                    for evidence in slide.get("evidence_items") or []
                ],
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


def _v22_reject_persuasion_fields(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in V22_PROHIBITED_PERSUASION_FIELDS:
                raise ContractValidationError(f"{path}.{key} is forbidden")
            _v22_reject_persuasion_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _v22_reject_persuasion_fields(child, path=f"{path}[{index}]")


def _v22_list(
    payload: dict[str, Any],
    field: str,
    *,
    non_empty: bool = False,
    objects: bool = False,
) -> list[Any]:
    if field not in payload or not isinstance(payload[field], list):
        raise ContractValidationError(f"{field} must be an array")
    values = copy.deepcopy(payload[field])
    if non_empty and not values:
        raise ContractValidationError(f"{field} must not be empty")
    if objects and any(not isinstance(item, dict) for item in values):
        raise ContractValidationError(f"{field} must be an object array")
    return values


def _v22_strings(
    payload: dict[str, Any], field: str, *, non_empty: bool = False
) -> list[str]:
    values = _v22_list(payload, field, non_empty=non_empty)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ContractValidationError(f"{field} must be a string array")
    return [item.strip() for item in values]


def _v22_mode(payload: dict[str, Any], *, field: str = "material_mode") -> str:
    mode = _text(payload, field)
    if mode not in V22_MATERIAL_MODES:
        raise ContractValidationError(
            f"{field} must be material-backed, mixed-evidence, or proposal-led"
        )
    return mode


def _v22_identity(payload: dict[str, Any], *, field: str = "identity") -> str:
    identity = _text(payload, field)
    if identity not in V22_CONTENT_IDENTITIES:
        raise ContractValidationError(f"{field} is not a supported content identity")
    return identity


def _v22_evidence_entry(
    value: dict[str, Any], *, require_source: bool
) -> dict[str, Any]:
    normalized = {
        "identity": _v22_identity(value),
        "statement": _text(value, "statement"),
        "source_refs": _v22_strings(value, "source_refs"),
        "location": _text(value, "location"),
        "version": _text(value, "version"),
        "usable_for": _v22_strings(value, "usable_for", non_empty=True),
        "limitations": _v22_strings(value, "limitations"),
    }
    if require_source and not normalized["source_refs"]:
        raise ContractValidationError("source_refs must bind every customer fact")
    return normalized


def validate_presales_evidence_book(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the v2.2 evidence boundary without accepting v1.6 modes."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PresalesEvidenceBook must be an object")
    _v22_reject_persuasion_fields(payload)
    normalized: dict[str, Any] = {
        "source_version": _text(payload, "source_version"),
        "material_mode": _v22_mode(payload),
    }
    entry_fields = (
        "facts",
        "user_confirmed_facts",
        "inferences",
        "conflicts",
        "unknowns",
        "evidence_gaps",
    )
    for field in entry_fields:
        values = _v22_list(payload, field, objects=True)
        require_source = field in {"facts", "user_confirmed_facts"}
        normalized[field] = [
            _v22_evidence_entry(item, require_source=require_source)
            for item in values
        ]
    normalized.update(
        {
            "forbidden_extrapolations": _v22_strings(
                payload, "forbidden_extrapolations"
            ),
            "excluded_material_refs": _v22_strings(
                payload, "excluded_material_refs"
            ),
            "source_refs": _v22_strings(payload, "source_refs"),
            "generated_by": _text(payload, "generated_by"),
            "generated_at": _text(payload, "generated_at"),
        }
    )
    if normalized["generated_by"] != "presales-solution-chief":
        raise ContractValidationError(
            "generated_by must be presales-solution-chief"
        )
    if normalized["material_mode"] == "proposal-led" and (
        normalized["facts"]
        or normalized["user_confirmed_facts"]
        or normalized["source_refs"]
    ):
        raise ContractValidationError(
            "proposal-led evidence book cannot contain sourced customer facts"
        )
    return normalized


def validate_customer_decision_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate customer decision context without a desired conclusion field."""

    if not isinstance(payload, dict):
        raise ContractValidationError("CustomerDecisionContext must be an object")
    _v22_reject_persuasion_fields(payload)
    return {
        "audience_roles": _v22_strings(payload, "audience_roles", non_empty=True),
        "decision_stage": _text(payload, "decision_stage"),
        "current_business_matter": _text(payload, "current_business_matter"),
        "known_consensus": _v22_strings(payload, "known_consensus"),
        "decision_questions": _v22_strings(
            payload, "decision_questions", non_empty=True
        ),
        "constraints": _v22_strings(payload, "constraints"),
        "unresolved_questions": _v22_strings(payload, "unresolved_questions"),
        "supported_next_actions": _v22_strings(
            payload, "supported_next_actions", non_empty=True
        ),
        "evidence_book_ref": _text(payload, "evidence_book_ref"),
    }


def _v22_fit_item(value: dict[str, Any], *, field: str) -> dict[str, str]:
    return {
        "item_id": _text(value, "item_id"),
        "identity": _v22_identity(value),
        "statement": _text(value, "statement"),
    }


def validate_problem_solution_fit_map(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate traceable problem-to-requirement-to-solution mappings."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ProblemSolutionFitMap must be an object")
    _v22_reject_persuasion_fields(payload)
    normalized: dict[str, Any] = {}
    collection_fields = (
        "situations",
        "symptoms",
        "causes_or_hypotheses",
        "impacts",
        "constraints",
        "unknowns",
        "derived_requirements",
        "solution_components",
        "boundaries",
        "alternatives",
        "validation_items",
    )
    known_ids: set[str] = set()
    for field in collection_fields:
        values = _v22_list(payload, field, objects=True)
        normalized[field] = [_v22_fit_item(item, field=field) for item in values]
        for item in normalized[field]:
            if item["item_id"] in known_ids:
                raise ContractValidationError(f"duplicate item_id: {item['item_id']}")
            known_ids.add(item["item_id"])
    mappings = _v22_list(payload, "mappings", non_empty=True, objects=True)
    normalized_mappings: list[dict[str, Any]] = []
    for mapping in mappings:
        normalized_mapping = {
            "mapping_id": _text(mapping, "mapping_id"),
            "problem_refs": _v22_strings(
                mapping, "problem_refs", non_empty=True
            ),
            "requirement_refs": _v22_strings(
                mapping, "requirement_refs", non_empty=True
            ),
            "solution_component_refs": _v22_strings(
                mapping, "solution_component_refs", non_empty=True
            ),
            "identity": _v22_identity(mapping),
            "evidence_refs": _v22_strings(
                mapping, "evidence_refs", non_empty=True
            ),
        }
        for field in (
            "problem_refs",
            "requirement_refs",
            "solution_component_refs",
        ):
            missing = set(normalized_mapping[field]) - known_ids
            if missing:
                raise ContractValidationError(
                    f"{field} contains unknown refs: {', '.join(sorted(missing))}"
                )
        normalized_mappings.append(normalized_mapping)
    normalized["mappings"] = normalized_mappings
    return normalized


def _v22_copy_block(value: dict[str, Any], *, field: str) -> dict[str, str]:
    normalized = {
        "block_id": _text(value, "block_id"),
        "text": _text(value, "text"),
    }
    if field == "visible_copy_blocks":
        normalized["role"] = _text(value, "role")
    else:
        normalized["identity"] = _v22_identity(value)
    return normalized


def _v22_reading_quality(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError("reading_quality must be an object")
    normalized: dict[str, Any] = {}
    for field in (
        "independently_readable",
        "complete_visible_copy",
        "identity_boundary_complete",
    ):
        if value.get(field) is not True:
            raise ContractValidationError(f"reading_quality.{field} must be true")
        normalized[field] = True
    normalized["review_note"] = _text(value, "review_note")
    return normalized


def _v22_reject_proposal_led_semantics(slide: dict[str, Any]) -> None:
    semantic = re.sub(
        r"不代表客户已确认(?:事实|方案)",
        "",
        " ".join(
        [
            str(slide.get("page_task") or ""),
            str(slide.get("reading_question") or ""),
            str(slide.get("neutral_title") or ""),
            *[
                str(item.get("text") or "")
                for item in slide.get("visible_copy_blocks") or []
                if isinstance(item, dict)
            ],
            *[
                str(item.get("text") or "")
                for item in slide.get("analysis_or_proposal_blocks") or []
                if isinstance(item, dict)
            ],
            str(slide.get("speaker_notes") or ""),
        ]
        ),
    )
    for pattern, reason in PROHIBITED_PROPOSAL_PATTERNS:
        if pattern.search(semantic):
            raise ContractValidationError(
                f"proposal-led content violates {reason} boundary"
            )


def validate_reading_deck_blueprint(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a complete, reading-first v2.2 deck blueprint."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ReadingDeckBlueprint must be an object")
    _v22_reject_persuasion_fields(payload)
    deck_mode = _v22_mode(payload)
    normalized: dict[str, Any] = {
        "project_id": _text(payload, "project_id"),
        "source_version": _text(payload, "source_version"),
        "material_mode": deck_mode,
        "evidence_book_ref": _text(payload, "evidence_book_ref"),
        "decision_context_ref": _text(payload, "decision_context_ref"),
        "problem_solution_fit_ref": _text(payload, "problem_solution_fit_ref"),
        "section_flow": _v22_strings(payload, "section_flow", non_empty=True),
        "hard_gate_refs": _v22_strings(payload, "hard_gate_refs"),
        "repair_history": _v22_list(payload, "repair_history"),
    }
    slides = _v22_list(payload, "slides", non_empty=True, objects=True)
    normalized_slides: list[dict[str, Any]] = []
    for slide in slides:
        order = slide.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ContractValidationError("order must be a positive integer")
        title = _text(slide, "neutral_title")
        if V22_UNSUPPORTED_TITLE_PATTERN.search(title):
            raise ContractValidationError(
                "neutral_title contains an unsupported strong conclusion"
            )
        slide_mode = _v22_mode(slide)
        if slide_mode != deck_mode:
            raise ContractValidationError(
                "slide material_mode must equal deck material_mode"
            )
        if deck_mode == "proposal-led":
            _v22_reject_proposal_led_semantics(slide)
        visible_copy = _v22_list(
            slide, "visible_copy_blocks", non_empty=True, objects=True
        )
        analysis = _v22_list(
            slide, "analysis_or_proposal_blocks", objects=True
        )
        identity_labels = _v22_strings(
            slide, "identity_labels", non_empty=True
        )
        if any(label not in V22_CONTENT_IDENTITIES for label in identity_labels):
            raise ContractValidationError("identity_labels contains an invalid identity")
        bindings = _v22_list(
            slide, "evidence_bindings", non_empty=True, objects=True
        )
        normalized_bindings: list[dict[str, Any]] = []
        for binding in bindings:
            normalized_bindings.append(
                {
                    "binding_id": _text(binding, "binding_id"),
                    "identity": _v22_identity(binding),
                    "source_refs": _v22_strings(binding, "source_refs"),
                    "supports_block_refs": _v22_strings(
                        binding, "supports_block_refs", non_empty=True
                    ),
                }
            )
        normalized_slides.append(
            {
                "slide_id": _text(slide, "slide_id"),
                "order": order,
                "section_id": _text(slide, "section_id"),
                "page_task": _text(slide, "page_task"),
                "reading_question": _text(slide, "reading_question"),
                "neutral_title": title,
                "visible_copy_blocks": [
                    _v22_copy_block(item, field="visible_copy_blocks")
                    for item in visible_copy
                ],
                "identity_labels": identity_labels,
                "evidence_bindings": normalized_bindings,
                "analysis_or_proposal_blocks": [
                    _v22_copy_block(item, field="analysis_or_proposal_blocks")
                    for item in analysis
                ],
                "solution_mapping_refs": _v22_strings(
                    slide, "solution_mapping_refs", non_empty=True
                ),
                "previous_relation": _text(slide, "previous_relation"),
                "next_relation": _text(slide, "next_relation"),
                "speaker_notes": _text(slide, "speaker_notes"),
                "reading_quality": _v22_reading_quality(
                    slide.get("reading_quality")
                ),
                "material_mode": slide_mode,
            }
        )
    orders = [slide["order"] for slide in normalized_slides]
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise ContractValidationError(
            "slide order must be unique and contiguous from 1"
        )
    normalized["slides"] = normalized_slides
    return normalized
