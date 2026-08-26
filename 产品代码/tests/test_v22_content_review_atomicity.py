from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.content_review.planning_service import (
    ContentRevisionPlanningService,
)
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.errors import (
    ContentWorkflowError,
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_review_projection import accepted_review
from tests.test_v22_content_repair_loop import build_content
from tests.v22_hard_gate_fixtures import semantic_checks


def accepted_multi_slide_review(kernel: ProjectKernel, slide_count: int = 3):
    blueprint_ref = build_content(kernel, slide_count=slide_count)
    blueprint_publication_revision = kernel.load().revision
    gates = ContentHardGateService(kernel)
    gates.run_evidence_gate(
        command_id="evidence-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=semantic_checks("evidence", blueprint_ref),
        reviewer_mode="isolated-review-task",
    )
    gates.run_presales_reading_gate(
        command_id="reading-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=semantic_checks("presales-reading", blueprint_ref),
        reviewer_mode="isolated-review-task",
    )
    state = kernel.load()
    _session_ref, session, state = ReviewSessionService(kernel).open_or_resume(
        command_id="open-review",
        expected_revision=state.revision,
        review_type="content-full-deck",
        target_artifact_ref=blueprint_ref,
        source_version="content-v1",
        source_revision=blueprint_publication_revision,
        open_policy="foreground-if-waiting",
    )
    return blueprint_ref, session, state


class ContentReviewAtomicityTests(unittest.TestCase):
    def test_batch_orders_the_exact_complete_set_and_rejects_stale_scope(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel)
            decisions = ContentDecisionService(kernel)
            for order in (3, 1, 2):
                decisions.save(
                    command_id=f"approve-{order}",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id=f"S{order:02d}",
                    decision="approved",
                    comment="",
                )
            before = kernel.load()
            batches = ContentReviewBatchService(kernel)
            for source_version, session_id, error in (
                ("content-v0", session["review_session_id"], ReviewSourceStaleError),
                ("content-v1", "wrong-session", ReviewSourceStaleError),
            ):
                with self.subTest(source=source_version, session=session_id), self.assertRaises(error):
                    batches.submit(
                        command_id=f"invalid-{source_version}-{session_id}",
                        expected_revision=before.revision,
                        review_session_id=session_id,
                        source_version=source_version,
                    )
                self.assertEqual(kernel.load(), before)
            _batch_ref, batch, _state = batches.submit(
                command_id="submit-ordered",
                expected_revision=before.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertEqual(batch["slide_ids"], ["S01", "S02", "S03"])
            self.assertEqual(
                batch["counts"],
                {"approved": 3, "modify": 0, "merge-or-delete": 0, "evidence": 0},
            )

    def test_submit_is_complete_frozen_idempotent_and_semantically_bound(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            batches = ContentReviewBatchService(kernel)
            before = kernel.load()
            with self.assertRaises(GateBlockedError):
                batches.submit(
                    command_id="incomplete",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )
            self.assertEqual(kernel.load(), before)

            ContentDecisionService(kernel).save(
                command_id="approve-s01",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, batch, submitted = batches.submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertEqual(batch["reading_blueprint_ref"], blueprint_ref)
            self.assertTrue(batch["immutable_after_submit"])
            self.assertEqual(submitted.gate_status["G0"], "locked")
            replay_ref, replay, replayed = batches.submit(
                command_id="submit",
                expected_revision=submitted.revision - 1,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertEqual((replay_ref, replay, replayed), (batch_ref, batch, submitted))
            with self.assertRaises(ContractValidationError):
                batches.submit(
                    command_id="submit",
                    expected_revision=submitted.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v2",
                )
            frozen = kernel.load()
            with self.assertRaises(ContentWorkflowError):
                ContentDecisionService(kernel).save(
                    command_id="mutate-frozen",
                    expected_revision=frozen.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="modify",
                    comment="不应写入",
                )
            self.assertEqual(kernel.load(), frozen)

    def test_withdraw_preserves_submitted_bytes_and_allows_a_new_batch(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            decisions = ContentDecisionService(kernel)
            batches = ContentReviewBatchService(kernel)
            decisions.save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, batch, submitted = batches.submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            withdrawn_ref, withdrawn, state = batches.withdraw(
                command_id="withdraw",
                expected_revision=submitted.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertNotEqual(withdrawn_ref, batch_ref)
            self.assertEqual(withdrawn["status"], "withdrawn")
            self.assertEqual(
                kernel.artifacts.resolve(ArtifactReference.parse(batch_ref))["payload"],
                batch,
            )
            decisions.save(
                command_id="revise",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment="修改后重新提交",
            )
            replacement_ref, replacement, _state = batches.submit(
                command_id="resubmit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertNotEqual(replacement_ref, batch_ref)
            self.assertEqual(replacement["supersedes_ref"], withdrawn_ref)

    def test_corrupt_decision_and_transaction_failure_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            kernel.commit(
                command_id="corrupt-decision-head",
                expected_revision=state.revision,
                event_type="test.corrupt-decision",
                artifact_updates={
                    "content/review/decision/S01": ("wrong-kind", {"slide_id": "S01"})
                },
            )
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                ContentReviewBatchService(kernel).submit(
                    command_id="reject-corrupt",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )
            self.assertEqual(kernel.load(), before)

        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p2")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            before = kernel.load()
            object_paths = set(kernel.artifacts.objects_root.rglob("*.json"))
            with patch.object(kernel, "commit", side_effect=RuntimeError("disk unavailable")):
                with self.assertRaises(RuntimeError):
                    ContentReviewBatchService(kernel).submit(
                        command_id="atomic-failure",
                        expected_revision=before.revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                    )
            self.assertEqual(kernel.load(), before)
            self.assertEqual(set(kernel.artifacts.objects_root.rglob("*.json")), object_paths)

    def test_concurrent_submissions_have_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            expected_revision = kernel.load().revision

            def submit(command_id: str):
                try:
                    return ContentReviewBatchService(kernel).submit(
                        command_id=command_id,
                        expected_revision=expected_revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                    )
                except (RevisionConflictError, ContentWorkflowError) as error:
                    return error

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(submit, ("submit-a", "submit-b")))
            self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
            self.assertEqual(kernel.load().revision, expected_revision + 1)

    def test_withdraw_requires_the_submitted_decisions_to_remain_current(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            _batch_ref, _batch, submitted = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            state = kernel.commit(
                command_id="remove-current-decision",
                expected_revision=submitted.revision,
                event_type="test.current-decision-removed",
                artifact_updates={},
                artifact_removals=("content/review/decision/S01",),
            )
            before = kernel.load()
            with self.assertRaises(ContentWorkflowError):
                ContentReviewBatchService(kernel).withdraw(
                    command_id="reject-stale-withdrawal",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )
            self.assertEqual(kernel.load(), before)

    def test_withdraw_replay_is_exact_and_a_revision_plan_freezes_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            _batch_ref, _batch, submitted = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            batches = ContentReviewBatchService(kernel)
            first = batches.withdraw(
                command_id="withdraw",
                expected_revision=submitted.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            self.assertEqual(
                batches.withdraw(
                    command_id="withdraw",
                    expected_revision=submitted.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                ),
                first,
            )
            with self.assertRaises(ContractValidationError):
                batches.withdraw(
                    command_id="withdraw",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v2",
                )

        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p2")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, submitted = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            ContentRevisionPlanningService(kernel).save_plan(
                command_id="plan",
                expected_revision=submitted.revision,
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
            with self.assertRaises(ContentWorkflowError):
                ContentReviewBatchService(kernel).withdraw(
                    command_id="frozen-withdraw",
                    expected_revision=before.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )
            self.assertEqual(kernel.load(), before)

    def test_corrupt_submitted_batch_fails_closed_without_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, session, state = accepted_multi_slide_review(kernel, 1)
            ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            batch_ref, _batch, _submitted = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            path = kernel.artifacts.path_for(ArtifactReference.parse(batch_ref))
            original = path.read_bytes()
            before = kernel.load()
            try:
                path.write_text("{}", encoding="utf-8")
                with self.assertRaises(ContractValidationError):
                    ContentReviewBatchService(kernel).withdraw(
                        command_id="reject-corrupt-batch",
                        expected_revision=before.revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                    )
                self.assertEqual(kernel.load(), before)
            finally:
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
