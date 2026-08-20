from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
from ai_ppt_studio.application.content_review.planning_service import ContentRevisionPlanningService
from ai_ppt_studio.application.content_review.projection_service import ContentReviewProjectionService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import (
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_repair_loop import build_content


def accepted_review(kernel: ProjectKernel, slide_count: int = 1):
    blueprint_ref = build_content(kernel, slide_count=slide_count)
    gates = ContentHardGateService(kernel)
    gates.run_evidence_gate(
        command_id="evidence-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    gates.run_presales_reading_gate(
        command_id="reading-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    state = kernel.load()
    session_ref, session, state = ReviewSessionService(kernel).open_or_resume(
        command_id="open-review",
        expected_revision=state.revision,
        review_type="content-full-deck",
        target_artifact_ref=blueprint_ref,
        source_version="content-v1",
        source_revision=state.revision,
        open_policy="foreground-if-waiting",
    )
    return blueprint_ref, session_ref, session, state


class ContentReviewProjectionTests(unittest.TestCase):
    def test_projection_requires_current_acceptance_and_source_bound_session(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            projection = ContentReviewProjectionService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(projection["review_session_id"], session["review_session_id"])
            self.assertEqual(projection["source_version"], "content-v1")
            self.assertEqual(projection["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(projection["slides"][0]["neutral_title"], "当前流程断点与证据边界")
            self.assertEqual(
                projection["slides"][0]["customerJudgment"],
                "客户确认现状边界后，再判断是否进入联合方案验证。",
            )
            self.assertNotIn("customer_decision_item", projection["slides"][0])
            self.assertEqual(
                projection["slides"][0]["material_views"],
                [{
                    "material_view_id": "S01-M01",
                    "source_ref": "artifact://material-finding/" + "a" * 64,
                    "asset_ref": "review-assets/content/S01-M01.png",
                    "source_file_name": "客户现状材料.pptx",
                    "page_number": 3,
                    "region_label": "整页",
                    "purpose": "证明当前流程断点",
                    "treatment": "原页只读呈现",
                    "evidence_identity": "来源事实",
                }],
            )
            self.assertNotIn("desired_customer_judgment", projection["slides"][0])
            self.assertNotIn("desiredCustomerJudgment", projection["slides"][0])
            self.assertNotIn("customer_judgment", projection["slides"][0])
            self.assertNotIn("framework", str(projection).lower())

            state = kernel.load()
            kernel.commit(
                command_id="remove-acceptance",
                expected_revision=state.revision,
                event_type="test.acceptance-removed",
                artifact_updates={},
                artifact_removals=("content/acceptance",),
            )
            with self.assertRaises(GateBlockedError):
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )

    def test_decision_is_closed_unicode_bounded_and_conflict_safe(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            service = ContentDecisionService(kernel)
            frozen_heads = dict(state.artifact_heads)
            frozen_revision = state.revision
            for decision in ("unknown", ""):
                with self.subTest(decision=decision), self.assertRaises(
                    ContractValidationError
                ):
                    service.save(
                        command_id=f"invalid-{decision or 'empty'}",
                        expected_revision=frozen_revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                        slide_id="S01",
                        decision=decision,
                        comment="意见",
                    )
            with self.assertRaises(ContractValidationError):
                service.save(
                    command_id="too-long",
                    expected_revision=frozen_revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="modify",
                    comment="意" * 1201,
                )
            with self.assertRaises(ReviewSourceStaleError):
                service.save(
                    command_id="stale-source",
                    expected_revision=frozen_revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v0",
                    slide_id="S01",
                    decision="modify",
                    comment="保留草稿，不写入",
                )
            self.assertEqual(kernel.load().revision, frozen_revision)
            self.assertEqual(kernel.load().artifact_heads, frozen_heads)

            decision_ref, decision, committed = service.save(
                command_id="save-unicode-boundary",
                expected_revision=frozen_revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment=" 意" * 600,
            )
            self.assertEqual(len(decision["comment"]), 1199)
            self.assertEqual(decision["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(committed.gate_status, state.gate_status)
            self.assertEqual(
                committed.artifact_heads["content/reading-blueprint"], blueprint_ref
            )
            replay_ref, replay, replay_state = service.save(
                command_id="save-unicode-boundary",
                expected_revision=frozen_revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment=" 意" * 600,
            )
            self.assertEqual((replay_ref, replay), (decision_ref, decision))
            self.assertEqual(replay_state.revision, committed.revision)
            with self.assertRaises(RevisionConflictError):
                service.save(
                    command_id="stale-revision",
                    expected_revision=frozen_revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="approved",
                    comment="",
                )

    def test_page_decision_batch_and_plan_are_separate_atomic_steps(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            decisions = ContentDecisionService(kernel)
            with self.assertRaises(ContractValidationError):
                decisions.save(
                    command_id="invalid-comment",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="modify",
                    comment="   ",
                )
            with self.assertRaises(GateBlockedError):
                ContentReviewBatchService(kernel).submit(
                    command_id="incomplete",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )

            _decision_ref, decision, state = decisions.save(
                command_id="approve-s01",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            self.assertEqual(decision["status"], "completed")
            self.assertEqual(state.gate_status["G0"], "locked")

            batch_ref, batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit-batch",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertTrue(batch["immutable_after_submit"])
            self.assertEqual(batch["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(state.gate_status["G0"], "locked")
            self.assertEqual(
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )["batch"]["status"],
                "submitted",
            )

            planning = ContentRevisionPlanningService(kernel)
            plan_ref, _plan, state = planning.save_plan(
                command_id="save-plan",
                expected_revision=state.revision,
                batch_ref=batch_ref,
                source_version="content-v1",
                plan={
                    "direct_changes": [],
                    "cross_slide_changes": [],
                    "merge_or_delete": [],
                    "evidence_downgrades": [],
                    "sequence_changes": [],
                    "preserved": ["S01"],
                    "conflicts": [],
                    "rereview_scope": ["all"],
                },
            )
            confirmation_ref, state = planning.confirm_plan(
                command_id="confirm-plan",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                source_version="content-v1",
                user_message_ref="chat://message/plan-confirmed",
            )
            change_ref, change, _state = planning.create_change_set(
                command_id="change-set",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                confirmation_ref=confirmation_ref,
                source_version="content-v1",
            )
            self.assertTrue(change_ref.startswith("artifact://content-change-set/"))
            self.assertEqual(change["status"], "ready")

    def test_plan_confirmation_requires_a_real_chat_message_reference(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            planning = ContentRevisionPlanningService(kernel)
            plan_ref, _plan, state = planning.save_plan(
                command_id="plan",
                expected_revision=state.revision,
                batch_ref=batch_ref,
                source_version="content-v1",
                plan={
                    "direct_changes": [],
                    "cross_slide_changes": [],
                    "merge_or_delete": [],
                    "evidence_downgrades": [],
                    "sequence_changes": [],
                    "preserved": ["S01"],
                    "conflicts": [],
                    "rereview_scope": ["all"],
                },
            )
            before = kernel.load()
            for value in ("message-1", "chat://thread/1", "chat://message/"):
                with self.subTest(value=value), self.assertRaises(
                    ContractValidationError
                ):
                    planning.confirm_plan(
                        command_id=f"invalid-confirm-{value}",
                        expected_revision=state.revision,
                        plan_ref=plan_ref,
                        source_version="content-v1",
                        user_message_ref=value,
                    )
            self.assertEqual(kernel.load(), before)

    def test_submitted_all_approved_review_opens_g0_and_chat_confirms_it(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            service = PresalesContentService(kernel)
            with self.assertRaises(GateBlockedError):
                service.open_g0_review(
                    command_id="open-g0-too-early",
                    expected_revision=kernel.load().revision,
                )

            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="approve-for-g0",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit-for-g0",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            state = service.open_g0_review(
                command_id="open-g0",
                expected_revision=state.revision,
            )
            self.assertEqual(state.gate_status["G0"], "user-reviewable")

            frozen = kernel.load()
            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    command_id="confirm-g0-without-chat",
                    expected_revision=frozen.revision,
                    user_message_ref="review://batch/approved",
                )
            self.assertEqual(kernel.load(), frozen)

            confirmed = service.confirm_g0(
                command_id="confirm-g0",
                expected_revision=frozen.revision,
                user_message_ref="chat://message/g0-confirmed",
            )
            self.assertEqual(confirmed.gate_status["G0"], "passed")
            self.assertEqual(confirmed.gate_status["G1"], "open")
            confirmation_ref = confirmed.artifact_heads["gate/G0/confirmation"]
            confirmation = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(confirmation["content_review_batch_ref"], batch_ref)
            self.assertNotIn("content_blueprint_ref", confirmation)

    def test_python_bridge_exposes_only_the_exact_content_review_operations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            projected = dispatch_v16(
                {
                    "operation": "get-content-review-projection",
                    "project_root": str(project_root),
                    "review_session_id": session["review_session_id"],
                }
            )
            self.assertEqual(
                projected["review"]["review_type"], "content-full-deck"
            )
            self.assertEqual(
                projected["review"]["slides"][0]["customerJudgment"],
                "客户确认现状边界后，再判断是否进入联合方案验证。",
            )
            saved = dispatch_v16(
                {
                    "operation": "save-content-page-decision",
                    "project_root": str(project_root),
                    "expected_revision": state.revision,
                    "review_session_id": session["review_session_id"],
                    "source_version": "content-v1",
                    "slide_id": "S01",
                    "decision": "approved",
                    "comment": "",
                }
            )
            self.assertEqual(saved["result"]["decision"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
