from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
from ai_ppt_studio.application.content_review.projection_service import ContentReviewProjectionService
from ai_ppt_studio.domains.content.page_decisions import validate_page_decision
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from ai_ppt_studio.errors import (
    ContentWorkflowError,
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v16_content_page_decisions import (
    accepted_v22_review,
    approve_v22,
    authority_snapshot_v22,
    valid_v22_batch,
    valid_v22_decision,
)


def artifact_ref(kind: str, marker: str) -> str:
    return f"artifact://{kind}/{marker * 64}"


def resolve_payload(kernel: ProjectKernel, reference: str) -> dict:
    return kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]


class ContentReviewBatchContractTests(unittest.TestCase):
    def test_batch_requires_exact_ordered_complete_slide_set_and_counts(self) -> None:
        refs = [
            artifact_ref("content-page-decision", "b"),
            artifact_ref("content-page-decision", "c"),
        ]
        payload = valid_v22_batch(
            slide_ids=["S01", "S02"],
            decision_refs=refs,
            counts={
                "approved": 1,
                "modify": 1,
                "evidence": 0,
                "merge-or-delete": 0,
            },
        )
        self.assertEqual(validate_content_review_batch(payload), payload)
        malformed = (
            {**payload, "decision_refs": [refs[0], refs[0]]},
            {
                **payload,
                "counts": {
                    "approved": 3,
                    "modify": 0,
                    "evidence": 0,
                    "merge-or-delete": 0,
                },
            },
            {
                **payload,
                "reading_blueprint_ref": artifact_ref("wrong-kind", "a"),
            },
            {**payload, "unexpected": True},
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate), self.assertRaises(
                ContractValidationError
            ):
                validate_content_review_batch(candidate)

    def test_completed_false_is_an_incomplete_batch(self) -> None:
        with self.assertRaises(ContractValidationError):
            validate_page_decision(valid_v22_decision(status="draft"))
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint, _session_ref, session, _state = accepted_v22_review(
                kernel, 2
            )
            approve_v22(kernel, session, "S01")
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(GateBlockedError) as caught:
                ContentReviewBatchService(kernel).submit(
                    command_id="incomplete",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version=session["source_version"],
                )
            self.assertIn("page-decisions-incomplete:1", caught.exception.missing_evidence)
            self.assertEqual(authority_snapshot_v22(kernel), before)

    def test_submitted_batch_lifecycle_fields_are_immutable(self) -> None:
        original = validate_content_review_batch(valid_v22_batch())
        withdrawn = validate_content_review_batch(
            {
                **original,
                "status": "withdrawn",
                "withdrawn_at": "2026-08-15T10:00:00+00:00",
                "supersedes_ref": artifact_ref("content-review-batch", "d"),
            }
        )
        self.assertEqual(original["status"], "submitted")
        self.assertEqual(withdrawn["status"], "withdrawn")
        for malformed in (
            {**original, "immutable_after_submit": False},
            {**original, "status": "superseded"},
            {**withdrawn, "withdrawn_at": ""},
        ):
            with self.subTest(malformed=malformed), self.assertRaises(
                ContractValidationError
            ):
                validate_content_review_batch(malformed)


class ContentReviewBatchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kernel = ProjectKernel.initialize(
            Path(self.temp.name), project_id="batch-project"
        )
        self.blueprint_ref, _session_ref, self.session, _state = accepted_v22_review(
            self.kernel, slide_count=4
        )
        self.source_version = self.session["source_version"]
        self.review_session_id = self.session["review_session_id"]
        self.decisions = ContentDecisionService(self.kernel)
        self.review = ContentReviewBatchService(self.kernel)
        self.command_index = 0

    def save(
        self,
        slide_id: str,
        decision: str,
        *,
        comment: str = "",
        command_id: str | None = None,
        expected_revision: int | None = None,
    ):
        self.command_index += 1
        return self.decisions.save(
            command_id=command_id or f"save-{slide_id}-{self.command_index}",
            expected_revision=(
                self.kernel.load().revision
                if expected_revision is None
                else expected_revision
            ),
            review_session_id=self.review_session_id,
            source_version=self.source_version,
            slide_id=slide_id,
            decision=decision,
            comment=comment,
        )

    def save_all(self) -> None:
        decisions = (
            ("S01", "approved", ""),
            ("S02", "modify", "修改第二页完整意见"),
            ("S03", "evidence", "补充第三页证据"),
            ("S04", "merge-or-delete", "与第三页合并"),
        )
        for slide_id, decision, comment in decisions:
            self.save(slide_id, decision, comment=comment)

    def submit(
        self,
        *,
        command_id: str = "submit-batch",
        expected_revision: int | None = None,
        source_version: str | None = None,
        review_session_id: str | None = None,
    ):
        return self.review.submit(
            command_id=command_id,
            expected_revision=(
                self.kernel.load().revision
                if expected_revision is None
                else expected_revision
            ),
            review_session_id=review_session_id or self.review_session_id,
            source_version=source_version or self.source_version,
        )

    def current_batch(self) -> tuple[str, dict]:
        reference = self.kernel.load().artifact_heads["content/review-batch"]
        return reference, resolve_payload(self.kernel, reference)

    def withdraw(self, command_id: str = "withdraw-batch"):
        return self.review.withdraw(
            command_id=command_id,
            expected_revision=self.kernel.load().revision,
            review_session_id=self.review_session_id,
            source_version=self.source_version,
        )

    def test_submission_context_reports_exact_incomplete_progress(self) -> None:
        self.save("S01", "approved")
        self.save("S02", "modify", comment="完整修改意见")
        projection = ContentReviewProjectionService(self.kernel).project(
            self.review_session_id
        )
        self.assertEqual(
            projection["progress"],
            {"completed": 2, "total": 4, "remaining": 2, "unsaved": 0},
        )
        before = authority_snapshot_v22(self.kernel)
        with self.assertRaises(GateBlockedError) as caught:
            self.submit(command_id="incomplete-submit")
        self.assertIn("page-decisions-incomplete:2", caught.exception.missing_evidence)
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_submission_context_binds_revision_source_set_and_ordered_refs(self) -> None:
        self.save_all()
        projection = ContentReviewProjectionService(self.kernel).project(
            self.review_session_id
        )
        self.assertEqual(projection["reading_blueprint_ref"], self.blueprint_ref)
        self.assertEqual(projection["source_version"], self.source_version)
        self.assertEqual(
            [row["slide_id"] for row in projection["decisions"]],
            ["S01", "S02", "S03", "S04"],
        )
        self.assertEqual(
            projection["authoritative_revision"], self.kernel.load().revision
        )

    def test_submit_freezes_exact_batch_and_has_no_downstream_side_effects(self) -> None:
        self.save_all()
        before = self.kernel.load()
        before_heads = dict(before.artifact_heads)
        expected_refs = [
            before_heads[f"content/review/decision/S{order:02d}"]
            for order in range(1, 5)
        ]
        batch_ref, batch, after = self.submit()
        self.assertEqual(after.revision, before.revision + 1)
        changed = {
            slot
            for slot in set(before_heads) | set(after.artifact_heads)
            if before_heads.get(slot) != after.artifact_heads.get(slot)
        }
        self.assertEqual(
            changed,
            {"content/review-batch", "review/session/content-full-deck"},
        )
        self.assertEqual(batch["status"], "submitted")
        self.assertEqual(
            batch["counts"],
            {
                "approved": 1,
                "modify": 1,
                "evidence": 1,
                "merge-or-delete": 1,
            },
        )
        self.assertEqual(batch["decision_refs"], expected_refs)
        self.assertEqual(after.artifact_heads["content/reading-blueprint"], self.blueprint_ref)
        self.assertEqual(after.gate_status, before.gate_status)
        self.assertEqual(resolve_payload(self.kernel, batch_ref), batch)
        frozen = authority_snapshot_v22(self.kernel)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save("S01", "modify", comment="冻结后不可改")
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(authority_snapshot_v22(self.kernel), frozen)

    def test_first_batch_without_withdrawal_allows_same_batch_decision_history(self) -> None:
        self.save_all()
        first_ref = self.kernel.load().artifact_heads["content/review/decision/S01"]
        _replacement_ref, replacement, _state = self.save(
            "S01", "modify", comment="首次审核内再次调整第一页判断"
        )
        before = self.kernel.load()
        self.assertNotIn("content/review-batch", before.artifact_heads)
        self.assertEqual(replacement["supersedes_decision_ref"], first_ref)
        batch_ref, batch, after = self.submit(
            command_id="submit-first-batch-with-decision-history"
        )
        self.assertEqual(after.revision, before.revision + 1)
        self.assertEqual(after.artifact_heads["content/review-batch"], batch_ref)
        self.assertEqual(batch["status"], "submitted")
        self.assertEqual(resolve_payload(self.kernel, first_ref)["status"], "completed")

    def test_stale_source_wrong_batch_revision_and_duplicates_are_zero_write(self) -> None:
        self.save_all()
        before = authority_snapshot_v22(self.kernel)
        cases = (
            (ReviewSourceStaleError, {"source_version": "content-v0"}),
            (ReviewSourceStaleError, {"review_session_id": "wrong-session"}),
            (RevisionConflictError, {"expected_revision": self.kernel.load().revision - 1}),
        )
        for error, changes in cases:
            with self.subTest(error=error.__name__), self.assertRaises(error):
                self.submit(command_id=f"invalid-{error.__name__}", **changes)
            self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_submission_challenge_scope_hmac_source_and_batch_mismatches_are_zero_write(self) -> None:
        self.save_all()
        before = authority_snapshot_v22(self.kernel)
        for index, changes in enumerate(
            (
                {"source_version": "content-v9"},
                {"review_session_id": "visual-professional-session"},
                {"expected_revision": self.kernel.load().revision + 1},
            )
        ):
            with self.subTest(changes=changes), self.assertRaises(
                (ReviewSourceStaleError, RevisionConflictError)
            ):
                self.submit(command_id=f"invalid-scope-{index}", **changes)
            self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_exact_command_replay_changed_replay_and_identity_reuse(self) -> None:
        self.save_all()
        expected_revision = self.kernel.load().revision
        first = self.submit(command_id="single-submit")
        after = authority_snapshot_v22(self.kernel)
        replay = self.submit(
            command_id="single-submit", expected_revision=expected_revision
        )
        self.assertEqual(replay, first)
        self.assertEqual(authority_snapshot_v22(self.kernel), after)
        with self.assertRaises(ContractValidationError):
            self.submit(
                command_id="single-submit",
                expected_revision=expected_revision,
                source_version="content-v2",
            )
        self.assertEqual(authority_snapshot_v22(self.kernel), after)

    def test_concurrent_different_submissions_have_only_one_winner(self) -> None:
        self.save_all()
        revision = self.kernel.load().revision

        def invoke(index: int):
            try:
                return self.submit(
                    command_id=f"submit-concurrent-{index}",
                    expected_revision=revision,
                )
            except Exception as error:  # noqa: BLE001 - assertion inspects type
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(invoke, (1, 2)))
        self.assertEqual(sum(isinstance(item, tuple) for item in results), 1)
        self.assertEqual(
            sum(isinstance(item, (RevisionConflictError, ContentWorkflowError)) for item in results),
            1,
        )

    def test_withdrawal_preserves_old_bytes_clones_decisions_and_allows_resubmit(self) -> None:
        self.save_all()
        submitted_ref, submitted, _state = self.submit()
        old_batch_path = self.kernel.artifacts.path_for(
            ArtifactReference.parse(submitted_ref)
        )
        old_batch_bytes = old_batch_path.read_bytes()
        decision_refs = list(submitted["decision_refs"])
        old_decision_bytes = {
            reference: self.kernel.artifacts.path_for(
                ArtifactReference.parse(reference)
            ).read_bytes()
            for reference in decision_refs
        }
        before_revision = self.kernel.load().revision
        withdrawn_ref, withdrawn, after = self.withdraw()
        self.assertEqual(after.revision, before_revision + 1)
        self.assertNotEqual(withdrawn_ref, submitted_ref)
        self.assertEqual(withdrawn["status"], "withdrawn")
        self.assertEqual(withdrawn["supersedes_ref"], submitted_ref)
        self.assertEqual(old_batch_path.read_bytes(), old_batch_bytes)
        for reference, prior_bytes in old_decision_bytes.items():
            self.assertEqual(
                self.kernel.artifacts.path_for(
                    ArtifactReference.parse(reference)
                ).read_bytes(),
                prior_bytes,
            )
        second_ref, second, _state = self.submit(
            command_id="submit-replacement-batch"
        )
        self.assertNotEqual(second_ref, withdrawn_ref)
        self.assertEqual(second["supersedes_ref"], withdrawn_ref)
        self.assertEqual(second["decision_refs"], decision_refs)

    def test_replacement_context_fails_closed_when_inherited_lineage_is_corrupt(self) -> None:
        self.save_all()
        ancestor_ref = self.kernel.load().artifact_heads["content/review/decision/S01"]
        self.save("S01", "modify", comment="形成第二代决定")
        path = self.kernel.artifacts.path_for(ArtifactReference.parse(ancestor_ref))
        original = path.read_bytes()
        before = authority_snapshot_v22(self.kernel)
        try:
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ContractValidationError):
                ContentReviewProjectionService(self.kernel).project(
                    self.review_session_id
                )
            self.assertEqual(authority_snapshot_v22(self.kernel), before)
        finally:
            path.write_bytes(original)

    def test_replacement_submission_fails_closed_when_inherited_lineage_is_corrupt(self) -> None:
        self.save_all()
        ancestor_ref = self.kernel.load().artifact_heads["content/review/decision/S01"]
        self.save("S01", "modify", comment="形成第二代决定")
        path = self.kernel.artifacts.path_for(ArtifactReference.parse(ancestor_ref))
        original = path.read_bytes()
        before = authority_snapshot_v22(self.kernel)
        try:
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ContractValidationError):
                self.submit(command_id="submit-corrupt-lineage")
            self.assertEqual(authority_snapshot_v22(self.kernel), before)
        finally:
            path.write_bytes(original)

    def test_replacement_context_rejects_a_missing_current_draft_batch_head(self) -> None:
        self.save_all()
        state = self.kernel.load()
        self.kernel.commit(
            command_id="remove-current-S01",
            expected_revision=state.revision,
            event_type="test.remove-current-page-decision",
            artifact_updates={},
            artifact_removals=("content/review/decision/S01",),
        )
        before = authority_snapshot_v22(self.kernel)
        projection = ContentReviewProjectionService(self.kernel).project(
            self.review_session_id
        )
        self.assertEqual(projection["progress"]["remaining"], 1)
        self.assertNotIn("content/review-batch", self.kernel.load().artifact_heads)
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_replacement_submission_rejects_a_missing_current_draft_batch_head(self) -> None:
        self.save_all()
        state = self.kernel.load()
        self.kernel.commit(
            command_id="remove-current-S04",
            expected_revision=state.revision,
            event_type="test.remove-current-page-decision",
            artifact_updates={},
            artifact_removals=("content/review/decision/S04",),
        )
        before = authority_snapshot_v22(self.kernel)
        with self.assertRaises(GateBlockedError):
            self.submit(command_id="submit-with-missing-decision")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_withdrawal_exact_replay_is_idempotent_but_changed_assertion_conflicts(self) -> None:
        self.save_all()
        self.submit()
        revision = self.kernel.load().revision
        first = self.review.withdraw(
            command_id="withdraw-replay-command",
            expected_revision=revision,
            review_session_id=self.review_session_id,
            source_version=self.source_version,
        )
        after = authority_snapshot_v22(self.kernel)
        replay = self.review.withdraw(
            command_id="withdraw-replay-command",
            expected_revision=revision,
            review_session_id=self.review_session_id,
            source_version=self.source_version,
        )
        self.assertEqual(replay, first)
        self.assertEqual(authority_snapshot_v22(self.kernel), after)
        with self.assertRaises(ContractValidationError):
            self.review.withdraw(
                command_id="withdraw-replay-command",
                expected_revision=revision,
                review_session_id=self.review_session_id,
                source_version="content-v2",
            )
        self.assertEqual(authority_snapshot_v22(self.kernel), after)

    def test_withdrawal_requires_the_submitted_batch_decision_set_to_remain_current(self) -> None:
        self.save_all()
        _submitted_ref, submitted, _state = self.submit()
        original_ref = submitted["decision_refs"][0]
        original = resolve_payload(self.kernel, original_ref)
        forged = {**original, "page_decision_id": "forged-current-decision"}
        self.kernel.commit(
            command_id="replace-current-decision-after-submit",
            expected_revision=self.kernel.load().revision,
            event_type="test.replace-current-page-decision",
            artifact_updates={
                "content/review/decision/S01": (
                    "content-page-decision",
                    forged,
                )
            },
        )
        before = authority_snapshot_v22(self.kernel)
        with self.assertRaises(ContentWorkflowError):
            self.withdraw(command_id="reject-stale-decisions")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_withdrawal_transaction_failure_is_fully_atomic(self) -> None:
        self.save_all()
        self.submit()
        before = authority_snapshot_v22(self.kernel)
        with patch(
            "ai_ppt_studio.kernel.persistence.atomic_write_json",
            side_effect=OSError("INJECT_WITHDRAWAL_FAILURE"),
        ):
            with self.assertRaises(OSError):
                self.withdraw(command_id="withdraw-fails-atomically")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

    def test_empty_reason_and_non_submitted_lifecycle_are_not_withdrawable(self) -> None:
        self.save_all()
        self.submit()
        self.withdraw()
        before = authority_snapshot_v22(self.kernel)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.withdraw(command_id="withdraw-again")
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_STALE")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)
        current = self.current_batch()[1]
        with self.assertRaises(ContractValidationError):
            validate_content_review_batch({**current, "withdrawn_at": ""})

    def test_all_frozen_lifecycle_statuses_reject_page_mutation(self) -> None:
        self.save_all()
        _ref, submitted, _state = self.submit()
        before = authority_snapshot_v22(self.kernel)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save("S01", "modify", comment="冻结生命周期不可修改")
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)
        for status in ("plan-proposed", "plan-confirmed", "applied", "superseded"):
            with self.subTest(status=status), self.assertRaises(
                ContractValidationError
            ):
                validate_content_review_batch({**submitted, "status": status})

    def test_malformed_batch_set_and_decision_artifacts_fail_closed(self) -> None:
        self.save_all()
        submitted_ref, submitted, _state = self.submit()
        targets = (submitted_ref, submitted["decision_refs"][0])
        before = authority_snapshot_v22(self.kernel)
        for reference in targets:
            path = self.kernel.artifacts.path_for(
                ArtifactReference.parse(reference)
            )
            original = path.read_bytes()
            path.write_text("{}", encoding="utf-8")
            try:
                with self.subTest(reference=reference):
                    with self.assertRaises(ContractValidationError):
                        self.withdraw(command_id=f"corrupt-{reference[-4:]}")
                    self.assertEqual(authority_snapshot_v22(self.kernel), before)
            finally:
                path.write_bytes(original)

    def test_corrupt_batch_confirmation_ledger_and_transaction_failure_fail_closed(self) -> None:
        self.save_all()
        before = authority_snapshot_v22(self.kernel)
        with patch(
            "ai_ppt_studio.kernel.persistence.atomic_write_json",
            side_effect=OSError("INJECT_SUBMIT_FAILURE"),
        ):
            with self.assertRaises(OSError):
                self.submit(command_id="submit-fails-atomically")
        self.assertEqual(authority_snapshot_v22(self.kernel), before)

        self.submit(command_id="submit-after-rollback")
        session_ref = self.kernel.load().artifact_heads[
            "review/session/content-full-deck"
        ]
        session_path = self.kernel.artifacts.path_for(
            ArtifactReference.parse(session_ref)
        )
        original = session_path.read_bytes()
        state = authority_snapshot_v22(self.kernel)
        try:
            session_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ContractValidationError):
                self.withdraw(command_id="withdraw-corrupt-session")
            self.assertEqual(authority_snapshot_v22(self.kernel), state)
        finally:
            session_path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
