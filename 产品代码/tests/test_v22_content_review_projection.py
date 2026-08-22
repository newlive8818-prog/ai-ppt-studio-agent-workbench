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
from ai_ppt_studio.application.project_status_projection import (
    ProjectStatusProjectionService,
)
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
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_v22_content_repair_loop import build_content


CONTENT_REVIEW_SLIDE_FIELDS = {
    "slide_id",
    "order",
    "section_id",
    "page_task",
    "reading_question",
    "neutral_title",
    "customerJudgment",
    "visible_copy_blocks",
    "material_views",
}
CONTENT_REVIEW_BLOCK_FIELDS = {"block_id", "text"}
CONTENT_REVIEW_MATERIAL_FIELDS = {"material_view_id", "asset_ref"}
CONTENT_REVIEW_FORBIDDEN_FIELDS = {
    "identity",
    "identity_labels",
    "evidence_bindings",
    "analysis_or_proposal_blocks",
    "solution_mapping_refs",
    "previous_relation",
    "next_relation",
    "speaker_notes",
    "reading_quality",
    "source_ref",
    "source_file_name",
    "page_number",
    "region_label",
    "purpose",
    "treatment",
    "evidence_identity",
}


def nested_keys(value) -> set[str]:
    if isinstance(value, list):
        return set().union(*(nested_keys(item) for item in value), set())
    if not isinstance(value, dict):
        return set()
    return set(value) | set().union(*(nested_keys(item) for item in value.values()), set())


def accepted_review(
    kernel: ProjectKernel,
    slide_count: int = 1,
    empty_material_view_orders: frozenset[int] = frozenset(),
):
    blueprint_ref = build_content(
        kernel,
        slide_count=slide_count,
        empty_material_view_orders=empty_material_view_orders,
    )
    blueprint_publication_revision = kernel.load().revision
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
        source_revision=blueprint_publication_revision,
        open_policy="foreground-if-waiting",
    )
    return blueprint_ref, session_ref, session, state


