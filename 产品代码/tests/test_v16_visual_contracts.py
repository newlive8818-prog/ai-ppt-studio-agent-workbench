from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import (
    confirmed_g0,
    passing_visual_review,
    prepared_visual_contracts,
    valid_contract_set,
    valid_design_system,
    valid_visual_brief,
)


class V16VisualContractTests(unittest.TestCase):
    def test_every_visual_write_requires_current_g0_confirmation_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            content, revision, blueprint_ref = confirmed_g0(Path(temp))
            visual = VisualService(content.kernel)
            brief_ref = visual.register_visual_brief(
                "brief-before-lineage-tamper",
                revision,
                valid_visual_brief(blueprint_ref),
            )
            state = visual.kernel.load()
            visual.kernel.commit(
                command_id="remove-current-g0-confirmation",
                expected_revision=state.revision,
                event_type="test.current-g0-confirmation-removed",
                artifact_updates={},
                artifact_removals=("gate/G0/confirmation",),
            )

            with self.assertRaises(GateBlockedError):
                visual.register_design_system(
                    "blocked-design-system",
                    state.revision + 1,
                    valid_design_system(brief_ref, blueprint_ref),
                )

            self.assertEqual(visual.kernel.load().revision, state.revision + 1)

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
                        "content_blueprint_ref": blueprint_ref,
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
            broken["slide_contracts"][0]["visible_copy"] = ["被改写"]
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
                        "slide_ids": ["s1"],
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
                    "slide_ids": ["s1", "s2", "s3"],
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
