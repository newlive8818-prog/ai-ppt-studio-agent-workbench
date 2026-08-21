from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_batch_revision_plan,
)
from ai_ppt_studio.application.content_batch_planning_service import (
    ContentBatchPlanningService,
)
from ai_ppt_studio.application.content_review_service import ContentReviewService
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.errors import (
    ContentWorkflowError,
    ContractValidationError,
    FeedbackGovernanceError,
)
from ai_ppt_studio.domains.feedback.contracts import (
    validate_feedback_governance,
)
from tests.test_v16_content_page_decisions import (
    accept_blueprint,
    resolve_payload,
)
from tests.test_v16_framework_discussion import TEST_SECRET, signed_assertion


def artifact_ref(kind: str, marker: str) -> str:
    return f"artifact://{kind}/{marker * 64}"


def valid_plan(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "plan_id": "plan-v1",
        "plan_version": 1,
        "review_batch_ref": artifact_ref("content-review-batch", "b"),
        "review_batch_id": "batch-v1",
        "source_version": artifact_ref("content-blueprint", "a"),
        "direct_actions": [
            {"slide_ids": ["S02"], "action": "改写结论标题"}
        ],
        "cross_page_actions": [
            {
                "slide_ids": ["S04", "S05"],
                "action": "合并重复建设原则",
            }
        ],
        "merge_delete_actions": [
            {
                "source_slide_ids": ["S08"],
                "target_slide_id": "S07",
                "preserve": "案例证据",
                "remove": "重复背景",
            }
        ],
        "evidence_actions": [
            {
                "slide_ids": ["S11"],
                "action": "降级为待联合验证",
                "required_material": "客户现状截图",
            }
        ],
        "revised_chapters": [
            {
                "chapter_id": "C02",
                "title": "一期路径",
                "slide_ids": ["S06", "S07"],
            }
        ],
        "estimated_slide_count": 11,
        "preserve_items": ["任务目标", "已核验来源事实"],
        "conflicts_and_risks": [
            "删页意见与保留完整案例证据存在冲突"
        ],
        "required_user_decisions": ["确认案例证据合并到 S07"],
        "re_review_scope": "new-blueprint-full-deck",
        "requires_blueprint_revision": True,
        "status": "proposed",
    }
    payload.update(updates)
    return payload


class ContentBatchRevisionPlanContractTests(unittest.TestCase):
    def test_valid_plan_preserves_every_whole_deck_decision(self) -> None:
        payload = valid_plan()
        self.assertEqual(validate_content_batch_revision_plan(payload), payload)

    def test_plan_rejects_missing_categories_wrong_refs_and_partial_review(self) -> None:
        source = valid_plan()
        malformed: list[dict[str, object]] = []
        for field in (
            "direct_actions",
            "cross_page_actions",
            "merge_delete_actions",
            "evidence_actions",
            "revised_chapters",
            "preserve_items",
            "conflicts_and_risks",
            "required_user_decisions",
        ):
            candidate = copy.deepcopy(source)
            candidate.pop(field)
            malformed.append(candidate)
        malformed.extend(
            [
                {**source, "review_batch_ref": artifact_ref("raw-feedback", "b")},
                {**source, "source_version": artifact_ref("slide-draft-set", "a")},
                {**source, "re_review_scope": "affected-pages-only"},
                {**source, "estimated_slide_count": 0},
                {**source, "status": "confirmed"},
                {**source, "unexpected": True},
            ]
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ContractValidationError):
                    validate_content_batch_revision_plan(candidate)

    def test_no_revision_plan_must_have_no_revision_actions(self) -> None:
        no_revision = valid_plan(
            direct_actions=[],
            cross_page_actions=[],
            merge_delete_actions=[],
            evidence_actions=[],
            revised_chapters=[],
            estimated_slide_count=4,
            conflicts_and_risks=[],
            required_user_decisions=[],
            requires_blueprint_revision=False,
        )
        self.assertEqual(
            validate_content_batch_revision_plan(no_revision), no_revision
        )
        with self.assertRaises(ContractValidationError):
            validate_content_batch_revision_plan(
                {**no_revision, "direct_actions": valid_plan()["direct_actions"]}
            )

    def test_batch_governance_requires_complete_confirmed_plan_lineage(self) -> None:
        base = {
            "raw_feedback_ref": artifact_ref("raw-feedback", "1"),
            "feedback_level": "F1",
            "diagnosis": "整套方案已确认",
            "scope": "whole-deck-confirmed-plan",
            "counterexamples": ["不得直接扩大单页意见"],
            "ai_recommendation": "按整套方案修改",
            "preserve_refs": [artifact_ref("content-blueprint", "a")],
        }
        with self.assertRaises(FeedbackGovernanceError):
            validate_feedback_governance(
                {
                    **base,
                    "review_batch_ref": artifact_ref("content-review-batch", "b"),
                }
            )
        complete = {
            **base,
            "review_batch_ref": artifact_ref("content-review-batch", "b"),
            "revision_plan_ref": artifact_ref(
                "content-batch-revision-plan", "c"
            ),
            "plan_confirmation_ref": artifact_ref(
                "content-batch-plan-confirmation", "d"
            ),
            "affected_refs": [artifact_ref("content-page-decision", "e")],
            "full_deck_re_review_route": "new-blueprint-full-deck",
        }
        self.assertEqual(
            validate_feedback_governance(complete)["status"], "executable"
        )


class ContentBatchPlanningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="planning-project"
        )
        self.source_version, self.blueprint = accept_blueprint(
            self.content, slide_count=4
        )
        self.review = ContentReviewService(self.content.kernel)
        self.batch_id = "planning-batch"
        self.env = patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def submit_batch(self, *, all_approved: bool = False) -> str:
        decisions = (
            ("s1", "approved", ""),
            ("s2", "approved" if all_approved else "modify", "" if all_approved else "修改第二页完整意见"),
            ("s3", "approved" if all_approved else "evidence", "" if all_approved else "补充第三页证据"),
            ("s4", "approved" if all_approved else "merge-or-delete", "" if all_approved else "与第三页合并"),
        )
        for slide_id, decision, comment in decisions:
            self.review.save_page_decision(
                command_id=f"save-{slide_id}-{uuid.uuid4()}",
                expected_revision=self.content.kernel.load().revision,
                source_version=self.source_version,
                review_batch_id=self.batch_id,
                slide_id=slide_id,
                decision=decision,
                comment=comment,
            )
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        batch_ref, _follow_up, _state = self.review.submit_review_batch(
            command_id="submit-planning-batch",
            expected_revision=int(context["challenge_revision"]),
            source_version=self.source_version,
            review_batch_id=self.batch_id,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        return batch_ref

    def plan_payload(
        self, batch_ref: str, *, requires_revision: bool = True
    ) -> dict[str, object]:
        if not requires_revision:
            return valid_plan(
                review_batch_ref=batch_ref,
                review_batch_id=self.batch_id,
                source_version=self.source_version,
                direct_actions=[],
                cross_page_actions=[],
                merge_delete_actions=[],
                evidence_actions=[],
                revised_chapters=[],
                estimated_slide_count=4,
                conflicts_and_risks=[],
                required_user_decisions=[],
                requires_blueprint_revision=False,
            )
        return valid_plan(
            review_batch_ref=batch_ref,
            review_batch_id=self.batch_id,
            source_version=self.source_version,
            direct_actions=[{"slide_ids": ["s2"], "action": "修改结论"}],
            cross_page_actions=[
                {"slide_ids": ["s3", "s4"], "action": "联动缺证和删并意见"}
            ],
            merge_delete_actions=[
                {
                    "source_slide_ids": ["s4"],
                    "target_slide_id": "s3",
                    "preserve": "关键证据",
                    "remove": "重复表达",
                }
            ],
            evidence_actions=[
                {
                    "slide_ids": ["s3"],
                    "action": "证据不足时降级",
                    "required_material": "客户材料",
                }
            ],
            revised_chapters=[
                {"chapter_id": "c1", "title": "修订章节", "slide_ids": ["s1", "s2", "s3"]}
            ],
            estimated_slide_count=3,
        )

    def save_and_confirm(
        self, planning: ContentBatchPlanningService, batch_ref: str
    ) -> tuple[str, str]:
        plan_ref, _batch_lifecycle_ref, _state = planning.save_revision_plan(
            command_id="save-plan",
            expected_revision=self.content.kernel.load().revision,
            payload=self.plan_payload(batch_ref),
        )
        context = planning.confirmation_context(
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
        )
        confirmation_ref, _confirmed_batch_ref, _state = (
            planning.confirm_revision_plan(
                command_id="confirm-plan",
                expected_revision=int(context["challenge_revision"]),
                review_batch_id=self.batch_id,
                plan_ref=plan_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )
        )
        return plan_ref, confirmation_ref

    def test_save_plan_binds_current_batch_and_changes_only_plan_lifecycle(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        before = self.content.kernel.load()
        plan_ref, lifecycle_ref, after = planning.save_revision_plan(
            command_id="save-plan",
            expected_revision=before.revision,
            payload=self.plan_payload(batch_ref),
        )
        self.assertEqual(after.artifact_heads["content/batch-revision-plan"], plan_ref)
        self.assertEqual(after.artifact_heads["content/review-batch"], lifecycle_ref)
        lifecycle = resolve_payload(self.content, lifecycle_ref)
        submitted = resolve_payload(self.content, batch_ref)
        self.assertEqual(lifecycle["status"], "plan-proposed")
        self.assertEqual(lifecycle["decision_refs"], submitted["decision_refs"])
        self.assertEqual(lifecycle["counts"], submitted["counts"])
        self.assertNotIn("feedback/governance", after.artifact_heads)
        self.assertNotIn("content/change-set", after.artifact_heads)
        self.assertEqual(before.gate_status, after.gate_status)

    def test_save_plan_exact_replay_is_idempotent_and_changed_replay_conflicts(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        initial_revision = self.content.kernel.load().revision
        first = planning.save_revision_plan(
            command_id="save-plan-replay",
            expected_revision=initial_revision,
            payload=self.plan_payload(batch_ref),
        )
        replay = planning.save_revision_plan(
            command_id="save-plan-replay",
            expected_revision=initial_revision,
            payload=self.plan_payload(batch_ref),
        )
        self.assertEqual(replay[0], first[0])
        self.assertEqual(replay[1], first[1])
        self.assertEqual(replay[2].revision, first[2].revision)
        with self.assertRaises(ContractValidationError):
            planning.save_revision_plan(
                command_id="save-plan-replay",
                expected_revision=initial_revision,
                payload={
                    **self.plan_payload(batch_ref),
                    "estimated_slide_count": 2,
                },
            )

    def test_save_plan_rejects_wrong_batch_or_source_without_writes(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        before = self.content.kernel.load()
        for candidate in (
            {
                **self.plan_payload(batch_ref),
                "review_batch_ref": artifact_ref("content-review-batch", "9"),
            },
            {
                **self.plan_payload(batch_ref),
                "source_version": artifact_ref("content-blueprint", "9"),
            },
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ContentWorkflowError):
                    planning.save_revision_plan(
                        command_id=f"wrong-plan-{uuid.uuid4()}",
                        expected_revision=before.revision,
                        payload=candidate,
                    )
                self.assertEqual(self.content.kernel.load(), before)

    def test_save_plan_rejects_actions_for_pages_outside_current_blueprint(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        before = self.content.kernel.load()
        candidate = self.plan_payload(batch_ref)
        candidate["direct_actions"] = [
            {"slide_ids": ["missing-slide"], "action": "不能修改不存在的页面"}
        ]
        with self.assertRaises(ContentWorkflowError) as caught:
            planning.save_revision_plan(
                command_id="plan-with-missing-slide",
                expected_revision=before.revision,
                payload=candidate,
            )
        self.assertEqual(caught.exception.code, "CONTENT_BATCH_PLAN_SLIDE_UNKNOWN")
        self.assertEqual(self.content.kernel.load(), before)

    def test_confirm_plan_has_independent_scope_and_no_gate_or_change_set(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        plan_ref, _batch_ref, _state = planning.save_revision_plan(
            command_id="save-plan",
            expected_revision=self.content.kernel.load().revision,
            payload=self.plan_payload(batch_ref),
        )
        context = planning.confirmation_context(
            review_batch_id=self.batch_id, plan_ref=plan_ref
        )
        self.assertEqual(context["scope_kind"], "content-batch-plan-confirmation")
        self.assertEqual(context["source_version"], plan_ref)
        self.assertEqual(context["evidence_refs"], [batch_ref, self.source_version, plan_ref])
        before_gates = dict(self.content.kernel.load().gate_status)
        confirmation_ref, confirmed_batch_ref, state = planning.confirm_revision_plan(
            command_id="confirm-plan",
            expected_revision=int(context["challenge_revision"]),
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        self.assertEqual(state.artifact_heads["content/batch-plan-confirmation"], confirmation_ref)
        self.assertEqual(resolve_payload(self.content, confirmed_batch_ref)["status"], "plan-confirmed")
        self.assertEqual(state.gate_status, before_gates)
        self.assertNotIn("content/change-set", state.artifact_heads)

    def test_confirmation_rejects_cross_scope_assertion_and_exact_replay_is_idempotent(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        plan_ref, _batch_ref, _state = planning.save_revision_plan(
            command_id="save-plan-for-replay",
            expected_revision=self.content.kernel.load().revision,
            payload=self.plan_payload(batch_ref),
        )
        context = planning.confirmation_context(
            review_batch_id=self.batch_id, plan_ref=plan_ref
        )
        before = self.content.kernel.load()
        with self.assertRaises(ContentWorkflowError):
            planning.confirm_revision_plan(
                command_id="confirm-wrong-scope",
                expected_revision=before.revision,
                review_batch_id=self.batch_id,
                plan_ref=plan_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    context, overrides={"scope_kind": "content-review-batch-submission"}
                ),
            )
        self.assertEqual(self.content.kernel.load(), before)

        assertion = signed_assertion(context)
        first = planning.confirm_revision_plan(
            command_id="confirm-plan-replay",
            expected_revision=before.revision,
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=assertion,
        )
        replay = planning.confirm_revision_plan(
            command_id="confirm-plan-replay",
            expected_revision=before.revision,
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=assertion,
        )
        self.assertEqual(replay[0], first[0])
        self.assertEqual(replay[1], first[1])
        self.assertEqual(replay[2].revision, first[2].revision)

    def test_confirmed_plan_atomically_creates_governance_and_lineaged_change_set(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        plan_ref, confirmation_ref = self.save_and_confirm(planning, batch_ref)
        governance_ref, change_set_ref, state = planning.create_governance_and_change_set(
            command_id="create-governed-change-set",
            expected_revision=self.content.kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
        )
        governance = resolve_payload(self.content, governance_ref)
        change_set = resolve_payload(self.content, change_set_ref)
        raw = resolve_payload(self.content, governance["raw_feedback_ref"])
        submitted = resolve_payload(self.content, batch_ref)
        decisions = [resolve_payload(self.content, ref) for ref in submitted["decision_refs"]]
        self.assertEqual(
            raw["page_decisions"],
            [
                {"decision_ref": ref, "decision": row["decision"], "comment": row["comment"]}
                for ref, row in zip(submitted["decision_refs"], decisions)
            ],
        )
        self.assertEqual(governance["status"], "executable")
        self.assertEqual(change_set["review_batch_ref"], batch_ref)
        self.assertEqual(change_set["revision_plan_ref"], plan_ref)
        self.assertEqual(change_set["plan_confirmation_ref"], confirmation_ref)
        self.assertEqual(change_set["source_blueprint_ref"], self.source_version)
        self.assertEqual(change_set["review_route"], "new-blueprint-full-deck")
        self.assertEqual(state.artifact_heads["feedback/governance"], governance_ref)
        self.assertEqual(state.artifact_heads["content/change-set"], change_set_ref)

        with self.assertRaises(ContentWorkflowError) as caught:
            self.content.create_content_change_set(
                "bypass-plan-confirmation",
                state.revision,
                governance_ref,
            )
        self.assertEqual(caught.exception.code, "CONTENT_BATCH_PLAN_NOT_CONFIRMED")

        direct_ref = self.content.create_content_change_set(
            "direct-with-current-confirmation",
            state.revision,
            governance_ref,
            confirmation_ref,
        )
        direct = resolve_payload(self.content, direct_ref)
        self.assertEqual(direct["review_batch_ref"], batch_ref)
        self.assertEqual(direct["revision_plan_ref"], plan_ref)
        self.assertEqual(direct["plan_confirmation_ref"], confirmation_ref)
        self.assertEqual(direct["source_blueprint_ref"], self.source_version)
        self.assertEqual(direct["review_route"], "new-blueprint-full-deck")

    def test_corrupt_plan_confirmation_lineage_fails_closed(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        _plan_ref, confirmation_ref = self.save_and_confirm(planning, batch_ref)
        corrupted = resolve_payload(self.content, confirmation_ref)
        corrupted["host_assertion_sha256"] = "3" * 64
        state = self.content.kernel.load()
        self.content.kernel.commit(
            command_id="inject-corrupt-plan-confirmation",
            expected_revision=state.revision,
            event_type="test.corrupt-plan-confirmation",
            artifact_updates={
                "content/batch-plan-confirmation": (
                    "content-batch-plan-confirmation",
                    corrupted,
                )
            },
        )
        corrupt_ref = self.content.kernel.load().artifact_heads[
            "content/batch-plan-confirmation"
        ]
        before = self.content.kernel.load()
        with self.assertRaises(ContentWorkflowError) as caught:
            planning.create_governance_and_change_set(
                command_id="reject-corrupt-confirmation",
                expected_revision=before.revision,
                plan_confirmation_ref=corrupt_ref,
            )
        self.assertEqual(caught.exception.code, "CONTENT_BATCH_PLAN_NOT_CONFIRMED")
        self.assertEqual(self.content.kernel.load(), before)

    def test_no_revision_path_requires_all_approved_and_leaves_blueprint_unchanged(self) -> None:
        batch_ref = self.submit_batch(all_approved=True)
        planning = ContentBatchPlanningService(self.content.kernel)
        plan_ref, _batch_ref, _state = planning.save_revision_plan(
            command_id="save-no-revision-plan",
            expected_revision=self.content.kernel.load().revision,
            payload=self.plan_payload(batch_ref, requires_revision=False),
        )
        context = planning.confirmation_context(
            review_batch_id=self.batch_id, plan_ref=plan_ref
        )
        confirmation_ref, _confirmed_batch_ref, _state = planning.confirm_revision_plan(
            command_id="confirm-no-revision-plan",
            expected_revision=int(context["challenge_revision"]),
            review_batch_id=self.batch_id,
            plan_ref=plan_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        applied_ref, state = planning.apply_no_revision_plan(
            command_id="apply-no-revision-plan",
            expected_revision=self.content.kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
        )
        self.assertEqual(resolve_payload(self.content, applied_ref)["status"], "applied")
        self.assertEqual(state.artifact_heads["content/blueprint"], self.source_version)
        self.assertNotIn("feedback/governance", state.artifact_heads)
        self.assertNotIn("content/change-set", state.artifact_heads)

    def test_no_revision_plan_rejects_any_non_approved_decision(self) -> None:
        batch_ref = self.submit_batch()
        planning = ContentBatchPlanningService(self.content.kernel)
        with self.assertRaises(ContentWorkflowError) as caught:
            planning.save_revision_plan(
                command_id="save-invalid-no-revision-plan",
                expected_revision=self.content.kernel.load().revision,
                payload=self.plan_payload(batch_ref, requires_revision=False),
            )
        self.assertEqual(caught.exception.code, "CONTENT_BATCH_REVISION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
