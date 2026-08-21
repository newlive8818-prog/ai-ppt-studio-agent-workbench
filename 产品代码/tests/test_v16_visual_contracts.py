from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.domains.visual.contracts import validate_anchor_slide_set
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import (
    confirmed_g0,
    passing_visual_review,
    prepared_visual_contracts,
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


def render_assets(slide_ids: list[str]) -> list[dict[str, str]]:
    return [
        {
            "slide_id": slide_id,
            "current_asset_ref": f"review-assets/anchors/{slide_id}-current.png",
            "previous_asset_ref": "",
        }
        for slide_id in slide_ids
    ]


def anchor_payload(slide_ids: list[str]) -> dict:
    return {
        "visual_contract_set_ref": "artifact://visual-contract-set/" + "a" * 64,
        "slide_ids": slide_ids,
        "selection_reason": "覆盖章节、证据和方案三类关键页面家族",
        "render_assets": render_assets(slide_ids),
        "native_first_pptx_ref": "artifact://native-pptx/" + "b" * 64,
        "pptx_sha256": "d" * 64,
        "native_first_frozen": True,
        "editability_evidence_refs": [
            "artifact://editability-evidence/" + "c" * 64
        ],
        "preflight_render_refs": ["artifact://preflight-render/" + "e" * 64],
    }


class V16VisualContractTests(unittest.TestCase):
    def test_anchor_set_requires_a_nonempty_selection_reason(self) -> None:
        contract_set = {
            "slide_contracts": [
                {"slide_id": f"S{index:02d}"} for index in range(1, 5)
            ]
        }
        for value in (None, "", "   "):
            with self.subTest(value=value), self.assertRaises(
                ContractValidationError
            ):
                payload = anchor_payload(["S01", "S02", "S03"])
                if value is None:
                    payload.pop("selection_reason")
                else:
                    payload["selection_reason"] = value
                validate_anchor_slide_set(payload, contract_set)

    def test_anchor_set_requires_exactly_three_current_rendered_slides(self) -> None:
        contract_set = {
            "slide_contracts": [
                {"slide_id": f"S{index:02d}"} for index in range(1, 5)
            ]
        }
        for slide_ids in (
            ["S01", "S02"],
            ["S01", "S02", "S03", "S04"],
        ):
            with self.subTest(slide_ids=slide_ids), self.assertRaises(
                ContractValidationError
            ):
                validate_anchor_slide_set(anchor_payload(slide_ids), contract_set)

        missing_current = anchor_payload(["S01", "S02", "S03"])
        missing_current["render_assets"][1]["current_asset_ref"] = ""
        with self.assertRaises(ContractValidationError):
            validate_anchor_slide_set(missing_current, contract_set)

        valid = validate_anchor_slide_set(
            anchor_payload(["S01", "S02", "S03"]), contract_set
        )
        self.assertEqual(
            valid["render_assets"], render_assets(["S01", "S02", "S03"])
        )

    def test_anchor_render_assets_are_closed_ordered_and_project_relative(self) -> None:
        contract_set = {
            "slide_contracts": [
                {"slide_id": f"S{index:02d}"} for index in range(1, 5)
            ]
        }
        invalid_assets: list[list[dict[str, str]]] = []

        missing = render_assets(["S01", "S02", "S03"])
        missing.pop()
        invalid_assets.append(missing)

        duplicate = render_assets(["S01", "S01", "S03"])
        invalid_assets.append(duplicate)

        wrong_order = render_assets(["S02", "S01", "S03"])
        invalid_assets.append(wrong_order)

        unknown = render_assets(["S01", "S02", "S04"])
        invalid_assets.append(unknown)

        extra_field = render_assets(["S01", "S02", "S03"])
        extra_field[0]["unexpected"] = "not closed"
        invalid_assets.append(extra_field)

        missing_previous = render_assets(["S01", "S02", "S03"])
        del missing_previous[0]["previous_asset_ref"]
        invalid_assets.append(missing_previous)

        for assets in invalid_assets:
            with self.subTest(assets=assets), self.assertRaises(
                ContractValidationError
            ):
                payload = anchor_payload(["S01", "S02", "S03"])
                payload["render_assets"] = assets
                validate_anchor_slide_set(payload, contract_set)

        for asset_ref in (
            "../S01-current.png",
            "review-assets/../S01-current.png",
            "/review-assets/anchors/S01-current.png",
            "https://example.com/S01-current.png",
            "asset://anchor/S01",
            r"review-assets\anchors\S01-current.png",
            "./review-assets/anchors/S01-current.png",
            "review-assets//anchors/S01-current.png",
            "review-assets/anchors/./S01-current.png",
            "review-assets/anchors/",
            "review-assets/anchors/S01\x00-current.png",
            "review-assets/anchors/S01\u0085-current.png",
            "review-assets/anchors/S01\u202e-current.png",
        ):
            with self.subTest(asset_ref=asset_ref), self.assertRaises(
                ContractValidationError
            ):
                payload = anchor_payload(["S01", "S02", "S03"])
                payload["render_assets"][0]["current_asset_ref"] = asset_ref
                validate_anchor_slide_set(payload, contract_set)

    def test_strict_route_brief_and_complete_design_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content, revision, blueprint_ref = confirmed_g0(Path(temp))
            visual = VisualService(content.kernel)
            with self.assertRaises(ContractValidationError):
                visual.register_visual_brief(
                    "bad-route",
                    revision,
                    {
                        **valid_visual_brief(blueprint_ref),
                        "production_route": "route-A",
                        "image2_master_ref": "artifact://image/" + "a" * 64,
                    },
                )
            brief_ref = visual.register_visual_brief(
                "brief", revision, valid_visual_brief(blueprint_ref)
            )
            self.assertTrue(brief_ref.startswith("artifact://visual-brief/"))
            with self.assertRaises(ContractValidationError):
                visual.register_design_system(
                    "incomplete-system",
                    revision + 1,
                    {
                        "visual_brief_ref": brief_ref,
                        "reading_blueprint_ref": blueprint_ref,
                        "production_route": "strict-B",
                        "theme_proposition": "可信",
                    },
                )
            system_ref = visual.register_design_system(
                "design-system",
                revision + 1,
                valid_design_system(brief_ref, blueprint_ref),
            )
            self.assertTrue(system_ref.startswith("artifact://deck-design-system/"))

    def test_visual_contracts_cover_frozen_content_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content, revision, blueprint_ref = confirmed_g0(Path(temp))
            visual = VisualService(content.kernel)
            brief_ref = visual.register_visual_brief(
                "brief", revision, valid_visual_brief(blueprint_ref)
            )
            system_ref = visual.register_design_system(
                "system",
                revision + 1,
                valid_design_system(brief_ref, blueprint_ref),
            )
            blueprint = content.kernel.artifacts.resolve(
                ArtifactReference.parse(blueprint_ref)
            )["payload"]
            contracts = valid_contract_set(
                system_ref, blueprint_ref, blueprint["slides"]
            )
            contract_ref = visual.register_visual_contract_set(
                "contracts",
                revision + 2,
                contracts,
            )
            self.assertTrue(
                contract_ref.startswith("artifact://visual-contract-set/")
            )

            broken = copy.deepcopy(contracts)
            broken["slide_contracts"][0]["visible_copy_blocks"] = [
                {"block_id": "forged", "text": "被改写", "identity": "来源事实"}
            ]
            with self.assertRaises(ContractValidationError):
                visual.register_visual_contract_set(
                    "broken", revision + 3, broken
                )
            missing = copy.deepcopy(contracts)
            missing["slide_contracts"] = []
            with self.assertRaises(ContractValidationError):
                visual.register_visual_contract_set(
                    "missing", revision + 3, missing
                )

    def test_native_first_anchor_and_image2_nonsemantic_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(
                Path(temp), slide_count=3
            )
            visual.register_convergence(
                "anchor-convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "三页锚点覆盖章节、证据和方案家族",
                    "convergence_status": "passed",
                },
            )
            visual.register_visual_review(
                "anchor-g1-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            g1 = visual.record_g1("anchor-g1", revision + 2)
            pptx_ref = str(
                visual.kernel.artifacts.put(
                    "native-pptx",
                    {"pptx_sha256": "d" * 64, "production_route": "strict-B"},
                )
            )
            editable_ref = str(
                visual.kernel.artifacts.put(
                    "editability-evidence", {"semantic_objects_editable": True}
                )
            )
            preflight_ref = str(
                visual.kernel.artifacts.put(
                    "preflight-render", {"identity": "preflight-only"}
                )
            )
            with self.assertRaises(ContractValidationError):
                visual.register_anchor_set(
                    "too-few-anchors",
                    g1.revision,
                    {
                        "visual_contract_set_ref": refs["contracts"],
                        "slide_ids": ["S01"],
                        "selection_reason": "用于验证数量拒绝原因",
                        "render_assets": render_assets(["S01"]),
                        "native_first_pptx_ref": pptx_ref,
                        "pptx_sha256": "d" * 64,
                        "native_first_frozen": True,
                        "editability_evidence_refs": [editable_ref],
                        "preflight_render_refs": [preflight_ref],
                    },
                )
            anchor_ref = visual.register_anchor_set(
                "anchors",
                g1.revision,
                {
                    "visual_contract_set_ref": refs["contracts"],
                    "slide_ids": ["S01", "S02", "S03"],
                    "selection_reason": "覆盖章节、证据和方案三类关键页面家族",
                    "render_assets": render_assets(["S01", "S02", "S03"]),
                    "native_first_pptx_ref": pptx_ref,
                    "pptx_sha256": "d" * 64,
                    "native_first_frozen": True,
                    "editability_evidence_refs": [editable_ref],
                    "preflight_render_refs": [preflight_ref],
                },
            )
            self.assertTrue(anchor_ref.startswith("artifact://anchor-slide-set/"))
            with self.assertRaises(ContractValidationError):
                visual.register_image_asset_pack(
                    "bad-image-assets",
                    g1.revision + 1,
                    {
                        "anchor_slide_set_ref": anchor_ref,
                        "asset_kind": "non-semantic",
                        "independent_layers": True,
                        "contains_text": True,
                        "contains_numbers": False,
                        "contains_business_relationships": False,
                        "simulates_real_evidence": False,
                        "whole_slide_master": False,
                    },
                )
            asset_ref = visual.register_image_asset_pack(
                "image-assets",
                g1.revision + 1,
                {
                    "anchor_slide_set_ref": anchor_ref,
                    "asset_kind": "non-semantic",
                    "independent_layers": True,
                    "contains_text": False,
                    "contains_numbers": False,
                    "contains_business_relationships": False,
                    "simulates_real_evidence": False,
                    "whole_slide_master": False,
                },
            )
            self.assertTrue(asset_ref.startswith("artifact://image-asset-pack/"))


if __name__ == "__main__":
    unittest.main()
