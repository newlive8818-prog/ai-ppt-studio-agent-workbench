from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import ContractValidationError

REF = "artifact://material-finding/" + "a" * 64


def material_view(source_ref: str = REF) -> dict:
    return {
        "material_view_id": "S01-M01",
        "source_ref": source_ref,
        "asset_ref": "review-assets/content/S01-M01.png",
        "source_file_name": "客户现状材料.pptx",
        "page_number": 3,
        "region_label": "整页",
        "purpose": "证明当前流程断点",
        "treatment": "原页只读呈现",
        "evidence_identity": "来源事实",
    }


def evidence_item(identity: str = "来源事实") -> dict:
    return {
        "item_id": "fact-1",
        "identity": identity,
        "statement": "客户材料记录了现有流程断点",
        "source_refs": [REF],
        "location": "会议纪要第 3 页",
        "version": "v1",
        "usable_for": ["现状", "问题"],
        "limitations": ["未包含量化影响"],
    }


def evidence_book(mode: str = "material-backed") -> dict:
    fact = evidence_item()
    return {
        "source_version": "content-v1",
        "material_mode": mode,
        "mission_confirmation_ref": "artifact://mission-confirmation/" + "b" * 64,
        "material_inventory_ref": "" if mode == "proposal-led" else "artifact://material-inventory/" + "c" * 64,
        "facts": [] if mode == "proposal-led" else [fact],
        "user_confirmed_facts": [],
        "inferences": [],
        "conflicts": [],
        "unknowns": [],
        "evidence_gaps": [
            {**fact, "item_id": "gap-1", "identity": "证据缺口", "statement": "业务影响待联合确认"}
        ],
        "forbidden_extrapolations": [
            {**fact, "item_id": "forbid-1", "identity": "禁止使用", "statement": "不得编造收益数字"}
        ],
        "excluded_material_refs": [],
        "source_refs": [] if mode == "proposal-led" else [REF],
        "generated_by": "presales-solution-chief",
        "generated_at": "2026-08-15T00:00:00+08:00",
    }


def decision_context() -> dict:
    return {
        "audience_roles": ["客户业务负责人"],
        "decision_stage": "联合方案验证",
        "current_business_matter": "确认一期问题范围和验证动作",
        "known_consensus": ["先核实断点范围"],
        "decision_questions": ["哪些断点优先进入一期"],
        "constraints": ["不承诺未经验证的收益"],
        "unresolved_questions": ["量化影响待确认"],
        "supported_next_actions": ["召开联合验证会"],
        "evidence_book_ref": "artifact://presales-evidence-book/" + "d" * 64,
    }


def fit_map() -> dict:
    node = lambda node_id, identity="来源事实": {
        "id": node_id,
        "statement": node_id,
        "identity": identity,
        "evidence_refs": [REF] if identity == "来源事实" else [],
    }
    return {
        "evidence_book_ref": "artifact://presales-evidence-book/" + "d" * 64,
        "decision_context_ref": "artifact://customer-decision-context/" + "e" * 64,
        "situations": [node("situation-1")],
        "symptoms": [node("symptom-1")],
        "causes_or_hypotheses": [node("cause-1", "诊断假设")],
        "impacts": [node("impact-1", "待联合验证")],
        "constraints": [node("constraint-1")],
        "unknowns": [node("unknown-1", "证据缺口")],
        "derived_requirements": [node("requirement-1", "AI 分析")],
        "solution_components": [node("solution-1", "方案建议")],
        "mappings": [{
            "mapping_id": "mapping-1",
            "problem_ref": "symptom-1",
            "requirement_ref": "requirement-1",
            "solution_component_ref": "solution-1",
            "identity": "方案建议",
            "evidence_refs": [REF],
        }],
        "boundaries": [node("boundary-1", "方案建议")],
        "alternatives": [node("alternative-1", "方案建议")],
        "validation_items": [node("validation-1", "待联合验证")],
    }


def blueprint(mode: str = "material-backed") -> dict:
    return {
        "project_id": "project-1",
        "source_version": "content-v1",
        "material_mode": mode,
        "evidence_book_ref": "artifact://presales-evidence-book/" + "d" * 64,
        "decision_context_ref": "artifact://customer-decision-context/" + "e" * 64,
        "problem_solution_fit_ref": "artifact://problem-solution-fit-map/" + "f" * 64,
        "section_flow": ["客户业务事项", "问题与验证方案"],
        "slides": [{
            "slide_id": "S01",
            "order": 1,
            "section_id": "problem",
            "page_task": "说明当前已知断点和证据边界",
            "reading_question": "当前已知什么，仍需验证什么",
            "neutral_title": "当前流程断点与证据边界",
            "visible_copy_blocks": [{"block_id": "b1", "text": "材料记录了流程断点", "identity": "来源事实"}],
            "identity_labels": ["来源事实"] if mode != "proposal-led" else ["诊断假设", "方案建议", "待联合验证"],
            "evidence_bindings": [] if mode == "proposal-led" else [{"content_ref": "b1", "source_refs": [REF]}],
            "material_views": [] if mode == "proposal-led" else [material_view()],
            "analysis_or_proposal_blocks": [{"block_id": "a1", "text": "建议联合核实影响范围", "identity": "方案建议"}],
            "solution_mapping_refs": ["mapping-1"],
            "previous_relation": "开篇",
            "next_relation": "进入方案要求",
            "speaker_notes": "完整讲解当前事实、未知和验证动作。",
            "reading_quality": {"independently_readable": True, "information_density": "moderate", "review_note": "事实与建议分开"},
            "material_mode": mode,
        }],
        "hard_gate_refs": [],
        "repair_history": [],
    }


