from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.visual.contracts import (  # noqa: E402
    validate_deck_design_system,
    validate_visual_brief,
    validate_visual_contract_set,
)
from ai_ppt_studio.errors import ContractValidationError  # noqa: E402
from tests.v16_visual_fixtures import (  # noqa: E402
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


BLUEPRINT_REF = "artifact://reading-deck-blueprint/" + "b" * 64
BRIEF_REF = "artifact://visual-brief/" + "a" * 64
SYSTEM_REF = "artifact://deck-design-system/" + "c" * 64

FORBIDDEN_VISUAL_MAP_KEY_VARIANTS = (
    "compiler",
    "compiler_version",
    "compiler-version",
    "compilerVersion",
    "CompilerVersion",
    "handoff_protocol_version",
    "role_runs",
    "release_target_policy_ref",
    "target_evidence_refs",
    "target_evidence_identities",
    "internal_review_refs",
    "gate_status",
    "gate-status",
    "gateStatus",
    "GateStatus",
    "gate_state",
    "artifact_heads",
    "artifact-heads",
    "processed_commands",
    "processedCommands",
    "last_transaction_id",
    "lineage",
    "raw_lineage",
    "raw-lineage",
    "rawLineage",
    "RawLineage",
    "future_backend_governance",
    "future-backend-governance",
    "futureBackendGovernance",
    "FutureBackendGovernance",
    "material_inventory",
    "material_details",
    "audit_log",
    "internal_process_state",
    "InternalProcessState",
    "tool_execution",
    "toolExecution",
    "tool_calls",
    "visual_compilation_plan",
    "visual_compilation_plan_ref",
    "visual-compilation-plan",
    "visualCompilationPlan",
    "VisualCompilationPlan",
    "technical_ledger",
    "technical-ledger",
    "technicalLedger",
    "TechnicalLedger",
    "head_ref",
    "head-ref",
    "headRef",
    "HeadRef",
)


def _five_second_contract() -> dict:
    return {
        "prompt": "五秒后隐藏页面并记录第一判断",
        "expected_judgment": "读者形成与页面合同一致的核心判断",
        "record_fields": [
            "first_noticed_object",
            "perceived_message",
            "perceived_relationship",
            "next_reading_step",
            "misdirection",
        ],
    }


def _visual_brief() -> dict:
    payload = valid_visual_brief(BLUEPRINT_REF)
    payload.update(
        {
            "decision_task": "让读者先理解执行主体变化，再判断治理边界",
            "design_stance": "编辑化、技术可信、克制",
            "emotional_boundary": "理性、清晰、有张力但不炫技",
            "brand_boundary": "中性墨色、暖白与单一冷色强调",
            "density_strategy": "章节低密度，证据中密度，结论有停顿",
            "forbidden_patterns": ["平均三卡片", "无意义图标", "整页位图"],
            "five_second_test_contract": _five_second_contract(),
        }
    )
    return payload


def _design_system() -> dict:
    payload = valid_design_system(BRIEF_REF, BLUEPRINT_REF)
    payload.update(
        {
            "density_rhythm": ["low", "medium", "pause"],
            "cross_slide_rhythm_rules": [
                "高密度页后必须出现低密度过渡",
                "章节页承担阅读重置",
            ],
            "emphasis_budget": {
                "max_primary_focal_points_per_slide": 1,
                "max_accent_color_roles": 2,
                "consecutive_high_density_slide_limit": 2,
            },
            "image_language": "图片只承担结构、解释或语境任务",
            "diagram_language": "原生形状与有方向的语义连接器",
            "five_second_test_rules": [
                "先记录第一视觉重心",
                "再记录页面主张与关系",
            ],
        }
    )
    return payload


def _powerpoint_requirements() -> dict:
    return {
        "object_plan": [
            {
                "role": "primary-subject",
                "object_type": "native-shape",
                "layer": "foreground",
                "editability": "native-editable",
            }
        ],
        "connector_semantics": [
            {
                "from_role": "human",
                "to_role": "ai",
                "meaning": "主要执行责任转移",
                "direction": "forward",
                "crossing_forbidden": True,
            }
        ],
        "layout_constraints": {
            "entry_region": "left",
            "focal_region": "center-right",
            "minimum_clear_space": "one-body-line",
        },
        "native_bitmap_routing": "事实、标签与关系原生；结构图为独立可替换图片层",
        "degradation_strategy": "复杂图像失败时保留原生主体与边界关系",
    }


def _acceptance_evidence_plan() -> dict:
    return {
        "automated_checks": ["frozen-content", "native-object-routing", "overflow"],
        "human_review_checks": ["five-second-judgment", "anti-pattern-review"],
        "target_powerpoint_checks": ["font", "crop", "connector", "editability"],
        "user_review_question": "五秒内是否先看到执行主体变化与软件治理边界？",
    }


def _contract_set() -> dict:
    payload = valid_contract_set(SYSTEM_REF, BLUEPRINT_REF)
    for slide in payload["slide_contracts"]:
        slide.update(
            {
                "reader_judgment": "读者先看到执行主体变化与治理边界",
                "primary_relationship": "causality",
                "secondary_relationship": "system-boundary",
                "visual_mechanism": "主体转移图与边界线",
                "focal_point": "center-right-primary-subject",
                "asset_roles": [
                    {
                        "asset_id": "hero-structure",
                        "role": "structure",
                        "source_ref": "",
                        "narrative_task": "建立主体、软件边界与责任关系",
                        "replaceable": True,
                    }
                ],
                "forbidden_patterns": ["三张等权卡片", "无语义装饰线"],
                "previous_rhythm_relation": "从章节停顿进入主体关系",
                "next_rhythm_relation": "为证据页增加关系密度",
                "text_density_budget": {
                    "max_body_lines": 8,
                    "max_text_blocks": 3,
                    "reduction_strategy": "先删解释性重复句",
                },
                "powerpoint_implementation_requirements": _powerpoint_requirements(),
                "acceptance_evidence_plan": _acceptance_evidence_plan(),
            }
        )
    return payload


class V23VisualSemanticContractTests(unittest.TestCase):
    def test_visual_brief_requires_each_v23_field(self) -> None:
        required_fields = (
            "decision_task",
            "design_stance",
            "emotional_boundary",
            "brand_boundary",
            "density_strategy",
            "forbidden_patterns",
            "five_second_test_contract",
        )
        for field in required_fields:
            with self.subTest(field=field):
                payload = _visual_brief()
                payload.pop(field)
                with self.assertRaises(ContractValidationError):
                    validate_visual_brief(payload, ("macos-powerpoint",))

    def test_visual_brief_closes_forbidden_patterns_and_five_second_contract(self) -> None:
        cases = []

        duplicate_patterns = _visual_brief()
        duplicate_patterns["forbidden_patterns"] = ["same", "same"]
        cases.append(duplicate_patterns)

        empty_patterns = _visual_brief()
        empty_patterns["forbidden_patterns"] = []
        cases.append(empty_patterns)

        extra_five_second_field = _visual_brief()
        extra_five_second_field["five_second_test_contract"]["unexpected"] = True
        cases.append(extra_five_second_field)

        missing_record_field = _visual_brief()
        missing_record_field["five_second_test_contract"]["record_fields"].pop()
        cases.append(missing_record_field)

        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(
                ContractValidationError
            ):
                validate_visual_brief(payload, ("macos-powerpoint",))

    def test_design_philosophy_refs_are_optional_but_closed_when_present(self) -> None:
        without_refs = validate_visual_brief(
            _visual_brief(), ("macos-powerpoint",)
        )
        self.assertNotIn("design_philosophy_refs", without_refs)

        with_refs = _visual_brief()
        with_refs["design_philosophy_refs"] = ["reading-order", "observer-viewpoint"]
        normalized = validate_visual_brief(with_refs, ("macos-powerpoint",))
        self.assertEqual(normalized["design_philosophy_refs"], with_refs["design_philosophy_refs"])

        empty_refs = _visual_brief()
        empty_refs["design_philosophy_refs"] = []
        self.assertEqual(
            validate_visual_brief(empty_refs, ("macos-powerpoint",))["design_philosophy_refs"],
            [],
        )

        for value in (["same", "same"], ["valid", 3]):
            with self.subTest(value=value), self.assertRaises(ContractValidationError):
                invalid = _visual_brief()
                invalid["design_philosophy_refs"] = value
                validate_visual_brief(invalid, ("macos-powerpoint",))

    def test_deck_design_system_requires_each_v23_field(self) -> None:
        required_fields = (
            "density_rhythm",
            "cross_slide_rhythm_rules",
            "emphasis_budget",
            "image_language",
            "diagram_language",
            "five_second_test_rules",
        )
        for field in required_fields:
            with self.subTest(field=field):
                payload = _design_system()
                payload.pop(field)
                with self.assertRaises(ContractValidationError):
                    validate_deck_design_system(payload)

    def test_deck_design_system_closes_emphasis_budget_and_rhythm_lists(self) -> None:
        invalid_payloads = []

        extra_budget_key = _design_system()
        extra_budget_key["emphasis_budget"]["unexpected"] = 1
        invalid_payloads.append(extra_budget_key)

        non_positive_limit = _design_system()
        non_positive_limit["emphasis_budget"]["max_accent_color_roles"] = 0
        invalid_payloads.append(non_positive_limit)

        duplicate_rhythm = _design_system()
        duplicate_rhythm["density_rhythm"] = ["low", "low"]
        invalid_payloads.append(duplicate_rhythm)

        duplicate_rules = _design_system()
        duplicate_rules["cross_slide_rhythm_rules"] = ["same", "same"]
        invalid_payloads.append(duplicate_rules)

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(
                ContractValidationError
            ):
                validate_deck_design_system(payload)

    def test_deck_design_system_requires_closed_string_token_maps(self) -> None:
        token_map_fields = ("color_tokens", "typography_tokens", "fallback_fonts")
        invalid_values = (
            "not-a-map",
            [],
            {},
            {"": "#fff"},
            {"   ": "#fff"},
            {"accent": 1},
            {"accent": "   "},
            {"accent": "#fff", " accent ": "#000"},
        )
        for field in token_map_fields:
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    payload = _design_system()
                    payload[field] = value
                    with self.assertRaises(ContractValidationError):
                        validate_deck_design_system(payload)

        for field in token_map_fields:
            for key in FORBIDDEN_VISUAL_MAP_KEY_VARIANTS:
                with self.subTest(field=field, key=key):
                    payload = _design_system()
                    payload[field] = {key: "hidden"}
                    with self.assertRaises(ContractValidationError):
                        validate_deck_design_system(payload)

    def test_deck_design_system_accepts_trimmed_business_token_keys(self) -> None:
        long_key = "x" * 65
        payload = _design_system()
        payload["color_tokens"] = {
            " headline ": " #172033 ",
            "plan_accent": " #3157D5 ",
            "customer-plan-accent": " #5B3DF5 ",
            long_key: " #ABCDEF ",
        }
        payload["typography_tokens"] = {
            "technical_diagram_font": " Aptos ",
            "1stLevel": " 32pt ",
        }
        payload["fallback_fonts"] = {"技术图示字体": " 苹方 "}

        normalized = validate_deck_design_system(payload)

        self.assertEqual(
            normalized["color_tokens"],
            {
                "headline": "#172033",
                "plan_accent": "#3157D5",
                "customer-plan-accent": "#5B3DF5",
                long_key: "#ABCDEF",
            },
        )
        self.assertEqual(
            normalized["typography_tokens"],
            {"technical_diagram_font": "Aptos", "1stLevel": "32pt"},
        )
        self.assertEqual(normalized["fallback_fonts"], {"技术图示字体": "苹方"})

    def test_complete_v23_visual_contract_set_validates(self) -> None:
        normalized = validate_visual_contract_set(
            _contract_set(),
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
        self.assertEqual(normalized["slide_contracts"][0]["primary_relationship"], "causality")

    def test_slide_contract_requires_all_v23_fields(self) -> None:
        required_text = (
            "reader_judgment",
            "primary_relationship",
            "visual_mechanism",
            "focal_point",
            "previous_rhythm_relation",
            "next_rhythm_relation",
            "text_density_budget",
        )
        required_values = (
            "secondary_relationship",
            "asset_roles",
            "forbidden_patterns",
            "powerpoint_implementation_requirements",
            "acceptance_evidence_plan",
        )
        for field in required_text + required_values:
            with self.subTest(field=field):
                payload = _contract_set()
                payload["slide_contracts"][0].pop(field)
                with self.assertRaises(ContractValidationError):
                    validate_visual_contract_set(
                        payload,
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

    def test_slide_relationships_are_closed_and_distinct(self) -> None:
        for field, value in (
            ("primary_relationship", "unknown-relationship"),
            ("secondary_relationship", "unknown-relationship"),
            ("secondary_relationship", "causality"),
        ):
            with self.subTest(field=field, value=value):
                payload = _contract_set()
                payload["slide_contracts"][0][field] = value
                with self.assertRaises(ContractValidationError):
                    validate_visual_contract_set(
                        payload,
                        {"slides": [copy.deepcopy(payload["slide_contracts"][0])]}
                    )

    def test_secondary_relationship_is_required_and_uses_null_for_no_relation(
        self,
    ) -> None:
        payload = _contract_set()
        payload["slide_contracts"][0]["secondary_relationship"] = None
        normalized = validate_visual_contract_set(
            payload,
            {"slides": [copy.deepcopy(payload["slide_contracts"][0])]},
        )
        self.assertIsNone(
            normalized["slide_contracts"][0]["secondary_relationship"]
        )

        missing = _contract_set()
        missing["slide_contracts"][0].pop("secondary_relationship")
        with self.assertRaises(ContractValidationError):
            validate_visual_contract_set(
                missing,
                {"slides": [copy.deepcopy(missing["slide_contracts"][0])]},
            )

        for value in ("", "unknown-relationship", "causality"):
            with self.subTest(value=value):
                invalid = _contract_set()
                invalid["slide_contracts"][0]["secondary_relationship"] = value
                with self.assertRaises(ContractValidationError):
                    validate_visual_contract_set(
                        invalid,
                        {
                            "slides": [
                                copy.deepcopy(invalid["slide_contracts"][0])
                            ]
                        },
                    )

    def test_slide_asset_roles_are_closed_and_evidence_requires_source(self) -> None:
        extra_key = _contract_set()
        extra_key["slide_contracts"][0]["asset_roles"][0]["unexpected"] = True

        invalid_role = _contract_set()
        invalid_role["slide_contracts"][0]["asset_roles"][0]["role"] = "decoration"

        evidence_without_source = _contract_set()
        evidence_without_source["slide_contracts"][0]["asset_roles"] = [
            {
                "asset_id": "evidence-image",
                "role": "evidence",
                "source_ref": "",
                "narrative_task": "支持页面判断",
                "replaceable": True,
            }
        ]

        for payload in (extra_key, invalid_role, evidence_without_source):
            with self.subTest(payload=payload), self.assertRaises(
                ContractValidationError
            ):
                validate_visual_contract_set(
                    payload,
                    {"slides": [copy.deepcopy(payload["slide_contracts"][0])]}
                )

    def test_powerpoint_and_acceptance_nested_structures_are_closed(self) -> None:
        cases = []

        extra_object_key = _contract_set()
        extra_object_key["slide_contracts"][0]["powerpoint_implementation_requirements"]["object_plan"][0]["unexpected"] = True
        cases.append(extra_object_key)

        identical_connector_endpoints = _contract_set()
        identical_connector_endpoints["slide_contracts"][0]["powerpoint_implementation_requirements"]["connector_semantics"][0]["to_role"] = "human"
        cases.append(identical_connector_endpoints)

        non_boolean_crossing = _contract_set()
        non_boolean_crossing["slide_contracts"][0]["powerpoint_implementation_requirements"]["connector_semantics"][0]["crossing_forbidden"] = "yes"
        cases.append(non_boolean_crossing)

        empty_automated_checks = _contract_set()
        empty_automated_checks["slide_contracts"][0]["acceptance_evidence_plan"]["automated_checks"] = []
        cases.append(empty_automated_checks)

        extra_acceptance_key = _contract_set()
        extra_acceptance_key["slide_contracts"][0]["acceptance_evidence_plan"]["unexpected"] = True
        cases.append(extra_acceptance_key)

        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(
                ContractValidationError
            ):
                validate_visual_contract_set(
                    payload,
                    {"slides": [copy.deepcopy(payload["slide_contracts"][0])]}
                )

    def test_frozen_content_fields_remain_verbatim_with_v23_fields(self) -> None:
        payload = _contract_set()
        frozen = {
            "slides": [
                {
                    "slide_id": "S01",
                    "page_task": "说明当前已知断点和证据边界",
                    "reading_question": "当前已知什么，仍需验证什么",
                    "neutral_title": "当前流程断点与证据边界",
                    "visible_copy_blocks": [
                        {"block_id": "b1", "text": "被改写", "identity": "来源事实"}
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
        }
        with self.assertRaises(ContractValidationError):
            validate_visual_contract_set(payload, frozen)


if __name__ == "__main__":
    unittest.main()
