from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.feedback_service import FeedbackService
from ai_ppt_studio.errors import FeedbackGovernanceError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class V16FeedbackGovernanceTests(unittest.TestCase):
    def test_raw_feedback_cannot_become_change_set_and_f2_requires_decision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            state = kernel.commit(
                command_id="seed-blueprint",
                expected_revision=0,
                event_type="test.blueprint-seeded",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        {"source_version": "content-v1"},
                    )
                },
            )
            blueprint_ref = state.artifact_heads["content/reading-blueprint"]
            service = FeedbackService(kernel)
            raw = service.capture(
                "f1",
                state.revision,
                {
                    "raw_feedback": "所有页面都改成大标题",
                    "target_refs": [blueprint_ref],
                },
            )
            with self.assertRaises(FeedbackGovernanceError):
                service.create_content_change_set("c1", kernel.load().revision, raw)

            governed = service.govern(
                "f2",
                kernel.load().revision,
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
                service.create_content_change_set("c2", kernel.load().revision, governed)

            decided = service.decide(
                "f3",
                kernel.load().revision,
                governed,
                "follow-ai-recommendation",
            )
            change = service.create_content_change_set(
                "change-3", kernel.load().revision, decided
            )
            self.assertTrue(change.startswith("artifact://content-change-set/"))
            self.assertEqual(kernel.load().revision, 5)


if __name__ == "__main__":
    unittest.main()
