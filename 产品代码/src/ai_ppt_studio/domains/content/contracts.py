"""Evidence-first v2.2 content artifact contracts."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from ai_ppt_studio.errors import ContractValidationError


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _boundary_text(payload: dict[str, Any], field: str) -> str:
    if field not in payload or not isinstance(payload[field], str):
        raise ContractValidationError(f"{field} must be a string")
    return payload[field].strip()


def _require_exact_keys(
    payload: dict[str, Any], fields: tuple[str, ...], contract: str
) -> None:
    expected, actual = set(fields), set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ContractValidationError(
            f"{contract} fields are not closed"
            f"; missing={missing}; unknown={unknown}"
        )


MATERIAL_MODES = frozenset({"material-backed", "mixed-evidence", "proposal-led"})
CONTENT_IDENTITIES = frozenset(
    {
        "来源事实",
        "材料推断",
        "用户已确认",
        "AI 分析",
        "诊断假设",
        "方案建议",
        "待联合验证",
        "证据缺口",
        "禁止使用",
    }
)
LEGACY_OPINION_KEYS = frozenset(
    {
        "desiredCustomerJudgment",
        "desired_customer_judgment",
        "customer_judgment",
        "coreClaim",
        "core_claim",
    }
)
STRONG_TITLE_PATTERN = re.compile(
    r"必须|唯一|最佳|领先|必然|确保|保证|彻底解决|显著(?:提升|降低)|决定性"
)
URL_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def _reject_legacy_opinion_fields(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = LEGACY_OPINION_KEYS.intersection(value)
        if forbidden:
            raise ContractValidationError(
                f"Legacy opinion-first field is forbidden: {sorted(forbidden)[0]}"
            )
        for child in value.values():
            _reject_legacy_opinion_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_legacy_opinion_fields(child)


def _v22_array(
    payload: dict[str, Any], field: str, *, non_empty: bool = False
) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list) or (non_empty and not value):
        raise ContractValidationError(f"{field} must be an array")
    return list(value)


def _v22_strings(
    payload: dict[str, Any], field: str, *, non_empty: bool = False
) -> list[str]:
    values = _v22_array(payload, field, non_empty=non_empty)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ContractValidationError(f"{field} must contain non-empty strings")
    return [value.strip() for value in values]


def _v22_objects(
    payload: dict[str, Any], field: str, *, non_empty: bool = False
) -> list[dict[str, Any]]:
    values = _v22_array(payload, field, non_empty=non_empty)
    if any(not isinstance(value, dict) for value in values):
        raise ContractValidationError(f"{field} must contain objects")
    return [dict(value) for value in values]


def _material_mode(payload: dict[str, Any]) -> str:
    mode = _text(payload, "material_mode")
    if mode not in MATERIAL_MODES:
        raise ContractValidationError(
            "material_mode must be material-backed, mixed-evidence, or proposal-led"
        )
    return mode


def _evidence_row(row: dict[str, Any], *, source_required: bool) -> dict[str, Any]:
    normalized = {
        "item_id": _text(row, "item_id"),
        "identity": _text(row, "identity"),
        "statement": _text(row, "statement"),
        "source_refs": _v22_strings(row, "source_refs", non_empty=source_required),
        "location": _text(row, "location"),
        "version": _text(row, "version"),
        "usable_for": _v22_strings(row, "usable_for", non_empty=True),
        "limitations": _v22_strings(row, "limitations"),
    }
    if normalized["identity"] not in CONTENT_IDENTITIES:
        raise ContractValidationError("Evidence row identity is unsupported")
    return normalized


def validate_presales_evidence_book(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("PresalesEvidenceBook must be an object")
    _reject_legacy_opinion_fields(payload)
    mode = _material_mode(payload)
    normalized = {
        "source_version": _text(payload, "source_version"),
        "material_mode": mode,
        "mission_confirmation_ref": _text(payload, "mission_confirmation_ref"),
        "material_inventory_ref": _boundary_text(payload, "material_inventory_ref"),
    }
    fields = (
        "facts",
        "user_confirmed_facts",
        "inferences",
        "conflicts",
        "unknowns",
        "evidence_gaps",
        "forbidden_extrapolations",
    )
    for field in fields:
        source_required = field in {"facts", "user_confirmed_facts"}
        normalized[field] = [
            _evidence_row(row, source_required=source_required)
            for row in _v22_objects(payload, field)
        ]
    normalized.update(
        {
            "excluded_material_refs": _v22_strings(payload, "excluded_material_refs"),
            "source_refs": _v22_strings(payload, "source_refs"),
            "generated_by": _text(payload, "generated_by"),
            "generated_at": _text(payload, "generated_at"),
        }
    )
    if normalized["generated_by"] != "presales-solution-chief":
        raise ContractValidationError("PresalesEvidenceBook must be generated by the chief")
    if mode == "proposal-led":
        if (
            normalized["material_inventory_ref"]
            or normalized["facts"]
            or normalized["user_confirmed_facts"]
            or normalized["source_refs"]
        ):
            raise ContractValidationError(
                "proposal-led evidence cannot claim project materials or customer facts"
            )
    else:
        if not normalized["material_inventory_ref"] or not normalized["source_refs"]:
            raise ContractValidationError(f"{mode} requires current material sources")
        if mode == "mixed-evidence" and not normalized["evidence_gaps"]:
            raise ContractValidationError("mixed-evidence requires explicit evidence gaps")
    return normalized


def validate_customer_decision_context(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("CustomerDecisionContext must be an object")
    _reject_legacy_opinion_fields(payload)
    return {
        "audience_roles": _v22_strings(payload, "audience_roles", non_empty=True),
        "decision_stage": _text(payload, "decision_stage"),
        "current_business_matter": _text(payload, "current_business_matter"),
        "known_consensus": _v22_strings(payload, "known_consensus"),
        "decision_questions": _v22_strings(payload, "decision_questions", non_empty=True),
        "constraints": _v22_strings(payload, "constraints"),
        "unresolved_questions": _v22_strings(payload, "unresolved_questions"),
        "supported_next_actions": _v22_strings(payload, "supported_next_actions", non_empty=True),
        "evidence_book_ref": _text(payload, "evidence_book_ref"),
    }


def _fit_node(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "id": _text(row, "id"),
        "statement": _text(row, "statement"),
        "identity": _text(row, "identity"),
        "evidence_refs": _v22_strings(row, "evidence_refs"),
    }
    if normalized["identity"] not in CONTENT_IDENTITIES:
        raise ContractValidationError("ProblemSolutionFit node identity is unsupported")
    if normalized["identity"] in {"来源事实", "用户已确认"} and not normalized["evidence_refs"]:
        raise ContractValidationError("Factual fit nodes require evidence")
    return normalized


def validate_problem_solution_fit_map(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ProblemSolutionFitMap must be an object")
    _reject_legacy_opinion_fields(payload)
    normalized: dict[str, Any] = {
        "evidence_book_ref": _text(payload, "evidence_book_ref"),
        "decision_context_ref": _text(payload, "decision_context_ref"),
    }
    node_fields = (
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
    ids: set[str] = set()
    for field in node_fields:
        rows = [_fit_node(row) for row in _v22_objects(payload, field)]
        if any(row["id"] in ids for row in rows):
            raise ContractValidationError("ProblemSolutionFit node ids must be unique")
        ids.update(row["id"] for row in rows)
        normalized[field] = rows
    mappings = []
    for row in _v22_objects(payload, "mappings", non_empty=True):
        mapping = {
            "mapping_id": _text(row, "mapping_id"),
            "problem_ref": _text(row, "problem_ref"),
            "requirement_ref": _text(row, "requirement_ref"),
            "solution_component_ref": _text(row, "solution_component_ref"),
            "identity": _text(row, "identity"),
            "evidence_refs": _v22_strings(row, "evidence_refs", non_empty=True),
        }
        if mapping["identity"] not in CONTENT_IDENTITIES:
            raise ContractValidationError("Mapping identity is unsupported")
        if any(mapping[key] not in ids for key in ("problem_ref", "requirement_ref", "solution_component_ref")):
            raise ContractValidationError("Mapping must reference current problem, requirement, and solution nodes")
        mappings.append(mapping)
    normalized["mappings"] = mappings
    return normalized


def _content_block(row: dict[str, Any]) -> dict[str, str]:
    _require_exact_keys(row, ("block_id", "text", "identity"), "ContentBlock")
    normalized = {
        "block_id": _text(row, "block_id"),
        "text": _text(row, "text"),
        "identity": _text(row, "identity"),
    }
    if normalized["identity"] not in CONTENT_IDENTITIES:
        raise ContractValidationError("Content block identity is unsupported")
    return normalized


def _material_view(row: dict[str, Any]) -> dict[str, Any]:
    _require_exact_keys(
        row,
        (
            "material_view_id",
            "source_ref",
            "asset_ref",
            "source_file_name",
            "page_number",
            "region_label",
            "purpose",
            "treatment",
            "evidence_identity",
        ),
        "material_view",
    )
    raw_asset_ref = row.get("asset_ref")
    asset_ref = _text(row, "asset_ref")
    asset_path = PurePosixPath(asset_ref)
    if (
        CONTROL_CHARACTER_PATTERN.search(raw_asset_ref)
        or URL_SCHEME_PATTERN.match(asset_ref)
        or asset_path.is_absolute()
        or not asset_path.parts
        or ".." in asset_path.parts
        or "\\" in asset_ref
        or asset_ref != asset_path.as_posix()
    ):
        raise ContractValidationError(
            "material_view asset_ref must be a project-relative POSIX path"
        )
    page_number = row.get("page_number")
    if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number < 1:
        raise ContractValidationError("material_view page_number must be a positive integer")
    evidence_identity = _text(row, "evidence_identity")
    if evidence_identity not in CONTENT_IDENTITIES:
        raise ContractValidationError("material_view evidence_identity is unsupported")
    return {
        "material_view_id": _text(row, "material_view_id"),
        "source_ref": _text(row, "source_ref"),
        "asset_ref": asset_ref,
        "source_file_name": _text(row, "source_file_name"),
        "page_number": page_number,
        "region_label": _text(row, "region_label"),
        "purpose": _text(row, "purpose"),
        "treatment": _text(row, "treatment"),
        "evidence_identity": evidence_identity,
    }


def _customer_decision_item(
    row: Any, *, material_mode: str
) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ContractValidationError(
            "customer_decision_item must be an object"
        )
    _require_exact_keys(
        row,
        ("text", "identity", "evidence_refs"),
        "customer_decision_item",
    )
    raw_text = row.get("text")
    text = _text(row, "text")
    if raw_text != text:
        raise ContractValidationError(
            "customer_decision_item text must be normalized"
        )
    if STRONG_TITLE_PATTERN.search(text):
        raise ContractValidationError(
            "customer_decision_item contains an unsupported conclusion"
        )
    identity = _text(row, "identity")
    if identity not in CONTENT_IDENTITIES:
        raise ContractValidationError(
            "customer_decision_item identity is unsupported"
        )
    evidence_refs = _v22_strings(row, "evidence_refs")
    if identity in {"来源事实", "用户已确认"} and not evidence_refs:
        raise ContractValidationError(
            "Factual customer_decision_item requires evidence"
        )
    if material_mode == "proposal-led" and (
        identity in {"来源事实", "用户已确认"} or evidence_refs
    ):
        raise ContractValidationError(
            "proposal-led customer_decision_item cannot claim customer facts or project evidence"
        )
    return {
        "text": text,
        "identity": identity,
        "evidence_refs": evidence_refs,
    }


def validate_reading_deck_blueprint(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ReadingDeckBlueprint must be an object")
    _require_exact_keys(
        payload,
        (
            "project_id",
            "source_version",
            "material_mode",
            "evidence_book_ref",
            "decision_context_ref",
            "problem_solution_fit_ref",
            "section_flow",
            "slides",
            "hard_gate_refs",
            "repair_history",
        ),
        "ReadingDeckBlueprint",
    )
    _reject_legacy_opinion_fields(payload)
    mode = _material_mode(payload)
    slides = []
    for row in _v22_objects(payload, "slides", non_empty=True):
        _require_exact_keys(
            row,
            (
                "slide_id",
                "order",
                "section_id",
                "page_task",
                "reading_question",
                "neutral_title",
                "customer_decision_item",
                "visible_copy_blocks",
                "identity_labels",
                "evidence_bindings",
                "material_views",
                "analysis_or_proposal_blocks",
                "solution_mapping_refs",
                "previous_relation",
                "next_relation",
                "speaker_notes",
                "reading_quality",
                "material_mode",
            ),
            "ReadingDeckBlueprint slide",
        )
        title = _text(row, "neutral_title")
        if STRONG_TITLE_PATTERN.search(title):
            raise ContractValidationError("neutral_title contains an unsupported conclusion")
        order = row.get("order")
        if isinstance(order, bool) or not isinstance(order, int) or order < 1:
            raise ContractValidationError("slide order must be a positive integer")
        slide_mode = _material_mode(row)
        if slide_mode != mode:
            raise ContractValidationError("slide material_mode must match the deck")
        quality = row.get("reading_quality")
        if not isinstance(quality, dict):
            raise ContractValidationError("reading_quality must be an object")
        _require_exact_keys(
            quality,
            ("independently_readable", "information_density", "review_note"),
            "reading_quality",
        )
        bindings = []
        for binding in _v22_objects(row, "evidence_bindings"):
            _require_exact_keys(
                binding,
                ("content_ref", "source_refs"),
                "evidence_binding",
            )
            bindings.append(
                {
                    "content_ref": _text(binding, "content_ref"),
                    "source_refs": _v22_strings(
                        binding, "source_refs", non_empty=True
                    ),
                }
            )
        material_views = [
            _material_view(material_view)
            for material_view in _v22_objects(row, "material_views")
        ]
        slide = {
            "slide_id": _text(row, "slide_id"),
            "order": order,
            "section_id": _text(row, "section_id"),
            "page_task": _text(row, "page_task"),
            "reading_question": _text(row, "reading_question"),
            "neutral_title": title,
            "customer_decision_item": _customer_decision_item(
                row.get("customer_decision_item"), material_mode=slide_mode
            ),
            "visible_copy_blocks": [_content_block(block) for block in _v22_objects(row, "visible_copy_blocks", non_empty=True)],
            "identity_labels": _v22_strings(row, "identity_labels", non_empty=True),
            "evidence_bindings": bindings,
            "material_views": material_views,
            "analysis_or_proposal_blocks": [_content_block(block) for block in _v22_objects(row, "analysis_or_proposal_blocks")],
            "solution_mapping_refs": _v22_strings(row, "solution_mapping_refs", non_empty=True),
            "previous_relation": _text(row, "previous_relation"),
            "next_relation": _text(row, "next_relation"),
            "speaker_notes": _text(row, "speaker_notes"),
            "reading_quality": {
                "independently_readable": quality.get("independently_readable")
                is True,
                "information_density": _text(quality, "information_density"),
                "review_note": _text(quality, "review_note"),
            },
            "material_mode": slide_mode,
        }
        if not set(slide["identity_labels"]).issubset(CONTENT_IDENTITIES):
            raise ContractValidationError("Slide identity_labels are unsupported")
        quality = slide["reading_quality"]
        if quality.get("independently_readable") is not True:
            raise ContractValidationError("Slide must be independently readable")
        _text(quality, "information_density")
        _text(quality, "review_note")
        if mode == "proposal-led":
            required = {"诊断假设", "方案建议", "待联合验证"}
            if not required.issubset(slide["identity_labels"]):
                raise ContractValidationError("proposal-led slides require hypothesis, recommendation, and validation identities")
            if slide["evidence_bindings"]:
                raise ContractValidationError("proposal-led slides cannot cite project evidence")
        elif not slide["evidence_bindings"]:
            raise ContractValidationError(f"{mode} slides require evidence bindings")
        slides.append(slide)
    orders = [slide["order"] for slide in slides]
    if sorted(orders) != list(range(1, len(slides) + 1)):
        raise ContractValidationError("slide order must be unique and contiguous from 1")
    if len({slide["slide_id"] for slide in slides}) != len(slides):
        raise ContractValidationError("slide_id must be unique")
    return {
        "project_id": _text(payload, "project_id"),
        "source_version": _text(payload, "source_version"),
        "material_mode": mode,
        "evidence_book_ref": _text(payload, "evidence_book_ref"),
        "decision_context_ref": _text(payload, "decision_context_ref"),
        "problem_solution_fit_ref": _text(payload, "problem_solution_fit_ref"),
        "section_flow": _v22_strings(payload, "section_flow", non_empty=True),
        "slides": slides,
        "hard_gate_refs": _v22_strings(payload, "hard_gate_refs"),
        "repair_history": _v22_objects(payload, "repair_history"),
    }


def _hard_gate_checks(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    checks = []
    for row in _v22_objects(payload, field):
        applicability = _text(row, "applicability")
        result = _text(row, "result")
        if applicability not in {"applicable", "not-applicable"}:
            raise ContractValidationError("Hard-gate applicability is invalid")
        if result not in {"passed", "failed", "not-applicable"}:
            raise ContractValidationError("Hard-gate result is invalid")
        if applicability == "not-applicable" and result != "not-applicable":
            raise ContractValidationError("Non-applicable checks must be not-applicable")
        failure_reason = _boundary_text(row, "failure_reason")
        if applicability == "applicable" and result == "failed" and not failure_reason:
            raise ContractValidationError("Failed hard-gate checks require a reason")
        checks.append(
            {
                "check_id": _text(row, "check_id"),
                "applicability": applicability,
                "result": result,
                "hard": row.get("hard") is True,
                "evidence_refs": _v22_strings(
                    row,
                    "evidence_refs",
                    non_empty=applicability == "applicable",
                ),
                "failure_reason": failure_reason,
            }
        )
    return checks


def validate_content_hard_gate_record(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("ContentHardGateRecord must be an object")
    gate_type = _text(payload, "gate_type")
    if gate_type not in {"evidence", "presales-reading"}:
        raise ContractValidationError("gate_type is invalid")
    reviewer_mode = _text(payload, "reviewer_mode")
    if reviewer_mode not in {"independent-agent", "isolated-review-task"}:
        raise ContractValidationError("reviewer_mode is invalid")
    normalized = {
        "gate_type": gate_type,
        "input_source_version": _text(payload, "input_source_version"),
        "input_hash": _text(payload, "input_hash"),
        "reviewer_mode": reviewer_mode,
        "independent_agent_instance_id": _boundary_text(
            payload, "independent_agent_instance_id"
        ),
        "context_pack_ref": _text(payload, "context_pack_ref"),
        "context_pack_hash": _text(payload, "context_pack_hash"),
        "output_ref": _boundary_text(payload, "output_ref"),
        "deterministic_check_results": _hard_gate_checks(
            payload, "deterministic_check_results"
        ),
        "semantic_check_results": _hard_gate_checks(
            payload, "semantic_check_results"
        ),
        "repair_requirements": _v22_objects(payload, "repair_requirements"),
        "reviewer_cannot_edit": payload.get("reviewer_cannot_edit") is True,
        "created_at": _text(payload, "created_at"),
    }
    if not normalized["reviewer_cannot_edit"]:
        raise ContractValidationError("reviewer_cannot_edit must be true")
    if reviewer_mode == "independent-agent" and any(
        not normalized[field]
        for field in (
            "independent_agent_instance_id",
            "input_hash",
            "context_pack_ref",
            "context_pack_hash",
            "output_ref",
        )
    ):
        raise ContractValidationError(
            "independent-agent requires instance, context, input, and output evidence"
        )
    failures = [
        check
        for check in (
            normalized["deterministic_check_results"]
            + normalized["semantic_check_results"]
        )
        if check["applicability"] == "applicable"
        and check["hard"]
        and check["result"] == "failed"
    ]
    computed = "failed" if failures else "passed"
    if payload.get("overall_result") != computed:
        raise ContractValidationError(f"overall_result must be {computed}")
    if failures and not normalized["repair_requirements"]:
        raise ContractValidationError("Failed hard gates require repair requirements")
    normalized["overall_result"] = computed
    return normalized
