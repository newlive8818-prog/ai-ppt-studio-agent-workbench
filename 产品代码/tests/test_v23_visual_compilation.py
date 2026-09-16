from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.visual.compilation import (  # noqa: E402
    COMPILER_VERSION,
    HANDOFF_VERSION,
    derive_visual_compilation_plan,
)
from ai_ppt_studio.domains.visual.contracts import (  # noqa: E402
    validate_deck_design_system,
    validate_visual_brief,
    validate_visual_contract_set,
)
from ai_ppt_studio.errors import ContractValidationError  # noqa: E402
from ai_ppt_studio.kernel.artifacts import ArtifactRepository  # noqa: E402
from tests.v16_visual_fixtures import (  # noqa: E402
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


BLUEPRINT_REF = "artifact://reading-deck-blueprint/" + "b" * 64
BRIEF_REF = "artifact://visual-brief/" + "a" * 64
SYSTEM_REF = "artifact://deck-design-system/" + "c" * 64
CONTRACT_REF = "artifact://visual-contract-set/" + "d" * 64
POLICY_REF = "artifact://release-target-policy/" + "e" * 64

PLAN_ROOT_FIELDS = {
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
PLAN_SLIDE_FIELDS = {
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


def _inputs() -> tuple[dict, dict, dict]:
    brief = validate_visual_brief(
        valid_visual_brief(BLUEPRINT_REF), ("macos-powerpoint",)
    )
    design = validate_deck_design_system(
        valid_design_system(BRIEF_REF, BLUEPRINT_REF)
    )
    contracts = validate_visual_contract_set(
        valid_contract_set(SYSTEM_REF, BLUEPRINT_REF),
        {
            "slides": [
                {
                    "slide_id": "S01",
                    "page_task": "说明当前已知断点和证据边界",
                    "reading_question": "当前已知什么，仍需验证什么",
                    "neutral_title": "当前流程断点与证据边界",
                    "visible_copy_blocks": [
                        {"block_id": "b1", "text": "材料记录了流程断点", "identity": "来源事实"}
                    ],
                    "identity_labels": ["来源事实"],
                    "evidence_bindings": [],
                    "analysis_or_proposal_blocks": [],
                    "solution_mapping_refs": ["mapping-1"],
                    "previous_relation": "开篇",
                    "next_relation": "进入方案要求",
                    "speaker_notes": "解释来源",
                    "reading_quality": {
                        "independently_readable": True,
                        "information_density": "moderate",
                        "review_note": "事实与建议分开",
                    },
                    "material_mode": "material-backed",
                }
            ]
        },
    )
    return brief, design, contracts


def _plan(**overrides: object) -> dict:
    brief, design, contracts = _inputs()
    values = {
        "reading_blueprint_ref": BLUEPRINT_REF,
        "visual_brief_ref": BRIEF_REF,
        "deck_design_system_ref": SYSTEM_REF,
        "visual_contract_set_ref": CONTRACT_REF,
        "release_target_policy_ref": POLICY_REF,
        "source_version": "visual-v23",
        "source_revision": 17,
        "visual_brief": brief,
        "design_system": design,
        "contract_set": contracts,
    }
    values.update(overrides)
    return derive_visual_compilation_plan(**values)


class V23VisualCompilationTests(unittest.TestCase):
    def test_plan_has_closed_root_and_slide_shapes(self) -> None:
        plan = _plan()
        self.assertEqual(set(plan), PLAN_ROOT_FIELDS)
        self.assertEqual(plan["artifact_type"], "visual-compilation-plan")
        self.assertEqual(plan["compiler_version"], COMPILER_VERSION)
        self.assertEqual(plan["handoff_version"], HANDOFF_VERSION)
        self.assertEqual(plan["production_route"], "strict-B")
        self.assertEqual(len(plan["slides"]), 1)
        self.assertEqual(set(plan["slides"][0]), PLAN_SLIDE_FIELDS)
        self.assertEqual(plan["slides"][0]["slide_id"], "S01")

    def test_plan_is_deterministic_and_has_a_canonical_artifact_ref(self) -> None:
        first = _plan()
        second = _plan()
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as folder:
            repository = ArtifactRepository(Path(folder), project_id="p1")
            self.assertEqual(
                repository.reference_for("visual-compilation-plan", first),
                repository.reference_for("visual-compilation-plan", second),
            )

        reordered = json.loads(json.dumps(first, ensure_ascii=False))
        reordered["slides"][0] = {
            key: reordered["slides"][0][key]
            for key in reversed(list(reordered["slides"][0]))
        }
        self.assertEqual(first, reordered)
        with tempfile.TemporaryDirectory() as folder:
            repository = ArtifactRepository(Path(folder), project_id="p1")
            self.assertEqual(
                repository.reference_for("visual-compilation-plan", first),
                repository.reference_for("visual-compilation-plan", reordered),
            )

    def test_plan_ref_changes_when_semantic_inputs_change(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = ArtifactRepository(Path(folder), project_id="p1")
            baseline = repository.reference_for("visual-compilation-plan", _plan())
            for change in (
                {"source_revision": 18},
                {"release_target_policy_ref": "artifact://release-target-policy/" + "f" * 64},
                {"source_version": "visual-v24"},
            ):
                with self.subTest(change=change):
                    self.assertNotEqual(
                        baseline,
                        repository.reference_for("visual-compilation-plan", _plan(**change)),
                    )

        brief, design, contracts = _inputs()
        changed_contracts = copy.deepcopy(contracts)
        changed_contracts["slide_contracts"][0]["visual_mechanism"] = "改用不等权路径"
        changed = derive_visual_compilation_plan(
            reading_blueprint_ref=BLUEPRINT_REF,
            visual_brief_ref=BRIEF_REF,
            deck_design_system_ref=SYSTEM_REF,
            visual_contract_set_ref=CONTRACT_REF,
            release_target_policy_ref=POLICY_REF,
            source_version="visual-v23",
            source_revision=17,
            visual_brief=brief,
            design_system=design,
            contract_set=changed_contracts,
        )
        self.assertNotEqual(_plan(), changed)

    def test_plan_rejects_mismatched_refs_before_derivation(self) -> None:
        brief, design, contracts = _inputs()
        with self.assertRaises(ContractValidationError):
            derive_visual_compilation_plan(
                reading_blueprint_ref=BLUEPRINT_REF,
                visual_brief_ref=BRIEF_REF,
                deck_design_system_ref=SYSTEM_REF,
                visual_contract_set_ref=CONTRACT_REF,
                release_target_policy_ref=POLICY_REF,
                source_version="visual-v23",
                source_revision=17,
                visual_brief={**brief, "reading_blueprint_ref": "artifact://reading-deck-blueprint/" + "f" * 64},
                design_system=design,
                contract_set=contracts,
            )

    def test_compilation_plan_does_not_create_a_second_content_truth(self) -> None:
        plan = _plan()
        def contains_key(value: object, forbidden: str) -> bool:
            if isinstance(value, dict):
                return forbidden in value or any(
                    contains_key(child, forbidden) for child in value.values()
                )
            if isinstance(value, list):
                return any(contains_key(child, forbidden) for child in value)
            return False

        for forbidden in (
            "visible_copy_blocks",
            "speaker_notes",
            "facts",
            "data",
            "source_text",
            "core_claim",
        ):
            self.assertFalse(contains_key(plan, forbidden))
        self.assertEqual(plan["slides"][0]["reading_path"], ["title", "facts", "impact"])
        self.assertEqual(plan["role_runs"], _inputs()[2]["role_runs"])

    def test_frozen_content_is_validated_before_compilation(self) -> None:
        invalid = valid_contract_set(SYSTEM_REF, BLUEPRINT_REF)
        invalid["slide_contracts"][0]["visible_copy_blocks"] = [
            {"block_id": "forged", "text": "被改写", "identity": "来源事实"}
        ]
        with self.assertRaises(ContractValidationError):
            validate_visual_contract_set(
                invalid,
                {
                    "slides": [
                        {
                            "slide_id": "S01",
                            "page_task": "说明当前已知断点和证据边界",
                            "reading_question": "当前已知什么，仍需验证什么",
                            "neutral_title": "当前流程断点与证据边界",
                            "visible_copy_blocks": [
                                {"block_id": "b1", "text": "材料记录了流程断点", "identity": "来源事实"}
                            ],
                            "identity_labels": ["来源事实"],
                            "evidence_bindings": [],
                            "analysis_or_proposal_blocks": [],
                            "solution_mapping_refs": ["mapping-1"],
                            "previous_relation": "开篇",
                            "next_relation": "进入方案要求",
                            "speaker_notes": "解释来源",
                            "reading_quality": {
                                "independently_readable": True,
                                "information_density": "moderate",
                                "review_note": "事实与建议分开",
                            },
                            "material_mode": "material-backed",
                        }
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
