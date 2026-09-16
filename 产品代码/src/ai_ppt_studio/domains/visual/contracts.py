"""Formal visual contracts for strict route B."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
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

VISUAL_RELATIONSHIPS = frozenset(
    {
        "comparison",
        "sequence",
        "causality",
        "hierarchy",
        "network",
        "system-boundary",
        "cycle",
        "tension",
        "evidence-to-judgment",
        "single-focus",
    }
)
VISUAL_ASSET_ROLES = frozenset(
    {"evidence", "structure", "explanation", "emotion-context"}
)

_V23_BRIEF_TEXT_FIELDS = (
    "decision_task",
    "design_stance",
    "emotional_boundary",
    "brand_boundary",
    "density_strategy",
)
_V23_DESIGN_TEXT_FIELDS = ("image_language", "diagram_language")
_V23_SLIDE_TEXT_FIELDS = (
    "reader_judgment",
    "visual_mechanism",
    "focal_point",
    "previous_rhythm_relation",
    "next_rhythm_relation",
)
V23_SLIDE_FIELDS = frozenset(
    {
        "reader_judgment",
        "primary_relationship",
        "secondary_relationship",
        "visual_mechanism",
        "focal_point",
        "asset_roles",
        "forbidden_patterns",
        "previous_rhythm_relation",
        "next_rhythm_relation",
        "text_density_budget",
        "powerpoint_implementation_requirements",
        "acceptance_evidence_plan",
    }
)
_V23_RESERVED_VISUAL_MAP_KEY_SEQUENCES = frozenset(
    {
        "compiler",
        "compilerversion",
        "handoffprotocolversion",
        "roleruns",
        "releasetargetpolicyref",
        "targetevidencerefs",
        "targetevidenceidentities",
        "internalreviewrefs",
        "rawlineage",
        "visualcompilationplan",
        "visualcompilationplanref",
        "technicalledger",
        "headref",
        "gatestatus",
        "gatestate",
        "artifactheads",
        "processedcommands",
        "lasttransactionid",
        "lineage",
        "futurebackendgovernance",
        "materialinventory",
        "materialdetails",
        "auditlog",
        "internalprocessstate",
        "toolexecution",
        "toolcalls",
    }
)


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


def _visual_map_key_compact(value: str) -> str:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", separated)
    return "".join(
        character
        for character in separated.casefold()
        if character.isascii() and character.isalnum()
    )


def _visual_text_map(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ContractValidationError(f"{field} must be a non-empty object")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ContractValidationError(
                f"{field} keys must be non-empty strings"
            )
        key = raw_key.strip()
        if _visual_map_key_compact(key) in _V23_RESERVED_VISUAL_MAP_KEY_SEQUENCES:
            raise ContractValidationError(f"{field} contains a reserved key")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ContractValidationError(
                f"{field} values must be non-empty strings"
            )
        if key in normalized:
            raise ContractValidationError(f"{field} keys must be unique after trim")
        normalized[key] = raw_value.strip()
    return normalized


def _unique_strings(
    value: Any, field: str, *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{field} must be a string array")
    if not allow_empty and not value:
        raise ContractValidationError(f"{field} must be non-empty")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractValidationError(f"{field} must contain non-empty strings")
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ContractValidationError(f"{field} must not contain duplicates")
    return normalized


def _exact_keys(
    payload: Any,
    required: set[str],
    optional: set[str] | None = None,
    *,
    field: str,
) -> dict[str, Any]:
    optional = optional or set()
    if not isinstance(payload, dict):
        raise ContractValidationError(f"{field} must be an object")
    keys = set(payload)
    if not required.issubset(keys) or keys.difference(required | optional):
        raise ContractValidationError(f"{field} uses a closed schema")
    return payload


def _five_second_test_contract(value: Any) -> dict[str, Any]:
    expected_fields = {"prompt", "expected_judgment", "record_fields"}
    contract = _exact_keys(
        value,
        expected_fields,
        field="five_second_test_contract",
    )
    if contract.get("prompt") != "五秒后隐藏页面并记录第一判断":
        raise ContractValidationError("five_second_test_contract prompt is invalid")
    if contract.get("expected_judgment") != "读者形成与页面合同一致的核心判断":
        raise ContractValidationError(
            "five_second_test_contract expected_judgment is invalid"
        )
    fields = _unique_strings(contract.get("record_fields"), "record_fields")
    if fields != [
        "first_noticed_object",
        "perceived_message",
        "perceived_relationship",
        "next_reading_step",
        "misdirection",
    ]:
        raise ContractValidationError("five_second_test_contract record_fields are invalid")
    return {
        "prompt": contract["prompt"],
        "expected_judgment": contract["expected_judgment"],
        "record_fields": fields,
    }


def _emphasis_budget(value: Any) -> dict[str, int]:
    required = {
        "max_primary_focal_points_per_slide",
        "max_accent_color_roles",
        "consecutive_high_density_slide_limit",
    }
    budget = _exact_keys(value, required, field="emphasis_budget")
    normalized: dict[str, int] = {}
    for field in required:
        item = budget.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ContractValidationError(
                f"emphasis_budget.{field} must be a positive integer"
            )
        normalized[field] = item
    return {
        "max_primary_focal_points_per_slide": normalized[
            "max_primary_focal_points_per_slide"
        ],
        "max_accent_color_roles": normalized["max_accent_color_roles"],
        "consecutive_high_density_slide_limit": normalized[
            "consecutive_high_density_slide_limit"
        ],
    }


def _text_density_budget(value: Any) -> dict[str, Any]:
    required = {"max_body_lines", "max_text_blocks", "reduction_strategy"}
    budget = _exact_keys(value, required, field="text_density_budget")
    normalized: dict[str, Any] = {}
    for field in ("max_body_lines", "max_text_blocks"):
        item = budget.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ContractValidationError(
                f"text_density_budget.{field} must be a positive integer"
            )
        normalized[field] = item
    normalized["reduction_strategy"] = _text(budget, "reduction_strategy")
    return normalized


def _asset_roles(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ContractValidationError("asset_roles must be an object array")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = {"asset_id", "role", "source_ref", "narrative_task", "replaceable"}
    for asset in value:
        item = _exact_keys(asset, required, field="asset_roles item")
        asset_id = _text(item, "asset_id")
        if asset_id in seen:
            raise ContractValidationError("asset_roles must have unique asset_id values")
        role = _text(item, "role")
        if role not in VISUAL_ASSET_ROLES:
            raise ContractValidationError(f"Unknown visual asset role: {role}")
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str) or source_ref != source_ref.strip():
            raise ContractValidationError("asset_roles source_ref must be a string")
        source_ref = source_ref.strip()
        if role == "evidence" and not source_ref:
            raise ContractValidationError(
                "Evidence assets require a non-empty source_ref"
            )
        replaceable = item.get("replaceable")
        if not isinstance(replaceable, bool):
            raise ContractValidationError("asset_roles replaceable must be boolean")
        seen.add(asset_id)
        normalized.append(
            {
                "asset_id": asset_id,
                "role": role,
                "source_ref": source_ref,
                "narrative_task": _text(item, "narrative_task"),
                "replaceable": replaceable,
            }
        )
    return normalized


def _powerpoint_implementation_requirements(value: Any) -> dict[str, Any]:
    required = {
        "object_plan",
        "connector_semantics",
        "layout_constraints",
        "native_bitmap_routing",
        "degradation_strategy",
    }
    implementation = _exact_keys(
        value,
        required,
        field="powerpoint_implementation_requirements",
    )

    object_plan = implementation.get("object_plan")
    if not isinstance(object_plan, list) or not object_plan:
        raise ContractValidationError("object_plan must be a non-empty object array")
    object_fields = {"role", "object_type", "layer", "editability"}
    normalized_objects: list[dict[str, str]] = []
    seen_roles: set[str] = set()
    for obj in object_plan:
        item = _exact_keys(obj, object_fields, field="object_plan item")
        role = _text(item, "role")
        if role in seen_roles:
            raise ContractValidationError("object_plan roles must be unique")
        seen_roles.add(role)
        normalized_objects.append(
            {
                "role": role,
                "object_type": _text(item, "object_type"),
                "layer": _text(item, "layer"),
                "editability": _text(item, "editability"),
            }
        )

    connector_semantics = implementation.get("connector_semantics")
    if not isinstance(connector_semantics, list):
        raise ContractValidationError(
            "connector_semantics must be an object array"
        )
    connector_fields = {
        "from_role",
        "to_role",
        "meaning",
        "direction",
        "crossing_forbidden",
    }
    normalized_connectors: list[dict[str, Any]] = []
    for connector in connector_semantics:
        item = _exact_keys(
            connector,
            connector_fields,
            field="connector_semantics item",
        )
        from_role = _text(item, "from_role")
        to_role = _text(item, "to_role")
        if from_role == to_role:
            raise ContractValidationError(
                "connector_semantics endpoints must be different"
            )
        crossing_forbidden = item.get("crossing_forbidden")
        if not isinstance(crossing_forbidden, bool):
            raise ContractValidationError(
                "connector_semantics crossing_forbidden must be boolean"
            )
        normalized_connectors.append(
            {
                "from_role": from_role,
                "to_role": to_role,
                "meaning": _text(item, "meaning"),
                "direction": _text(item, "direction"),
                "crossing_forbidden": crossing_forbidden,
            }
        )

    layout_fields = {"entry_region", "focal_region", "minimum_clear_space"}
    layout = _exact_keys(
        implementation.get("layout_constraints"),
        layout_fields,
        field="layout_constraints",
    )
    normalized_layout = {
        field: _text(layout, field)
        for field in ("entry_region", "focal_region", "minimum_clear_space")
    }
    return {
        "object_plan": normalized_objects,
        "connector_semantics": normalized_connectors,
        "layout_constraints": normalized_layout,
        "native_bitmap_routing": _text(implementation, "native_bitmap_routing"),
        "degradation_strategy": _text(implementation, "degradation_strategy"),
    }


def _acceptance_evidence_plan(value: Any) -> dict[str, Any]:
    required = {
        "automated_checks",
        "human_review_checks",
        "target_powerpoint_checks",
        "user_review_question",
    }
    plan = _exact_keys(value, required, field="acceptance_evidence_plan")
    return {
        "automated_checks": _unique_strings(
            plan.get("automated_checks"), "automated_checks"
        ),
        "human_review_checks": _unique_strings(
            plan.get("human_review_checks"), "human_review_checks"
        ),
        "target_powerpoint_checks": _unique_strings(
            plan.get("target_powerpoint_checks"), "target_powerpoint_checks"
        ),
        "user_review_question": _text(plan, "user_review_question"),
    }


def assess_visual_contract_set_v23(payload: dict[str, Any]) -> str:
    """Classify immutable contract payloads without silently upgrading legacy data."""

    slides = payload.get("slide_contracts") if isinstance(payload, dict) else None
    if not isinstance(slides, list) or not slides:
        return "legacy / unassessed-by-v23"
    if len(slides) != sum(isinstance(slide, dict) for slide in slides):
        return "legacy / unassessed-by-v23"
    return (
        "v23-assessed"
        if all(V23_SLIDE_FIELDS.issubset(slide) for slide in slides)
        else "legacy / unassessed-by-v23"
    )


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
    normalized = deepcopy(payload)
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
    for field in _V23_BRIEF_TEXT_FIELDS:
        normalized[field] = _text(payload, field)
    normalized["forbidden_patterns"] = _unique_strings(
        payload.get("forbidden_patterns"), "forbidden_patterns"
    )
    normalized["five_second_test_contract"] = _five_second_test_contract(
        payload.get("five_second_test_contract")
    )
    if "design_philosophy_refs" in payload:
        normalized["design_philosophy_refs"] = _unique_strings(
            payload.get("design_philosophy_refs"),
            "design_philosophy_refs",
            allow_empty=True,
        )
    return normalized


def validate_deck_design_system(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("DeckDesignSystem must be an object")
    _strict_route(payload)
    normalized = deepcopy(payload)
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
    for field in ("page_families", "forbidden_patterns", "rule_definitions"):
        normalized[field] = _nonempty(payload, field)
    for field in ("typography_tokens", "color_tokens", "fallback_fonts"):
        normalized[field] = _visual_text_map(payload.get(field), field)
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
    normalized["density_rhythm"] = _unique_strings(
        payload.get("density_rhythm"), "density_rhythm"
    )
    normalized["cross_slide_rhythm_rules"] = _unique_strings(
        payload.get("cross_slide_rhythm_rules"), "cross_slide_rhythm_rules"
    )
    normalized["emphasis_budget"] = _emphasis_budget(
        payload.get("emphasis_budget")
    )
    for field in _V23_DESIGN_TEXT_FIELDS:
        normalized[field] = _text(payload, field)
    normalized["five_second_test_rules"] = _unique_strings(
        payload.get("five_second_test_rules"), "five_second_test_rules"
    )
    return normalized


def image_led_visible_fields(selected_copy: dict[str, Any]) -> dict[str, Any]:
    """Project selected items for the existing UI without normalizing their text."""
    from ai_ppt_studio.domains.visual.image_led import validate_selected_copy

    items = validate_selected_copy(selected_copy)["items"]
    return {
        "neutral_title": next(item["text"] for item in items if item.get("role") == "title"),
        "visible_copy_blocks": [
            {"block_id": item["item_id"], "text": item["text"],
             "identity": "定版可见文案"}
            for item in items
            if item["kind"] != "relation"
            and not (item["kind"] == "text" and item["role"] == "title")
        ],
    }


def _validate_image_led_contract_binding(
    payload: dict[str, Any], *, selection: dict[str, Any],
    region_inventory: dict[str, Any], selection_ref: str,
    region_inventory_ref: str,
) -> dict[str, Any]:
    from ai_ppt_studio.domains.visual.image_led import validate_region_inventory
    from ai_ppt_studio.kernel.references import ArtifactReference

    for value, kind in ((selection_ref, "image-led-selection"),
                        (region_inventory_ref, "image-led-region-inventory")):
        try:
            parsed = ArtifactReference.parse(value)
        except Exception as exc:
            raise ContractValidationError("IMAGE_LED_CONTRACT: invalid dependency ref") from exc
        if parsed.kind != kind:
            raise ContractValidationError("IMAGE_LED_CONTRACT: wrong dependency kind")
    inventory = validate_region_inventory(region_inventory, selection,
                                          selection_ref=selection_ref)
    identity = {"project_id": inventory["project_id"], "selection_ref": selection_ref,
                "region_inventory_ref": region_inventory_ref}
    if not isinstance(payload, dict) or payload.get("image_led") != identity:
        raise ContractValidationError("IMAGE_LED_CONTRACT: finalized identity differs")
    slides = payload.get("slide_contracts")
    if not isinstance(slides, list) or len(slides) != len(inventory["slides"]):
        raise ContractValidationError("IMAGE_LED_CONTRACT: incomplete slide coverage")
    for contract, selected, regions in zip(slides, selection["slides"], inventory["slides"], strict=True):
        expected = {"target_binding": selected["target_binding"],
                    "selected_copy": selected["selected_copy"],
                    "canvas": regions["canvas"],
                    "source_image_size": regions["source_image_size"]}
        if not isinstance(contract, dict) or contract.get("image_led") != expected:
            raise ContractValidationError("IMAGE_LED_CONTRACT: slide binding differs")
        target = selected["target_binding"]
        if (contract.get("slide_id") != target["slide_id"]
                or contract.get("order") != target["page_order"]
                or contract.get("regions") != regions["regions"]):
            raise ContractValidationError("IMAGE_LED_CONTRACT: region or page differs")
        for field, value in image_led_visible_fields(selected["selected_copy"]).items():
            if contract.get(field) != value:
                raise ContractValidationError(f"IMAGE_LED_CONTRACT: selected {field} differs")
    return deepcopy(payload)


def validate_image_led_contract_set(
    payload: dict[str, Any], content_blueprint: dict[str, Any], *,
    selection: dict[str, Any], region_inventory: dict[str, Any],
    selection_ref: str, region_inventory_ref: str,
) -> dict[str, Any]:
    """Validate selected content explicitly while retaining the formal R3 contract.

    G0 remains provenance. Only the two visible-copy projection fields derive from
    the trusted selection; none of the source/evidence fields are overwritten.
    The legacy implementation description remains reviewable but never compiles
    into image-led objects: only the exact regions do.
    """
    bound = _validate_image_led_contract_binding(payload, selection=selection,
        region_inventory=region_inventory, selection_ref=selection_ref,
        region_inventory_ref=region_inventory_ref)
    blueprint = deepcopy(content_blueprint)
    source_slides = blueprint.get("slides")
    if not isinstance(source_slides, list) or len(source_slides) != len(selection["slides"]):
        raise ContractValidationError("IMAGE_LED_CONTRACT: G0 slide coverage differs")
    for source, selected in zip(source_slides, selection["slides"], strict=True):
        if not isinstance(source, dict) or source.get("slide_id") != selected["target_binding"]["slide_id"]:
            raise ContractValidationError("IMAGE_LED_CONTRACT: G0 page identity differs")
        source.update(image_led_visible_fields(selected["selected_copy"]))
    identity = bound.pop("image_led")
    normalized = validate_visual_contract_set(bound, blueprint)
    normalized["image_led"] = identity
    return normalized


def validate_visual_contract_set(
    payload: dict[str, Any], content_blueprint: dict[str, Any]
) -> dict[str, Any]:
    """Require one complete, verbatim visual contract per frozen slide."""

    if not isinstance(payload, dict):
        raise ContractValidationError("VisualContractSet must be an object")
    _strict_route(payload)
    if "image_led" in payload:
        raise ContractValidationError("IMAGE_LED_SELECTION: finalized selection must be resolved before validation")
    normalized = deepcopy(payload)
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
    normalized_role_runs: list[dict[str, str]] = []
    for run in role_runs:
        normalized_run = deepcopy(run)
        for field in (
            "role_id",
            "display_name",
            "role_kind",
            "context_pack_version",
            "tool_pack_version",
        ):
            normalized_run[field] = _text(run, field)
        if normalized_run["role_id"] in role_ids or normalized_run["role_kind"] not in {
            "production",
            "review",
        }:
            raise ContractValidationError("Visual role runs must be unique and typed")
        if not re.search(r"[\u4e00-\u9fff]", normalized_run["display_name"]):
            raise ContractValidationError(
                "User-facing visual role names must be Chinese"
            )
        role_ids.add(normalized_run["role_id"])
        role_kinds.add(normalized_run["role_kind"])
        normalized_role_runs.append(normalized_run)
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
        normalized_contract = deepcopy(contract)
        for field in required_text:
            normalized_contract[field] = _text(contract, field)
        for field in (
            "regions",
            "object_relationships",
            "reading_order",
            "fallbacks",
            "acceptance_criteria",
        ):
            _nonempty(normalized_contract, field)
        if not isinstance(normalized_contract.get("allowed_exceptions"), list):
            raise ContractValidationError("allowed_exceptions must be an array")
        criteria = deepcopy(normalized_contract["acceptance_criteria"])
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
        for field in _V23_SLIDE_TEXT_FIELDS:
            normalized_contract[field] = _text(contract, field)
        primary_relationship = normalized_contract.get("primary_relationship")
        if primary_relationship not in VISUAL_RELATIONSHIPS:
            raise ContractValidationError(
                f"Unknown visual primary relationship: {primary_relationship}"
            )
        if "secondary_relationship" not in contract:
            raise ContractValidationError(
                "secondary_relationship must be present and may be null"
            )
        secondary_relationship = contract["secondary_relationship"]
        if secondary_relationship is not None:
            if (
                not isinstance(secondary_relationship, str)
                or secondary_relationship not in VISUAL_RELATIONSHIPS
            ):
                raise ContractValidationError(
                    f"Unknown visual secondary relationship: {secondary_relationship}"
                )
            if secondary_relationship == primary_relationship:
                raise ContractValidationError(
                    "Primary and secondary relationships must differ"
                )
        normalized_contract["secondary_relationship"] = secondary_relationship
        normalized_contract["asset_roles"] = _asset_roles(
            contract.get("asset_roles")
        )
        normalized_contract["forbidden_patterns"] = _unique_strings(
            contract.get("forbidden_patterns"),
            f"{slide_id}.forbidden_patterns",
        )
        normalized_contract["text_density_budget"] = _text_density_budget(
            contract.get("text_density_budget")
        )
        normalized_contract[
            "powerpoint_implementation_requirements"
        ] = _powerpoint_implementation_requirements(
            contract.get("powerpoint_implementation_requirements")
        )
        normalized_contract["acceptance_evidence_plan"] = _acceptance_evidence_plan(
            contract.get("acceptance_evidence_plan")
        )
        normalized_contract["acceptance_criteria"] = criteria
        seen.add(slide_id)
        normalized_contracts.append(normalized_contract)
    normalized["role_runs"] = normalized_role_runs
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
    normalized["visual_compilation_plan_ref"] = _text(
        payload, "visual_compilation_plan_ref"
    )
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