class ContentReviewProjectionTests(unittest.TestCase):
    def test_projection_preserves_mixed_empty_and_non_empty_material_views(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_review(
                kernel,
                slide_count=2,
                empty_material_view_orders=frozenset({2}),
            )

            projection = ContentReviewProjectionService(kernel).project(
                session["review_session_id"]
            )

            self.assertEqual(
                projection["slides"][0]["material_views"],
                [{
                    "material_view_id": "S01-M01",
                    "asset_ref": "review-assets/content/S01-M01.png",
                }],
            )
            self.assertEqual(projection["slides"][1]["material_views"], [])
            self.assertEqual(
                [slide["slide_id"] for slide in projection["slides"]],
                ["S01", "S02"],
            )
            self.assertEqual(
                set(projection["slides"][0]["material_views"][0]),
                CONTENT_REVIEW_MATERIAL_FIELDS,
            )
            self.assertTrue(
                CONTENT_REVIEW_FORBIDDEN_FIELDS.isdisjoint(nested_keys(projection))
            )

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
            self.assertEqual(
                set(projection["slides"][0]), CONTENT_REVIEW_SLIDE_FIELDS
            )
            self.assertEqual(
                set(projection["slides"][0]["visible_copy_blocks"][0]),
                CONTENT_REVIEW_BLOCK_FIELDS,
            )
            self.assertNotIn("customer_decision_item", projection["slides"][0])
            self.assertEqual(
                projection["slides"][0]["material_views"],
                [{
                    "material_view_id": "S01-M01",
                    "asset_ref": "review-assets/content/S01-M01.png",
                }],
            )
            self.assertEqual(
                set(projection["slides"][0]["material_views"][0]),
                CONTENT_REVIEW_MATERIAL_FIELDS,
            )
            self.assertTrue(
                CONTENT_REVIEW_FORBIDDEN_FIELDS.isdisjoint(nested_keys(projection))
            )

            internal_blueprint = kernel.artifacts.resolve(
                ArtifactReference.parse(blueprint_ref)
            )["payload"]
            self.assertTrue(
                {
                    "identity_labels",
                    "evidence_bindings",
                    "analysis_or_proposal_blocks",
                    "speaker_notes",
                    "reading_quality",
                }.issubset(internal_blueprint["slides"][0])
            )
            self.assertTrue(
                {
                    "source_ref",
                    "source_file_name",
                    "page_number",
                    "purpose",
                    "evidence_identity",
                }.issubset(internal_blueprint["slides"][0]["material_views"][0])
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
            self.assertTrue(
                callable(getattr(planning, "confirmation_context", None)),
                "ContentRevisionPlanningService must expose the current trusted confirmation context",
            )
            context = planning.confirmation_context(
                plan_ref=plan_ref,
                source_version="content-v1",
            )
            self.assertEqual(context["scope_kind"], "content-revision-plan")
            self.assertEqual(context["scope_id"], plan_ref)
            self.assertEqual(context["source_version"], "content-v1")
            self.assertEqual(
                context["evidence_refs"],
                [batch_ref, plan_ref, blueprint_ref],
            )
            self.assertEqual(context["challenge_revision"], state.revision)
            consumed_before = len(state.consumed_user_confirmations)
            confirmation_ref, state = planning.confirm_plan(
                command_id="confirm-plan",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                **gate_confirmation_kwargs(
                    context,
                    identity_type="verified-message",
                    identity_ref="chat://message/verified-plan-confirmation",
                ),
            )
            confirmation = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["project_id"], "p1")
            self.assertEqual(confirmation["scope_kind"], "content-revision-plan")
            self.assertEqual(confirmation["scope_id"], plan_ref)
            self.assertEqual(confirmation["source_version"], "content-v1")
            self.assertEqual(confirmation["evidence_refs"], context["evidence_refs"])
            self.assertEqual(confirmation["challenge_id"], context["challenge_id"])
            self.assertEqual(
                confirmation["challenge_revision"], context["challenge_revision"]
            )
            self.assertEqual(confirmation["confirmation_identity_type"], "verified-message")
            self.assertFalse(confirmation["user_action_ref"])
            self.assertEqual(
                confirmation["user_message_ref"],
                "chat://message/verified-plan-confirmation",
            )
            self.assertRegex(confirmation["host_assertion_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(confirmation["plan_ref"], plan_ref)
            self.assertEqual(confirmation["batch_ref"], batch_ref)
            self.assertEqual(confirmation["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(confirmation["status"], "confirmed")
            self.assertIs(confirmation["is_g0"], False)
            self.assertEqual(
                len(state.consumed_user_confirmations), consumed_before + 1
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

    def test_plan_confirmation_rejects_unverified_chat_message_references(self) -> None:
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
            for value in (
                "message-1",
                "chat://thread/1",
                "chat://message/",
                "chat://message/fabricated-plan-confirmation",
            ):
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

    def test_change_set_rechecks_current_blueprint_after_plan_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="approve-for-lineage-check",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit-for-lineage-check",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            planning = ContentRevisionPlanningService(kernel)
            plan_ref, _plan, state = planning.save_plan(
                command_id="plan-for-lineage-check",
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
            context = planning.confirmation_context(
                plan_ref=plan_ref,
                source_version="content-v1",
            )
            confirmation_ref, state = planning.confirm_plan(
                command_id="confirm-for-lineage-check",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                **gate_confirmation_kwargs(context),
            )

            blueprint = kernel.artifacts.resolve(
                ArtifactReference.parse(blueprint_ref)
            )["payload"]
            rewritten_blueprint = {
                **blueprint,
                "slides": [
                    {
                        **slide,
                        "neutral_title": f"{slide['neutral_title']}·rewritten",
                    }
                    for slide in blueprint["slides"]
                ],
            }
            state = kernel.commit(
                command_id="rewrite-blueprint-after-plan-confirmation",
                expected_revision=state.revision,
                event_type="test.reading-blueprint-rewritten",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        rewritten_blueprint,
                    )
                },
            )
            before = kernel.load()

            with self.assertRaises(ContractValidationError):
                planning.create_change_set(
                    command_id="change-set-after-lineage-rewrite",
                    expected_revision=state.revision,
                    plan_ref=plan_ref,
                    confirmation_ref=confirmation_ref,
                    source_version="content-v1",
                )

            self.assertEqual(kernel.load(), before)

    def test_change_set_rejects_confirmation_without_atomic_consumption_binding(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="approve-for-binding-check",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit-for-binding-check",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            planning = ContentRevisionPlanningService(kernel)
            plan_ref, _plan, state = planning.save_plan(
                command_id="plan-for-binding-check",
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
            context = planning.confirmation_context(
                plan_ref=plan_ref,
                source_version="content-v1",
            )
            trusted_ref, state = planning.confirm_plan(
                command_id="confirm-for-binding-check",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                **gate_confirmation_kwargs(context),
            )
            trusted = kernel.artifacts.resolve(
                ArtifactReference.parse(trusted_ref)
            )["payload"]
            forged = {
                **trusted,
                "confirmation_id": "forged-plan-confirmation",
                "user_action_ref": "host-action://forged-plan-confirmation",
                "user_message_ref": "",
                "confirmation_identity_type": "host-action",
                "host_assertion_sha256": "0" * 64,
            }
            state = kernel.commit(
                command_id="install-forged-plan-confirmation",
                expected_revision=state.revision,
                event_type="test.plan-confirmation-forged",
                artifact_updates={
                    "content/revision-plan-confirmation": (
                        "content-batch-revision-plan-confirmation",
                        forged,
                    )
                },
            )
            forged_ref = state.artifact_heads["content/revision-plan-confirmation"]
            before = kernel.load()

            with self.assertRaises(ContractValidationError):
                planning.create_change_set(
                    command_id="change-set-with-forged-confirmation",
                    expected_revision=state.revision,
                    plan_ref=plan_ref,
                    confirmation_ref=forged_ref,
                    source_version="content-v1",
                )

            self.assertEqual(kernel.load(), before)

    def test_confirmed_change_set_application_forces_new_source_full_rereview(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            first_blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="modify-before-application",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment="按确认后的整套方案改写本页并全稿复审。",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit-before-application",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            planning = ContentRevisionPlanningService(kernel)
            plan_ref, _plan, state = planning.save_plan(
                command_id="plan-before-application",
                expected_revision=state.revision,
                batch_ref=batch_ref,
                source_version="content-v1",
                plan={
                    "direct_changes": ["S01"],
                    "cross_slide_changes": [],
                    "merge_or_delete": [],
                    "evidence_downgrades": [],
                    "sequence_changes": [],
                    "preserved": [],
                    "conflicts": [],
                    "rereview_scope": ["all"],
                },
            )
            context = planning.confirmation_context(
                plan_ref=plan_ref,
                source_version="content-v1",
            )
            confirmation_ref, state = planning.confirm_plan(
                command_id="confirm-before-application",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                **gate_confirmation_kwargs(context),
            )
            change_set_ref, _change_set, state = planning.create_change_set(
                command_id="change-set-before-application",
                expected_revision=state.revision,
                plan_ref=plan_ref,
                confirmation_ref=confirmation_ref,
                source_version="content-v1",
            )

            second_blueprint_ref = build_content(kernel, source_version="content-v2")
            second_blueprint_publication_revision = kernel.load().revision
            replaced = kernel.load()
            application_ref = replaced.artifact_heads.get(
                "content/revision-plan-application", ""
            )
            self.assertTrue(
                application_ref.startswith(
                    "artifact://content-batch-revision-plan-application/"
                ),
                "Publishing the replacement blueprint must atomically record the confirmed plan application",
            )
            application = kernel.artifacts.resolve(
                ArtifactReference.parse(application_ref)
            )["payload"]
            self.assertEqual(application["status"], "applied")
            self.assertEqual(application["source_version"], "content-v1")
            self.assertEqual(application["new_source_version"], "content-v2")
            self.assertEqual(application["reading_blueprint_ref"], first_blueprint_ref)
            self.assertEqual(
                application["new_reading_blueprint_ref"], second_blueprint_ref
            )
            self.assertEqual(application["batch_ref"], batch_ref)
            self.assertEqual(application["plan_ref"], plan_ref)
            self.assertEqual(application["confirmation_ref"], confirmation_ref)
            self.assertEqual(application["change_set_ref"], change_set_ref)
            self.assertEqual(application["rereview_scope"], ["all"])
            for stale_slot in (
                "content/review-batch",
                "content/revision-plan",
                "content/revision-plan-confirmation",
                "content/change-set",
                "review/session/content-full-deck",
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
                "content/review/decision/S01",
            ):
                self.assertNotIn(stale_slot, replaced.artifact_heads)
            self.assertNotEqual(first_blueprint_ref, second_blueprint_ref)
            self.assertNotEqual(decision_ref, replaced.artifact_heads.get(
                "content/review/decision/S01", ""
            ))

            gates = ContentHardGateService(kernel)
            gates.run_evidence_gate(
                command_id="evidence-pass-after-application",
                expected_revision=replaced.revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            gates.run_presales_reading_gate(
                command_id="reading-pass-after-application",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            _new_session_ref, new_session, new_state = ReviewSessionService(
                kernel
            ).open_or_resume(
                command_id="open-rereview-after-application",
                expected_revision=kernel.load().revision,
                review_type="content-full-deck",
                target_artifact_ref=second_blueprint_ref,
                source_version="content-v2",
                source_revision=second_blueprint_publication_revision,
                open_policy="foreground-if-waiting",
            )
            with self.assertRaises(GateBlockedError):
                ContentReviewBatchService(kernel).submit(
                    command_id="submit-rereview-without-new-decisions",
                    expected_revision=new_state.revision,
                    review_session_id=new_session["review_session_id"],
                    source_version="content-v2",
                )

    def test_submitted_all_approved_review_requires_trusted_g0_confirmation(self) -> None:
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
                    command_id="confirm-g0-with-fabricated-chat",
                    expected_revision=frozen.revision,
                    user_message_ref="chat://message/fabricated-g0",
                )
            self.assertEqual(kernel.load(), frozen)

            context = service.gate_confirmation_context()
            confirmed = service.confirm_g0(
                command_id="confirm-g0",
                expected_revision=frozen.revision,
                **gate_confirmation_kwargs(context),
            )
            self.assertEqual(confirmed.gate_status["G0"], "passed")
            self.assertEqual(confirmed.gate_status["G1"], "open")
            projected_status = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(projected_status["object_type"], "runtime-task")
            self.assertNotEqual(
                projected_status["reason"], "审核反馈已保存并提交"
            )
            confirmation_ref = confirmed.artifact_heads["gate/G0/confirmation"]
            confirmation = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(confirmation["content_review_batch_ref"], batch_ref)
            self.assertEqual(confirmation["source_version"], "content-v1")
            self.assertEqual(confirmation["challenge_id"], context["challenge_id"])
            self.assertEqual(
                confirmation["challenge_revision"], context["challenge_revision"]
            )
            self.assertEqual(confirmation["confirmation_identity_type"], "host-action")
            self.assertTrue(confirmation["user_action_ref"])
            self.assertFalse(confirmation["user_message_ref"])
            self.assertRegex(confirmation["host_assertion_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(len(confirmed.consumed_user_confirmations), 1)
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

    def test_python_bridge_uses_scoped_confirmation_for_revision_plans(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="bridge-plan-approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="bridge-plan-submit",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            plan_ref, _plan, state = ContentRevisionPlanningService(kernel).save_plan(
                command_id="bridge-plan-save",
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
            operation = "get-content-revision-plan-confirmation-context"
            self.assertIn(
                operation,
                dispatch_v16.__globals__["HANDLERS"],
                "The Python Bridge must expose the current scoped plan confirmation context",
            )
            context_response = dispatch_v16(
                {
                    "operation": operation,
                    "project_root": str(project_root),
                    "plan_ref": plan_ref,
                    "source_version": "content-v1",
                }
            )
            context = context_response["confirmation_context"]
            self.assertEqual(context["scope_kind"], "content-revision-plan")
            self.assertEqual(context["scope_id"], plan_ref)
            confirmed = dispatch_v16(
                {
                    "operation": "confirm-content-batch-revision-plan",
                    "project_root": str(project_root),
                    "command_id": "bridge-plan-confirm",
                    "expected_revision": state.revision,
                    "plan_ref": plan_ref,
                    "source_version": context["source_version"],
                    "challenge_id": context["challenge_id"],
                    "challenge_revision": context["challenge_revision"],
                    "host_confirmation_assertion": gate_confirmation_kwargs(
                        context
                    )["host_confirmation_assertion"],
                    "user_action_ref": "",
                    "user_message_ref": "",
                }
            )
            self.assertTrue(
                confirmed["result"]["confirmation_ref"].startswith(
                    "artifact://content-batch-revision-plan-confirmation/"
                )
            )


if __name__ == "__main__":
    unittest.main()
