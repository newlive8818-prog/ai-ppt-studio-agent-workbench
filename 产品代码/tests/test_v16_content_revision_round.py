from __future__ import annotations

import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_batch_planning_service import (
    ContentBatchPlanningService,
)
from ai_ppt_studio.application.content_review_service import ContentReviewService
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_review_batch,
)
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from tests.test_v16_content_acceptance import review_payload
from tests.test_v16_content_page_decisions import (
    accept_blueprint,
    resolve_payload,
)
from tests.test_v16_framework_discussion import TEST_SECRET, signed_assertion
from tests.v16_content_fixtures import (
    complete_slide_draft_payload,
    publish_content_review,
    publish_content_stage,
)


class ContentRevisionRoundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="revision-round-project"
        )
        self.v1_ref, self.v1 = accept_blueprint(self.content, slide_count=4)
        self.review = ContentReviewService(self.content.kernel)
        self.batch_id = "revision-round-v1"
        self.env = patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def submit_batch(self, *, all_approved: bool, batch_id: str) -> str:
        choices = (
            ("s1", "approved", ""),
            ("s2", "approved" if all_approved else "modify", "" if all_approved else "改写第二页结论"),
            ("s3", "approved" if all_approved else "evidence", "" if all_approved else "补足第三页证据"),
            ("s4", "approved" if all_approved else "merge-or-delete", "" if all_approved else "第四页并入第三页"),
        )
        source = self.content.kernel.load().artifact_heads["content/blueprint"]
        for slide_id, decision, comment in choices:
            self.review.save_page_decision(
                command_id=f"save-{batch_id}-{slide_id}-{uuid.uuid4()}",
                expected_revision=self.content.kernel.load().revision,
                source_version=source,
                review_batch_id=batch_id,
                slide_id=slide_id,
                decision=decision,
                comment=comment,
            )
        context = self.review.submission_context(
            source_version=source, review_batch_id=batch_id
        )
        batch_ref, _follow_up, _state = self.review.submit_review_batch(
            command_id=f"submit-{batch_id}",
            expected_revision=int(context["challenge_revision"]),
            source_version=source,
            review_batch_id=batch_id,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        return batch_ref

    def confirm_plan(
        self,
        *,
        batch_ref: str,
        batch_id: str,
        requires_revision: bool,
    ) -> tuple[str, str]:
        source = self.content.kernel.load().artifact_heads["content/blueprint"]
        planning = ContentBatchPlanningService(self.content.kernel)
        plan = {
            "plan_id": f"plan-{batch_id}",
            "plan_version": 1,
            "review_batch_ref": batch_ref,
            "review_batch_id": batch_id,
            "source_version": source,
            "direct_actions": (
                [{"slide_ids": ["s2"], "action": "改写结论"}]
                if requires_revision
                else []
            ),
            "cross_page_actions": (
                [{"slide_ids": ["s3", "s4"], "action": "合并并补证"}]
                if requires_revision
                else []
            ),
            "merge_delete_actions": (
                [{"source_slide_ids": ["s4"], "target_slide_id": "s3", "preserve": "证据", "remove": "重复文字"}]
                if requires_revision
                else []
            ),
            "evidence_actions": (
                [{"slide_ids": ["s3"], "action": "补证或降级", "required_material": "客户材料"}]
                if requires_revision
                else []
            ),
            "revised_chapters": (
                [{"chapter_id": "ch1", "title": "新版章节", "slide_ids": ["s1", "s2", "s3"]}]
                if requires_revision
                else []
            ),
            "estimated_slide_count": 4,
            "preserve_items": ["任务目标", "已核验事实"],
            "conflicts_and_risks": [],
            "required_user_decisions": [],
            "re_review_scope": "new-blueprint-full-deck",
            "requires_blueprint_revision": requires_revision,
            "status": "proposed",
        }
        plan_ref, _lifecycle_ref, _state = planning.save_revision_plan(
            command_id=f"save-plan-{batch_id}",
            expected_revision=self.content.kernel.load().revision,
            payload=plan,
        )
        context = planning.confirmation_context(
            review_batch_id=batch_id, plan_ref=plan_ref
        )
        confirmation_ref, _batch_lifecycle_ref, _state = (
            planning.confirm_revision_plan(
                command_id=f"confirm-plan-{batch_id}",
                expected_revision=int(context["challenge_revision"]),
                review_batch_id=batch_id,
                plan_ref=plan_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )
        )
        return plan_ref, confirmation_ref

    def publish_v2(self, plan_confirmation_ref: str) -> tuple[str, dict]:
        planning = ContentBatchPlanningService(self.content.kernel)
        planning.create_governance_and_change_set(
            command_id="govern-v1-plan",
            expected_revision=self.content.kernel.load().revision,
            plan_confirmation_ref=plan_confirmation_ref,
        )
        state = self.content.kernel.load()
        payload = complete_slide_draft_payload(
            argument_map_ref=state.artifact_heads["content/argument-map"],
            material_ref=state.artifact_heads["materials"],
            slide_count=4,
            slide_id_prefix="s",
        )
        payload["slides"][0]["title"] = "新版经营判断"
        draft_ref = publish_content_stage(
            self.content, "publish-v2-draft", "slide-draft-set", payload
        )
        for index, role in enumerate(
            (
                "presales-reviewer",
                "decision-maker-reviewer",
                "evidence-reviewer",
                "narrative-reviewer",
                "editorial-reviewer",
            )
        ):
            publish_content_review(
                self.content,
                f"v2-review-{index}",
                review_payload(draft_ref, role),
            )
        accepted = self.content.accept_content(
            "accept-v2", self.content.kernel.load().revision
        )
        return accepted.blueprint_ref, resolve_payload(
            self.content, accepted.blueprint_ref
        )

    def test_v2_binds_confirmed_plan_and_starts_review_from_zero(self) -> None:
        batch_ref = self.submit_batch(
            all_approved=False, batch_id=self.batch_id
        )
        plan_ref, confirmation_ref = self.confirm_plan(
            batch_ref=batch_ref,
            batch_id=self.batch_id,
            requires_revision=True,
        )
        v2_ref, v2 = self.publish_v2(confirmation_ref)
        self.assertNotEqual(v2_ref, self.v1_ref)
        self.assertEqual(v2["supersedes_blueprint_ref"], self.v1_ref)
        self.assertEqual(v2["review_batch_ref"], batch_ref)
        self.assertEqual(v2["batch_revision_plan_ref"], plan_ref)
        self.assertEqual(v2["batch_plan_confirmation_ref"], confirmation_ref)
        applied_v1 = resolve_payload(
            self.content,
            self.content.kernel.load().artifact_heads["content/review-batch"],
        )
        self.assertEqual(applied_v1["status"], "applied")
        self.assertEqual(applied_v1["source_version"], self.v1_ref)
        self.assertEqual(applied_v1["result_blueprint_ref"], v2_ref)
        progress = self.review.progress(v2_ref)
        self.assertEqual(progress["completed"], 0)
        self.assertEqual(progress["remaining"], len(v2["slides"]))
        current_set = self.review.current_decision_set(v2_ref)
        self.assertEqual(current_set["decision_refs"], [])
        self.assertEqual(current_set["source_version"], v2_ref)
        with self.assertRaises(GateBlockedError) as caught:
            GateConfirmationPolicy(self.content.kernel).context("G0")
        self.assertIn(
            "content-review-batch-current-source-incomplete",
            caught.exception.missing_evidence,
        )
        old_decision_refs = set(applied_v1["decision_refs"])
        first_v2, first_progress, _state = self.review.save_page_decision(
            command_id="first-v2-decision",
            expected_revision=self.content.kernel.load().revision,
            source_version=v2_ref,
            review_batch_id="fresh-v2-review",
            slide_id="s2",
            decision="approved",
            comment="旧版意见不得继承",
        )
        first_payload = resolve_payload(
            self.content, first_v2["page_decision_ref"]
        )
        self.assertNotIn(first_v2["page_decision_ref"], old_decision_refs)
        self.assertEqual(first_payload["comment"], "")
        self.assertEqual(first_progress["completed"], 1)
        self.assertEqual(first_progress["remaining"], 3)
        fresh_set = self.review.current_decision_set(v2_ref)
        self.assertEqual(fresh_set["review_batch_id"], "fresh-v2-review")
        self.assertEqual(
            [row["decision_ref"] for row in fresh_set["decision_refs"]],
            [first_v2["page_decision_ref"]],
        )

    def test_result_blueprint_ref_is_reserved_for_applied_revision_lifecycle(self) -> None:
        batch_ref = self.submit_batch(
            all_approved=False, batch_id=self.batch_id
        )
        submitted = resolve_payload(self.content, batch_ref)
        malformed = {**submitted, "result_blueprint_ref": self.v1_ref}
        with self.assertRaises(ContractValidationError):
            validate_content_review_batch(malformed)

    def test_legacy_g0_service_cannot_bypass_current_applied_review(self) -> None:
        before = self.content.kernel.load()
        with self.assertRaises(GateBlockedError) as caught:
            self.content.confirm_g0(
                "reject-g0-before-review",
                before.revision,
                user_message_ref="chat://message/not-yet-reviewed",
            )
        self.assertIn(
            "content-review-batch-current-source-incomplete",
            caught.exception.missing_evidence,
        )
        self.assertEqual(self.content.kernel.load(), before)

    def test_g0_requires_current_source_applied_round_not_old_applied_round(self) -> None:
        batch_ref = self.submit_batch(
            all_approved=False, batch_id=self.batch_id
        )
        _plan_ref, confirmation_ref = self.confirm_plan(
            batch_ref=batch_ref,
            batch_id=self.batch_id,
            requires_revision=True,
        )
        v2_ref, _v2 = self.publish_v2(confirmation_ref)
        with self.assertRaises(GateBlockedError):
            GateConfirmationPolicy(self.content.kernel).context("G0")

        v2_batch_id = "revision-round-v2"
        v2_batch_ref = self.submit_batch(
            all_approved=True, batch_id=v2_batch_id
        )
        _v2_plan_ref, v2_confirmation_ref = self.confirm_plan(
            batch_ref=v2_batch_ref,
            batch_id=v2_batch_id,
            requires_revision=False,
        )
        ContentBatchPlanningService(self.content.kernel).apply_no_revision_plan(
            command_id="apply-v2-no-revision",
            expected_revision=self.content.kernel.load().revision,
            plan_confirmation_ref=v2_confirmation_ref,
        )
        context = GateConfirmationPolicy(self.content.kernel).context("G0")
        self.assertEqual(context["scope_kind"], "gate")
        self.assertEqual(context["scope_id"], "G0")
        self.assertEqual(context["source_version"], v2_ref)
        self.assertEqual(
            context["evidence_refs"],
            [
                self.content.kernel.load().artifact_heads["content/acceptance"],
                v2_ref,
                self.content.kernel.load().artifact_heads["content/review-batch"],
                self.content.kernel.load().artifact_heads["content/batch-revision-plan"],
                self.content.kernel.load().artifact_heads["content/batch-plan-confirmation"],
            ],
        )
        self.assertIn("4 页", context["review_summary"])
        self.assertIn("无需修改", context["review_summary"])
        payload, consumptions = GateConfirmationPolicy(
            self.content.kernel
        ).confirmation_payload(
            gate="G0",
            source_version=v2_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        self.assertEqual(payload["scope_kind"], "gate")
        self.assertEqual(payload["scope_id"], "G0")
        self.assertEqual(len(consumptions), 1)

        for scope_kind in (
            "content-framework-confirmation",
            "full-deck-expansion-authorization",
            "content-review-batch-submission",
            "content-review-batch-withdrawal",
            "content-batch-plan-confirmation",
        ):
            with self.subTest(scope_kind=scope_kind):
                foreign_context = {
                    **context,
                    "scope_kind": scope_kind,
                    "scope_id": f"foreign-{scope_kind}",
                }
                with self.assertRaises(GateBlockedError):
                    GateConfirmationPolicy(
                        self.content.kernel
                    ).confirmation_payload(
                        gate="G0",
                        source_version=v2_ref,
                        challenge_id=str(context["challenge_id"]),
                        challenge_revision=int(context["challenge_revision"]),
                        host_confirmation_assertion=signed_assertion(
                            foreign_context
                        ),
                    )

    def test_g0_batch_corruption_fails_closed_as_gate_blocker(self) -> None:
        batch_ref = self.submit_batch(
            all_approved=True, batch_id=self.batch_id
        )
        _plan_ref, confirmation_ref = self.confirm_plan(
            batch_ref=batch_ref,
            batch_id=self.batch_id,
            requires_revision=False,
        )
        ContentBatchPlanningService(self.content.kernel).apply_no_revision_plan(
            command_id="apply-ready-no-revision",
            expected_revision=self.content.kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
        )
        ready_ref = self.content.kernel.load().artifact_heads[
            "content/review-batch"
        ]
        ready_batch = resolve_payload(self.content, ready_ref)
        self.assertEqual(ready_batch["status"], "applied")
        corruptions = (
            {
                **ready_batch,
                "decision_refs": ready_batch["decision_refs"][:-1],
            },
            {**ready_batch, "expected_slide_count": 3},
            {**ready_batch, "source_version": "artifact://content-blueprint/" + "f" * 64},
        )
        for index, corrupt in enumerate(corruptions):
            with self.subTest(index=index):
                self.content.kernel.commit(
                    command_id=f"install-corrupt-batch-{index}",
                    expected_revision=self.content.kernel.load().revision,
                    event_type="test.corrupt-review-batch",
                    artifact_updates={
                        "content/review-batch": (
                            "content-review-batch",
                            corrupt,
                        )
                    },
                )
                with self.assertRaises(GateBlockedError) as caught:
                    GateConfirmationPolicy(self.content.kernel).context("G0")
                self.assertIn(
                    "content-review-batch-current-source-incomplete",
                    caught.exception.missing_evidence,
                )


if __name__ == "__main__":
    unittest.main()
