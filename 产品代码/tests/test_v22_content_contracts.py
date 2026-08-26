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
    gap = {
        **fact,
        "item_id": "gap-1",
        "identity": "证据缺口",
        "statement": "业务影响待联合确认",
        "source_refs": [] if mode == "proposal-led" else [REF],
    }
    forbidden = {
        **fact,
        "item_id": "forbid-1",
        "identity": "禁止使用",
        "statement": "不得编造收益数字",
        "source_refs": [] if mode == "proposal-led" else [REF],
    }
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
        "evidence_gaps": [gap],
        "forbidden_extrapolations": [forbidden],
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


def fit_map(mode: str = "material-backed") -> dict:
    def node(node_id: str, identity: str = "来源事实") -> dict:
        effective_identity = identity
        if mode == "proposal-led":
            if node_id.startswith(("situation", "symptom", "cause", "impact", "constraint", "unknown")):
                effective_identity = "诊断假设"
            elif node_id.startswith("requirement"):
                effective_identity = "AI 分析"
            elif node_id.startswith(("solution", "boundary", "alternative")):
                effective_identity = "方案建议"
            elif node_id.startswith("validation"):
                effective_identity = "待联合验证"
        return {
        "id": node_id,
        "statement": node_id,
        "identity": effective_identity,
        "evidence_refs": [] if mode == "proposal-led" else ([REF] if identity == "来源事实" else []),
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
            "evidence_refs": [] if mode == "proposal-led" else [REF],
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
            "customer_decision_item": {
                "text": "客户确认现状边界后，再判断是否进入联合方案验证。",
                "identity": "待联合验证",
                "evidence_refs": [],
            },
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
        validated = validate_reading_deck_blueprint(blueprint())
        self.assertEqual(validated["slides"][0]["neutral_title"], "当前流程断点与证据边界")
        self.assertEqual(
            validated["slides"][0]["customer_decision_item"],
            {
                "text": "客户确认现状边界后，再判断是否进入联合方案验证。",
                "identity": "待联合验证",
                "evidence_refs": [],
            },
        )

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

    def test_authoritative_roots_and_nested_records_are_closed(self) -> None:
        cases = []

        value = evidence_book()
        value["unexpected"] = True
        cases.append(("evidence-root", value, validate_presales_evidence_book))
        value = evidence_book()
        value["facts"][0]["unexpected"] = True
        cases.append(("evidence-row", value, validate_presales_evidence_book))

        value = decision_context()
        value["unexpected"] = True
        cases.append(("decision-root", value, validate_customer_decision_context))

        value = fit_map()
        value["unexpected"] = True
        cases.append(("fit-root", value, validate_problem_solution_fit_map))
        value = fit_map()
        value["symptoms"][0]["unexpected"] = True
        cases.append(("fit-node", value, validate_problem_solution_fit_map))
        value = fit_map()
        value["mappings"][0]["unexpected"] = True
        cases.append(("fit-mapping", value, validate_problem_solution_fit_map))

        for field in ("visible_copy_blocks", "analysis_or_proposal_blocks"):
            value = blueprint()
            value["slides"][0][field][0]["unexpected"] = True
            cases.append((field, value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["evidence_bindings"][0]["unexpected"] = True
        cases.append(("evidence-binding", value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["reading_quality"]["unexpected"] = True
        cases.append(("reading-quality", value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["unexpected"] = True
        cases.append(("slide", value, validate_reading_deck_blueprint))

        for label, payload, validator in cases:
            with self.subTest(label=label), self.assertRaisesRegex(
                ContractValidationError,
                "fields are not closed",
            ):
                validator(payload)

    def test_evidence_book_buckets_enforce_identity_roles(self) -> None:
        wrong_identities = {
            "facts": "方案建议",
            "user_confirmed_facts": "来源事实",
            "inferences": "来源事实",
            "conflicts": "方案建议",
            "unknowns": "材料推断",
            "evidence_gaps": "来源事实",
            "forbidden_extrapolations": "待联合验证",
        }
        for field, identity in wrong_identities.items():
            invalid = evidence_book()
            row = evidence_item(identity)
            row["item_id"] = f"{field}-1"
            invalid[field] = [row]
            with self.subTest(field=field, identity=identity), self.assertRaises(
                ContractValidationError
            ):
                validate_presales_evidence_book(invalid)

    def test_evidence_book_sources_are_unique_disjoint_and_declared(self) -> None:
        duplicate_source = evidence_book()
        duplicate_source["source_refs"].append(REF)
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(duplicate_source)

        excluded_ref = "artifact://material-finding/" + "b" * 64
        duplicate_excluded = evidence_book()
        duplicate_excluded["excluded_material_refs"] = [excluded_ref, excluded_ref]
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(duplicate_excluded)

        overlapping = evidence_book()
        overlapping["excluded_material_refs"] = [REF]
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(overlapping)

        undeclared = evidence_book()
        undeclared["facts"][0]["source_refs"] = [excluded_ref]
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(undeclared)

        excluded = evidence_book()
        excluded["facts"][0]["source_refs"] = [excluded_ref]
        excluded["source_refs"].append(excluded_ref)
        excluded["excluded_material_refs"] = [excluded_ref]
        with self.assertRaises(ContractValidationError):
            validate_presales_evidence_book(excluded)

    def test_ai_analysis_is_internal_only(self) -> None:
        valid_fit = fit_map()
        valid_fit["derived_requirements"][0]["identity"] = "AI 分析"
        self.assertEqual(
            validate_problem_solution_fit_map(valid_fit)["derived_requirements"][0][
                "identity"
            ],
            "AI 分析",
        )
        valid_blueprint = blueprint()
        valid_blueprint["slides"][0]["analysis_or_proposal_blocks"][0][
            "identity"
        ] = "AI 分析"
        self.assertEqual(
            validate_reading_deck_blueprint(valid_blueprint)["slides"][0][
                "analysis_or_proposal_blocks"
            ][0]["identity"],
            "AI 分析",
        )

        invalid_cases = []
        value = evidence_book()
        value["facts"][0]["identity"] = "AI 分析"
        invalid_cases.append(("fact", value, validate_presales_evidence_book))
        value = blueprint()
        value["slides"][0]["visible_copy_blocks"][0]["identity"] = "AI 分析"
        invalid_cases.append(("visible-copy", value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["identity_labels"] = ["AI 分析"]
        invalid_cases.append(("identity-label", value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["material_views"][0]["evidence_identity"] = "AI 分析"
        invalid_cases.append(("material-view", value, validate_reading_deck_blueprint))
        value = blueprint()
        value["slides"][0]["customer_decision_item"]["identity"] = "AI 分析"
        invalid_cases.append(("customer-decision", value, validate_reading_deck_blueprint))

        for label, payload, validator in invalid_cases:
            with self.subTest(label=label), self.assertRaises(ContractValidationError):
                validator(payload)

    def test_fit_map_ids_and_mapping_categories_are_closed(self) -> None:
        duplicate_node = fit_map()
        duplicate_node["symptoms"].append(copy.deepcopy(duplicate_node["symptoms"][0]))
        with self.assertRaises(ContractValidationError):
            validate_problem_solution_fit_map(duplicate_node)

        duplicate_mapping = fit_map()
        duplicate_mapping["mappings"].append(
            copy.deepcopy(duplicate_mapping["mappings"][0])
        )
        with self.assertRaises(ContractValidationError):
            validate_problem_solution_fit_map(duplicate_mapping)

        for field, wrong_ref in (
            ("problem_ref", "requirement-1"),
            ("requirement_ref", "solution-1"),
            ("solution_component_ref", "symptom-1"),
        ):
            invalid = fit_map()
            invalid["mappings"][0][field] = wrong_ref
            with self.subTest(field=field), self.assertRaises(
                ContractValidationError
            ):
                validate_problem_solution_fit_map(invalid)

    def test_blueprint_local_ids_and_references_are_closed(self) -> None:
        duplicate_block = blueprint()
        duplicate_block["slides"][0]["analysis_or_proposal_blocks"][0][
            "block_id"
        ] = "b1"
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(duplicate_block)

        unknown_content = blueprint()
        unknown_content["slides"][0]["evidence_bindings"][0][
            "content_ref"
        ] = "missing"
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(unknown_content)

        duplicate_binding = blueprint()
        duplicate_binding["slides"][0]["evidence_bindings"].append(
            copy.deepcopy(duplicate_binding["slides"][0]["evidence_bindings"][0])
        )
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(duplicate_binding)

        for field in ("identity_labels", "solution_mapping_refs"):
            invalid = blueprint()
            invalid["slides"][0][field].append(invalid["slides"][0][field][0])
            with self.subTest(field=field), self.assertRaises(
                ContractValidationError
            ):
                validate_reading_deck_blueprint(invalid)

        duplicate_section = blueprint()
        duplicate_section["section_flow"].append(duplicate_section["section_flow"][0])
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(duplicate_section)

    def test_customer_decision_item_is_closed_normalized_and_non_coercive(self) -> None:
        for invalid_item in (None, [], "not-an-object"):
            invalid = blueprint()
            invalid["slides"][0]["customer_decision_item"] = invalid_item
            with self.subTest(invalid_item=invalid_item), self.assertRaises(
                ContractValidationError
            ):
                validate_reading_deck_blueprint(invalid)

        for mutation in (
            lambda item: item.pop("text"),
            lambda item: item.__setitem__("unknown", "not closed"),
            lambda item: item.__setitem__("text", ""),
            lambda item: item.__setitem__("text", "  客户先核实现状  "),
            lambda item: item.__setitem__("text", "客户必须选择唯一平台才能成功"),
            lambda item: item.__setitem__("identity", "未知身份"),
        ):
            invalid = blueprint()
            mutation(invalid["slides"][0]["customer_decision_item"])
            with self.subTest(item=invalid["slides"][0]["customer_decision_item"]), self.assertRaises(
                ContractValidationError
            ):
                validate_reading_deck_blueprint(invalid)

    def test_factual_customer_decision_item_requires_evidence(self) -> None:
        for identity in ("来源事实", "用户已确认"):
            with self.subTest(identity=identity):
                invalid = blueprint()
                invalid["slides"][0]["customer_decision_item"].update(
                    identity=identity,
                    evidence_refs=[],
                )
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(invalid)

                valid = blueprint()
                valid["slides"][0]["customer_decision_item"].update(
                    identity=identity,
                    evidence_refs=[REF],
                )
                self.assertEqual(
                    validate_reading_deck_blueprint(valid)["slides"][0][
                        "customer_decision_item"
                    ]["evidence_refs"],
                    [REF],
                )

    def test_proposal_led_customer_decision_item_cannot_claim_customer_facts(self) -> None:
        proposal = blueprint("proposal-led")
        proposal["slides"][0]["customer_decision_item"].update(
            identity="来源事实",
            evidence_refs=[REF],
        )
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(proposal)

        proposal = blueprint("proposal-led")
        proposal["slides"][0]["customer_decision_item"]["evidence_refs"] = [REF]
        with self.assertRaises(ContractValidationError):
            validate_reading_deck_blueprint(proposal)

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

    def test_all_material_modes_allow_empty_material_views_and_preserve_closed_views(self) -> None:
        expected = material_view()
        for mode in ("material-backed", "mixed-evidence", "proposal-led"):
            with self.subTest(mode=mode, material_views="empty"):
                without_views = blueprint(mode)
                without_views["slides"][0]["material_views"] = []
                validated = validate_reading_deck_blueprint(without_views)
                self.assertEqual(validated["slides"][0]["material_views"], [])

        for mode in ("material-backed", "mixed-evidence"):
            with self.subTest(mode=mode, material_views="present"):
                validated = validate_reading_deck_blueprint(blueprint(mode))
                self.assertEqual(validated["slides"][0]["material_views"], [expected])

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

    def test_material_modes_still_require_evidence_bindings_when_views_are_empty(self) -> None:
        for mode in ("material-backed", "mixed-evidence"):
            with self.subTest(mode=mode):
                invalid = blueprint(mode)
                invalid["slides"][0]["material_views"] = []
                invalid["slides"][0]["evidence_bindings"] = []
                with self.assertRaisesRegex(
                    ContractValidationError,
                    rf"{mode} slides require evidence bindings",
                ):
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
