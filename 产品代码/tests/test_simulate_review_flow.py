"""Schema 3 professional-review integration flow.

This test uses deterministic target-evidence fixtures. It verifies the current
authoritative kernel, projection, and exact-mark contracts; it is not real
desktop PowerPoint/WPS evidence.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai_ppt_studio.application.review_service import ReviewService
from tests.v16_visual_fixtures import prepared_g2


class SimulateReviewFlowTests(unittest.TestCase):
    def test_full_review_flow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ppt-v16-review-flow-") as temp:
            visual, revision, _refs = prepared_g2(Path(temp), slide_count=2)
            published = visual.publish_visual_review("publish-review", revision)
            reviewer = ReviewService(visual.kernel)

            content = reviewer.content_projection()
            visual_projection = reviewer.visual_projection()
            content_pages = [
                section["anchor"]
                for section in content["sections"]
                if section["anchor"].startswith("slide-")
            ]
            visual_pages = [
                section["anchor"]
                for section in visual_projection["sections"]
                if section["anchor"].startswith("visual-slide-")
            ]

            self.assertEqual(content_pages, ["slide-s1", "slide-s2"])
            self.assertEqual(visual_pages, ["visual-slide-s1", "visual-slide-s2"])
            self.assertEqual(content["gate_status"], {"G0": "passed"})
            self.assertEqual(
                visual_projection["gate_status"],
                {"G1": "passed", "G2": "passed", "G3": "user-reviewable"},
            )

            saved = reviewer.save_marks(
                command_id="save-review-flow-mark",
                expected_revision=published.revision,
                review_type="content",
                source_version=content["source_version"],
                marks=[
                    {
                        "mark_id": "m-flow",
                        "field_anchor": "slide-s1-visible-copy",
                        "exact_text": "三条断点",
                        "prefix": "五套系统",
                        "suffix": "",
                        "comment": "补充断点来源",
                    }
                ],
            )
            refreshed = reviewer.content_projection()
            self.assertEqual(saved.gate_status["G0"], "passed")
            self.assertEqual(refreshed["mark_set"]["status"], "pending-governance")
            self.assertEqual(refreshed["mark_set"]["marks"][0]["mark_id"], "m-flow")


if __name__ == "__main__":
    unittest.main()
