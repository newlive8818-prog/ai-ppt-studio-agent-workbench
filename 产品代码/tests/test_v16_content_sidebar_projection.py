from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_batch_planning_service import (
    ContentBatchPlanningService,
)
from ai_ppt_studio.application.content_review_service import (
    CONTENT_SIDEBAR_PHASES,
    ContentReviewService,
)
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_framework_discussion import TEST_SECRET, signed_assertion
from tests.test_v16_review_marks import accepted_content


FORBIDDEN_FRAMEWORK_KEYS = {
    "slides",
    "slide_titles",
    "speaker_notes",
    "evidence_items",
}


def keys_at_any_depth(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for item in value.values():
            keys.update(keys_at_any_depth(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(keys_at_any_depth(item))
    return keys


def resolve(service: ContentService, reference: str) -> dict:
    return service.kernel.artifacts.resolve(
        ArtifactReference.parse(reference)
    )["payload"]


class ContentSidebarProgressProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="sidebar-progress"
        )
        draft_ref = self.content.save_mission_draft(
            "sidebar-mission",
            0,
            {
                "topic": "经营一体化方案",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准一期联合验证",
            },
        )
        self.mission_confirmation_ref = self.content.confirm_mission(
            "sidebar-confirm-mission",
            1,
            mission_draft_ref=draft_ref,
            material_mode="no-materials-confirmed",
            material_inventory_ref="",
            user_action_ref="test-user-action://sidebar-mission",
            user_message_ref="",
        )
        self.review = ContentReviewService(self.content.kernel)
        self.env = patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def assert_no_page_data(self, projection: dict) -> None:
        self.assertTrue(
            FORBIDDEN_FRAMEWORK_KEYS.isdisjoint(
                keys_at_any_depth(projection)
            )
        )

    def test_current_phase_vocabulary_and_production_state_never_leak_page_data(self) -> None:
        self.assertEqual(
            CONTENT_SIDEBAR_PHASES,
            (
                "content-producing",
                "content-hard-gate-review",
                "full-deck-review-ready",
                "review-batch-submitted",
                "batch-plan-proposed",
                "batch-plan-confirmed",
            ),
        )
        producing = self.review.content_sidebar_projection()
        self.assertEqual(producing["display_policy"], "content-sidebar-progress")
        self.assertEqual(producing["phase"], "content-producing")
        self.assertEqual(
            producing["next_action"], "continue-content-production"
        )
        self.assertNotIn("framework", producing)
        self.assert_no_page_data(producing)


class ContentSidebarFullDeckProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="sidebar-full-deck"
        )
        _revision, self.source = accepted_content(
            self.content, slide_count=3
        )
        self.blueprint = resolve(self.content, self.source)
        self.slide_ids = [
            slide["slide_id"] for slide in self.blueprint["slides"]
        ]
        self.review = ContentReviewService(self.content.kernel)
        self.batch_id = "sidebar-review-batch"
        self.env = patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def save(
        self, slide_id: str, decision: str, comment: str = ""
    ) -> dict:
        page, _progress, _state = self.review.save_page_decision(
            command_id=f"sidebar-save-{slide_id}-{decision}",
            expected_revision=self.content.kernel.load().revision,
            source_version=self.source,
            review_batch_id=self.batch_id,
            slide_id=slide_id,
            decision=decision,
            comment=comment,
        )
        return page

    def test_review_ready_projection_copies_every_complete_slide_without_truncation(self) -> None:
        projection = self.review.content_sidebar_projection()
        self.assertEqual(projection["phase"], "full-deck-review-ready")
        self.assertEqual(projection["display_policy"], "content-sidebar-full-deck")
        self.assertEqual(projection["source_version"], self.source)
        self.assertEqual(len(projection["slides"]), 3)
        self.assertNotIn("framework", projection)
        self.assertNotIn("desired_judgment_or_action", projection["mission_summary"])
        for source_slide, projected_slide in zip(
            self.blueprint["slides"], projection["slides"]
        ):
            decision_state = projected_slide["decision_state"]
            self.assertEqual(
                projected_slide["neutral_title"], source_slide["title"]
            )
            self.assertEqual(
                projected_slide["page_task"], source_slide["page_purpose"]
            )
            self.assertEqual(
                projected_slide["reading_question"],
                source_slide["user_judgment_prompt"],
            )
            self.assertEqual(
                projected_slide["visible_copy"], source_slide["visible_copy"]
            )
            self.assertNotIn("core_claim", projected_slide)
            self.assertNotIn("user_judgment_prompt", projected_slide)
            self.assertEqual(
                decision_state,
                {
                    "selected": "",
                    "comment": "",
                    "completed": False,
                    "saved": False,
                    "frozen": False,
                },
            )
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertIn("五套系统", serialized)
        self.assertIn("解释来源", serialized)
        self.assertNotIn("…", serialized)
        self.assertNotIn("核心主张", serialized)
        self.assertEqual(
            projection["review_progress"],
            {
                "total": 3,
                "completed": 0,
                "remaining": 3,
                "saved_comment_count": 0,
                "next_incomplete_slide_id": self.slide_ids[0],
                "counts": {
                    "approved": 0,
                    "modify": 0,
                    "evidence": 0,
                    "merge_or_delete": 0,
                },
            },
        )

    def test_saved_decisions_and_batch_plan_phases_project_authoritative_state(self) -> None:
        first = self.save(self.slide_ids[0], "modify", "保留完整修改意见")
        self.save(self.slide_ids[1], "approved")
        self.save(self.slide_ids[2], "approved")
        review_ready = self.review.content_sidebar_projection()
        self.assertEqual(review_ready["phase"], "full-deck-review-ready")
        self.assertEqual(
            review_ready["slides"][0]["decision_state"],
            {
                "selected": "modify",
                "comment": "保留完整修改意见",
                "completed": True,
                "saved": True,
                "frozen": False,
            },
        )
        self.assertEqual(
            review_ready["slides"][0]["decision_state"]["comment"],
            resolve(self.content, first["page_decision_ref"])["comment"],
        )

        submission = self.review.submission_context(
            source_version=self.source,
            review_batch_id=self.batch_id,
        )
        batch_ref, _follow_up, _state = self.review.submit_review_batch(
            command_id="sidebar-submit-batch",
            expected_revision=int(submission["challenge_revision"]),
            source_version=self.source,
            review_batch_id=self.batch_id,
            challenge_id=str(submission["challenge_id"]),
            challenge_revision=int(submission["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(submission),
        )
        submitted = self.review.content_sidebar_projection()
        self.assertEqual(submitted["phase"], "review-batch-submitted")
        self.assertEqual(submitted["current_batch"]["status"], "submitted")
        self.assertTrue(submitted["slides"][0]["decision_state"]["frozen"])

        planning = ContentBatchPlanningService(self.content.kernel)
        plan_ref, _lifecycle_ref, _state = planning.save_revision_plan(
            command_id="sidebar-save-plan",
            expected_revision=self.content.kernel.load().revision,
            payload={
                "plan_id": "sidebar-plan",
                "plan_version": 1,
                "review_batch_ref": batch_ref,
                "review_batch_id": self.batch_id,
                "source_version": self.source,
                "direct_actions": [
                    {
                        "slide_ids": [self.slide_ids[0]],
                        "action": "按意见改写第一页",
                    }
                ],
                "cross_page_actions": [],
                "merge_delete_actions": [],
                "evidence_actions": [],
                "revised_chapters": [],
                "estimated_slide_count": 3,
                "preserve_items": ["第二页和第三页"],
                "conflicts_and_risks": [],
                "required_user_decisions": [],
                "re_review_scope": "new-blueprint-full-deck",
                "requires_blueprint_revision": True,
                "status": "proposed",
            },
        )
        proposed = self.review.content_sidebar_projection()
        self.assertEqual(proposed["phase"], "batch-plan-proposed")
        self.assertEqual(proposed["current_plan"]["plan_ref"], plan_ref)

        plan_context = planning.confirmation_context(
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
        )
        confirmation_ref, _lifecycle_ref, _state = planning.confirm_revision_plan(
            command_id="sidebar-confirm-plan",
            expected_revision=int(plan_context["challenge_revision"]),
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
            challenge_id=str(plan_context["challenge_id"]),
            challenge_revision=int(plan_context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(plan_context),
        )
        confirmed = self.review.content_sidebar_projection()
        self.assertEqual(confirmed["phase"], "batch-plan-confirmed")
        self.assertEqual(
            confirmed["current_plan"]["confirmation_ref"], confirmation_ref
        )
        self.assertEqual(confirmed["current_batch"]["status"], "plan-confirmed")


if __name__ == "__main__":
    unittest.main()
