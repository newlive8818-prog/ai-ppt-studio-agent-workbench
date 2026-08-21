from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
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

    def test_g2_requires_independent_reviews_and_current_required_target(self) -> None:
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
            with self.assertRaises(GateBlockedError):
                visual.record_g2("missing-target-g2", current_revision)
            self.assertEqual(visual.kernel.load().revision, current_revision)
            mac_ref = visual.register_target_render_evidence(
                "target-macos-powerpoint",
                current_revision,
                rich_target_payload(visual, "macos-powerpoint", refs),
            )
            state = visual.record_g2("pass-g2", current_revision + 1)
            self.assertEqual(state.gate_status["G2"], "passed")
            self.assertEqual(state.gate_status["G3"], "locked")
            self.assertNotIn(
                "visual/target-evidence/G2/macos-wps",
                state.artifact_heads,
            )
            policy_ref = state.artifact_heads["release/target-policy"]
            lineage = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(state.artifact_heads["gate/G2/lineage"])
            )["payload"]
            self.assertEqual(lineage["release_target_policy_ref"], policy_ref)
            self.assertEqual(lineage["required_target_ids"], ["macos-powerpoint"])
            self.assertEqual(
                lineage["deferred_target_ids"],
                ["macos-wps", "windows-powerpoint", "windows-wps"],
            )
            self.assertEqual(lineage["target_evidence_refs"], [mac_ref])

    def test_deferred_wps_evidence_cannot_substitute_for_required_mac(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp))
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
            visual.register_target_render_evidence(
                "deferred-macos-wps",
                revision + 2,
                rich_target_payload(visual, "macos-wps", refs),
            )

            with self.assertRaises(GateBlockedError) as raised:
                visual.record_g2("wps-cannot-substitute", revision + 3)

            self.assertIn("missing-target:macos-powerpoint", raised.exception.missing_evidence)


if __name__ == "__main__":
    unittest.main()
