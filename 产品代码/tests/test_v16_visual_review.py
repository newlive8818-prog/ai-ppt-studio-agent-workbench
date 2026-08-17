from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.review_service import ReviewService
from ai_ppt_studio.errors import GateBlockedError, ReviewSourceStaleError
from tests.v16_visual_fixtures import prepared_g2


def visual_marks() -> list[dict[str, str]]:
    return [
        {
            "mark_id": "visual-m1",
            "field_anchor": "visual-slide-s01-visible-copy-blocks",
            "exact_text": "材料记录了流程断点",
            "prefix": "",
            "suffix": "",
            "comment": "这里需要强化证据层级",
        }
    ]


class V16VisualReviewTests(unittest.TestCase):
    def test_complete_projection_marks_and_chat_only_g3(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=3)
            published = visual.publish_visual_review("publish-visual-review", revision)
            self.assertEqual(published.gate_status["G3"], "user-reviewable")
            visual_contract_ref = published.artifact_heads["visual/contract"]
            reviewer = ReviewService(visual.kernel)
            projection = reviewer.visual_projection()
            text = json.dumps(projection, ensure_ascii=False)
            anchors = [section["anchor"] for section in projection["sections"]]
            self.assertEqual(
                anchors,
                [
                    "visual-framework",
                    "deck-design-system",
                    "visual-slide-s01",
                    "visual-slide-s02",
                    "visual-slide-s03",
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
                "当前流程断点与证据边界",
                "材料记录了流程断点",
                "建议联合核实影响范围",
                "完整讲解当前事实、未知和验证动作",
                "information_hierarchy",
                "native_first_pptx_ref",
                "macos-powerpoint",
            ):
                self.assertIn(literal, text)
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
            confirmed = visual.confirm_g3(
                "confirm-g3",
                saved.revision,
                user_message_ref="chat://message/visual-contract-accepted",
            )
            self.assertEqual(confirmed.gate_status["G3"], "passed")
            self.assertEqual(confirmed.gate_status["G4"], "open")

    def test_visual_marks_reject_a_stale_source_without_overwriting_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=3)
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
