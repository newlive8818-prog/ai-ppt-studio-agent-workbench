from __future__ import annotations

import copy
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.scoped_confirmation import (  # noqa: E402
    HOST_CONFIRMATION_SECRET_ENV,
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.application.content_service import ContentService  # noqa: E402
from ai_ppt_studio.application.content_hard_gate_service import (  # noqa: E402
    ContentHardGateService,
)
from ai_ppt_studio.application.gate_confirmation import (  # noqa: E402
    GateConfirmationPolicy,
)
from ai_ppt_studio.application.project_service import (  # noqa: E402
    ProjectCommandService,
)
from ai_ppt_studio.application.presales_content_service import (  # noqa: E402
    PresalesContentService,
)
from ai_ppt_studio.application.review_session_service import (  # noqa: E402
    ReviewSessionService,
)
from ai_ppt_studio.application.review_service import ReviewService  # noqa: E402
from ai_ppt_studio.domains.content.revision_plans import (  # noqa: E402
    validate_revision_plan_confirmation,
)
from ai_ppt_studio.errors import (  # noqa: E402
    ContentWorkflowError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from tests.test_v22_content_review_decisions import decision_service_type  # noqa: E402
from tests.test_v16_visual_review import visual_marks  # noqa: E402
from tests.test_v22_content_hard_gates import (  # noqa: E402
    build_blueprint,
    submit_gate_via_command,
)
from tests.test_v22_content_review_projection import review_ready_kernel  # noqa: E402
from tests.v16_delivery_fixtures import (  # noqa: E402
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)
from tests.test_v16_framework_discussion import (  # noqa: E402
    TEST_SECRET,
    signed_assertion,
)


def batch_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_review.batch_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 content review batch service") from exc
    candidate = getattr(module, "ContentReviewBatchService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing ContentReviewBatchService")
    return candidate


def planning_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_review.planning_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 content batch planning service") from exc
    candidate = getattr(module, "ContentBatchPlanningService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing ContentBatchPlanningService")
    return candidate


class ContentReviewBatchServiceTests(unittest.TestCase):
    def test_revision_plan_confirmation_requires_a_non_negative_integer_revision(
        self,
    ) -> None:
        def payload(challenge_revision: object) -> dict[str, object]:
            return {
                "project_id": "project-v22-confirmation-validator",
                "revision_plan_ref": (
                    "artifact://content-batch-revision-plan/" + "1" * 64
                ),
                "review_batch_ref": "artifact://content-review-batch/" + "2" * 64,
                "source_version": "artifact://reading-deck-blueprint/" + "3" * 64,
                "scope_kind": "content-batch-plan-confirmation",
                "scope_id": "test-scope",
                "challenge_id": "challenge-v22-confirmation-validator",
                "challenge_revision": challenge_revision,
                "confirmed_at": "2026-08-24T00:00:00+00:00",
            }

        for invalid in (True, False, "7", 1.5, "not-a-revision", -1):
            with self.subTest(challenge_revision=repr(invalid)):
                with self.assertRaisesRegex(
                    ContractValidationError,
                    "Revision plan confirmation revision is invalid",
                ):
                    validate_revision_plan_confirmation(payload(invalid))

        confirmed = validate_revision_plan_confirmation(payload(0))
        self.assertEqual(confirmed["challenge_revision"], 0)
        self.assertIsInstance(confirmed["challenge_revision"], int)

    def test_trusted_confirmation_rejects_non_integer_challenge_revisions_before_writes(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=1)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        decisions = decision_service_type()(kernel)
        decisions.save(
            command_id="save-confirmation-type-boundary-page",
            expected_revision=kernel.load().revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="confirmation-type-boundary-batch",
            slide_id=str(blueprint["slides"][0]["slide_id"]),
            decision="approved",
            comment="",
        )
        service = batch_service_type()(kernel)
        context = service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="confirmation-type-boundary-batch",
        )
        assertion = signed_assertion(context)
        before = kernel.load()
        before_events = self._event_count(kernel)

        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            with self.assertRaises(ContentWorkflowError) as raised:
                service.submit_review_batch(
                    command_id="reject-float-confirmation-revision",
                    expected_revision=before.revision,
                    review_session_id=str(session["review_session_id"]),
                    review_batch_id="confirmation-type-boundary-batch",
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=float(context["challenge_revision"]),
                    host_confirmation_assertion=assertion,
                )

            self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")

            for expected_revision, invalid in ((0, False), (1, True)):
                with self.subTest(challenge_revision=repr(invalid)):
                    current = {
                        **context,
                        "challenge_revision": expected_revision,
                    }
                    with self.assertRaises(ContentWorkflowError) as boolean_raised:
                        ScopedConfirmationPolicy(kernel).confirmation_payload(
                            current=current,
                            source_version=str(current["source_version"]),
                            challenge_id=str(current["challenge_id"]),
                            challenge_revision=invalid,
                            host_confirmation_assertion=signed_assertion(current),
                        )
                    self.assertEqual(
                        boolean_raised.exception.code,
                        "CONTENT_REVIEW_CONFLICT",
                    )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    @staticmethod
    def _event_count(kernel: Any) -> int:
        return len(list(kernel.events_root.glob("r*.json")))

    @staticmethod
    def _replace_event_head(
        kernel: Any,
        *,
        command_id: str,
        slot: str,
        replacement_ref: str | None,
    ) -> None:
        """Deliberately corrupt one persisted receipt for fail-closed recovery tests."""

        revision = kernel.load().processed_commands[command_id]
        path = kernel.events_root / f"r{revision:08d}.json"
        event = json.loads(path.read_text(encoding="utf-8"))
        heads = event["artifact_heads"]
        if replacement_ref is None:
            heads.pop(slot, None)
        else:
            heads[slot] = replacement_ref
        path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _plan_arguments(
        *,
        command_id: str,
        expected_revision: int,
        submitted_batch_ref: str,
        blueprint: dict[str, Any],
        summary: str,
        all_keep: bool = False,
    ) -> dict[str, Any]:
        return {
            "command_id": command_id,
            "expected_revision": expected_revision,
            "review_batch_ref": submitted_batch_ref,
            "producer_id": "presales-solution-chief",
            "summary": summary,
            "page_actions": [
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if all_keep or index == 0 else "revise",
                    "rationale": (
                        "当前页认可。"
                        if all_keep
                        else "保留当前页。"
                        if index == 0
                        else "补足来源位置。"
                    ),
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        }

    @staticmethod
    def _changed_blueprint(
        blueprint: dict[str, Any], *, source_version: str, reason: str
    ) -> dict[str, Any]:
        candidate = copy.deepcopy(blueprint)
        candidate["source_version"] = source_version
        candidate["hard_gate_refs"] = []
        candidate["repair_history"].append({"reason": reason})
        return candidate

    def _publish_later_blueprint(
        self,
        kernel: Any,
        blueprint: dict[str, Any],
        *,
        command_id: str,
        source_version: str,
        reason: str,
    ) -> tuple[str, dict[str, Any]]:
        payload = self._changed_blueprint(
            blueprint,
            source_version=source_version,
            reason=reason,
        )
        blueprint_ref = PresalesContentService(kernel).build_reading_blueprint(
            command_id=command_id,
            expected_revision=kernel.load().revision,
            actor_role_id="presales-solution-chief",
            material_mode=str(payload["material_mode"]),
            evidence_book_ref=str(payload["evidence_book_ref"]),
            decision_context_ref=str(payload["decision_context_ref"]),
            problem_solution_fit_ref=str(payload["problem_solution_fit_ref"]),
            payload=payload,
        )
        # This helper intentionally creates an independent later source to
        # exercise historical replay. Mirror the authoritative changed-source
        # boundary before starting that source's new review round: old review
        # current heads must not be projected into the new deck.
        state = kernel.load()
        kernel.commit(
            command_id=f"{command_id}-clear-prior-review-heads",
            expected_revision=state.revision,
            event_type="test.clear-prior-content-review-heads-for-later-source",
            artifact_updates={},
            artifact_removals=tuple(
                slot
                for slot in (
                    "content/gate/evidence",
                    "content/gate/presales-reading",
                    "content/acceptance",
                    "content/page-decisions",
                    "content/review-batch",
                    "content/revision-plan",
                    "content/revision-plan-confirmation",
                    "review/session/current/content-full-deck",
                )
                if slot in state.artifact_heads
            ),
        )
        return blueprint_ref, payload

    def _submitted_review(
        self, *, all_approved: bool = False
    ) -> tuple[Any, dict[str, Any], dict[str, Any], Any, str]:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(blueprint["slides"]):
            decisions.save(
                command_id=f"save-withdraw-page-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
                slide_id=str(slide["slide_id"]),
                decision="approved" if all_approved or index == 0 else "modify",
                comment="" if all_approved or index == 0 else "需要补足来源位置。",
            )
        service = batch_service_type()(kernel)
        context = service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="withdrawable-v22-batch",
        )
        assertion = signed_assertion(context)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            batch_ref, _follow_up, committed = service.submit_review_batch(
                command_id="submit-withdrawable-v22-batch",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )
        return kernel, blueprint, session, service, batch_ref

    def test_submission_context_rejects_an_incomplete_current_v22_deck(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            __import__("ai_ppt_studio.kernel.references", fromlist=["ArtifactReference"])
            .ArtifactReference.parse(blueprint_ref)
        )["payload"]
        first_slide_id = str(blueprint["slides"][0]["slide_id"])
        decision_service_type()(kernel).save(
            command_id="save-only-first-page",
            expected_revision=kernel.load().revision,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="incomplete-v22-batch",
            slide_id=first_slide_id,
            decision="approved",
            comment="",
        )

        with self.assertRaises(ContentWorkflowError) as raised:
            batch_service_type()(kernel).submission_context(
                review_session_id=str(session["review_session_id"]),
                review_batch_id="incomplete-v22-batch",
            )

        self.assertEqual(
            raised.exception.code, "CONTENT_REVIEW_BATCH_INCOMPLETE"
        )
        self.assertEqual(
            raised.exception.details["remaining"], len(blueprint["slides"]) - 1
        )

    def test_submit_freezes_current_v22_batch_without_content_or_gate_side_effects(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        initial = kernel.load()
        protected_heads = {
            key: initial.artifact_heads.get(key, "")
            for key in (
                "content/reading-deck-blueprint",
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
                "gate/G0/confirmation",
            )
        }
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(blueprint["slides"]):
            decisions.save(
                command_id=f"save-batch-page-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submitted-v22-batch",
                slide_id=str(slide["slide_id"]),
                decision="approved" if index == 0 else "modify",
                comment="" if index == 0 else "补充本页的来源定位。",
            )

        service = batch_service_type()(kernel)
        context = service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="submitted-v22-batch",
        )
        self.assertEqual(context["source_version"], blueprint_ref)
        self.assertEqual(context["expected_slide_count"], 2)
        self.assertEqual(context["counts"], {
            "approved": 1,
            "modify": 1,
            "evidence": 0,
            "merge_or_delete": 0,
        })

        assertion = signed_assertion(context)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            batch_ref, follow_up, committed = service.submit_review_batch(
                command_id="submit-v22-review-batch",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submitted-v22-batch",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )

        self.assertEqual(follow_up, "已提交，等待整套修改方案")
        self.assertEqual(
            ArtifactReference.parse(batch_ref).kind,
            "content-review-batch",
        )
        batch = kernel.artifacts.resolve(ArtifactReference.parse(batch_ref))["payload"]
        self.assertEqual(batch["status"], "submitted")
        self.assertEqual(batch["source_version"], blueprint_ref)
        self.assertEqual(batch["expected_slide_count"], 2)
        self.assertEqual(batch["counts"], context["counts"])
        self.assertNotEqual(batch["decision_set_ref"], context["decision_set_ref"])
        self.assertEqual(batch["decision_refs"], context["decision_refs"])
        self.assertEqual(
            committed.artifact_heads["content/review-batch"], batch_ref
        )
        self.assertEqual(
            committed.artifact_heads["content/page-decisions"],
            batch["decision_set_ref"],
        )
        self.assertEqual(
            {
                key: committed.artifact_heads.get(key, "")
                for key in protected_heads
            },
            protected_heads,
        )
        submitted_session = kernel.artifacts.resolve(
            ArtifactReference.parse(
                committed.artifact_heads[
                    "review/session/current/content-full-deck"
                ]
            )
        )["payload"]
        self.assertEqual(submitted_session["status"], "submitted")
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replayed_ref, replayed_follow_up, replayed = service.submit_review_batch(
                command_id="submit-v22-review-batch",
                expected_revision=int(context["challenge_revision"]),
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submitted-v22-batch",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )
        self.assertEqual(replayed_ref, batch_ref)
        self.assertEqual(replayed_follow_up, follow_up)
        self.assertEqual(replayed.revision, committed.revision)
        with self.assertRaises(ContentWorkflowError) as frozen:
            decisions.save(
                command_id="attempt-edit-submitted-v22-batch",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submitted-v22-batch",
                slide_id=str(blueprint["slides"][0]["slide_id"]),
                decision="modify",
                comment="提交后不允许覆盖。",
            )
        self.assertEqual(frozen.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(
            batch_service_type()(kernel).projection.project(
                review_session_id=str(session["review_session_id"])
            )["review_progress"]["remaining"],
            0,
        )

    def test_withdrawal_preserves_submitted_batch_and_opens_replacement_lineage(
        self,
    ) -> None:
        kernel, blueprint, session, service, submitted_batch_ref = (
            self._submitted_review()
        )
        before = kernel.load()
        protected_heads = {
            key: before.artifact_heads.get(key, "")
            for key in (
                "content/reading-deck-blueprint",
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
                "gate/G0/confirmation",
            )
        }
        context = service.withdrawal_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="withdrawable-v22-batch",
        )
        assertion = signed_assertion(context)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replacement, committed = service.withdraw_review_batch(
                command_id="withdraw-v22-review-batch",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
                reason="继续补充同一批次的逐页意见。",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )
            replayed, replayed_state = service.withdraw_review_batch(
                command_id="withdraw-v22-review-batch",
                expected_revision=int(context["challenge_revision"]),
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
                reason="继续补充同一批次的逐页意见。",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )

        self.assertNotEqual(replacement["review_batch_id"], "withdrawable-v22-batch")
        self.assertEqual(replayed, replacement)
        self.assertEqual(replayed_state.revision, committed.revision)
        self.assertEqual(replacement["decision_set"]["status"], "draft")
        self.assertEqual(
            replacement["decision_set"]["source_version"],
            kernel.artifacts.resolve(
                ArtifactReference.parse(submitted_batch_ref)
            )["payload"]["source_version"],
        )
        self.assertEqual(
            kernel.artifacts.resolve(ArtifactReference.parse(submitted_batch_ref))["payload"]
            ["status"],
            "submitted",
        )
        self.assertEqual(
            committed.artifact_heads["content/page-decisions"],
            replacement["decision_set_ref"],
        )
        self.assertNotIn("content/review-batch", committed.artifact_heads)
        self.assertEqual(
            {
                key: committed.artifact_heads.get(key, "")
                for key in protected_heads
            },
            protected_heads,
        )
        replacement_session = kernel.artifacts.resolve(
            ArtifactReference.parse(
                committed.artifact_heads[
                    "review/session/current/content-full-deck"
                ]
            )
        )["payload"]
        self.assertEqual(replacement_session["status"], "ready")
        self.assertNotEqual(
            replacement_session["review_session_id"],
            session["review_session_id"],
        )
        self.assertEqual(len(replacement["decision_set"]["decision_refs"]), len(blueprint["slides"]))

    def test_chief_can_save_one_whole_deck_revision_plan_for_current_batch(self) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        before = kernel.load()
        plan_ref, committed = planning_service_type()(kernel).save_revision_plan(
            command_id="save-v22-whole-deck-plan",
            expected_revision=before.revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="先补足来源定位，再统一收紧跨页叙述。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "认可当前页面。" if index == 0 else "补足来源位置。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        )
        plan = kernel.artifacts.resolve(ArtifactReference.parse(plan_ref))["payload"]
        self.assertEqual(plan["status"], "proposed")
        self.assertEqual(plan["review_batch_ref"], submitted_batch_ref)
        self.assertEqual(plan["source_version"], kernel.artifacts.resolve(
            ArtifactReference.parse(submitted_batch_ref)
        )["payload"]["source_version"])
        self.assertEqual(len(plan["page_actions"]), len(blueprint["slides"]))
        self.assertEqual(committed.artifact_heads["content/revision-plan"], plan_ref)
        self.assertEqual(
            committed.artifact_heads["content/reading-deck-blueprint"],
            before.artifact_heads["content/reading-deck-blueprint"],
        )

    def test_save_revision_plan_replays_original_result_with_original_expected_revision(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        original_revision = kernel.load().revision
        arguments = {
            "command_id": "replay-v22-whole-deck-plan",
            "expected_revision": original_revision,
            "review_batch_ref": submitted_batch_ref,
            "producer_id": "presales-solution-chief",
            "summary": "同一批次只保存一次整套修改方案。",
            "page_actions": [
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "保留当前页。" if index == 0 else "补足来源位置。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        }

        original_ref, original_state = planning.save_revision_plan(**arguments)
        replayed_ref, replayed_state = planning.save_revision_plan(**arguments)

        self.assertEqual(replayed_ref, original_ref)
        self.assertEqual(replayed_state.revision, original_state.revision)

    def test_save_plan_replay_after_confirmation_returns_original_proposed_plan_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        arguments = self._plan_arguments(
            command_id="replay-v22-plan-after-confirmation",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="先保留已认可页面，再完整补足来源定位。",
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            _confirmation_ref, confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-plan-before-historical-replay",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )

        self.assertNotEqual(confirmed_plan_ref, proposed_ref)
        before = kernel.load()
        before_events = self._event_count(kernel)
        replayed_ref, replayed_state = planning.save_revision_plan(**arguments)

        self.assertEqual(replayed_ref, proposed_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_save_plan_replay_after_changed_plan_application_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        arguments = self._plan_arguments(
            command_id="replay-v22-plan-after-application",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="按整套逐页意见生成新的阅读稿。",
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-plan-before-application-replay",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        new_blueprint = copy.deepcopy(blueprint)
        new_blueprint["source_version"] = "reading-v2-after-historical-plan-replay"
        new_blueprint["hard_gate_refs"] = []
        new_blueprint["repair_history"].append(
            {"reason": "apply-confirmed-content-review-plan-for-historical-replay"}
        )
        planning.apply_confirmed_plan(
            command_id="apply-v22-plan-before-historical-replay",
            expected_revision=kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
            new_blueprint=new_blueprint,
        )

        self.assertNotIn("content/review-batch", kernel.load().artifact_heads)
        self.assertNotIn("content/revision-plan", kernel.load().artifact_heads)
        before = kernel.load()
        before_events = self._event_count(kernel)
        replayed_ref, replayed_state = planning.save_revision_plan(**arguments)

        self.assertEqual(replayed_ref, proposed_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_save_plan_replay_rejects_changed_expected_revision_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        arguments = self._plan_arguments(
            command_id="reject-v22-plan-replay-with-changed-revision",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="同一份整套方案只接受原始写入语义。",
        )
        planning.save_revision_plan(**arguments)
        before = kernel.load()
        before_events = self._event_count(kernel)
        changed_arguments = {
            **arguments,
            "expected_revision": before.revision,
        }

        with self.assertRaisesRegex(
            ContractValidationError, "Processed command has different semantics"
        ):
            planning.save_revision_plan(**changed_arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_submit_batch_replay_after_withdrawal_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(blueprint["slides"]):
            decisions.save(
                command_id=f"save-submit-replay-page-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submit-replay-withdrawn-v22-batch",
                slide_id=str(slide["slide_id"]),
                decision="approved" if index == 0 else "modify",
                comment="" if index == 0 else "需要补足来源位置。",
            )
        service = batch_service_type()(kernel)
        submission_context = service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="submit-replay-withdrawn-v22-batch",
        )
        submission_arguments = {
            "command_id": "submit-v22-replay-after-withdrawal",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "submit-replay-withdrawn-v22-batch",
            "challenge_id": str(submission_context["challenge_id"]),
            "challenge_revision": int(submission_context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(submission_context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            submitted_ref, follow_up, _submitted_state = service.submit_review_batch(
                **submission_arguments
            )
            withdrawal_context = service.withdrawal_context(
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submit-replay-withdrawn-v22-batch",
            )
            service.withdraw_review_batch(
                command_id="withdraw-v22-before-submit-replay",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="submit-replay-withdrawn-v22-batch",
                reason="继续补充同一批次的逐页意见。",
                challenge_id=str(withdrawal_context["challenge_id"]),
                challenge_revision=int(withdrawal_context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(withdrawal_context),
            )

            before = kernel.load()
            before_events = self._event_count(kernel)
            replayed_ref, replayed_follow_up, replayed_state = (
                service.submit_review_batch(**submission_arguments)
            )

        self.assertEqual(replayed_ref, submitted_ref)
        self.assertEqual(replayed_follow_up, follow_up)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_withdrawal_replay_after_replacement_edit_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, session, service, _submitted_batch_ref = (
            self._submitted_review()
        )
        withdrawal_context = service.withdrawal_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="withdrawable-v22-batch",
        )
        withdrawal_arguments = {
            "command_id": "withdraw-v22-replay-after-replacement-edit",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "withdrawable-v22-batch",
            "reason": "继续补充同一批次的逐页意见。",
            "challenge_id": str(withdrawal_context["challenge_id"]),
            "challenge_revision": int(withdrawal_context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(withdrawal_context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replacement, _withdrawn_state = service.withdraw_review_batch(
                **withdrawal_arguments
            )
        decision_service_type()(kernel).save(
            command_id="edit-v22-withdrawal-replacement-before-replay",
            expected_revision=kernel.load().revision,
            review_session_id=str(replacement["review_session_id"]),
            review_batch_id=str(replacement["review_batch_id"]),
            slide_id=str(blueprint["slides"][0]["slide_id"]),
            decision="modify",
            comment="替换批次之后又补充了本页意见。",
        )
        later_decision_set_ref = str(
            kernel.load().artifact_heads["content/page-decisions"]
        )
        self.assertNotEqual(later_decision_set_ref, replacement["decision_set_ref"])
        before = kernel.load()
        before_events = self._event_count(kernel)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replayed, replayed_state = service.withdraw_review_batch(
                **withdrawal_arguments
            )

        self.assertEqual(replayed["review_batch_id"], replacement["review_batch_id"])
        self.assertEqual(replayed["decision_set_ref"], replacement["decision_set_ref"])
        self.assertEqual(replayed["review_session_id"], replacement["review_session_id"])
        self.assertNotEqual(replayed["decision_set_ref"], later_decision_set_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_submitted_batch_rejects_different_batch_id_for_same_current_session_without_writes(
        self,
    ) -> None:
        kernel, blueprint, session, _service, _submitted_batch_ref = (
            self._submitted_review()
        )
        before = kernel.load()
        before_events = self._event_count(kernel)

        with self.assertRaises(ContentWorkflowError) as raised:
            decision_service_type()(kernel).save(
                command_id="reject-v22-submitted-batch-id-bypass",
                expected_revision=before.revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="different-v22-batch-id-after-submission",
                slide_id=str(blueprint["slides"][0]["slide_id"]),
                decision="modify",
                comment="不得通过替换 batch ID 覆盖冻结决定。",
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_plan_proposed_batch_rejects_different_batch_id_for_same_current_session_without_writes(
        self,
    ) -> None:
        kernel, blueprint, session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning_service_type()(kernel).save_revision_plan(
            **self._plan_arguments(
                command_id="save-v22-plan-before-batch-id-bypass",
                expected_revision=kernel.load().revision,
                submitted_batch_ref=submitted_batch_ref,
                blueprint=blueprint,
                summary="计划提出后继续冻结原提交审核批次。",
            )
        )
        before = kernel.load()
        before_events = self._event_count(kernel)

        with self.assertRaises(ContentWorkflowError) as raised:
            decision_service_type()(kernel).save(
                command_id="reject-v22-plan-proposed-batch-id-bypass",
                expected_revision=before.revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="different-v22-batch-id-after-plan",
                slide_id=str(blueprint["slides"][0]["slide_id"]),
                decision="modify",
                comment="计划提出后不能通过新的 batch ID 改写同一会话。",
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_withdrawal_replacement_requires_its_returned_batch_id_and_resubmission_traces_original_batch(
        self,
    ) -> None:
        kernel, blueprint, session, service, submitted_batch_ref = (
            self._submitted_review()
        )
        withdrawal_context = service.withdrawal_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="withdrawable-v22-batch",
        )
        withdrawal_arguments = {
            "command_id": "withdraw-v22-replacement-batch-id-contract",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "withdrawable-v22-batch",
            "reason": "继续完善同一份审核批次。",
            "challenge_id": str(withdrawal_context["challenge_id"]),
            "challenge_revision": int(withdrawal_context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(withdrawal_context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replacement, _withdrawn_state = service.withdraw_review_batch(
                **withdrawal_arguments
            )
        before_wrong_id = kernel.load()
        before_wrong_id_events = self._event_count(kernel)

        with self.assertRaises(ContentWorkflowError) as wrong_id:
            decision_service_type()(kernel).save(
                command_id="reject-v22-withdrawal-wrong-replacement-id",
                expected_revision=before_wrong_id.revision,
                review_session_id=str(replacement["review_session_id"]),
                review_batch_id="different-v22-withdrawal-replacement-id",
                slide_id=str(blueprint["slides"][0]["slide_id"]),
                decision="modify",
                comment="不得绕过撤回返回的 replacement batch ID。",
            )

        self.assertIn(
            wrong_id.exception.code,
            {"CONTENT_REVIEW_BATCH_FROZEN", "CONTENT_REVIEW_CONFLICT"},
        )
        self.assertEqual(kernel.load().revision, before_wrong_id.revision)
        self.assertEqual(kernel.load().artifact_heads, before_wrong_id.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_wrong_id_events)

        decision_service_type()(kernel).save(
            command_id="save-v22-withdrawal-returned-replacement-id",
            expected_revision=kernel.load().revision,
            review_session_id=str(replacement["review_session_id"]),
            review_batch_id=str(replacement["review_batch_id"]),
            slide_id=str(blueprint["slides"][0]["slide_id"]),
            decision="modify",
            comment="使用撤回回执中的 replacement batch ID 继续修改。",
        )
        replacement_context = service.submission_context(
            review_session_id=str(replacement["review_session_id"]),
            review_batch_id=str(replacement["review_batch_id"]),
        )
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replacement_batch_ref, _follow_up, _resubmitted_state = (
                service.submit_review_batch(
                    command_id="submit-v22-withdrawal-replacement",
                    expected_revision=kernel.load().revision,
                    review_session_id=str(replacement["review_session_id"]),
                    review_batch_id=str(replacement["review_batch_id"]),
                    challenge_id=str(replacement_context["challenge_id"]),
                    challenge_revision=int(replacement_context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(replacement_context),
                )
            )

        withdrawal = kernel.artifacts.resolve(
            ArtifactReference.parse(
                kernel.load().artifact_heads["content/review-batch-withdrawal"]
            )
        )["payload"]
        replacement_batch = kernel.artifacts.resolve(
            ArtifactReference.parse(replacement_batch_ref)
        )["payload"]
        self.assertEqual(
            withdrawal["submitted_batch_ref"],
            submitted_batch_ref,
        )
        self.assertEqual(
            withdrawal["replacement_review_batch_id"],
            replacement["review_batch_id"],
        )
        self.assertEqual(
            replacement_batch["review_batch_id"],
            withdrawal["replacement_review_batch_id"],
        )

    def test_save_plan_replay_rejects_same_project_receipt_for_different_actions_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        original_arguments = self._plan_arguments(
            command_id="save-v22-plan-receipt-actions-original",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="原始计划只修订需要补足来源的页面。",
        )
        planning.save_revision_plan(**original_arguments)
        wrong_actions_ref, _wrong_actions_state = planning.save_revision_plan(
            **self._plan_arguments(
                command_id="save-v22-plan-receipt-actions-wrong",
                expected_revision=kernel.load().revision,
                submitted_batch_ref=submitted_batch_ref,
                blueprint=blueprint,
                summary="同项目同批次但动作不同的错误历史计划。",
                all_keep=True,
            )
        )
        self._replace_event_head(
            kernel,
            command_id=original_arguments["command_id"],
            slot="content/revision-plan",
            replacement_ref=wrong_actions_ref,
        )
        before = kernel.load()
        before_events = self._event_count(kernel)

        with self.assertRaisesRegex(
            ContractValidationError, "Processed revision plan has different semantics"
        ):
            planning.save_revision_plan(**original_arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_submitted_batch_replay_rejects_same_project_receipt_for_different_decisions_and_session_without_writes(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        original_batch_id = "original-v22-submission-receipt-batch"
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(blueprint["slides"]):
            decisions.save(
                command_id=f"save-v22-original-submission-receipt-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id=original_batch_id,
                slide_id=str(slide["slide_id"]),
                decision="approved" if index == 0 else "modify",
                comment="" if index == 0 else "补足来源定位。",
            )
        service = batch_service_type()(kernel)
        original_context = service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id=original_batch_id,
        )
        original_arguments = {
            "command_id": "submit-v22-submission-receipt-original",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": original_batch_id,
            "challenge_id": str(original_context["challenge_id"]),
            "challenge_revision": int(original_context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(original_context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            original_batch_ref, _follow_up, _submitted_state = (
                service.submit_review_batch(**original_arguments)
            )
            withdrawal_context = service.withdrawal_context(
                review_session_id=str(session["review_session_id"]),
                review_batch_id=original_batch_id,
            )
            replacement, _withdrawal_state = service.withdraw_review_batch(
                command_id="withdraw-v22-before-submission-receipt-corruption",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id=original_batch_id,
                reason="为重提同一审核对象补充判断。",
                challenge_id=str(withdrawal_context["challenge_id"]),
                challenge_revision=int(withdrawal_context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(withdrawal_context),
            )
            replacement_context = service.submission_context(
                review_session_id=str(replacement["review_session_id"]),
                review_batch_id=str(replacement["review_batch_id"]),
            )
            wrong_batch_ref, _follow_up, _resubmitted_state = (
                service.submit_review_batch(
                    command_id="submit-v22-submission-receipt-wrong",
                    expected_revision=kernel.load().revision,
                    review_session_id=str(replacement["review_session_id"]),
                    review_batch_id=str(replacement["review_batch_id"]),
                    challenge_id=str(replacement_context["challenge_id"]),
                    challenge_revision=int(replacement_context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(replacement_context),
                )
            )

        self.assertNotEqual(wrong_batch_ref, original_batch_ref)
        self._replace_event_head(
            kernel,
            command_id=original_arguments["command_id"],
            slot="content/review-batch",
            replacement_ref=wrong_batch_ref,
        )
        before = kernel.load()
        before_events = self._event_count(kernel)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            with self.assertRaisesRegex(
                ContractValidationError,
                "Processed content review batch command has different semantics",
            ):
                service.submit_review_batch(**original_arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_withdrawal_replay_rejects_receipt_missing_its_withdrawal_lineage_without_writes(
        self,
    ) -> None:
        kernel, _blueprint, session, service, _submitted_batch_ref = (
            self._submitted_review()
        )
        context = service.withdrawal_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id="withdrawable-v22-batch",
        )
        arguments = {
            "command_id": "withdraw-v22-receipt-lineage-original",
            "expected_revision": kernel.load().revision,
            "review_session_id": str(session["review_session_id"]),
            "review_batch_id": "withdrawable-v22-batch",
            "reason": "受控损坏回执前先形成合法撤回。",
            "challenge_id": str(context["challenge_id"]),
            "challenge_revision": int(context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            service.withdraw_review_batch(**arguments)
        self._replace_event_head(
            kernel,
            command_id=arguments["command_id"],
            slot="content/review-batch-withdrawal",
            replacement_ref=None,
        )
        before = kernel.load()
        before_events = self._event_count(kernel)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            with self.assertRaisesRegex(
                ContractValidationError,
                "Processed content review withdrawal has different semantics",
            ):
                service.withdraw_review_batch(**arguments)

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_changed_plan_application_atomically_invalidates_g0_and_current_downstream_heads(
        self,
    ) -> None:
        project_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(project_root))
        delivery, _delivery_revision, delivery_refs = prepared_delivery_ready(
            project_root,
            slide_count=2,
        )
        kernel = delivery.kernel
        package_ref = delivery.register_delivery_package(
            "register-v22-application-invalidation-package",
            kernel.load().revision,
            valid_package_payload(
                delivery_refs,
                package_artifacts(delivery, delivery_refs),
            ),
        )
        delivery.record_public_chat_delivery(
            "send-v22-application-invalidation-chat-delivery",
            kernel.load().revision,
            delivery_type="pptx",
            artifact_refs=[package_ref, str(delivery_refs["final_pptx"])],
            message_ref="chat://message/v22-application-invalidation",
            send_status="sent",
            retry_of="",
        )
        legacy_visual_ref = str(kernel.load().artifact_heads["visual/contract"])
        ReviewService(kernel).save_marks(
            command_id="save-v22-application-invalidation-visual-mark",
            expected_revision=kernel.load().revision,
            source_version=legacy_visual_ref,
            review_type="visual",
            marks=visual_marks(),
        )
        legacy_downstream_refs = {
            slot: str(kernel.load().artifact_heads[slot])
            for slot in (
                "visual/brief",
                "visual/contract",
                "delivery/build",
                "delivery/package",
                "chat-delivery/pptx",
                "review-marks/visual",
            )
        }
        # The delivery fixture carries a v1.6 decision-set head that cannot be
        # read by the v2.2 source-bound PageDecision contract. Remove only that
        # obsolete review input before building the independent v2.2 round; the
        # downstream G0/visual/delivery state under test remains intact.
        legacy_state = kernel.load()
        if "content/page-decisions" in legacy_state.artifact_heads:
            kernel.commit(
                command_id="clear-legacy-page-decisions-before-v22-invalidation",
                expected_revision=legacy_state.revision,
                event_type="test.clear-legacy-page-decisions-before-v22-review",
                artifact_updates={},
                artifact_removals=("content/page-decisions",),
            )

        blueprint_ref = build_blueprint(kernel, slide_count=2)
        submit_gate_via_command(
            kernel,
            blueprint_ref,
            gate_type="evidence",
            command_prefix="application-invalidation-v22-evidence",
        )
        submit_gate_via_command(
            kernel,
            blueprint_ref,
            gate_type="presales-reading",
            command_prefix="application-invalidation-v22-reading",
        )
        ContentHardGateService(kernel).accept_current_content(
            command_id="application-invalidation-v22-accept",
            expected_revision=kernel.load().revision,
        )
        blueprint = kernel.artifacts.resolve(
            ArtifactReference.parse(blueprint_ref)
        )["payload"]
        session, _session_state = ReviewSessionService(kernel).open_or_resume(
            command_id="open-v22-application-invalidation-review",
            expected_revision=kernel.load().revision,
            review_type="content-full-deck",
            target_artifact_ref=blueprint_ref,
            source_version=str(blueprint["source_version"]),
            target_revision=kernel.load().revision,
            open_policy="foreground-if-waiting",
        )
        review_batch_id = "v22-application-invalidation-batch"
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(blueprint["slides"]):
            decisions.save(
                command_id=f"save-v22-application-invalidation-page-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id=review_batch_id,
                slide_id=str(slide["slide_id"]),
                decision="approved",
                comment="",
            )
        batch_service = batch_service_type()(kernel)
        submission_context = batch_service.submission_context(
            review_session_id=str(session["review_session_id"]),
            review_batch_id=review_batch_id,
        )
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            submitted_batch_ref, _follow_up, _submitted_state = (
                batch_service.submit_review_batch(
                    command_id="submit-v22-application-invalidation-batch",
                    expected_revision=kernel.load().revision,
                    review_session_id=str(session["review_session_id"]),
                    review_batch_id=review_batch_id,
                    challenge_id=str(submission_context["challenge_id"]),
                    challenge_revision=int(submission_context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(submission_context),
                )
            )
        planning = planning_service_type()(kernel)
        initial_plan_ref, _initial_plan_state = planning.save_revision_plan(
            **self._plan_arguments(
                command_id="save-v22-application-invalidation-no-change-plan",
                expected_revision=kernel.load().revision,
                submitted_batch_ref=submitted_batch_ref,
                blueprint=blueprint,
                summary="先完成可确认的无内容改写审核回合。",
                all_keep=True,
            )
        )
        initial_context = planning.confirmation_context(plan_ref=initial_plan_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            initial_confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-application-invalidation-no-change-plan",
                    expected_revision=kernel.load().revision,
                    plan_ref=initial_plan_ref,
                    challenge_id=str(initial_context["challenge_id"]),
                    challenge_revision=int(initial_context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(initial_context),
                )
            )
        planning.apply_no_change_plan(
            command_id="apply-v22-application-invalidation-no-change-plan",
            expected_revision=kernel.load().revision,
            plan_confirmation_ref=initial_confirmation_ref,
        )
        g0_context = GateConfirmationPolicy(kernel).context("G0")
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            g0_passed = ContentService(kernel).confirm_g0(
                "confirm-v22-application-invalidation-g0",
                kernel.load().revision,
                host_confirmation_assertion=signed_assertion(g0_context),
                source_version=str(g0_context["source_version"]),
                challenge_id=str(g0_context["challenge_id"]),
                challenge_revision=int(g0_context["challenge_revision"]),
        )
        self.assertEqual(g0_passed.gate_status["G0"], "passed")
        reopened = ContentService(kernel).reopen_g0(
            "reopen-v22-application-invalidation-before-changed-plan",
            kernel.load().revision,
            reason="用户在已确认内容后要求改稿，必须先显式重开 G0。",
        )
        self.assertNotEqual(reopened.gate_status["G0"], "passed")
        _active_ref, active_task, _active_state = ProjectCommandService(
            kernel
        ).request_agent_action(
            "request-v22-application-invalidation-active-task",
            kernel.load().revision,
            action_type="run-content-evidence-gate",
            target_refs=[blueprint_ref],
            instructions="内容版本即将改变，活动任务必须随下游状态失效。",
        )
        changed_plan_ref, _changed_plan_state = planning.save_revision_plan(
            **self._plan_arguments(
                command_id="save-v22-application-invalidation-changed-plan",
                expected_revision=kernel.load().revision,
                submitted_batch_ref=submitted_batch_ref,
                blueprint=blueprint,
                summary="现在发布新的完整 ReadingDeckBlueprint。",
            )
        )
        changed_context = planning.confirmation_context(plan_ref=changed_plan_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            changed_confirmation_ref, _confirmed_changed_plan_ref, _state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-application-invalidation-changed-plan",
                    expected_revision=kernel.load().revision,
                    plan_ref=changed_plan_ref,
                    challenge_id=str(changed_context["challenge_id"]),
                    challenge_revision=int(changed_context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(changed_context),
                )
            )
        new_blueprint = self._changed_blueprint(
            blueprint,
            source_version="reading-v2-application-must-invalidate-downstream",
            reason="changed-plan-application-must-invalidate-downstream",
        )
        before_apply = kernel.load()
        before_apply_events = self._event_count(kernel)
        downstream_before_apply = {
            slot
            for slot in before_apply.artifact_heads
            if slot.startswith(
                ("visual/", "delivery/", "chat-delivery/", "review-marks/visual")
            )
        }
        new_blueprint_ref, committed = planning.apply_confirmed_plan(
            command_id="apply-v22-application-must-invalidate-downstream",
            expected_revision=before_apply.revision,
            plan_confirmation_ref=changed_confirmation_ref,
            new_blueprint=new_blueprint,
        )

        self.assertEqual(committed.revision, before_apply.revision + 1)
        self.assertEqual(self._event_count(kernel), before_apply_events + 1)
        self.assertEqual(
            committed.artifact_heads["content/reading-deck-blueprint"],
            new_blueprint_ref,
        )
        self.assertNotEqual(new_blueprint_ref, blueprint_ref)
        self.assertEqual(committed.gate_status["G0"], "open")
        self.assertEqual(
            {gate: committed.gate_status[gate] for gate in ("G1", "G2", "G3", "G4")},
            {"G1": "locked", "G2": "locked", "G3": "locked", "G4": "locked"},
        )
        for slot in (
            "gate/G0/confirmation",
            "agent/task/active",
        ):
            self.assertNotIn(slot, committed.artifact_heads)
        for slot in downstream_before_apply:
            self.assertNotIn(slot, committed.artifact_heads)
        self.assertEqual(
            kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))["payload"],
            blueprint,
        )
        for reference in legacy_downstream_refs.values():
            self.assertTrue(
                kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]
            )
        invalidated_task = kernel.artifacts.resolve(
            ArtifactReference.parse(
                committed.artifact_heads[f"agent/task/{active_task['task_id']}"]
            )
        )["payload"]
        self.assertEqual(invalidated_task["status"], "invalidated")

    def test_confirm_replay_after_changed_plan_application_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-plan-before-confirm-replay-after-application",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="整套修改方案已准备好进入可信确认。",
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        confirmation_arguments = {
            "command_id": "confirm-v22-replay-after-changed-application",
            "expected_revision": kernel.load().revision,
            "plan_ref": proposed_ref,
            "challenge_id": str(context["challenge_id"]),
            "challenge_revision": int(context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(**confirmation_arguments)
            )
        new_blueprint = self._changed_blueprint(
            blueprint,
            source_version="reading-v2-before-confirm-replay-after-application",
            reason="apply-confirmed-content-review-plan-before-confirm-replay",
        )
        planning.apply_confirmed_plan(
            command_id="apply-v22-before-confirm-replay-after-application",
            expected_revision=kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
            new_blueprint=new_blueprint,
        )

        before = kernel.load()
        before_events = self._event_count(kernel)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replayed_confirmation_ref, replayed_confirmed_plan_ref, replayed_state = (
                planning.confirm_revision_plan(**confirmation_arguments)
            )

        self.assertEqual(replayed_confirmation_ref, confirmation_ref)
        self.assertEqual(replayed_confirmed_plan_ref, confirmed_plan_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_confirm_replay_after_no_change_application_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review(all_approved=True)
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-no-change-plan-before-confirm-replay",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="全部页面认可，确认后进入无需重写内容的路径。",
            all_keep=True,
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        confirmation_arguments = {
            "command_id": "confirm-v22-replay-after-no-change-application",
            "expected_revision": kernel.load().revision,
            "plan_ref": proposed_ref,
            "challenge_id": str(context["challenge_id"]),
            "challenge_revision": int(context["challenge_revision"]),
            "host_confirmation_assertion": signed_assertion(context),
        }
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(**confirmation_arguments)
            )
        planning.apply_no_change_plan(
            command_id="apply-v22-no-change-before-confirm-replay",
            expected_revision=kernel.load().revision,
            plan_confirmation_ref=confirmation_ref,
        )

        before = kernel.load()
        before_events = self._event_count(kernel)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            replayed_confirmation_ref, replayed_confirmed_plan_ref, replayed_state = (
                planning.confirm_revision_plan(**confirmation_arguments)
            )

        self.assertEqual(replayed_confirmation_ref, confirmation_ref)
        self.assertEqual(replayed_confirmed_plan_ref, confirmed_plan_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_changed_plan_application_replay_after_later_blueprint_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-plan-before-application-replay",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="先应用经确认的方案，再验证历史应用回执。",
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-before-application-replay",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        new_blueprint = self._changed_blueprint(
            blueprint,
            source_version="reading-v2-before-application-replay",
            reason="apply-confirmed-content-review-plan-before-application-replay",
        )
        application_arguments = {
            "command_id": "apply-v22-replay-after-later-blueprint",
            "expected_revision": kernel.load().revision,
            "plan_confirmation_ref": confirmation_ref,
            "new_blueprint": new_blueprint,
        }
        original_new_blueprint_ref, _applied_state = (
            planning.apply_confirmed_plan(**application_arguments)
        )
        later_blueprint_ref, _later_blueprint = self._publish_later_blueprint(
            kernel,
            new_blueprint,
            command_id="publish-v22-later-blueprint-before-application-replay",
            source_version="reading-v3-after-application-replay",
            reason="later-reading-deck-before-application-replay",
        )

        self.assertNotEqual(later_blueprint_ref, original_new_blueprint_ref)
        before = kernel.load()
        before_events = self._event_count(kernel)
        replayed_blueprint_ref, replayed_state = planning.apply_confirmed_plan(
            **application_arguments
        )

        self.assertEqual(replayed_blueprint_ref, original_new_blueprint_ref)
        self.assertNotEqual(replayed_blueprint_ref, later_blueprint_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_no_change_application_replay_after_later_review_plan_returns_original_receipt_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review(all_approved=True)
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-no-change-plan-before-application-replay",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="先完成无内容改写应用，再建立下一轮全稿审核。",
            all_keep=True,
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-no-change-before-application-replay",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        application_arguments = {
            "command_id": "apply-v22-no-change-replay-after-later-plan",
            "expected_revision": kernel.load().revision,
            "plan_confirmation_ref": confirmation_ref,
        }
        first_applied_plan_ref, _applied_state = planning.apply_no_change_plan(
            **application_arguments
        )
        later_blueprint_ref, later_blueprint = self._publish_later_blueprint(
            kernel,
            blueprint,
            command_id="publish-v22-later-blueprint-before-no-change-replay",
            source_version="reading-v2-after-no-change-application-replay",
            reason="later-reading-deck-before-no-change-application-replay",
        )
        submit_gate_via_command(
            kernel,
            later_blueprint_ref,
            gate_type="evidence",
            command_prefix="later-no-change-replay-evidence",
        )
        submit_gate_via_command(
            kernel,
            later_blueprint_ref,
            gate_type="presales-reading",
            command_prefix="later-no-change-replay-reading",
        )
        ContentHardGateService(kernel).accept_current_content(
            command_id="later-no-change-replay-accept",
            expected_revision=kernel.load().revision,
        )
        later_session, _session_state = ReviewSessionService(kernel).open_or_resume(
            command_id="open-v22-later-review-before-no-change-replay",
            expected_revision=kernel.load().revision,
            review_type="content-full-deck",
            target_artifact_ref=later_blueprint_ref,
            source_version=str(later_blueprint["source_version"]),
            target_revision=kernel.load().revision,
            open_policy="foreground-if-waiting",
        )
        later_batch_id = "later-v22-no-change-application-replay-batch"
        decisions = decision_service_type()(kernel)
        for index, slide in enumerate(later_blueprint["slides"]):
            decisions.save(
                command_id=f"save-later-no-change-replay-page-{index}",
                expected_revision=kernel.load().revision,
                review_session_id=str(later_session["review_session_id"]),
                review_batch_id=later_batch_id,
                slide_id=str(slide["slide_id"]),
                decision="approved",
                comment="",
            )
        later_batch_service = batch_service_type()(kernel)
        later_submission_context = later_batch_service.submission_context(
            review_session_id=str(later_session["review_session_id"]),
            review_batch_id=later_batch_id,
        )
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            later_batch_ref, _follow_up, _submitted_state = (
                later_batch_service.submit_review_batch(
                    command_id="submit-v22-later-review-before-no-change-replay",
                    expected_revision=kernel.load().revision,
                    review_session_id=str(later_session["review_session_id"]),
                    review_batch_id=later_batch_id,
                    challenge_id=str(later_submission_context["challenge_id"]),
                    challenge_revision=int(
                        later_submission_context["challenge_revision"]
                    ),
                    host_confirmation_assertion=signed_assertion(
                        later_submission_context
                    ),
                )
            )
        later_plan_ref, _later_plan_state = planning.save_revision_plan(
            **self._plan_arguments(
                command_id="save-v22-later-plan-before-no-change-replay",
                expected_revision=kernel.load().revision,
                submitted_batch_ref=later_batch_ref,
                blueprint=later_blueprint,
                summary="下一轮全稿审核已经形成新的整套修改方案。",
                all_keep=True,
            )
        )

        self.assertNotEqual(later_plan_ref, first_applied_plan_ref)
        before = kernel.load()
        before_events = self._event_count(kernel)
        replayed_plan_ref, replayed_state = planning.apply_no_change_plan(
            **application_arguments
        )

        self.assertEqual(replayed_plan_ref, first_applied_plan_ref)
        self.assertNotEqual(replayed_plan_ref, later_plan_ref)
        self.assertEqual(replayed_state.revision, before.revision)
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_changed_plan_application_replay_rejects_changed_expected_revision_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-plan-before-application-semantic-collision",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="验证内容改写应用的 expected_revision 是命令语义。",
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-before-application-semantic-collision",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        application_arguments = {
            "command_id": "apply-v22-changed-plan-semantic-collision",
            "expected_revision": kernel.load().revision,
            "plan_confirmation_ref": confirmation_ref,
            "new_blueprint": self._changed_blueprint(
                blueprint,
                source_version="reading-v2-application-semantic-collision",
                reason="changed-application-semantic-collision",
            ),
        }
        planning.apply_confirmed_plan(**application_arguments)
        before = kernel.load()
        before_events = self._event_count(kernel)

        with self.assertRaisesRegex(
            ContractValidationError, "Processed command has different semantics"
        ):
            planning.apply_confirmed_plan(
                **{**application_arguments, "expected_revision": before.revision}
            )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_no_change_application_replay_rejects_changed_expected_revision_without_writes(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review(all_approved=True)
        )
        planning = planning_service_type()(kernel)
        plan_arguments = self._plan_arguments(
            command_id="save-v22-no-change-before-application-semantic-collision",
            expected_revision=kernel.load().revision,
            submitted_batch_ref=submitted_batch_ref,
            blueprint=blueprint,
            summary="验证无内容改写应用的 expected_revision 是命令语义。",
            all_keep=True,
        )
        proposed_ref, _proposed_state = planning.save_revision_plan(**plan_arguments)
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _confirmed_state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-before-no-change-semantic-collision",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        application_arguments = {
            "command_id": "apply-v22-no-change-semantic-collision",
            "expected_revision": kernel.load().revision,
            "plan_confirmation_ref": confirmation_ref,
        }
        planning.apply_no_change_plan(**application_arguments)
        before = kernel.load()
        before_events = self._event_count(kernel)

        with self.assertRaisesRegex(
            ContractValidationError, "Processed command has different semantics"
        ):
            planning.apply_no_change_plan(
                **{**application_arguments, "expected_revision": before.revision}
            )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(self._event_count(kernel), before_events)

    def test_withdrawal_context_rejects_current_submitted_batch_after_plan_proposal_without_writes(
        self,
    ) -> None:
        kernel, blueprint, session, service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning_service_type()(kernel).save_revision_plan(
            command_id="save-v22-plan-before-withdrawal-context",
            expected_revision=kernel.load().revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="整套修改方案已经提出，撤回应在此停止。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "保留当前页。" if index == 0 else "补足来源位置。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        )
        before = kernel.load()
        before_event_count = len(list((kernel.project_root / "kernel" / "events").glob("r*.json")))

        with self.assertRaises(ContentWorkflowError) as raised:
            service.withdrawal_context(
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(
            len(list((kernel.project_root / "kernel" / "events").glob("r*.json"))),
            before_event_count,
        )

    def test_withdraw_rejects_current_submitted_batch_after_plan_proposal_without_writes(
        self,
    ) -> None:
        kernel, blueprint, session, service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning_service_type()(kernel).save_revision_plan(
            command_id="save-v22-plan-before-withdrawal-command",
            expected_revision=kernel.load().revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="整套修改方案已经提出，撤回应在此停止。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "保留当前页。" if index == 0 else "补足来源位置。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        )
        before = kernel.load()
        before_event_count = len(list((kernel.project_root / "kernel" / "events").glob("r*.json")))

        with self.assertRaises(ContentWorkflowError) as raised:
            service.withdraw_review_batch(
                command_id="reject-v22-withdraw-after-plan-proposal",
                expected_revision=before.revision,
                review_session_id=str(session["review_session_id"]),
                review_batch_id="withdrawable-v22-batch",
                reason="计划提出后不能再撤回。",
                challenge_id="irrelevant-after-plan-proposal",
                challenge_revision=before.revision,
                host_confirmation_assertion="irrelevant-after-plan-proposal",
            )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(
            len(list((kernel.project_root / "kernel" / "events").glob("r*.json"))),
            before_event_count,
        )
        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")

    def test_chief_revision_plan_must_target_exact_current_batch_pages(self) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        actions = [
            {
                "slide_id": str(slide["slide_id"]),
                "action": "keep",
                "rationale": "当前页已纳入整稿判断。",
            }
            for slide in blueprint["slides"]
        ]
        actions[-1]["slide_id"] = "unknown-slide"

        with self.assertRaisesRegex(
            ContractValidationError, "exact current batch pages"
        ):
            planning_service_type()(kernel).save_revision_plan(
                command_id="reject-v22-plan-with-unknown-page",
                expected_revision=kernel.load().revision,
                review_batch_ref=submitted_batch_ref,
                producer_id="presales-solution-chief",
                summary="不允许用不存在的页面替代当前审核页。",
                page_actions=actions,
            )

    def test_trusted_confirmation_locks_current_whole_deck_plan_without_revising_content(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        proposed_ref, _proposed = planning.save_revision_plan(
            command_id="save-v22-plan-for-confirmation",
            expected_revision=kernel.load().revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="逐页修订已收口为一套可确认的整稿方案。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "保留当前页。" if index == 0 else "补足来源定位。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        )
        before = kernel.load()
        protected_heads = {
            key: before.artifact_heads.get(key, "")
            for key in (
                "content/reading-deck-blueprint",
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
                "gate/G0/confirmation",
                "content/page-decisions",
                "content/review-batch",
            )
        }
        context = planning.confirmation_context(plan_ref=proposed_ref)
        assertion = signed_assertion(context)

        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, confirmed_plan_ref, committed = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-whole-deck-plan",
                    expected_revision=before.revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=assertion,
                )
            )
            replayed = planning.confirm_revision_plan(
                command_id="confirm-v22-whole-deck-plan",
                expected_revision=before.revision,
                plan_ref=proposed_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )

        confirmation = kernel.artifacts.resolve(
            ArtifactReference.parse(confirmation_ref)
        )["payload"]
        confirmed_plan = kernel.artifacts.resolve(
            ArtifactReference.parse(confirmed_plan_ref)
        )["payload"]
        self.assertEqual(
            ArtifactReference.parse(confirmation_ref).kind,
            "content-batch-plan-confirmation",
        )
        self.assertEqual(confirmation["revision_plan_ref"], proposed_ref)
        self.assertEqual(confirmation["review_batch_ref"], submitted_batch_ref)
        self.assertEqual(confirmation["source_version"], before.artifact_heads[
            "content/reading-deck-blueprint"
        ])
        self.assertEqual(confirmed_plan["status"], "confirmed")
        self.assertEqual(confirmed_plan["supersedes_ref"], proposed_ref)
        self.assertEqual(
            committed.artifact_heads["content/revision-plan"], confirmed_plan_ref
        )
        self.assertEqual(
            committed.artifact_heads["content/revision-plan-confirmation"],
            confirmation_ref,
        )
        self.assertEqual(
            {
                key: committed.artifact_heads.get(key, "")
                for key in protected_heads
            },
            protected_heads,
        )
        self.assertEqual(replayed[0], confirmation_ref)
        self.assertEqual(replayed[1], confirmed_plan_ref)
        self.assertEqual(replayed[2].revision, committed.revision)

    def test_apply_confirmed_plan_publishes_new_source_and_clears_review_current_heads(
        self,
    ) -> None:
        kernel, blueprint, session, _service, submitted_batch_ref = (
            self._submitted_review()
        )
        planning = planning_service_type()(kernel)
        proposed_ref, _state = planning.save_revision_plan(
            command_id="save-v22-plan-for-application",
            expected_revision=kernel.load().revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="按逐页意见生成新的完整阅读稿。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep" if index == 0 else "revise",
                    "rationale": "保留当前页。" if index == 0 else "补足来源定位。",
                }
                for index, slide in enumerate(blueprint["slides"])
            ],
        )
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-plan-for-application",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        new_blueprint = copy.deepcopy(blueprint)
        new_blueprint["source_version"] = "reading-v2-after-review"
        new_blueprint["hard_gate_refs"] = []
        new_blueprint["repair_history"].append(
            {"reason": "apply-confirmed-content-review-plan"}
        )
        before = kernel.load()
        new_blueprint_ref, committed = planning.apply_confirmed_plan(
            command_id="apply-v22-confirmed-plan",
            expected_revision=before.revision,
            plan_confirmation_ref=confirmation_ref,
            new_blueprint=new_blueprint,
        )

        self.assertNotEqual(
            new_blueprint_ref, before.artifact_heads["content/reading-deck-blueprint"]
        )
        self.assertEqual(
            committed.artifact_heads["content/reading-deck-blueprint"],
            new_blueprint_ref,
        )
        for slot in (
            "content/gate/evidence",
            "content/gate/presales-reading",
            "content/acceptance",
            "content/page-decisions",
            "content/review-batch",
            "content/revision-plan",
            "content/revision-plan-confirmation",
            "review/session/current/content-full-deck",
        ):
            self.assertNotIn(slot, committed.artifact_heads)
        old_session = kernel.artifacts.resolve(
            ArtifactReference.parse(
                committed.artifact_heads[
                    f"review/session/{session['review_session_id']}"
                ]
            )
        )["payload"]
        self.assertEqual(old_session["status"], "superseded")
        self.assertEqual(
            kernel.artifacts.resolve(ArtifactReference.parse(submitted_batch_ref))["payload"]
            ["status"],
            "submitted",
        )

    def test_apply_no_change_plan_makes_current_content_user_reviewable_for_g0(
        self,
    ) -> None:
        kernel, blueprint, _session, _service, submitted_batch_ref = (
            self._submitted_review(all_approved=True)
        )
        planning = planning_service_type()(kernel)
        proposed_ref, _state = planning.save_revision_plan(
            command_id="save-v22-no-change-plan",
            expected_revision=kernel.load().revision,
            review_batch_ref=submitted_batch_ref,
            producer_id="presales-solution-chief",
            summary="本轮完整审核全部认可，无需改写内容。",
            page_actions=[
                {
                    "slide_id": str(slide["slide_id"]),
                    "action": "keep",
                    "rationale": "当前页认可。",
                }
                for slide in blueprint["slides"]
            ],
        )
        context = planning.confirmation_context(plan_ref=proposed_ref)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmation_ref, _confirmed_plan_ref, _state = (
                planning.confirm_revision_plan(
                    command_id="confirm-v22-no-change-plan",
                    expected_revision=kernel.load().revision,
                    plan_ref=proposed_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
            )
        before = kernel.load()
        applied_plan_ref, committed = planning.apply_no_change_plan(
            command_id="apply-v22-no-change-plan",
            expected_revision=before.revision,
            plan_confirmation_ref=confirmation_ref,
        )

        applied_plan = kernel.artifacts.resolve(
            ArtifactReference.parse(applied_plan_ref)
        )["payload"]
        self.assertEqual(applied_plan["status"], "applied")
        self.assertEqual(
            committed.artifact_heads["content/reading-deck-blueprint"],
            before.artifact_heads["content/reading-deck-blueprint"],
        )
        self.assertEqual(
            committed.artifact_heads["content/review-batch"], submitted_batch_ref
        )
        self.assertEqual(
            committed.artifact_heads["content/revision-plan"], applied_plan_ref
        )
        self.assertEqual(
            committed.artifact_heads["content/revision-plan-confirmation"],
            confirmation_ref,
        )
        blueprint_ref = str(committed.artifact_heads["content/reading-deck-blueprint"])
        self.assertEqual(committed.gate_status["G0"], "user-reviewable")
        g0_context = GateConfirmationPolicy(kernel).context("G0")
        self.assertEqual(g0_context["source_version"], blueprint_ref)
        self.assertEqual(
            g0_context["evidence_refs"],
            [
                str(committed.artifact_heads["content/acceptance"]),
                blueprint_ref,
                submitted_batch_ref,
                applied_plan_ref,
                confirmation_ref,
            ],
        )
        with self.assertRaises(GateBlockedError) as unsigned:
            ContentService(kernel).confirm_g0(
                "reject-v22-g0-without-fresh-trusted-assertion",
                committed.revision,
                host_confirmation_assertion="",
                source_version=str(g0_context["source_version"]),
                challenge_id=str(g0_context["challenge_id"]),
                challenge_revision=int(g0_context["challenge_revision"]),
            )
        self.assertIn("trusted-host-assertion-invalid", unsigned.exception.missing_evidence)
        with patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            confirmed = ContentService(kernel).confirm_g0(
                "confirm-v22-g0-after-applied-review",
                committed.revision,
                host_confirmation_assertion=signed_assertion(g0_context),
                source_version=str(g0_context["source_version"]),
                challenge_id=str(g0_context["challenge_id"]),
                challenge_revision=int(g0_context["challenge_revision"]),
            )
        self.assertEqual(confirmed.gate_status["G0"], "passed")

        before = kernel.load()
        before_events = self._event_count(kernel)
        with self.assertRaisesRegex(
            ContentWorkflowError,
            "already has an applied revision plan",
        ):
            planning.save_revision_plan(
                **self._plan_arguments(
                    command_id="reject-v22-second-plan-after-applied-g0",
                    expected_revision=before.revision,
                    submitted_batch_ref=submitted_batch_ref,
                    blueprint=blueprint,
                    summary="不允许用同一已应用审核批次重新提出方案。",
                    all_keep=True,
                )
            )
        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(kernel.load().gate_status, before.gate_status)
        self.assertEqual(self._event_count(kernel), before_events)


if __name__ == "__main__":
    unittest.main()
