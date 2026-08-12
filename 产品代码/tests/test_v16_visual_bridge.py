from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from tests.v16_visual_fixtures import (
    confirmed_g0,
    passing_visual_review,
    prepared_g2,
    prepared_visual_contracts,
    valid_visual_brief,
)


class V16VisualBridgeTests(unittest.TestCase):
    def test_existing_commit_and_internal_gate_operations_route_to_visual_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            _content, revision, blueprint_ref = confirmed_g0(project)
            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "kind": "visual-brief",
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )
            self.assertIn(
                "visual/brief",
                committed["result"]["snapshot"]["artifacts"],
            )

        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_visual_contracts(project)
            convergence_ref = visual.register_convergence(
                "bridge-convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "视觉命题与页面家族已收敛",
                    "convergence_status": "passed",
                },
            )
            review_ref = visual.register_visual_review(
                "bridge-g1-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            passed = dispatch_v16(
                {
                    "operation": "record-internal-gate",
                    "project_root": str(project),
                    "expected_revision": revision + 2,
                    "gate": "G1",
                    "reviewer_role": "独立审美审查智能体",
                    "acceptance_record_refs": [convergence_ref, review_ref],
                }
            )
            self.assertEqual(
                passed["result"]["snapshot"]["gate_state"]["gates"]["G1"],
                "passed",
            )

    def test_visual_projection_marks_and_g3_use_existing_public_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g2(project, slide_count=2)
            published = visual.publish_visual_review("bridge-publish", revision)
            source_version = published.artifact_heads["visual/contract"]
            projection = dispatch_v16(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project),
                    "review_type": "visual",
                }
            )
            self.assertEqual(
                projection["review"]["source_version"], source_version
            )
            saved = dispatch_v16(
                {
                    "operation": "save-review-marks",
                    "project_root": str(project),
                    "expected_revision": published.revision,
                    "review_type": "visual",
                    "source_version": source_version,
                    "marks": [
                        {
                            "mark_id": "bridge-visual-mark",
                            "field_anchor": "visual-slide-s1-visible-copy",
                            "exact_text": "三条断点",
                            "prefix": "五套系统",
                            "suffix": "",
                            "comment": "增强证据层级",
                        }
                    ],
                }
            )
            saved_revision = saved["result"]["snapshot"]["revision"]
            self.assertEqual(
                saved["result"]["snapshot"]["gate_state"]["gates"]["G3"],
                "user-reviewable",
            )
            confirmed = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": saved_revision,
                    "gate": "G3",
                    "user_message_ref": "chat://message/bridge-g3-accepted",
                }
            )
            self.assertEqual(
                confirmed["result"]["snapshot"]["gate_state"]["gates"]["G3"],
                "passed",
            )


if __name__ == "__main__":
    unittest.main()
