from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.errors import FeedbackGovernanceError
from tests.test_v16_review_marks import accepted_content


class V16FeedbackGovernanceTests(unittest.TestCase):
    def test_raw_feedback_cannot_become_change_set_and_f2_requires_decision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            raw = service.capture_feedback(
                "f1",
                revision,
                {
                    "raw_feedback": "所有页面都改成大标题",
                    "target_refs": [blueprint_ref],
                },
            )
            with self.assertRaises(FeedbackGovernanceError):
                service.create_content_change_set("c1", revision + 1, raw)

            governed = service.govern_feedback(
                "f2",
                revision + 1,
                {
                    "raw_feedback_ref": raw,
                    "feedback_level": "F2",
                    "diagnosis": "局部阅读负担被扩大成整套规则",
                    "scope": "page-family",
                    "counterexamples": ["证据页需要信息密度"],
                    "ai_recommendation": "只调整章节页",
                    "preserve_refs": [blueprint_ref],
                },
            )
            with self.assertRaises(FeedbackGovernanceError):
                service.create_content_change_set("c2", revision + 2, governed)

            decided = service.decide_feedback(
                "f3",
                revision + 2,
                governed,
                "follow-ai-recommendation",
            )
            change = service.create_content_change_set(
                "change-3", revision + 3, decided
            )
            self.assertTrue(change.startswith("artifact://content-change-set/"))
            self.assertEqual(service.kernel.load().revision, revision + 4)


if __name__ == "__main__":
    unittest.main()
