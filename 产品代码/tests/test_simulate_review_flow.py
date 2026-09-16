"""Deterministic v2.2 professional-review integration flow.

The fixtures prove Runtime contracts only. They are not Browser, host receipt,
AI receipt, PowerPoint, or customer acceptance evidence.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_review_projection import accepted_review
from tests.test_v22_visual_review_service import seed_visual_review


class SimulateReviewFlowTests(unittest.TestCase):
    def test_full_review_flow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ppt-v22-review-flow-") as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="review-flow")
            _blueprint_ref, _content_ref, content_session, content_state = (
                accepted_review(kernel, slide_count=4)
            )
            (
                _design_ref,
                _anchor_ref,
                visual_contract_ref,
                _visual_ref,
                visual_session,
                visual_state,
            ) = seed_visual_review(kernel)

            content = ContentReviewProjectionService(kernel).project(
                content_session["review_session_id"]
            )
            visual = VisualReviewService(kernel).project(
                visual_session["review_session_id"]
            )
            self.assertEqual(content["review_type"], "content-full-deck")
            self.assertEqual(
                [slide["slide_id"] for slide in content["slides"]],
                ["S01", "S02", "S03", "S04"],
            )
            self.assertEqual(visual["review_type"], "visual-professional")
            self.assertEqual(len(visual["anchors"]), 3)
            self.assertEqual(len(visual["slide_visual_contracts"]), 4)

            self.assertEqual(
                kernel.load().artifact_heads["content/reading-blueprint"],
                _blueprint_ref,
            )
            self.assertEqual(visual_state.gate_status["G0"], "passed")

            mark = {
                "mark_id": "review-flow-mark",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "构图关系需要更明确",
                "visual_contract_ref": visual_contract_ref,
                "source_version": "visual-v1",
                "revision": kernel.load().revision,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
            _marks_ref, marks, final = VisualReviewService(
                kernel
            ).save_contract_review_marks(
                command_id="review-flow-visual-mark",
                expected_revision=kernel.load().revision,
                review_session_id=visual_session["review_session_id"],
                source_version="visual-v1",
                marks=[mark],
            )
            self.assertEqual(marks["marks"][0]["mark_id"], "review-flow-mark")
            self.assertNotIn("visual/anchor-feedback-batch", final.artifact_heads)
            self.assertEqual(final.gate_status["G3"], "user-reviewable")


if __name__ == "__main__":
    unittest.main()