class V22ContentContractTests(unittest.TestCase):
    def test_four_authoritative_objects_validate(self) -> None:
        self.assertEqual(validate_presales_evidence_book(evidence_book())["material_mode"], "material-backed")
        self.assertEqual(validate_customer_decision_context(decision_context())["decision_stage"], "联合方案验证")
        self.assertEqual(validate_problem_solution_fit_map(fit_map())["mappings"][0]["mapping_id"], "mapping-1")
        self.assertEqual(validate_reading_deck_blueprint(blueprint())["slides"][0]["neutral_title"], "当前流程断点与证据边界")

    def test_rejects_legacy_opinion_first_fields_anywhere(self) -> None:
        for payload, validator, key in (
            (decision_context(), validate_customer_decision_context, "desiredCustomerJudgment"),
            (blueprint(), validate_reading_deck_blueprint, "coreClaim"),
        ):
            invalid = copy.deepcopy(payload)
            invalid[key] = "客户必须接受方案"
            with self.subTest(key=key), self.assertRaises(ContractValidationError):
                validator(invalid)

    def test_rejects_unsourced_fact_strong_title_and_incomplete_mapping(self) -> None:
        unsourced = evidence_book()
        unsourced["facts"][0]["source_refs"] = []
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(unsourced)

        strong = blueprint()
        strong["slides"][0]["neutral_title"] = "必须选择唯一平台才能成功"
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(strong)

        incomplete = fit_map()
        del incomplete["mappings"][0]["evidence_refs"]
        with self.assertRaises(ContractValidationError):
            validate_problem_solution_fit_map(incomplete)

    def test_proposal_led_is_complete_but_cannot_claim_customer_facts(self) -> None:
        proposal = validate_reading_deck_blueprint(blueprint("proposal-led"))
        self.assertEqual(
            set(proposal["slides"][0]["identity_labels"]),
            {"诊断假设", "方案建议", "待联合验证"},
        )
        invalid = evidence_book("proposal-led")
        invalid["facts"] = [evidence_item()]
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(invalid)

    def test_material_modes_require_closed_material_views_and_preserve_them(self) -> None:
        expected = material_view()
        for mode in ("material-backed", "mixed-evidence"):
            with self.subTest(mode=mode):
                validated = validate_reading_deck_blueprint(blueprint(mode))
                self.assertEqual(validated["slides"][0]["material_views"], [expected])

                missing_views = blueprint(mode)
                missing_views["slides"][0]["material_views"] = []
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(missing_views)

        proposal = validate_reading_deck_blueprint(blueprint("proposal-led"))
        self.assertEqual(proposal["slides"][0]["material_views"], [])

        for field in expected:
            with self.subTest(missing_field=field):
                invalid = blueprint()
                del invalid["slides"][0]["material_views"][0][field]
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)

        invalid = blueprint()
        invalid["slides"][0]["material_views"][0]["unexpected"] = "not closed"
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(invalid)

    def test_material_view_asset_ref_must_be_a_safe_project_relative_posix_path(self) -> None:
        for asset_ref in (
            "",
            "../S01-M01.png",
            "review-assets/../S01-M01.png",
            "/review-assets/content/S01-M01.png",
            "https://example.com/S01-M01.png",
            "asset://content/S01-M01.png",
            r"review-assets\content\S01-M01.png",
            "./review-assets/content/S01-M01.png",
            "review-assets//content/S01-M01.png",
            "review-assets/content/./S01-M01.png",
            "review-assets/content/",
            "review-assets/content/S01\x00-M01.png",
            "review-assets/content/S01\n-M01.png",
            "review-assets/content/S01\x7f-M01.png",
        ):
            with self.subTest(asset_ref=asset_ref):
                invalid = blueprint()
                invalid["slides"][0]["material_views"][0]["asset_ref"] = asset_ref
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)

    def test_material_view_page_number_must_be_a_positive_integer(self) -> None:
        valid = validate_reading_deck_blueprint(blueprint())
        self.assertEqual(valid["slides"][0]["material_views"][0]["page_number"], 3)

        for page_number in (False, 0, -1, 1.0, "3"):
            with self.subTest(page_number=page_number):
                invalid = blueprint()
                invalid["slides"][0]["material_views"][0]["page_number"] = page_number
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)

        one = blueprint()
        one["slides"][0]["material_views"][0]["page_number"] = 1
        self.assertEqual(
            validate_reading_deck_blueprint(one)["slides"][0]["material_views"][0]["page_number"],
            1,
        )

    def test_material_view_evidence_identity_must_be_supported(self) -> None:
        valid = validate_reading_deck_blueprint(blueprint())
        self.assertEqual(
            valid["slides"][0]["material_views"][0]["evidence_identity"],
            "来源事实",
        )

        for evidence_identity in ("", "未知值"):
            with self.subTest(evidence_identity=evidence_identity):
                invalid = blueprint()
                invalid["slides"][0]["material_views"][0][
                    "evidence_identity"
                ] = evidence_identity
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)


if __name__ == "__main__":
    unittest.main()
