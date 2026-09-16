"""Migration guard: v1.6 content ReviewMark writes were replaced by PageDecision."""

from __future__ import annotations

import unittest

from ai_ppt_studio.application.bridge.content import HANDLERS as CONTENT_HANDLERS
from ai_ppt_studio.application.v16_bridge import HANDLERS


class ContentReviewWriteMigrationTests(unittest.TestCase):
    def test_content_review_uses_page_decisions_without_legacy_mark_writes(self) -> None:
        self.assertIn("save-content-page-decision", CONTENT_HANDLERS)
        self.assertIn("submit-content-review-batch", CONTENT_HANDLERS)
        self.assertNotIn("save-review-marks", HANDLERS)
        self.assertNotIn("get-review-projection", HANDLERS)


if __name__ == "__main__":
    unittest.main()
