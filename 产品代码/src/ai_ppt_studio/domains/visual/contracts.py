"""Formal visual contracts for strict route B."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath
from typing import Any

from ai_ppt_studio.domains.presentation.release_policy import SUPPORTED_TARGET_IDS
from ai_ppt_studio.errors import ContractValidationError

VISUAL_RULE_LEVELS = frozenset(
    {"must-follow", "minimum-aesthetic", "reference-implementation"}
)
HARD_VISUAL_RULE_LEVELS = frozenset({"must-follow", "minimum-aesthetic"})
FORBIDDEN_SCORE_FIELDS = frozenset(
    {"score", "rating", "weighted_score", "average", "vote_count", "conditional_pass"}
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
URL_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _nonempty(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if not isinstance(value, (dict, list, str)) or not value:
        raise ContractValidationError(f"{field} must be non-empty")
    return value


def _strict_route(payload: dict[str, Any]) -> None:
    if payload.get("production_route") != "strict-B":
        raise ContractValidationError("Formal visual production requires strict-B")
    forbidden = {
        "image2_master_ref",
        "whole_slide_image_ref",
        "visual_exploration_master_ref",
    }
    if forbidden.intersection(payload):
        raise ContractValidationError(
            "Formal route B cannot consume an Image 2 whole-slide master"
        )


def _project_relative_posix_path(
    value: Any, field: str, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be a string")
    if allow_empty and value == "":
        return ""
    if not value or value != value.strip():
        raise ContractValidationError(
            f"{field} must be a project-relative POSIX path"
        )
    path = PurePosixPath(value)
    if (
        any(unicodedata.category(character).startswith("C") for character in value)
        or URL_SCHEME_PATTERN.match(value)
        or path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or "\\" in value
        or value != path.as_posix()
    ):
        raise ContractValidationError(
            f"{field} must be a project-relative POSIX path"
        )
    return value


def validate_anchor_render_assets(
    payload: dict[str, Any], *, valid_slide_ids: set[str] | None = None
) -> dict[str, Any]:
    """Close the three-slide identity and its current/previous review renders."""

    if not isinstance(payload, dict):
        raise ContractValidationError("Anchor render identity must be an object")
    slide_ids = payload.get("slide_ids")
    if (
        not isinstance(slide_ids, list)
        or len(slide_ids) != 3
        or any(
            not isinstance(slide_id, str)
            or not slide_id
            or slide_id != slide_id.strip()
            for slide_id in slide_ids
        )
        or len(set(slide_ids)) != 3
    ):
        raise ContractValidationError(
            "AnchorSlideSet must contain exactly three unique slide IDs"
        )
    if valid_slide_ids is not None and not set(slide_ids).issubset(
        valid_slide_ids
    ):
        raise ContractValidationError(
            "Every anchor slide must belong to the current visual contract set"
        )

    render_assets = payload.get("render_assets")
    if (
        not isinstance(render_assets, list)
        or len(render_assets) != 3
        or any(not isinstance(item, dict) for item in render_assets)
    ):
        raise ContractValidationError(
            "AnchorSlideSet render_assets must contain exactly three objects"
        )
    normalized_assets: list[dict[str, str]] = []
    expected_fields = {
        "slide_id",
        "current_asset_ref",
        "previous_asset_ref",
    }
    for expected_slide_id, item in zip(slide_ids, render_assets, strict=True):
        if set(item) != expected_fields:
            raise ContractValidationError(
                "Anchor render assets must use the closed current/previous schema"
            )
        slide_id = item.get("slide_id")
        if slide_id != expected_slide_id:
            raise ContractValidationError(
                "Anchor render assets must uniquely follow slide_ids order"
            )
        current_asset_ref = _project_relative_posix_path(
            item.get("current_asset_ref"),
            "current_asset_ref",
        )
        previous_asset_ref = _project_relative_posix_path(
            item.get("previous_asset_ref"),
            "previous_asset_ref",
            allow_empty=True,
        )
        normalized_assets.append(
            {
                "slide_id": slide_id,
                "current_asset_ref": current_asset_ref,
                "previous_asset_ref": previous_asset_ref,
            }
        )
    return {
        "slide_ids": list(slide_ids),
        "render_assets": normalized_assets,
    }


def validate_visual_brief(
    payload: dict[str, Any], required_target_ids: tuple[str, ...]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("VisualBrief must be an object")
    _strict_route(payload)
    normalized = dict(payload)
    for field in (
        "reading_blueprint_ref",
        "design_proposition",
        "audience_fit",
        "narrative_rhythm",
        "imagery_strategy",
        "diagram_strategy",
        "powerpoint_constraints",
    ):
        normalized[field] = _text(payload, field)
    if (
        not required_target_ids
        or set(required_target_ids).difference(SUPPORTED_TARGET_IDS)
        or tuple(payload.get("target_ids") or ()) != required_target_ids
    ):
        raise ContractValidationError(
            "VisualBrief target IDs must equal the current release policy"
        )
    normalized["target_ids"] = list(required_target_ids)
    return normalized


def validate_deck_design_system(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("DeckDesignSystem must be an object")
    _strict_route(payload)
    normalized = dict(payload)
    for field in (
        "visual_brief_ref",
        "reading_blueprint_ref",
        "theme_proposition",
        "composition_grammar",
        "imagery_strategy",
        "diagram_strategy",
        "table_strategy",
        "editability_rules",
    ):
        normalized[field] = _text(payload, field)
    for field in (
        "page_families",
        "typography_tokens",
        "color_tokens",
        "fallback_fonts",
        "forbidden_patterns",
        "rule_definitions",
    ):
        normalized[field] = _nonempty(payload, field)
    rules = normalized["rule_definitions"]
    if not isinstance(rules, list) or any(not isinstance(rule, dict) for rule in rules):
        raise ContractValidationError("rule_definitions must be an object array")
    for rule in rules:
        for field in (
            "rule_id",
            "level",
            "condition",
            "expected_outcome",
            "evidence_method",
        ):
            rule[field] = _text(rule, field)
        if rule["level"] not in VISUAL_RULE_LEVELS:
            raise ContractValidationError(
                f"Unknown visual rule level: {rule['level']}"
            )
    return normalized


def validate_visual_contract_set(
    payload: dict[str, Any], content_blueprint: dict[str, Any]
) -> dict[str, Any]:
    """Require one complete, verbatim visual contract per frozen slide."""

    if not isinstance(payload, dict):
        raise ContractValidationError("VisualContractSet must be an object")
    _strict_route(payload)
    normalized = dict(payload)
    for field in ("deck_design_system_ref", "reading_blueprint_ref"):
        normalized[field] = _text(payload, field)

    role_runs = payload.get("role_runs")
    if not isinstance(role_runs, list) or len(role_runs) < 2 or any(
        not isinstance(run, dict) for run in role_runs
    ):
        raise ContractValidationError(
            "Visual contract requires isolated production and review role runs"
        )
    role_ids: set[str] = set()
    role_kinds: set[str] = set()
    for run in role_runs:
        for field in (
            "role_id",
            "display_name",
            "role_kind",
            "context_pack_version",
            "tool_pack_version",
        ):
            run[field] = _text(run, field)
        if run["role_id"] in role_ids or run["role_kind"] not in {
            "production",
            "review",
        }:
            raise ContractValidationError("Visual role runs must be unique and typed")
        if not re.search(r"[\u4e00-\u9fff]", run["display_name"]):
            raise ContractValidationError(
                "User-facing visual role names must be Chinese"
            )
        role_ids.add(run["role_id"])
        role_kinds.add(run["role_kind"])
    if role_kinds != {"production", "review"}:
        raise ContractValidationError(
            "Visual role runs must include production and independent review"
        )

    frozen_slides = content_blueprint.get("slides")
    contracts = payload.get("slide_contracts")
    if not isinstance(frozen_slides, list) or not isinstance(contracts, list):
        raise ContractValidationError("Frozen slides and slide contracts are required")
    if len(contracts) != len(frozen_slides) or not contracts:
        raise ContractValidationError(
            "Every frozen content slide needs exactly one visual contract"
        )
    normalized_contracts: list[dict[str, Any]] = []
    seen: set[str] = set()
    exact_fields = (
        "slide_id",
        "page_task",
        "reading_question",
        "neutral_title",
        "visible_copy_blocks",
        "identity_labels",
        "evidence_bindings",
        "analysis_or_proposal_blocks",
        "solution_mapping_refs",
        "previous_relation",
        "next_relation",
        "speaker_notes",
        "reading_quality",
        "material_mode",
    )
    required_text = (
        "page_family",
        "information_hierarchy",
        "composition_intent",
        "image_selection_and_crop",
        "typography_application",
        "color_application",
        "diagram_chart_table_treatment",
        "native_bitmap_routing",
        "editability_requirements",
    )
    for index, (contract, frozen) in enumerate(
        zip(contracts, frozen_slides, strict=True), start=1
    ):
        if not isinstance(contract, dict) or not isinstance(frozen, dict):
            raise ContractValidationError("Slide contracts must be objects")
        slide_id = _text(contract, "slide_id")
        if slide_id in seen or contract.get("order") != index:
            raise ContractValidationError(
                "Slide contract IDs and order must be unique and final"
            )
        for field in exact_fields:
            if contract.get(field) != frozen.get(field):
                raise ContractValidationError(
                    f"Visual contract rewrote frozen field {field} on {slide_id}"
                )
        for field in required_text:
            contract[field] = _text(contract, field)
        for field in (
            "regions",
            "object_relationships",
            "reading_order",
            "fallbacks",
            "acceptance_criteria",
        ):
            _nonempty(contract, field)
        if not isinstance(contract.get("allowed_exceptions"), list):
            raise ContractValidationError("allowed_exceptions must be an array")
        criteria = contract["acceptance_criteria"]
        if any(not isinstance(item, dict) for item in criteria):
            raise ContractValidationError(
                "acceptance_criteria must be an object array"
            )
        for criterion in criteria:
            for field in ("criterion_id", "level", "expected_outcome"):
                criterion[field] = _text(criterion, field)
            if criterion["level"] not in VISUAL_RULE_LEVELS:
                raise ContractValidationError(
                    f"Unknown visual criterion level: {criterion['level']}"
                )
        seen.add(slide_id)
        normalized_contracts.append(dict(contract))
    normalized["role_runs"] = [dict(run) for run in role_runs]
    normalized["slide_contracts"] = normalized_contracts
    return normalized


def validate_visual_convergence(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("VisualConvergence must be an object")
    _strict_route(payload)
    normalized = dict(payload)
    for field in (
        "visual_contract_set_ref",
        "producer_role",
        "decision_summary",
        "convergence_status",
    ):
        normalized[field] = _text(payload, field)
    if normalized["convergence_status"] != "passed":
        raise ContractValidationError("Visual convergence must be binary passed")
    return normalized


def validate_visual_review(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("VisualReviewRecord must be an object")
    forbidden = FORBIDDEN_SCORE_FIELDS.intersection(payload)
    if forbidden:
        raise ContractValidationError(
            f"Visual review cannot contain score fields: {', '.join(sorted(forbidden))}"
        )
    normalized = dict(payload)
    for field in (
        "stage",
        "target_ref",
        "reviewer_kind",
        "reviewer_role",
        "producer_role",
    ):
        normalized[field] = _text(payload, field)
    if normalized["stage"] not in {"G1", "G2", "G4"}:
        raise ContractValidationError("Visual review stage must be G1, G2, or G4")
    if normalized["reviewer_kind"] not in {"aesthetic", "engineering"}:
        raise ContractValidationError("Visual reviewer kind is invalid")
    if normalized["reviewer_role"] == normalized["producer_role"]:
        raise ContractValidationError("A production role cannot review its own work")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(check, dict) for check in checks
    ):
        raise ContractValidationError("Visual review requires binary checks")
    hard_failed = False
    for check in checks:
        for field in ("criterion_id", "level", "applicability", "result"):
            check[field] = _text(check, field)
        if check["level"] not in VISUAL_RULE_LEVELS:
            raise ContractValidationError("Unknown visual review rule level")
        if check["applicability"] not in {"applicable", "not-applicable"}:
            raise ContractValidationError("Unknown visual review applicability")
        if check["result"] not in {"passed", "failed", "not-applicable"}:
            raise ContractValidationError("Unknown visual review result")
        if check["applicability"] == "not-applicable" and check["result"] != "not-applicable":
            raise ContractValidationError(
                "A non-applicable visual check must be not-applicable"
            )
        evidence = check.get("evidence_refs")
        if check["applicability"] == "applicable" and (
            not isinstance(evidence, list)
            or not evidence
            or any(not isinstance(ref, str) or not ref for ref in evidence)
        ):
            raise ContractValidationError(
                "Every applicable visual check requires evidence"
            )
        if check["result"] == "failed":
            if not str(check.get("failure_reason") or "").strip():
                raise ContractValidationError("Failed visual checks require a reason")
            if check["level"] in HARD_VISUAL_RULE_LEVELS:
                hard_failed = True
    computed = "failed" if hard_failed else "passed"
    if payload.get("overall_result") != computed:
        raise ContractValidationError(
            f"Visual review overall_result must be {computed}"
        )
    normalized["checks"] = [dict(check) for check in checks]
    normalized["overall_result"] = computed
    return normalized


def validate_anchor_slide_set(
    payload: dict[str, Any], visual_contract_set: dict[str, Any]
) -> dict[str, Any]:
    """Validate a strict-B, native-first set of exactly three anchor slides."""

    if not isinstance(payload, dict):
        raise ContractValidationError("AnchorSlideSet must be an object")
    normalized = dict(payload)
    normalized["visual_contract_set_ref"] = _text(
        payload, "visual_contract_set_ref"
    )
    contract_ids = {
        contract.get("slide_id")
        for contract in visual_contract_set.get("slide_contracts") or []
        if isinstance(contract, dict)
    }
    render_identity = validate_anchor_render_assets(
        payload, valid_slide_ids=contract_ids
    )
    normalized.update(render_identity)
    normalized["selection_reason"] = _text(payload, "selection_reason")
    normalized["native_first_pptx_ref"] = _text(
        payload, "native_first_pptx_ref"
    )
    pptx_sha256 = _text(payload, "pptx_sha256")
    if not SHA256_PATTERN.fullmatch(pptx_sha256):
        raise ContractValidationError(
            "AnchorSlideSet pptx_sha256 must be a lowercase SHA-256"
        )
    normalized["pptx_sha256"] = pptx_sha256
    if payload.get("native_first_frozen") is not True:
        raise ContractValidationError(
            "Native-first anchors must be frozen before optional Image 2 assets"
        )
    normalized["native_first_frozen"] = True
    for field in ("editability_evidence_refs", "preflight_render_refs"):
        refs = payload.get(field)
        if (
            not isinstance(refs, list)
            or not refs
            or any(not isinstance(ref, str) or not ref for ref in refs)
        ):
            raise ContractValidationError(f"{field} must contain artifact references")
        normalized[field] = list(refs)
    forbidden = {
        "image_asset_pack_ref",
        "image2_master_ref",
        "whole_slide_image_ref",
    }
    if forbidden.intersection(payload):
        raise ContractValidationError(
            "Native-first anchors cannot depend on Image 2 assets or whole-slide masters"
        )
    return normalized


def validate_image_asset_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep Image 2 assets optional, non-semantic, independent, and removable."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ImageAssetPack must be an object")
    normalized = dict(payload)
    normalized["anchor_slide_set_ref"] = _text(
        payload, "anchor_slide_set_ref"
    )
    if payload.get("asset_kind") != "non-semantic":
        raise ContractValidationError("Image 2 assets must be non-semantic")
    if payload.get("independent_layers") is not True:
        raise ContractValidationError(
            "Image 2 assets must remain independent, replaceable layers"
        )
    forbidden_truths = (
        "contains_text",
        "contains_numbers",
        "contains_business_relationships",
        "simulates_real_evidence",
        "whole_slide_master",
    )
    if any(payload.get(field) is not False for field in forbidden_truths):
        raise ContractValidationError(
            "Image 2 assets cannot contain text, numbers, business relationships, "
            "simulated evidence, or whole-slide masters"
        )
    normalized["asset_kind"] = "non-semantic"
    normalized["independent_layers"] = True
    for field in forbidden_truths:
        normalized[field] = False
    return normalized
