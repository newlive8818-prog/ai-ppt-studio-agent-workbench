from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.content import contracts  # noqa: E402
from ai_ppt_studio.errors import ContractValidationError  # noqa: E402


MATERIAL_MODES = ("material-backed", "mixed-evidence", "proposal-led")


def validator(name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    candidate = getattr(contracts, name, None)
    if not callable(candidate):
        raise AssertionError(f"missing v2.2 content validator: {name}")
    return candidate


def evidence_item(
    *,
    identity: str = "来源事实",
    statement: str = "客户材料记录了现有审批流程。",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "identity": identity,
        "statement": statement,
        "source_refs": ["artifact://material/source-a"] if source_refs is None else source_refs,
        "location": "第 2 页 / 审批流程",
        "version": "source-version-1",
        "usable_for": ["problem-diagnosis", "solution-mapping"],
        "limitations": ["仅覆盖当前访谈范围"],
    }


def valid_evidence_book(mode: str = "material-backed") -> dict[str, Any]:
    facts = [evidence_item()] if mode != "proposal-led" else []
    gaps = [
        evidence_item(
            identity="证据缺口",
            statement="仍需联合确认审批时长和参与角色。",
            source_refs=[],
        )
    ]
    return {
        "source_version": "source-version-1",
        "material_mode": mode,
        "facts": facts,
        "user_confirmed_facts": [],
        "inferences": [],
        "conflicts": [],
        "unknowns": gaps,
        "evidence_gaps": gaps,
        "forbidden_extrapolations": ["不得推断审批效率提升比例"],
        "excluded_material_refs": [],
        "source_refs": [] if mode == "proposal-led" else ["artifact://material/source-a"],
        "generated_by": "presales-solution-chief",
        "generated_at": "2026-08-23T00:00:00+00:00",
    }


def valid_decision_context() -> dict[str, Any]:
    return {
        "audience_roles": ["业务负责人", "数字化负责人"],
        "decision_stage": "一期范围联合研讨",
        "current_business_matter": "梳理经营审批协同范围",
        "known_consensus": ["先确认一期边界"],
        "decision_questions": ["哪些审批场景优先进入一期？"],
        "constraints": ["当前没有统一的周期基线"],
        "unresolved_questions": ["参与角色仍需确认"],
        "supported_next_actions": ["开展流程访谈并确认一期清单"],
        "evidence_book_ref": "artifact://presales-evidence-book/book-a",
    }


def valid_fit_map() -> dict[str, Any]:
    return {
        "situations": [
            {"item_id": "situation-1", "identity": "来源事实", "statement": "审批流程跨多个角色"}
        ],
        "symptoms": [
            {"item_id": "symptom-1", "identity": "材料推断", "statement": "信息交接可能存在重复确认"}
        ],
        "causes_or_hypotheses": [
            {"item_id": "cause-1", "identity": "诊断假设", "statement": "流程信息缺少统一承载"}
        ],
        "impacts": [
            {"item_id": "impact-1", "identity": "待联合验证", "statement": "协同成本需要进一步核实"}
        ],
        "constraints": [
            {"item_id": "constraint-1", "identity": "来源事实", "statement": "一期范围需要受控"}
        ],
        "unknowns": [
            {"item_id": "unknown-1", "identity": "证据缺口", "statement": "缺少当前审批周期数据"}
        ],
        "derived_requirements": [
            {"item_id": "requirement-1", "identity": "方案建议", "statement": "支持流程信息统一记录"}
        ],
        "solution_components": [
            {"item_id": "solution-1", "identity": "方案建议", "statement": "审批协同工作台"}
        ],
        "mappings": [
            {
                "mapping_id": "mapping-1",
                "problem_refs": ["situation-1", "symptom-1", "cause-1"],
                "requirement_refs": ["requirement-1"],
                "solution_component_refs": ["solution-1"],
                "identity": "方案建议",
                "evidence_refs": ["evidence-item-1"],
            }
        ],
        "boundaries": [
            {"item_id": "boundary-1", "identity": "方案建议", "statement": "一期不承诺全域流程覆盖"}
        ],
        "alternatives": [
            {"item_id": "alternative-1", "identity": "方案建议", "statement": "先验证单一审批场景"}
        ],
        "validation_items": [
            {"item_id": "validation-1", "identity": "待联合验证", "statement": "确认一期场景和角色"}
        ],
    }


def valid_blueprint(mode: str = "mixed-evidence") -> dict[str, Any]:
    return {
        "project_id": "project-a",
        "source_version": "source-version-1",
        "material_mode": mode,
        "evidence_book_ref": "artifact://presales-evidence-book/book-a",
        "decision_context_ref": "artifact://customer-decision-context/context-a",
        "problem_solution_fit_ref": "artifact://problem-solution-fit-map/map-a",
        "section_flow": ["现状与问题", "方案与验证"],
        "slides": [
            {
                "slide_id": "slide-1",
                "order": 1,
                "section_id": "section-1",
                "page_task": "界定当前业务事项",
                "reading_question": "当前需要共同确认什么？",
                "neutral_title": "经营审批协同的一期讨论范围",
                "visible_copy_blocks": [
                    {"block_id": "copy-1", "role": "body", "text": "当前先梳理审批协同范围与验证事项。"}
                ],
                "identity_labels": ["方案建议", "待联合验证"],
                "evidence_bindings": [
                    {
                        "binding_id": "binding-1",
                        "identity": "待联合验证",
                        "source_refs": [],
                        "supports_block_refs": ["copy-1"],
                    }
                ],
                "analysis_or_proposal_blocks": [
                    {"block_id": "analysis-1", "identity": "方案建议", "text": "建议先验证一个审批场景。"}
                ],
                "solution_mapping_refs": ["mapping-1"],
                "previous_relation": "开篇",
                "next_relation": "下一页展开当前问题和证据缺口",
                "speaker_notes": "说明本页只界定讨论范围，不代表客户已确认方案。",
                "reading_quality": {
                    "independently_readable": True,
                    "complete_visible_copy": True,
                    "identity_boundary_complete": True,
                    "review_note": "正文可独立阅读。",
                },
                "material_mode": mode,
            }
        ],
        "hard_gate_refs": [],
        "repair_history": [],
    }


class V22ContentContractTests(unittest.TestCase):
    def test_accepts_all_three_material_modes(self) -> None:
        validate = validator("validate_presales_evidence_book")
        for mode in MATERIAL_MODES:
            with self.subTest(mode=mode):
                self.assertEqual(validate(valid_evidence_book(mode))["material_mode"], mode)

    def test_rejects_legacy_or_unknown_material_modes(self) -> None:
        validate = validator("validate_presales_evidence_book")
        for mode in ("proposal-only", "materials-provided", "no-materials-confirmed", "unknown"):
            payload = valid_evidence_book()
            payload["material_mode"] = mode
            with self.subTest(mode=mode), self.assertRaises(ContractValidationError):
                validate(payload)

    def test_evidence_book_requires_source_for_customer_fact(self) -> None:
        payload = valid_evidence_book()
        payload["facts"][0]["source_refs"] = []
        with self.assertRaisesRegex(ContractValidationError, "source_refs"):
            validator("validate_presales_evidence_book")(payload)

    def test_decision_context_rejects_desired_customer_judgment_aliases(self) -> None:
        validate = validator("validate_customer_decision_context")
        for field in ("desiredCustomerJudgment", "desired_customer_judgment"):
            payload = valid_decision_context()
            payload[field] = "希望客户接受本方案"
            with self.subTest(field=field), self.assertRaisesRegex(ContractValidationError, field):
                validate(payload)

    def test_fit_mapping_requires_problem_requirement_solution_identity_and_evidence(self) -> None:
        validate = validator("validate_problem_solution_fit_map")
        required_mapping_fields = (
            "problem_refs",
            "requirement_refs",
            "solution_component_refs",
            "identity",
            "evidence_refs",
        )
        for field in required_mapping_fields:
            payload = valid_fit_map()
            del payload["mappings"][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(ContractValidationError, field):
                validate(payload)

    def test_blueprint_accepts_complete_reading_first_slide(self) -> None:
        payload = valid_blueprint()
        result = validator("validate_reading_deck_blueprint")(payload)
        self.assertEqual(result["slides"][0]["neutral_title"], payload["slides"][0]["neutral_title"])
        self.assertEqual(result["slides"][0]["visible_copy_blocks"], payload["slides"][0]["visible_copy_blocks"])

    def test_blueprint_preserves_only_an_explicit_typed_material_reference(self) -> None:
        payload = valid_blueprint()
        binding = payload["slides"][0]["evidence_bindings"][0]
        binding["material_ref"] = "artifact://material/material-a"

        result = validator("validate_reading_deck_blueprint")(payload)

        self.assertEqual(
            result["slides"][0]["evidence_bindings"][0]["material_ref"],
            "artifact://material/material-a",
        )
        without_material = valid_blueprint()
        without_result = validator("validate_reading_deck_blueprint")(
            without_material
        )
        self.assertNotIn(
            "material_ref",
            without_result["slides"][0]["evidence_bindings"][0],
        )

    def test_blueprint_preserves_explicit_evidence_image_metadata(self) -> None:
        payload = valid_blueprint()
        binding = payload["slides"][0]["evidence_bindings"][0]
        binding.update(
            {
                "asset_ref": "review-assets/content-evidence-page.jpg",
                "caption": "真实成稿 P02",
                "material_kind": "image",
            }
        )

        result = validator("validate_reading_deck_blueprint")(payload)

        self.assertEqual(
            result["slides"][0]["evidence_bindings"][0]["asset_ref"],
            "review-assets/content-evidence-page.jpg",
        )
        self.assertEqual(
            result["slides"][0]["evidence_bindings"][0]["caption"],
            "真实成稿 P02",
        )
        self.assertEqual(
            result["slides"][0]["evidence_bindings"][0]["material_kind"],
            "image",
        )

    def test_blueprint_rejects_legacy_persuasion_fields_anywhere(self) -> None:
        validate = validator("validate_reading_deck_blueprint")
        for field in (
            "desiredCustomerJudgment",
            "desired_customer_judgment",
            "coreClaim",
            "core_claim",
        ):
            payload = valid_blueprint()
            payload["slides"][0][field] = "该方案是客户必须接受的唯一选择"
            with self.subTest(field=field), self.assertRaisesRegex(ContractValidationError, field):
                validate(payload)

    def test_blueprint_rejects_unsupported_strong_conclusion_title(self) -> None:
        payload = valid_blueprint()
        payload["slides"][0]["neutral_title"] = "唯一正确的审批协同方案"
        with self.assertRaisesRegex(ContractValidationError, "neutral_title"):
            validator("validate_reading_deck_blueprint")(payload)

    def test_blueprint_requires_every_reading_first_slide_field(self) -> None:
        validate = validator("validate_reading_deck_blueprint")
        required_fields = (
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
        for field in required_fields:
            payload = valid_blueprint()
            del payload["slides"][0][field]
            with self.subTest(field=field), self.assertRaisesRegex(ContractValidationError, field):
                validate(payload)

    def test_blueprint_rejects_slide_mode_that_differs_from_deck(self) -> None:
        payload = valid_blueprint("proposal-led")
        payload["slides"][0]["material_mode"] = "mixed-evidence"
        with self.assertRaisesRegex(ContractValidationError, "material_mode"):
            validator("validate_reading_deck_blueprint")(payload)

    def test_proposal_led_rejects_unsourced_customer_truth_and_promises(self) -> None:
        validate = validator("validate_reading_deck_blueprint")
        prohibited_copy = (
            "客户当前已经完成流程统一",
            "现有审批周期为 7 天",
            "某客户成功案例证明方案有效",
            "本方案保证实现效率提升",
        )
        for copy_text in prohibited_copy:
            payload = valid_blueprint("proposal-led")
            payload["slides"][0]["visible_copy_blocks"][0]["text"] = copy_text
            with self.subTest(copy_text=copy_text), self.assertRaisesRegex(
                ContractValidationError, "proposal-led"
            ):
                validate(payload)

    def test_validation_does_not_mutate_the_caller_payload(self) -> None:
        payload = valid_blueprint()
        original = copy.deepcopy(payload)
        validator("validate_reading_deck_blueprint")(payload)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
