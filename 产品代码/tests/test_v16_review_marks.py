from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.review_service import ReviewService
from ai_ppt_studio.errors import (
    ContractValidationError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from tests.test_v16_content_acceptance import register_reviews
from tests.test_v16_content_chain import build_ready_draft


def accepted_content(service: ContentService, slide_count: int = 1) -> tuple[int, str]:
    revision, draft_ref, _refs = build_ready_draft(service, slide_count)
    revision = register_reviews(service, revision, draft_ref)
    result = service.accept_content("accept", revision)
    return result.state.revision, result.blueprint_ref


def valid_marks() -> list[dict[str, str]]:
    return [
        {
            "mark_id": "m1",
            "field_anchor": "slide-s1-visible-copy",
            "exact_text": "三条断点",
            "prefix": "五套系统",
            "suffix": "",
            "comment": "补充来源",
        }
    ]


class V16ReviewMarkTests(unittest.TestCase):
    def test_projection_is_complete_and_marks_never_confirm_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            reviewer = ReviewService(service.kernel)
            review = reviewer.content_projection()
            text = json.dumps(review, ensure_ascii=False)
            for literal in ("五套系统", "三条断点", "解释来源"):
                self.assertIn(literal, text)
            self.assertNotIn("…", text)
            self.assertEqual(review["source_version"], blueprint_ref)
            self.assertEqual(review["revision"], revision)
            self.assertEqual(review["project_name"], "经营一体化方案")
            self.assertTrue(review["title"])
            self.assertEqual(review["source_refs"], [blueprint_ref])
            self.assertEqual(
                review["gate_status"],
                {"G0": "user-reviewable"},
            )

            saved = reviewer.save_marks(
                command_id="marks",
                expected_revision=revision,
                source_version=blueprint_ref,
                marks=valid_marks(),
            )
            self.assertEqual(saved.gate_status["G0"], "user-reviewable")
            refreshed = reviewer.content_projection()
            self.assertEqual(refreshed["mark_set"]["status"], "pending-governance")
            self.assertEqual(refreshed["mark_set"]["marks"], valid_marks())

    def test_stale_source_or_revision_preserves_previous_mark_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            reviewer = ReviewService(service.kernel)
            before = service.kernel.load().artifact_heads.get(
                "review-marks/content"
            )
            with self.assertRaises(ReviewSourceStaleError):
                reviewer.save_marks(
                    command_id="stale",
                    expected_revision=revision,
                    source_version=(
                        "artifact://content-blueprint/" + "f" * 64
                    ),
                    marks=valid_marks(),
                )
            self.assertEqual(
                service.kernel.load().artifact_heads.get("review-marks/content"),
                before,
            )

            saved = reviewer.save_marks(
                command_id="valid",
                expected_revision=revision,
                source_version=blueprint_ref,
                marks=valid_marks(),
            )
            head = saved.artifact_heads["review-marks/content"]
            with self.assertRaises(RevisionConflictError):
                reviewer.save_marks(
                    command_id="conflict",
                    expected_revision=revision,
                    source_version=blueprint_ref,
                    marks=[{**valid_marks()[0], "comment": "冲突意见"}],
                )
            self.assertEqual(
                service.kernel.load().artifact_heads["review-marks/content"], head
            )

    def test_duplicate_exact_text_requires_context_that_selects_one_occurrence(self) -> None:
        projection = {
            "sections": [
                {
                    "anchor": "slide-s1",
                    "fields": [
                        {
                            "anchor": "slide-s1-visible-copy",
                            "label": "visible_copy",
                            "value": "第一处 三条断点 中间 第二处 三条断点 结束",
                        }
                    ],
                }
            ]
        }
        intended = {
            "mark_id": "duplicate-2",
            "field_anchor": "slide-s1-visible-copy",
            "exact_text": "三条断点",
            "prefix": "中间 第二处 ",
            "suffix": " 结束",
            "comment": "标记第二处",
        }
        self.assertEqual(
            ReviewService._normalize_marks([intended], projection), [intended]
        )
        with self.assertRaisesRegex(ContractValidationError, "context"):
            ReviewService._normalize_marks(
                [{**intended, "prefix": "", "suffix": ""}], projection
            )


if __name__ == "__main__":
    unittest.main()
