from __future__ import annotations

import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.review_service import ReviewService
from ai_ppt_studio.errors import GateBlockedError, ReviewSourceStaleError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import prepared_g2, valid_design_system
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


def visual_marks() -> list[dict[str, str]]:
    return [
        {
            "mark_id": "visual-m1",
            "field_anchor": "visual-slide-s1-visible-copy",
            "exact_text": "三条断点",
            "prefix": "五套系统",
            "suffix": "",
            "comment": "这里需要强化证据层级",
        }
    ]


class V16VisualReviewTests(unittest.TestCase):
    def test_g2_pass_freezes_every_visual_write_until_g3_publication(self) -> None:
        def current_payload(visual, slot: str) -> dict:
            reference = ArtifactReference.parse(
                visual.kernel.load().artifact_heads[slot]
            )
            return copy.deepcopy(
                visual.kernel.artifacts.resolve(reference)["payload"]
            )

        attempts = {
            "visual-brief": lambda visual, revision, refs: visual.register_visual_brief(
                "rewrite-brief-after-g2",
                revision,
                current_payload(visual, "visual/brief"),
            ),
            "design-system": lambda visual, revision, refs: visual.register_design_system(
                "rewrite-design-system-after-g2",
                revision,
                valid_design_system(refs["brief"], refs["blueprint"]),
            ),
            "contract-set": lambda visual, revision, refs: visual.register_visual_contract_set(
                "rewrite-contracts-after-g2",
                revision,
                current_payload(visual, "visual/contracts"),
            ),
            "convergence": lambda visual, revision, refs: visual.register_convergence(
                "rewrite-convergence-after-g2",
                revision,
                current_payload(visual, "visual/convergence"),
            ),
            "visual-review": lambda visual, revision, refs: visual.register_visual_review(
                "rewrite-review-after-g2",
                revision,
                current_payload(visual, "visual/review/G2/aesthetic"),
            ),
            "anchor-set": lambda visual, revision, refs: visual.register_anchor_set(
                "rewrite-anchors-after-g2",
                revision,
                current_payload(visual, "visual/anchors"),
            ),
            "image-assets": lambda visual, revision, refs: visual.register_image_asset_pack(
                "rewrite-images-after-g2",
                revision,
                {
                    "anchor_slide_set_ref": refs["anchors"],
                    "asset_kind": "non-semantic",
                    "independent_layers": True,
                    "contains_text": False,
                    "contains_numbers": False,
                    "contains_business_relationships": False,
                    "simulates_real_evidence": False,
                    "whole_slide_master": False,
                },
            ),
            "target-evidence": lambda visual, revision, refs: visual.register_target_render_evidence(
                "rewrite-target-evidence-after-g2",
                revision,
                current_payload(
                    visual, "visual/target-evidence/G2/macos-powerpoint"
                ),
            ),
            "record-g1": lambda visual, revision, refs: visual.record_g1(
                "rewrite-g1-after-g2", revision
            ),
            "record-g2": lambda visual, revision, refs: visual.record_g2(
                "rewrite-g2-after-g2", revision
            ),
        }
        for name, attempt in attempts.items():
            with self.subTest(entrypoint=name), tempfile.TemporaryDirectory() as temp:
                visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
                with self.assertRaises(GateBlockedError) as raised:
                    attempt(visual, revision, refs)
                self.assertIn(
                    "G2-visual-lineage-frozen-until-G3-publication",
                    raised.exception.missing_evidence,
                )
                self.assertEqual(visual.kernel.load().revision, revision)

    def test_g3_publication_rejects_any_head_diverged_from_g2_reviewed_lineage(self) -> None:
        slots = (
            "content/blueprint",
            "visual/brief",
            "visual/convergence",
            "visual/design-system",
            "visual/contracts",
            "visual/anchors",
            "visual/review/G1/aesthetic",
            "visual/review/G2/aesthetic",
            "visual/review/G2/engineering",
            "release/target-policy",
            "visual/target-evidence/G2/macos-powerpoint",
            "gate/G2/lineage",
        )
        for index, slot in enumerate(slots):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as temp:
                visual, revision, _refs = prepared_g2(Path(temp), slide_count=2)
                current_ref = visual.kernel.load().artifact_heads[slot]
                reference = ArtifactReference.parse(current_ref)
                replacement = copy.deepcopy(
                    visual.kernel.artifacts.resolve(reference)["payload"]
                )
                replacement["test_g2_lineage_divergence"] = slot
                diverged = visual.kernel.commit(
                    command_id=f"simulate-pre-g3-lineage-rewrite-{index}",
                    expected_revision=revision,
                    event_type="test.pre-g3-visual-lineage-diverged",
                    artifact_updates={slot: (reference.kind, replacement)},
                )

                with self.assertRaises(GateBlockedError) as raised:
                    visual.publish_visual_review(
                        "publish-diverged-visual-review", diverged.revision
                    )
                if slot == "content/blueprint":
                    self.assertIn(
                        "current-G0-confirmation-lineage-stale",
                        raised.exception.missing_evidence,
                    )
                else:
                    self.assertIn(
                        "G2-reviewed-visual-lineage-stale",
                        raised.exception.missing_evidence,
                    )
                self.assertNotIn(
                    "visual/contract", visual.kernel.load().artifact_heads
                )

    def test_g3_publication_freezes_all_visual_production_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-visual-review", revision)
            attempts = {
                "visual-brief": lambda: visual.register_visual_brief(
                    "rewrite-brief-after-g3", published.revision, {}
                ),
                "design-system": lambda: visual.register_design_system(
                    "rewrite-design-system-after-g3",
                    published.revision,
                    valid_design_system(refs["brief"], refs["blueprint"]),
                ),
                "contract-set": lambda: visual.register_visual_contract_set(
                    "rewrite-contracts-after-g3", published.revision, {}
                ),
                "convergence": lambda: visual.register_convergence(
                    "rewrite-convergence-after-g3", published.revision, {}
                ),
                "visual-review": lambda: visual.register_visual_review(
                    "rewrite-review-after-g3", published.revision, {}
                ),
                "anchor-set": lambda: visual.register_anchor_set(
                    "rewrite-anchors-after-g3", published.revision, {}
                ),
                "image-assets": lambda: visual.register_image_asset_pack(
                    "rewrite-images-after-g3", published.revision, {}
                ),
                "target-evidence": lambda: visual.register_target_render_evidence(
                    "rewrite-target-evidence-after-g3", published.revision, {}
                ),
                "record-g1": lambda: visual.record_g1(
                    "rewrite-g1-after-g3", published.revision
                ),
                "record-g2": lambda: visual.record_g2(
                    "rewrite-g2-after-g3", published.revision
                ),
                "republish-contract": lambda: visual.publish_visual_review(
                    "republish-visual-review-after-g3", published.revision
                ),
            }
            for name, attempt in attempts.items():
                with self.subTest(entrypoint=name):
                    with self.assertRaises(GateBlockedError):
                        attempt()

            state = visual.kernel.load()
            self.assertEqual(state.revision, published.revision)
            self.assertEqual(
                state.artifact_heads["visual/design-system"], refs["system"]
            )
            self.assertEqual(
                state.artifact_heads["visual/contract"],
                published.artifact_heads["visual/contract"],
            )

    def test_g3_context_rejects_contract_lineage_diverged_from_current_heads(self) -> None:
        slots = (
            "content/blueprint",
            "visual/convergence",
            "visual/design-system",
            "visual/contracts",
            "visual/anchors",
            "visual/review/G1/aesthetic",
            "visual/review/G2/aesthetic",
            "visual/review/G2/engineering",
            "release/target-policy",
            "visual/target-evidence/G2/macos-powerpoint",
            "gate/G2/lineage",
        )
        for index, slot in enumerate(slots):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as temp:
                visual, revision, _refs = prepared_g2(Path(temp), slide_count=2)
                published = visual.publish_visual_review(
                    "publish-visual-review", revision
                )
                current_ref = published.artifact_heads[slot]
                reference = ArtifactReference.parse(current_ref)
                replacement = copy.deepcopy(
                    visual.kernel.artifacts.resolve(reference)["payload"]
                )
                replacement["test_lineage_divergence"] = slot
                tampered = visual.kernel.commit(
                    command_id=f"simulate-lineage-rewrite-{index}",
                    expected_revision=published.revision,
                    event_type="test.visual-lineage-diverged",
                    artifact_updates={slot: (reference.kind, replacement)},
                )

                from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy

                with self.assertRaises(GateBlockedError):
                    GateConfirmationPolicy(visual.kernel).context("G3")
                self.assertEqual(visual.kernel.load().revision, tampered.revision)

    def test_formal_g3_reopen_removes_current_visual_lineage_before_rework(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-visual-review", revision)
            contract_ref = published.artifact_heads["visual/contract"]

            reopened = visual.reopen_g3(
                "reopen-g3-for-user-change",
                published.revision,
                reason="用户要求调整整套视觉合同",
            )

            self.assertEqual(reopened.gate_status["G0"], "passed")
            self.assertEqual(reopened.gate_status["G1"], "open")
            for gate in ("G2", "G3", "G4"):
                self.assertEqual(reopened.gate_status[gate], "locked")
            self.assertFalse(
                any(slot.startswith("visual/") for slot in reopened.artifact_heads)
            )
            self.assertNotIn("gate/G3/confirmation", reopened.artifact_heads)
            self.assertIn("gate/G3/reopen", reopened.artifact_heads)
            self.assertEqual(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(contract_ref)
                )["payload"]["status"],
                "user-reviewable",
            )

            brief_ref = visual.register_visual_brief(
                "new-visual-brief-after-reopen",
                reopened.revision,
                {
                    "content_blueprint_ref": refs["blueprint"],
                    "production_route": "strict-B",
                    "design_proposition": "重开后的新视觉命题",
                    "audience_fit": "决策者先看结论",
                    "narrative_rhythm": "问题—证据—方案—价值—行动",
                    "imagery_strategy": "只使用可追溯素材和非语义装饰",
                    "diagram_strategy": "关系使用原生可编辑对象",
                    "powerpoint_constraints": "事实与关系保持原生可编辑",
                    "target_ids": ["macos-powerpoint"],
                },
            )
            self.assertTrue(brief_ref.startswith("artifact://visual-brief/"))

    def test_g3_confirmation_rechecks_lineage_after_challenge_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-visual-review", revision)
            from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy

            context = GateConfirmationPolicy(visual.kernel).context("G3")
            assertion = gate_confirmation_kwargs(context)[
                "host_confirmation_assertion"
            ]
            replacement = valid_design_system(refs["brief"], refs["blueprint"])
            replacement["theme_proposition"] = "challenge 后被改写的视觉主题"
            diverged = visual.kernel.commit(
                command_id="diverge-after-challenge",
                expected_revision=published.revision,
                event_type="test.visual-lineage-diverged-after-challenge",
                artifact_updates={
                    "visual/design-system": ("deck-design-system", replacement)
                },
            )

            with self.assertRaises(GateBlockedError):
                visual.confirm_g3(
                    "confirm-diverged-g3",
                    diverged.revision,
                    host_confirmation_assertion=assertion,
                    source_version=context["source_version"],
                    challenge_id=context["challenge_id"],
                    challenge_revision=context["challenge_revision"],
                )

            self.assertEqual(visual.kernel.load().revision, diverged.revision)
            self.assertEqual(
                visual.kernel.load().gate_status["G3"], "user-reviewable"
            )

    def test_complete_projection_marks_and_chat_only_g3(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-visual-review", revision)
            self.assertEqual(published.gate_status["G3"], "user-reviewable")
            visual_contract_ref = published.artifact_heads["visual/contract"]
            reviewer = ReviewService(visual.kernel)
            projection = reviewer.visual_projection()
            self.assertEqual(
                projection["release_target_policy"],
                {
                    "policy_ref": published.artifact_heads["release/target-policy"],
                    "policy_id": "v1.6-macos-powerpoint",
                    "required_target_ids": ["macos-powerpoint"],
                    "deferred_target_ids": [
                        "macos-wps",
                        "windows-powerpoint",
                        "windows-wps",
                    ],
                    "compatibility_claim_scope": ["macos-powerpoint"],
                },
            )
            text = json.dumps(projection, ensure_ascii=False)
            anchors = [section["anchor"] for section in projection["sections"]]
            self.assertEqual(
                anchors,
                [
                    "visual-framework",
                    "deck-design-system",
                    "visual-slide-s1",
                    "visual-slide-s2",
                ],
            )
            self.assertNotIn("visual-overview", anchors)
            framework_labels = {
                field["label"] for field in projection["sections"][0]["fields"]
            }
            design_system_labels = {
                field["label"] for field in projection["sections"][1]["fields"]
            }
            self.assertIn("anchor_identity", framework_labels)
            self.assertNotIn("deck_design_system", framework_labels)
            self.assertIn("theme_proposition", design_system_labels)
            evidence_field = next(
                field
                for field in projection["sections"][0]["fields"]
                if field["label"] == "target_evidence_identities"
            )
            self.assertEqual(len(evidence_field["value"]), 1)
            self.assertEqual(
                set(evidence_field["value"][0]),
                {
                    "target_id",
                    "operating_system",
                    "operating_system_version",
                    "application",
                    "application_version",
                    "font_inventory_ref",
                    "font_substitution_plan_ref",
                    "source_pptx_ref",
                    "pptx_sha256",
                    "overall_result",
                    "evidence_ref",
                },
            )
            self.assertNotIn("slide_checks", evidence_field["value"][0])
            self.assertEqual(
                projection["gate_status"],
                {"G1": "passed", "G2": "passed", "G3": "user-reviewable"},
            )
            for literal in (
                "可信的经营证据链",
                "为什么现在必须改变",
                "五套系统",
                "三条断点",
                "解释来源",
                "information_hierarchy",
                "native_first_pptx_ref",
                "macos-powerpoint",
            ):
                self.assertIn(literal, text)
            visual_contract = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(visual_contract_ref)
            )["payload"]
            self.assertEqual(
                visual_contract["release_target_policy_ref"],
                published.artifact_heads["release/target-policy"],
            )
            self.assertEqual(
                visual_contract["required_target_ids"], ["macos-powerpoint"]
            )
            self.assertEqual(
                visual_contract["deferred_target_ids"],
                ["macos-wps", "windows-powerpoint", "windows-wps"],
            )
            self.assertNotIn("…", text)
            self.assertEqual(projection["source_version"], visual_contract_ref)

            saved = reviewer.save_marks(
                command_id="save-visual-marks",
                expected_revision=published.revision,
                review_type="visual",
                source_version=visual_contract_ref,
                marks=visual_marks(),
            )
            self.assertEqual(saved.gate_status["G3"], "user-reviewable")
            self.assertEqual(
                reviewer.visual_projection()["mark_set"]["status"],
                "pending-governance",
            )
            with self.assertRaises(GateBlockedError):
                visual.confirm_g3(
                    "invalid-g3",
                    saved.revision,
                    user_message_ref="review://saved/visual-m1",
                )
            self.assertEqual(visual.kernel.load().revision, saved.revision)
            from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy

            context = GateConfirmationPolicy(visual.kernel).context("G3")
            confirmed = visual.confirm_g3(
                "confirm-g3",
                saved.revision,
                **gate_confirmation_kwargs(context),
            )
            self.assertEqual(confirmed.gate_status["G3"], "passed")
            self.assertEqual(confirmed.gate_status["G4"], "open")

    def test_visual_marks_reject_a_stale_source_without_overwriting_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-visual-review", revision)
            reviewer = ReviewService(visual.kernel)
            with self.assertRaises(ReviewSourceStaleError):
                reviewer.save_marks(
                    command_id="stale-visual-marks",
                    expected_revision=published.revision,
                    review_type="visual",
                    source_version="artifact://visual-contract/" + "f" * 64,
                    marks=visual_marks(),
                )
            self.assertNotIn(
                "review-marks/visual", visual.kernel.load().artifact_heads
            )


if __name__ == "__main__":
    unittest.main()
