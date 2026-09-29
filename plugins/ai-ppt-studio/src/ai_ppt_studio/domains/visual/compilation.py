"""Deterministic compilation of visual contracts into a native handoff plan."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_ppt_studio.domains.visual.contracts import (
    VISUAL_RELATIONSHIPS,
    _acceptance_evidence_plan,
    _asset_roles,
    _powerpoint_implementation_requirements,
    _text,
    _unique_strings,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference


COMPILER_VERSION = "visual-semantic-compiler/v1"
HANDOFF_VERSION = "codex-presentations-handoff/v23-v1"
IMAGE_LED_COMPILER_VERSION = "image-led-faithful-compiler/v1"
IMAGE_LED_HANDOFF_VERSION = "codex-presentations-image-led/v1"
IMAGE_LED_COMPILER_VERSION_V2 = "image-led-faithful-compiler/v2"
IMAGE_LED_HANDOFF_VERSION_V2 = "codex-presentations-image-led/v2"
IMAGE_LED_COMPILER_VERSION_V3 = "image-led-faithful-compiler/v3"
IMAGE_LED_HANDOFF_VERSION_V3 = "codex-presentations-image-led/v3"


def image_led_versions(selection, region_inventory=None):
    from ai_ppt_studio.domains.visual.image_led import REGION_VERSION_V3
    versions = {s['selected_copy'].get('copy_version','v1') for s in selection['slides']}
    if region_inventory is not None and 'region_version' in region_inventory:
        if region_inventory['region_version'] != REGION_VERSION_V3 or versions != {'image-led-selected-copy/v2'}:
            raise ContractValidationError('IMAGE_LED_PLAN: v3 regions require original v2 selected copy')
        return IMAGE_LED_COMPILER_VERSION_V3, IMAGE_LED_HANDOFF_VERSION_V3
    if versions == {'image-led-selected-copy/v2'}:
        return IMAGE_LED_COMPILER_VERSION_V2, IMAGE_LED_HANDOFF_VERSION_V2
    if versions == {'v1'}:
        return IMAGE_LED_COMPILER_VERSION, IMAGE_LED_HANDOFF_VERSION
    raise ContractValidationError('IMAGE_LED_PLAN: unsupported or mixed selected-copy versions')

_PLAN_ROOT_FIELDS = {
    "artifact_type",
    "compiler_version",
    "handoff_version",
    "production_route",
    "reading_blueprint_ref",
    "visual_brief_ref",
    "deck_design_system_ref",
    "visual_contract_set_ref",
    "release_target_policy_ref",
    "source_version",
    "source_revision",
    "role_runs",
    "experience_refs",
    "slides",
}
_PLAN_SLIDE_FIELDS = {
    "slide_id",
    "primary_relationship",
    "visual_mechanism",
    "focal_point",
    "reading_path",
    "object_plan",
    "connector_semantics",
    "asset_plan",
    "layout_constraints",
    "native_bitmap_routing",
    "powerpoint_constraints",
    "anti_pattern_checks",
    "acceptance_evidence_plan",
}


def _artifact_ref(value: Any, field: str, expected_kind: str) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be an artifact reference")
    try:
        reference = ArtifactReference.parse(value)
    except Exception as exc:
        raise ContractValidationError(f"{field} must be an artifact reference") from exc
    if reference.kind != expected_kind:
        raise ContractValidationError(
            f"{field} must reference {expected_kind}, got {reference.kind}"
        )
    return str(reference)


def _normalized_role_runs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) < 2:
        raise ContractValidationError("role_runs must contain production and review")
    normalized: list[dict[str, Any]] = []
    for run in value:
        if not isinstance(run, dict):
            raise ContractValidationError("role_runs must contain objects")
        normalized.append(deepcopy(run))
    return normalized


def _normalized_plan_slide(slide: Any, contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(slide, dict):
        raise ContractValidationError("Visual compilation slides must be objects")
    if set(slide) != _PLAN_SLIDE_FIELDS:
        raise ContractValidationError("Visual compilation slide schema is not closed")
    if slide.get("slide_id") != contract.get("slide_id"):
        raise ContractValidationError("Compilation slide IDs must follow contracts")

    slide_id = _text(slide, "slide_id")
    primary_relationship = slide.get("primary_relationship")
    if primary_relationship not in VISUAL_RELATIONSHIPS:
        raise ContractValidationError(
            f"Unknown compiled primary relationship: {primary_relationship}"
        )
    visual_mechanism = _text(slide, "visual_mechanism")
    focal_point = _text(slide, "focal_point")
    if slide.get("primary_relationship") != contract.get("primary_relationship"):
        raise ContractValidationError(
            f"Compiled primary relationship diverges from {slide_id}"
        )
    if visual_mechanism != contract.get("visual_mechanism"):
        raise ContractValidationError(f"Compiled visual mechanism diverges from {slide_id}")
    if focal_point != contract.get("focal_point"):
        raise ContractValidationError(f"Compiled focal point diverges from {slide_id}")

    reading_path = slide.get("reading_path")
    if not isinstance(reading_path, list) or not reading_path:
        raise ContractValidationError("reading_path must be a non-empty array")
    if reading_path != contract.get("reading_order"):
        raise ContractValidationError(f"Compiled reading path diverges from {slide_id}")

    implementation = _powerpoint_implementation_requirements(
        contract.get("powerpoint_implementation_requirements")
    )
    if slide.get("object_plan") != implementation["object_plan"]:
        raise ContractValidationError(f"Compiled object plan diverges from {slide_id}")
    if slide.get("connector_semantics") != implementation["connector_semantics"]:
        raise ContractValidationError(
            f"Compiled connector semantics diverge from {slide_id}"
        )
    if slide.get("layout_constraints") != implementation["layout_constraints"]:
        raise ContractValidationError(
            f"Compiled layout constraints diverge from {slide_id}"
        )
    if slide.get("native_bitmap_routing") != implementation["native_bitmap_routing"]:
        raise ContractValidationError(
            f"Compiled bitmap routing diverges from {slide_id}"
        )
    if not isinstance(slide.get("powerpoint_constraints"), dict):
        raise ContractValidationError("powerpoint_constraints must be an object")
    if set(slide["powerpoint_constraints"]) != {"deck", "slide"}:
        raise ContractValidationError("powerpoint_constraints schema is not closed")
    if slide["powerpoint_constraints"]["slide"] != implementation["degradation_strategy"]:
        raise ContractValidationError(
            f"Compiled slide degradation strategy diverges from {slide_id}"
        )

    if slide.get("asset_plan") != _asset_roles(contract.get("asset_roles")):
        raise ContractValidationError(f"Compiled asset plan diverges from {slide_id}")
    if slide.get("anti_pattern_checks") != _unique_strings(
        contract.get("forbidden_patterns"), f"{slide_id}.forbidden_patterns"
    ):
        raise ContractValidationError(
            f"Compiled anti-pattern checks diverge from {slide_id}"
        )
    if slide.get("acceptance_evidence_plan") != _acceptance_evidence_plan(
        contract.get("acceptance_evidence_plan")
    ):
        raise ContractValidationError(
            f"Compiled acceptance evidence diverges from {slide_id}"
        )

    return {
        "slide_id": slide_id,
        "primary_relationship": primary_relationship,
        "visual_mechanism": visual_mechanism,
        "focal_point": focal_point,
        "reading_path": deepcopy(reading_path),
        "object_plan": deepcopy(slide["object_plan"]),
        "connector_semantics": deepcopy(slide["connector_semantics"]),
        "asset_plan": deepcopy(slide["asset_plan"]),
        "layout_constraints": deepcopy(slide["layout_constraints"]),
        "native_bitmap_routing": slide["native_bitmap_routing"],
        "powerpoint_constraints": deepcopy(slide["powerpoint_constraints"]),
        "anti_pattern_checks": deepcopy(slide["anti_pattern_checks"]),
        "acceptance_evidence_plan": deepcopy(slide["acceptance_evidence_plan"]),
    }


def validate_visual_compilation_plan(
    payload: dict[str, Any], *, contract_set: dict[str, Any]
) -> dict[str, Any]:
    """Validate and return a deep normalized immutable compilation payload."""

    if not isinstance(payload, dict):
        raise ContractValidationError("VisualCompilationPlan must be an object")
    if set(payload) != _PLAN_ROOT_FIELDS:
        raise ContractValidationError("VisualCompilationPlan root schema is not closed")
    if payload.get("artifact_type") != "visual-compilation-plan":
        raise ContractValidationError("VisualCompilationPlan artifact_type is invalid")
    if payload.get("compiler_version") != COMPILER_VERSION:
        raise ContractValidationError("VisualCompilationPlan compiler_version is invalid")
    if payload.get("handoff_version") != HANDOFF_VERSION:
        raise ContractValidationError("VisualCompilationPlan handoff_version is invalid")
    if payload.get("production_route") != "strict-B":
        raise ContractValidationError("VisualCompilationPlan requires strict-B")

    refs = {
        "reading_blueprint_ref": _artifact_ref(
            payload.get("reading_blueprint_ref"),
            "reading_blueprint_ref",
            "reading-deck-blueprint",
        ),
        "visual_brief_ref": _artifact_ref(
            payload.get("visual_brief_ref"), "visual_brief_ref", "visual-brief"
        ),
        "deck_design_system_ref": _artifact_ref(
            payload.get("deck_design_system_ref"),
            "deck_design_system_ref",
            "deck-design-system",
        ),
        "visual_contract_set_ref": _artifact_ref(
            payload.get("visual_contract_set_ref"),
            "visual_contract_set_ref",
            "visual-contract-set",
        ),
        "release_target_policy_ref": _artifact_ref(
            payload.get("release_target_policy_ref"),
            "release_target_policy_ref",
            "release-target-policy",
        ),
    }
    source_version = payload.get("source_version")
    if not isinstance(source_version, str) or not source_version.strip():
        raise ContractValidationError("source_version must be a non-empty string")
    source_revision = payload.get("source_revision")
    if isinstance(source_revision, bool) or not isinstance(source_revision, int) or source_revision <= 0:
        raise ContractValidationError("source_revision must be a positive integer")

    if not isinstance(contract_set, dict):
        raise ContractValidationError("contract_set must be an object")
    if contract_set.get("reading_blueprint_ref") != refs["reading_blueprint_ref"]:
        raise ContractValidationError("Compilation plan blueprint ref diverges from contracts")
    if contract_set.get("deck_design_system_ref") != refs["deck_design_system_ref"]:
        raise ContractValidationError("Compilation plan design-system ref diverges from contracts")

    role_runs = _normalized_role_runs(payload.get("role_runs"))
    if role_runs != contract_set.get("role_runs"):
        raise ContractValidationError("Compilation plan role runs diverge from contracts")
    experience_refs = _unique_strings(
        payload.get("experience_refs"), "experience_refs", allow_empty=True
    )

    contracts = contract_set.get("slide_contracts")
    slides = payload.get("slides")
    if not isinstance(contracts, list) or not contracts:
        raise ContractValidationError("contract_set must contain slide contracts")
    if not isinstance(slides, list) or len(slides) != len(contracts):
        raise ContractValidationError("Compilation plan must cover every slide contract")
    normalized_slides = [
        _normalized_plan_slide(slide, contract)
        for slide, contract in zip(slides, contracts, strict=True)
    ]
    slide_ids = [slide["slide_id"] for slide in normalized_slides]
    if len(set(slide_ids)) != len(slide_ids):
        raise ContractValidationError("Compilation plan slide IDs must be unique")

    return {
        "artifact_type": "visual-compilation-plan",
        "compiler_version": COMPILER_VERSION,
        "handoff_version": HANDOFF_VERSION,
        "production_route": "strict-B",
        **refs,
        "source_version": source_version.strip(),
        "source_revision": source_revision,
        "role_runs": role_runs,
        "experience_refs": experience_refs,
        "slides": normalized_slides,
    }


def derive_visual_compilation_plan(
    *,
    reading_blueprint_ref: str,
    visual_brief_ref: str,
    deck_design_system_ref: str,
    visual_contract_set_ref: str,
    release_target_policy_ref: str,
    source_version: str,
    source_revision: int,
    visual_brief: dict[str, Any],
    design_system: dict[str, Any],
    contract_set: dict[str, Any],
) -> dict[str, Any]:
    """Purely derive one deterministic implementation plan from current contracts."""

    if (
        visual_brief.get("reading_blueprint_ref") != reading_blueprint_ref
        or design_system.get("reading_blueprint_ref") != reading_blueprint_ref
        or design_system.get("visual_brief_ref") != visual_brief_ref
        or contract_set.get("reading_blueprint_ref") != reading_blueprint_ref
        or contract_set.get("deck_design_system_ref") != deck_design_system_ref
    ):
        raise ContractValidationError(
            "Visual compilation inputs do not bind the supplied current refs"
        )

    slides: list[dict[str, Any]] = []
    for contract in contract_set.get("slide_contracts") or []:
        if not isinstance(contract, dict):
            raise ContractValidationError("Visual contract slides must be objects")
        implementation = _powerpoint_implementation_requirements(
            contract.get("powerpoint_implementation_requirements")
        )
        slides.append(
            {
                "slide_id": contract.get("slide_id"),
                "primary_relationship": contract.get("primary_relationship"),
                "visual_mechanism": contract.get("visual_mechanism"),
                "focal_point": contract.get("focal_point"),
                "reading_path": deepcopy(contract.get("reading_order")),
                "object_plan": deepcopy(implementation["object_plan"]),
                "connector_semantics": deepcopy(implementation["connector_semantics"]),
                "asset_plan": deepcopy(contract.get("asset_roles")),
                "layout_constraints": deepcopy(implementation["layout_constraints"]),
                "native_bitmap_routing": implementation["native_bitmap_routing"],
                "powerpoint_constraints": {
                    "deck": visual_brief.get("powerpoint_constraints"),
                    "slide": implementation["degradation_strategy"],
                },
                "anti_pattern_checks": deepcopy(contract.get("forbidden_patterns")),
                "acceptance_evidence_plan": deepcopy(
                    contract.get("acceptance_evidence_plan")
                ),
            }
        )

    role_runs = deepcopy(contract_set.get("role_runs"))
    experience_refs = list(
        dict.fromkeys(
            str(run["experience_slice_ref"])
            for run in role_runs or []
            if isinstance(run, dict) and run.get("experience_slice_ref")
        )
    )
    plan = {
        "artifact_type": "visual-compilation-plan",
        "compiler_version": COMPILER_VERSION,
        "handoff_version": HANDOFF_VERSION,
        "production_route": "strict-B",
        "reading_blueprint_ref": reading_blueprint_ref,
        "visual_brief_ref": visual_brief_ref,
        "deck_design_system_ref": deck_design_system_ref,
        "visual_contract_set_ref": visual_contract_set_ref,
        "release_target_policy_ref": release_target_policy_ref,
        "source_version": source_version,
        "source_revision": source_revision,
        "role_runs": role_runs,
        "experience_refs": experience_refs,
        "slides": slides,
    }
    return validate_visual_compilation_plan(plan, contract_set=contract_set)


def _image_led_slides(region_inventory: dict[str, Any], selection=None) -> list[dict[str, Any]]:
    """This compiler adds identities and native/bitmap modes, never geometry."""
    slides = deepcopy(region_inventory["slides"])
    v2 = selection is not None and image_led_versions(selection)[0] == IMAGE_LED_COMPILER_VERSION_V2
    for index, slide in enumerate(slides):
        if 'region_version' in region_inventory:
            slide['region_version'] = region_inventory['region_version']
        if v2:
            slide['selected_copy'] = deepcopy(selection['slides'][index]['selected_copy'])
        slide["objects"] = [
            {**deepcopy(region), "object_id": "object-" + region["region_id"],
             "render_mode": "bitmap" if region["kind"] in {"image", "decoration"} else "native"}
            for region in slide["regions"]
        ]
    return slides


def validate_image_led_compilation_plan(
    payload: dict[str, Any], *, contract_set: dict[str, Any],
    selection: dict[str, Any], region_inventory: dict[str, Any],
    selection_ref: str, region_inventory_ref: str,
) -> dict[str, Any]:
    from ai_ppt_studio.domains.visual.contracts import _validate_image_led_contract_binding
    from ai_ppt_studio.domains.visual.image_led import validate_faithful_objects

    _validate_image_led_contract_binding(contract_set, selection=selection,
        region_inventory=region_inventory, selection_ref=selection_ref,
        region_inventory_ref=region_inventory_ref)
    fields = _PLAN_ROOT_FIELDS | {"project_id", "selection_ref", "region_inventory_ref"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ContractValidationError("IMAGE_LED_PLAN: root schema is not closed")
    compiler_version, handoff_version = image_led_versions(selection, region_inventory)
    constants = {"artifact_type": "visual-compilation-plan", "production_route": "strict-B",
                 "compiler_version": compiler_version,
                 "handoff_version": handoff_version,
                 "project_id": selection["project_id"], "selection_ref": selection_ref,
                 "region_inventory_ref": region_inventory_ref}
    if any(payload[key] != value for key, value in constants.items()):
        raise ContractValidationError("IMAGE_LED_PLAN: version or finalized identity differs")
    for field, kind in (("reading_blueprint_ref", "reading-deck-blueprint"),
                        ("visual_brief_ref", "visual-brief"),
                        ("deck_design_system_ref", "deck-design-system"),
                        ("visual_contract_set_ref", "visual-contract-set"),
                        ("release_target_policy_ref", "release-target-policy")):
        _artifact_ref(payload[field], field, kind)
    if any(payload[field] != contract_set.get(field)
           for field in ("reading_blueprint_ref", "deck_design_system_ref")):
        raise ContractValidationError("IMAGE_LED_PLAN: source refs differ from contract")
    _text(payload, "source_version")
    revision = payload["source_revision"]
    if type(revision) is not int or revision <= 0:
        raise ContractValidationError("IMAGE_LED_PLAN: source revision must be positive")
    if _normalized_role_runs(payload["role_runs"]) != contract_set["role_runs"]:
        raise ContractValidationError("IMAGE_LED_PLAN: role runs differ from contract")
    experience_refs = list(dict.fromkeys(
        str(run["experience_slice_ref"]) for run in contract_set["role_runs"]
        if run.get("experience_slice_ref")))
    if payload["experience_refs"] != experience_refs:
        raise ContractValidationError("IMAGE_LED_PLAN: experience refs differ from contract")
    if payload["slides"] != _image_led_slides(region_inventory, selection):
        raise ContractValidationError("IMAGE_LED_PLAN: compiled objects must equal exact regions")
    for slide in payload["slides"]:
        validate_faithful_objects(slide["regions"], slide["objects"], region_version=slide.get('region_version'))
    return deepcopy(payload)


def compile_image_led_plan(
    *, reading_blueprint_ref: str, visual_brief_ref: str,
    deck_design_system_ref: str, visual_contract_set_ref: str,
    release_target_policy_ref: str, source_version: str, source_revision: int,
    visual_brief: dict[str, Any], design_system: dict[str, Any],
    contract_set: dict[str, Any], selection: dict[str, Any],
    region_inventory: dict[str, Any], selection_ref: str, region_inventory_ref: str,
) -> dict[str, Any]:
    """Deterministically compile only the finalized image's complete regions."""
    if (visual_brief.get("reading_blueprint_ref") != reading_blueprint_ref
            or design_system.get("reading_blueprint_ref") != reading_blueprint_ref
            or design_system.get("visual_brief_ref") != visual_brief_ref):
        raise ContractValidationError("IMAGE_LED_PLAN: brief/design source refs differ")
    role_runs = deepcopy(contract_set.get("role_runs"))
    if not isinstance(role_runs, list):
        raise ContractValidationError("IMAGE_LED_PLAN: contract role runs are required")
    compiler_version, handoff_version = image_led_versions(selection, region_inventory)
    plan = {"artifact_type": "visual-compilation-plan", "production_route": "strict-B",
            "compiler_version": compiler_version, "handoff_version": handoff_version,
            "project_id": selection.get("project_id"), "selection_ref": selection_ref,
            "region_inventory_ref": region_inventory_ref,
            "reading_blueprint_ref": reading_blueprint_ref, "visual_brief_ref": visual_brief_ref,
            "deck_design_system_ref": deck_design_system_ref,
            "visual_contract_set_ref": visual_contract_set_ref,
            "release_target_policy_ref": release_target_policy_ref,
            "source_version": source_version, "source_revision": source_revision,
            "role_runs": role_runs, "experience_refs": list(dict.fromkeys(
                str(run["experience_slice_ref"]) for run in role_runs
                if isinstance(run, dict) and run.get("experience_slice_ref"))),
            "slides": _image_led_slides(region_inventory, selection)}
    return validate_image_led_compilation_plan(plan, contract_set=contract_set,
        selection=selection, region_inventory=region_inventory, selection_ref=selection_ref,
        region_inventory_ref=region_inventory_ref)


__all__ = [
    "COMPILER_VERSION",
    "HANDOFF_VERSION",
    "derive_visual_compilation_plan",
    "validate_visual_compilation_plan",
    "IMAGE_LED_COMPILER_VERSION",
    "IMAGE_LED_HANDOFF_VERSION",
    "compile_image_led_plan",
    "validate_image_led_compilation_plan",
]
