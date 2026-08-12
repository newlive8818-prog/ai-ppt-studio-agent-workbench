from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.domains.presentation.targets import REQUIRED_TARGET_IDS
from tests.v16_visual_fixtures import (
    passing_visual_review,
    prepared_g1_anchor,
    prepared_visual_contracts,
    rich_target_payload,
)


class V16VisualGateTests(unittest.TestCase):
    def test_g1_requires_convergence_and_independent_binary_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(Path(temp))
            with self.assertRaises(GateBlockedError):
                visual.record_g1("early-g1", revision)
            convergence = visual.register_convergence(
                "convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "采用经营证据链命题与三类页面节奏",
                    "convergence_status": "passed",
                },
            )
            review = visual.register_visual_review(
                "g1-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            self.assertTrue(convergence.startswith("artifact://visual-convergence/"))
            self.assertTrue(review.startswith("artifact://visual-review-record/"))
            state = visual.record_g1("pass-g1", revision + 2)
            self.assertEqual(state.gate_status["G1"], "passed")
            self.assertEqual(state.gate_status["G2"], "open")

    def test_g1_rejects_scores_self_review_and_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(Path(temp))
            invalid = passing_visual_review(refs["contracts"])
            invalid["score"] = 95
            with self.assertRaises(ContractValidationError):
                visual.register_visual_review("scored", revision, invalid)
            self_review = passing_visual_review(
                refs["contracts"], reviewer_role="visual-art-director"
            )
            with self.assertRaises(ContractValidationError):
                visual.register_visual_review("self", revision, self_review)
            failed = passing_visual_review(refs["contracts"])
            failed["checks"][0].update(
                {
                    "result": "failed",
                    "failure_reason": "视觉层级不成立",
                    "repair_instruction": "重建层级",
                }
            )
            failed["overall_result"] = "failed"
            visual.register_visual_review("failed", revision, failed)
            with self.assertRaises(GateBlockedError):
                visual.record_g1("blocked-g1", revision + 1)

    def test_g2_requires_independent_reviews_and_four_rich_same_hash_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp))
            with self.assertRaises(GateBlockedError):
                visual.record_g2("early-g2", revision)
            visual.register_visual_review(
                "g2-aesthetic",
                revision,
                passing_visual_review(
                    refs["anchors"], stage="G2", reviewer_kind="aesthetic"
                ),
            )
            visual.register_visual_review(
                "g2-engineering",
                revision + 1,
                passing_visual_review(
                    refs["anchors"],
                    stage="G2",
                    reviewer_kind="engineering",
                    reviewer_role="independent-ppt-engineering-reviewer",
                ),
            )
            current_revision = revision + 2
            for target_id in REQUIRED_TARGET_IDS[:-1]:
                visual.register_target_render_evidence(
                    f"target-{target_id}",
                    current_revision,
                    rich_target_payload(visual, target_id, refs),
                )
                current_revision += 1
            with self.assertRaises(GateBlockedError):
                visual.record_g2("missing-target-g2", current_revision)
            self.assertEqual(visual.kernel.load().revision, current_revision)
            final_target = REQUIRED_TARGET_IDS[-1]
            visual.register_target_render_evidence(
                f"target-{final_target}",
                current_revision,
                rich_target_payload(visual, final_target, refs),
            )
            state = visual.record_g2("pass-g2", current_revision + 1)
            self.assertEqual(state.gate_status["G2"], "passed")
            self.assertEqual(state.gate_status["G3"], "locked")


if __name__ == "__main__":
    unittest.main()
