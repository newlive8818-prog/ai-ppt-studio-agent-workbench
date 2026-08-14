from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review_service import (
    CONTENT_REVIEW_BATCH_FOLLOW_UP,
    ContentReviewService,
)
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_review_batch,
    validate_content_review_batch_withdrawal,
)
from ai_ppt_studio.errors import (
    ConfirmationTransactionError,
    ContentWorkflowError,
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import CONFIRMATION_LEDGER_SLOT
from tests.test_v16_content_page_decisions import (
    accept_blueprint,
    event_files,
    object_files,
    resolve_payload,
)
from tests.test_v16_framework_discussion import (
    TEST_SECRET,
    signed_assertion,
)


def artifact_ref(kind: str, marker: str) -> str:
    return f"artifact://{kind}/{marker * 64}"


def valid_batch(**updates: object) -> dict[str, object]:
    source = artifact_ref("content-blueprint", "a")
    set_ref = artifact_ref("content-page-decision-set", "b")
    decision_refs = [
        artifact_ref("content-page-decision", "c"),
        artifact_ref("content-page-decision", "d"),
    ]
    payload: dict[str, object] = {
        "review_batch_id": "batch-1",
        "project_id": "project-1",
        "review_type": "content",
        "source_version": source,
        "decision_set_ref": set_ref,
        "page_snapshot_refs": [
            artifact_ref("content-visible-copy-snapshot", "e"),
            artifact_ref("content-visible-copy-snapshot", "f"),
        ],
        "decision_refs": decision_refs,
        "expected_slide_count": 2,
        "counts": {
            "approved": 1,
            "modify": 1,
            "evidence": 0,
            "merge_or_delete": 0,
        },
        "status": "submitted",
        "submitted_at": "2026-08-14T10:00:00+00:00",
        "submitted_by": "host-action://submit-1",
        "supersedes_ref": "",
        "scope_kind": "content-review-batch-submission",
        "scope_id": f"batch-1:{source}",
        "evidence_refs": [source, set_ref, *decision_refs],
        "challenge_id": "1" * 64,
        "challenge_revision": 9,
        "user_action_ref": "host-action://submit-1",
        "user_message_ref": "",
        "confirmation_identity_type": "host-action",
        "host_assertion_sha256": "2" * 64,
        "confirmed_at": "2026-08-14T10:00:00+00:00",
    }
    payload.update(updates)
    return payload


def decision_payload(
    *,
    ref: str,
    slide_id: str,
    slide_order: int,
    decision: str,
    completed: bool = True,
) -> tuple[str, dict[str, object]]:
    comment = "" if decision == "approved" else f"{slide_id} 的完整意见"
    return ref, {
        "page_decision_id": f"decision-{slide_id}",
        "review_batch_id": "batch-1",
        "project_id": "project-1",
        "review_type": "content",
        "source_version": artifact_ref("content-blueprint", "a"),
        "slide_id": slide_id,
        "slide_order": slide_order,
        "slide_title_snapshot": f"{slide_id} 标题",
        "visible_copy_snapshot_ref": artifact_ref(
            "content-visible-copy-snapshot",
            chr(ord("e") + slide_order - 1),
        ),
        "decision": decision,
        "comment": comment,
        "completed": completed,
        "saved_at": "2026-08-14T10:00:00+00:00",
        "supersedes_decision_ref": "",
    }


class ContentReviewBatchContractTests(unittest.TestCase):
    def test_batch_requires_exact_ordered_complete_slide_set_and_counts(self) -> None:
        first_ref, first = decision_payload(
            ref=artifact_ref("content-page-decision", "c"),
            slide_id="s1",
            slide_order=1,
            decision="approved",
        )
        second_ref, second = decision_payload(
            ref=artifact_ref("content-page-decision", "d"),
            slide_id="s2",
            slide_order=2,
            decision="modify",
        )
        payload = valid_batch()
        self.assertEqual(
            validate_content_review_batch(
                payload,
                authoritative_slides=[
                    {"slide_id": "s1", "order": 1},
                    {"slide_id": "s2", "order": 2},
                ],
                decisions_by_ref={first_ref: first, second_ref: second},
            ),
            payload,
        )

        malformed: list[dict[str, object]] = []
        malformed.append({**payload, "expected_slide_count": 3})
        malformed.append(
            {**payload, "decision_refs": [first_ref, first_ref]}
        )
        malformed.append(
            {
                **payload,
                "counts": {
                    "approved": 2,
                    "modify": 0,
                    "evidence": 0,
                    "merge_or_delete": 0,
                },
            }
        )
        malformed.append({**payload, "source_version": artifact_ref("content-blueprint", "9")})
        malformed.append({**payload, "unexpected": True})
        for candidate in malformed:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ContractValidationError):
                    validate_content_review_batch(
                        candidate,
                        authoritative_slides=[
                            {"slide_id": "s1", "order": 1},
                            {"slide_id": "s2", "order": 2},
                        ],
                        decisions_by_ref={first_ref: first, second_ref: second},
                    )

        with self.assertRaises(ContractValidationError):
            validate_content_review_batch(
                {**payload, "project_id": "wrong-project"},
                authoritative_slides=[
                    {"slide_id": "s1", "order": 1},
                    {"slide_id": "s2", "order": 2},
                ],
                decisions_by_ref={first_ref: first, second_ref: second},
            )

    def test_completed_false_is_an_incomplete_batch(self) -> None:
        first_ref, first = decision_payload(
            ref=artifact_ref("content-page-decision", "c"),
            slide_id="s1",
            slide_order=1,
            decision="approved",
            completed=False,
        )
        second_ref, second = decision_payload(
            ref=artifact_ref("content-page-decision", "d"),
            slide_id="s2",
            slide_order=2,
            decision="modify",
        )
        with self.assertRaises(ContentWorkflowError) as caught:
            validate_content_review_batch(
                valid_batch(),
                authoritative_slides=[
                    {"slide_id": "s1", "order": 1},
                    {"slide_id": "s2", "order": 2},
                ],
                decisions_by_ref={first_ref: first, second_ref: second},
            )
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_INCOMPLETE")
        self.assertEqual(caught.exception.details["remaining"], 1)
        self.assertEqual(
            caught.exception.details["next_incomplete_slide_id"], "s1"
        )

    def test_submitted_batch_lifecycle_fields_are_immutable(self) -> None:
        original = valid_batch()
        for field, value in (
            ("source_version", artifact_ref("content-blueprint", "9")),
            ("decision_refs", list(reversed(original["decision_refs"]))),
            (
                "counts",
                {
                    "approved": 0,
                    "modify": 2,
                    "evidence": 0,
                    "merge_or_delete": 0,
                },
            ),
        ):
            lifecycle = {**original, field: value, "status": "superseded"}
            lifecycle["supersedes_ref"] = artifact_ref(
                "content-review-batch", "8"
            )
            with self.subTest(field=field):
                with self.assertRaises(ContractValidationError):
                    validate_content_review_batch(
                        lifecycle,
                        prior_submitted=original,
                    )


class ContentReviewBatchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.content = ContentService.initialize(
            Path(self.temp.name), project_id="batch-project"
        )
        self.source_version, self.blueprint = accept_blueprint(
            self.content, slide_count=4
        )
        self.review = ContentReviewService(self.content.kernel)
        self.batch_id = "review-batch-current"
        self.env = patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def save(
        self,
        slide_id: str,
        decision: str,
        *,
        comment: str = "",
        command_id: str | None = None,
        expected_revision: int | None = None,
        review_batch_id: str | None = None,
    ):
        return self.review.save_page_decision(
            command_id=command_id or f"save-{slide_id}-{uuid.uuid4()}",
            expected_revision=(
                self.content.kernel.load().revision
                if expected_revision is None
                else expected_revision
            ),
            source_version=self.source_version,
            review_batch_id=review_batch_id or self.batch_id,
            slide_id=slide_id,
            decision=decision,
            comment=comment,
        )

    def save_all(self) -> None:
        decisions = (
            ("s1", "approved", ""),
            ("s2", "modify", "修改第二页完整意见"),
            ("s3", "evidence", "补充第三页证据"),
            ("s4", "merge-or-delete", "与第三页合并"),
        )
        for slide_id, decision, comment in decisions:
            self.save(slide_id, decision, comment=comment)

    def submit(
        self,
        *,
        command_id: str = "submit-batch",
        expected_revision: int | None = None,
        context: dict[str, object] | None = None,
        assertion: str | None = None,
        source_version: str | None = None,
        review_batch_id: str | None = None,
    ):
        current = context or self.review.submission_context(
            source_version=source_version or self.source_version,
            review_batch_id=review_batch_id or self.batch_id,
        )
        return self.review.submit_review_batch(
            command_id=command_id,
            expected_revision=(
                int(current["challenge_revision"])
                if expected_revision is None
                else expected_revision
            ),
            source_version=source_version or self.source_version,
            review_batch_id=review_batch_id or self.batch_id,
            challenge_id=str(current["challenge_id"]),
            challenge_revision=int(current["challenge_revision"]),
            host_confirmation_assertion=assertion or signed_assertion(current),
        )

    def current_decision_set(self) -> tuple[str, dict]:
        reference = self.content.kernel.load().artifact_heads[
            "content/page-decisions"
        ]
        return reference, resolve_payload(self.content, reference)

    def current_batch(self) -> tuple[str, dict]:
        reference = self.content.kernel.load().artifact_heads[
            "content/review-batch"
        ]
        return reference, resolve_payload(self.content, reference)

    def test_submission_context_reports_exact_incomplete_progress(self) -> None:
        self.save("s1", "approved")
        self.save("s2", "modify", comment="完整修改意见")
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.review.submission_context(
                source_version=self.source_version,
                review_batch_id=self.batch_id,
            )
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_INCOMPLETE")
        self.assertEqual(caught.exception.details["remaining"], 2)
        self.assertEqual(
            caught.exception.details["next_incomplete_slide_id"], "s3"
        )
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), before_objects)
        self.assertEqual(event_files(self.content), before_events)

    def test_submission_context_binds_revision_source_set_and_ordered_refs(self) -> None:
        self.save_all()
        set_ref, decision_set = self.current_decision_set()
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        ordered = [row["decision_ref"] for row in decision_set["decision_refs"]]
        self.assertEqual(
            context["scope_kind"], "content-review-batch-submission"
        )
        self.assertEqual(
            context["scope_id"], f"{self.batch_id}:{self.source_version}"
        )
        self.assertEqual(context["source_version"], self.source_version)
        self.assertEqual(context["decision_set_ref"], set_ref)
        self.assertEqual(context["ordered_decision_refs"], ordered)
        self.assertEqual(
            context["evidence_refs"], [self.source_version, set_ref, *ordered]
        )
        self.assertEqual(
            context["challenge_revision"], self.content.kernel.load().revision
        )
        self.assertEqual(
            context["counts"],
            {
                "approved": 1,
                "modify": 1,
                "evidence": 1,
                "merge_or_delete": 1,
            },
        )
        self.assertNotIn("authoritative_slides", context)
        self.assertNotIn("decisions_by_ref", context)

    def test_submit_freezes_exact_batch_and_has_no_downstream_side_effects(self) -> None:
        self.save_all()
        before = self.content.kernel.load()
        before_heads = dict(before.artifact_heads)
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        assertion = signed_assertion(
            context, identity_ref="host-action://submit-exact"
        )
        batch_ref, follow_up, after = self.submit(
            context=context, assertion=assertion
        )
        self.assertEqual(follow_up, CONTENT_REVIEW_BATCH_FOLLOW_UP)
        self.assertEqual(after.revision, before.revision + 1)
        changed = {
            slot
            for slot in set(before_heads) | set(after.artifact_heads)
            if before_heads.get(slot) != after.artifact_heads.get(slot)
        }
        self.assertEqual(changed, {"content/review-batch", CONFIRMATION_LEDGER_SLOT})
        batch = resolve_payload(self.content, batch_ref)
        self.assertEqual(batch["status"], "submitted")
        self.assertEqual(batch["submitted_by"], "host-action://submit-exact")
        self.assertEqual(batch["submitted_at"], batch["confirmed_at"])
        self.assertEqual(batch["counts"], context["counts"])
        self.assertEqual(batch["decision_refs"], context["ordered_decision_refs"])
        self.assertEqual(after.artifact_heads["content/blueprint"], self.source_version)
        self.assertEqual(after.gate_status, before.gate_status)
        for forbidden in (
            "feedback/governance",
            "content/change-set",
            "content/batch-revision-plan",
        ):
            self.assertEqual(after.artifact_heads.get(forbidden), before_heads.get(forbidden))

        state_before_rejected_save = self.content.kernel.load()
        objects_before_rejected_save = object_files(self.content)
        with self.assertRaises(ContentWorkflowError) as caught:
            self.save("s1", "modify", comment="冻结后不可改")
        self.assertEqual(caught.exception.code, "CONTENT_REVIEW_BATCH_FROZEN")
        self.assertEqual(caught.exception.details["batch_ref"], batch_ref)
        self.assertEqual(caught.exception.details["status"], "submitted")
        self.assertEqual(self.content.kernel.load(), state_before_rejected_save)
        self.assertEqual(object_files(self.content), objects_before_rejected_save)

    def test_stale_source_wrong_batch_revision_and_duplicates_are_zero_write(self) -> None:
        self.save_all()
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        invalid_calls = (
            lambda: self.review.submission_context(
                source_version=artifact_ref("content-blueprint", "9"),
                review_batch_id=self.batch_id,
            ),
            lambda: self.review.submission_context(
                source_version=self.source_version,
                review_batch_id="wrong-batch",
            ),
        )
        for invoke in invalid_calls:
            with self.subTest(invoke=invoke):
                with self.assertRaises(ContentWorkflowError):
                    invoke()
                self.assertEqual(self.content.kernel.load(), before)
                self.assertEqual(object_files(self.content), before_objects)
                self.assertEqual(event_files(self.content), before_events)

        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        with self.assertRaises(RevisionConflictError):
            self.submit(context=context, expected_revision=before.revision - 1)
        self.assertEqual(self.content.kernel.load(), before)

        set_ref, decision_set = self.current_decision_set()
        malicious = copy.deepcopy(decision_set)
        malicious["decision_refs"][1] = copy.deepcopy(
            malicious["decision_refs"][0]
        )
        malicious_ref = str(
            self.content.kernel.artifacts.put(
                "content-page-decision-set", malicious
            )
        )
        state_payload = json.loads(
            self.content.kernel.state_path.read_text(encoding="utf-8")
        )
        state_payload["artifact_heads"]["content/page-decisions"] = malicious_ref
        self.content.kernel.state_path.write_text(
            json.dumps(state_payload), encoding="utf-8"
        )
        with self.assertRaises(ContentWorkflowError):
            self.review.submission_context(
                source_version=self.source_version,
                review_batch_id=self.batch_id,
            )
        self.assertNotEqual(set_ref, malicious_ref)

    def test_submission_challenge_scope_hmac_source_and_batch_mismatches_are_zero_write(self) -> None:
        self.save_all()
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        cases = (
            {
                "challenge_id": "0" * 64,
                "host_confirmation_assertion": signed_assertion(context),
            },
            {
                "challenge_revision": int(context["challenge_revision"]) + 1,
                "host_confirmation_assertion": signed_assertion(context),
            },
            {"host_confirmation_assertion": "v1.invalid.invalid"},
            {
                "host_confirmation_assertion": signed_assertion(
                    context,
                    overrides={"scope_kind": "content-review-batch-withdrawal"},
                )
            },
            {
                "source_version": artifact_ref("content-blueprint", "9"),
                "host_confirmation_assertion": signed_assertion(context),
            },
            {
                "review_batch_id": "changed-review-batch",
                "host_confirmation_assertion": signed_assertion(context),
            },
        )
        defaults: dict[str, object] = {
            "command_id": "never-committed",
            "expected_revision": before.revision,
            "source_version": self.source_version,
            "review_batch_id": self.batch_id,
            "challenge_id": context["challenge_id"],
            "challenge_revision": context["challenge_revision"],
            "host_confirmation_assertion": signed_assertion(context),
        }
        for index, changes in enumerate(cases):
            request = {**defaults, "command_id": f"invalid-submit-{index}", **changes}
            with self.subTest(changes=changes):
                with self.assertRaises(
                    (ContentWorkflowError, ContractValidationError)
                ):
                    self.review.submit_review_batch(**request)
                self.assertEqual(self.content.kernel.load(), before)
                self.assertEqual(object_files(self.content), before_objects)
                self.assertEqual(event_files(self.content), before_events)

    def test_exact_command_replay_changed_replay_and_identity_reuse(self) -> None:
        self.save_all()
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        assertion = signed_assertion(
            context, identity_ref="host-action://single-submit"
        )
        first = self.submit(context=context, assertion=assertion)
        state_after = self.content.kernel.load()
        objects_after = object_files(self.content)
        events_after = event_files(self.content)
        replay = self.submit(
            context=context,
            assertion=assertion,
            expected_revision=int(context["challenge_revision"]),
        )
        self.assertEqual(replay[0], first[0])
        self.assertEqual(replay[1], first[1])
        self.assertEqual(replay[2], state_after)
        self.assertEqual(object_files(self.content), objects_after)
        self.assertEqual(event_files(self.content), events_after)

        with self.assertRaises(ContractValidationError):
            self.submit(
                context=context,
                assertion=signed_assertion(
                    context,
                    identity_ref="host-action://different-replay-identity",
                ),
                expected_revision=int(context["challenge_revision"]),
            )
        self.assertEqual(self.content.kernel.load(), state_after)
        self.assertEqual(object_files(self.content), objects_after)
        self.assertEqual(event_files(self.content), events_after)

        with self.assertRaises(ContractValidationError):
            self.review.submit_review_batch(
                command_id="submit-batch",
                expected_revision=int(context["challenge_revision"]),
                source_version=self.source_version,
                review_batch_id="changed-batch",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=assertion,
            )
        self.assertEqual(self.content.kernel.load(), state_after)

        withdrawal = self.review.withdrawal_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        reused = signed_assertion(
            withdrawal, identity_ref="host-action://single-submit"
        )
        with self.assertRaises(ContentWorkflowError) as caught:
            self.review.withdraw_review_batch(
                command_id="withdraw-with-reused-identity",
                expected_revision=state_after.revision,
                source_version=self.source_version,
                review_batch_id=self.batch_id,
                reason="需要重新调整判断",
                challenge_id=str(withdrawal["challenge_id"]),
                challenge_revision=int(withdrawal["challenge_revision"]),
                host_confirmation_assertion=reused,
            )
        self.assertEqual(
            caught.exception.details["kernel_error_code"],
            "CONFIRMATION_IDENTITY_REPLAYED",
        )
        self.assertEqual(self.content.kernel.load(), state_after)

    def test_concurrent_different_submissions_have_only_one_winner(self) -> None:
        self.save_all()
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        barrier = threading.Barrier(2)
        results: list[object] = []

        def invoke(index: int) -> None:
            barrier.wait()
            try:
                results.append(
                    self.submit(
                        command_id=f"submit-concurrent-{index}",
                        context=context,
                        assertion=signed_assertion(
                            context,
                            identity_ref=f"host-action://concurrent-{index}",
                        ),
                    )
                )
            except Exception as error:  # noqa: BLE001 - assertion inspects type
                results.append(error)

        threads = [threading.Thread(target=invoke, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(isinstance(item, tuple) for item in results), 1)
        self.assertEqual(
            sum(isinstance(item, (RevisionConflictError, ContentWorkflowError)) for item in results),
            1,
        )

    def test_withdrawal_preserves_old_bytes_clones_decisions_and_allows_resubmit(self) -> None:
        self.save_all()
        submitted_ref, _follow_up, _state = self.submit()
        old_batch_path = self.content.kernel.artifacts.path_for(
            ArtifactReference.parse(submitted_ref)
        )
        old_batch_bytes = old_batch_path.read_bytes()
        _old_set_ref, old_set = self.current_decision_set()
        old_decision_bytes = {
            row["decision_ref"]: self.content.kernel.artifacts.path_for(
                ArtifactReference.parse(row["decision_ref"])
            ).read_bytes()
            for row in old_set["decision_refs"]
        }
        context = self.review.withdrawal_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        self.assertEqual(
            context["scope_kind"], "content-review-batch-withdrawal"
        )
        self.assertEqual(context["scope_id"], self.batch_id)
        before_revision = self.content.kernel.load().revision
        new_batch_id, after = self.review.withdraw_review_batch(
            command_id="withdraw-batch",
            expected_revision=before_revision,
            source_version=self.source_version,
            review_batch_id=self.batch_id,
            reason="  先调整两页意见后再集中提交  ",
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context, identity_ref="host-action://withdraw-exact"
            ),
        )
        self.assertNotEqual(new_batch_id, self.batch_id)
        self.assertEqual(after.revision, before_revision + 1)
        self.assertEqual(old_batch_path.read_bytes(), old_batch_bytes)
        for reference, prior_bytes in old_decision_bytes.items():
            self.assertEqual(
                self.content.kernel.artifacts.path_for(
                    ArtifactReference.parse(reference)
                ).read_bytes(),
                prior_bytes,
            )
        new_set_ref, new_set = self.current_decision_set()
        self.assertEqual(new_set["review_batch_id"], new_batch_id)
        self.assertEqual(new_set["status"], "draft")
        self.assertEqual(new_set["source_version"], self.source_version)
        self.assertEqual(len(new_set["decision_refs"]), len(old_set["decision_refs"]))
        for old_row, new_row in zip(old_set["decision_refs"], new_set["decision_refs"]):
            self.assertNotEqual(old_row["decision_ref"], new_row["decision_ref"])
            cloned = resolve_payload(self.content, new_row["decision_ref"])
            self.assertEqual(
                cloned["supersedes_decision_ref"], old_row["decision_ref"]
            )
            self.assertEqual(cloned["review_batch_id"], new_batch_id)
        batch_ref, draft_batch = self.current_batch()
        self.assertEqual(draft_batch["status"], "draft")
        self.assertEqual(draft_batch["review_batch_id"], new_batch_id)
        withdrawal_ref = after.artifact_heads["content/review-batch-withdrawal"]
        withdrawal = resolve_payload(self.content, withdrawal_ref)
        self.assertEqual(
            validate_content_review_batch_withdrawal(withdrawal), withdrawal
        )
        for malformed in (
            {
                **withdrawal,
                "evidence_refs": [
                    *withdrawal["evidence_refs"][:2],
                    self.source_version,
                    *withdrawal["evidence_refs"][3:],
                ],
            },
            {
                **withdrawal,
                "superseded_batch_ref": withdrawal[
                    "submitted_batch_ref"
                ],
            },
        ):
            with self.assertRaises(ContractValidationError):
                validate_content_review_batch_withdrawal(malformed)
        self.assertEqual(withdrawal["reason"], "先调整两页意见后再集中提交")
        self.assertEqual(withdrawal["submitted_batch_ref"], submitted_ref)
        superseded = resolve_payload(
            self.content, withdrawal["superseded_batch_ref"]
        )
        self.assertEqual(superseded["status"], "superseded")
        self.assertEqual(
            superseded["decision_refs"],
            [row["decision_ref"] for row in old_set["decision_refs"]],
        )
        self.assertNotIn(withdrawal["superseded_batch_ref"], after.artifact_heads.values())

        self.save(
            "s1",
            "modify",
            comment="新批次可独立修改",
            review_batch_id=new_batch_id,
        )
        second_context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=new_batch_id,
        )
        second_ref, follow_up, _state = self.submit(
            command_id="submit-replacement-batch",
            context=second_context,
            review_batch_id=new_batch_id,
        )
        self.assertNotEqual(second_ref, batch_ref)
        self.assertEqual(follow_up, CONTENT_REVIEW_BATCH_FOLLOW_UP)

    def test_withdrawal_exact_replay_is_idempotent_but_changed_assertion_conflicts(self) -> None:
        self.save_all()
        self.submit()
        context = self.review.withdrawal_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        assertion = signed_assertion(
            context, identity_ref="host-action://withdraw-replay"
        )
        first = self.review.withdraw_review_batch(
            command_id="withdraw-replay-command",
            expected_revision=int(context["challenge_revision"]),
            source_version=self.source_version,
            review_batch_id=self.batch_id,
            reason="重新检查整套判断",
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=assertion,
        )
        after = self.content.kernel.load()
        objects_after = object_files(self.content)
        events_after = event_files(self.content)
        replay = self.review.withdraw_review_batch(
            command_id="withdraw-replay-command",
            expected_revision=int(context["challenge_revision"]),
            source_version=self.source_version,
            review_batch_id=self.batch_id,
            reason="重新检查整套判断",
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=assertion,
        )
        self.assertEqual(replay[0], first[0])
        self.assertEqual(replay[1], after)
        self.assertEqual(object_files(self.content), objects_after)
        self.assertEqual(event_files(self.content), events_after)

        ledger_ref = after.artifact_heads[CONFIRMATION_LEDGER_SLOT]
        ledger_path = self.content.kernel.artifacts.path_for(
            ArtifactReference.parse(ledger_ref)
        )
        ledger_bytes = ledger_path.read_bytes()
        ledger_path.write_text("{}", encoding="utf-8")
        try:
            with self.assertRaises(ContractValidationError):
                self.review.withdraw_review_batch(
                    command_id="withdraw-replay-command",
                    expected_revision=int(context["challenge_revision"]),
                    source_version=self.source_version,
                    review_batch_id=self.batch_id,
                    reason="重新检查整套判断",
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=assertion,
                )
        finally:
            ledger_path.write_bytes(ledger_bytes)

        with self.assertRaises(ContractValidationError):
            self.review.withdraw_review_batch(
                command_id="withdraw-replay-command",
                expected_revision=int(context["challenge_revision"]),
                source_version=self.source_version,
                review_batch_id=self.batch_id,
                reason="重新检查整套判断",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    context,
                    identity_ref="host-action://changed-withdraw-replay",
                ),
            )
        self.assertEqual(self.content.kernel.load(), after)
        self.assertEqual(object_files(self.content), objects_after)
        self.assertEqual(event_files(self.content), events_after)

    def test_withdrawal_requires_the_submitted_batch_decision_set_to_remain_current(self) -> None:
        self.save_all()
        submitted_ref, _follow_up, _state = self.submit()
        submitted = resolve_payload(self.content, submitted_ref)
        original_set = resolve_payload(
            self.content, submitted["decision_set_ref"]
        )
        replacement_set = {
            **original_set,
            "updated_at": "2026-08-14T23:59:59+00:00",
        }
        self.content.kernel.commit(
            command_id="replace-current-set-after-submit",
            expected_revision=self.content.kernel.load().revision,
            event_type="test.replace-current-decision-set",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    replacement_set,
                )
            },
        )
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        with self.assertRaises(ContentWorkflowError):
            self.review.withdrawal_context(
                source_version=self.source_version,
                review_batch_id=self.batch_id,
            )
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), before_objects)
        self.assertEqual(event_files(self.content), before_events)

    def test_withdrawal_transaction_failure_is_fully_atomic(self) -> None:
        self.save_all()
        self.submit()
        context = self.review.withdrawal_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        with patch(
            "ai_ppt_studio.kernel.transactions.atomic_write_json",
            side_effect=OSError("INJECT_WITHDRAWAL_FAILURE"),
        ):
            with self.assertRaises(OSError):
                self.review.withdraw_review_batch(
                    command_id="withdraw-fails-atomically",
                    expected_revision=before.revision,
                    source_version=self.source_version,
                    review_batch_id=self.batch_id,
                    reason="测试撤回事务回滚",
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(context),
                )
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), before_objects)
        self.assertEqual(event_files(self.content), before_events)

    def test_empty_reason_and_non_submitted_lifecycle_are_not_withdrawable(self) -> None:
        self.save_all()
        submitted_ref, _follow_up, _state = self.submit()
        context = self.review.withdrawal_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        before = self.content.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.review.withdraw_review_batch(
                command_id="withdraw-empty",
                expected_revision=before.revision,
                source_version=self.source_version,
                review_batch_id=self.batch_id,
                reason="  \n ",
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )
        self.assertEqual(self.content.kernel.load(), before)

        submitted = resolve_payload(self.content, submitted_ref)
        for status in ("plan-proposed", "plan-confirmed", "applied", "superseded"):
            lifecycle = {**submitted, "status": status, "supersedes_ref": submitted_ref}
            self.content.kernel.commit(
                command_id=f"install-{status}",
                expected_revision=self.content.kernel.load().revision,
                event_type="test.install-review-batch-lifecycle",
                artifact_updates={
                    "content/review-batch": ("content-review-batch", lifecycle)
                },
            )
            state = self.content.kernel.load()
            objects = object_files(self.content)
            events = event_files(self.content)
            with self.subTest(status=status):
                with self.assertRaises(ContentWorkflowError) as caught:
                    self.review.withdrawal_context(
                        source_version=self.source_version,
                        review_batch_id=self.batch_id,
                    )
                self.assertEqual(
                    caught.exception.code, "CONTENT_REVIEW_BATCH_NOT_WITHDRAWABLE"
                )
                self.assertEqual(self.content.kernel.load(), state)
                self.assertEqual(object_files(self.content), objects)
                self.assertEqual(event_files(self.content), events)

    def test_all_frozen_lifecycle_statuses_reject_page_mutation(self) -> None:
        self.save_all()
        submitted_ref, _follow_up, _state = self.submit()
        submitted = resolve_payload(self.content, submitted_ref)
        for status in ("submitted", "plan-proposed", "plan-confirmed", "applied"):
            if status != "submitted":
                lifecycle = {
                    **submitted,
                    "status": status,
                    "supersedes_ref": submitted_ref,
                }
                self.content.kernel.commit(
                    command_id=f"install-frozen-{status}",
                    expected_revision=self.content.kernel.load().revision,
                    event_type="test.install-frozen-review-batch",
                    artifact_updates={
                        "content/review-batch": (
                            "content-review-batch",
                            lifecycle,
                        )
                    },
                )
            before = self.content.kernel.load()
            before_objects = object_files(self.content)
            before_events = event_files(self.content)
            with self.subTest(status=status):
                with self.assertRaises(ContentWorkflowError) as caught:
                    self.save(
                        "s1",
                        "modify",
                        comment="冻结生命周期不可修改",
                    )
                self.assertEqual(
                    caught.exception.code, "CONTENT_REVIEW_BATCH_FROZEN"
                )
                self.assertEqual(caught.exception.details["status"], status)
                self.assertEqual(self.content.kernel.load(), before)
                self.assertEqual(object_files(self.content), before_objects)
                self.assertEqual(event_files(self.content), before_events)

    def test_malformed_batch_set_and_decision_artifacts_fail_closed(self) -> None:
        self.save_all()
        submitted_ref, _follow_up, _state = self.submit()
        submitted = resolve_payload(self.content, submitted_ref)
        targets = (
            submitted_ref,
            submitted["decision_set_ref"],
            submitted["decision_refs"][0],
        )
        state = self.content.kernel.load()
        state_bytes = self.content.kernel.state_path.read_bytes()
        events = event_files(self.content)
        for reference in targets:
            path = self.content.kernel.artifacts.path_for(
                ArtifactReference.parse(reference)
            )
            original = path.read_bytes()
            path.write_text("{}", encoding="utf-8")
            try:
                with self.subTest(reference=reference):
                    with self.assertRaises(ContentWorkflowError):
                        self.review.withdrawal_context(
                            source_version=self.source_version,
                            review_batch_id=self.batch_id,
                        )
                    self.assertEqual(self.content.kernel.load(), state)
                    self.assertEqual(
                        self.content.kernel.state_path.read_bytes(), state_bytes
                    )
                    self.assertEqual(event_files(self.content), events)
            finally:
                path.write_bytes(original)

    def test_corrupt_batch_confirmation_ledger_and_transaction_failure_fail_closed(self) -> None:
        self.save_all()
        context = self.review.submission_context(
            source_version=self.source_version,
            review_batch_id=self.batch_id,
        )
        before = self.content.kernel.load()
        before_objects = object_files(self.content)
        before_events = event_files(self.content)
        with patch(
            "ai_ppt_studio.kernel.transactions.atomic_write_json",
            side_effect=OSError("INJECT_SUBMIT_FAILURE"),
        ):
            with self.assertRaises(OSError):
                self.submit(context=context)
        self.assertEqual(self.content.kernel.load(), before)
        self.assertEqual(object_files(self.content), before_objects)
        self.assertEqual(event_files(self.content), before_events)

        self.submit(command_id="submit-after-rollback", context=context)
        ledger_ref = self.content.kernel.load().artifact_heads[
            CONFIRMATION_LEDGER_SLOT
        ]
        ledger_path = self.content.kernel.artifacts.path_for(
            ArtifactReference.parse(ledger_ref)
        )
        ledger_path.write_text("{}", encoding="utf-8")
        state = self.content.kernel.load()
        state_bytes = self.content.kernel.state_path.read_bytes()
        events = event_files(self.content)
        with self.assertRaises((ContentWorkflowError, ConfirmationTransactionError)):
            self.review.withdrawal_context(
                source_version=self.source_version,
                review_batch_id=self.batch_id,
            )
        self.assertEqual(self.content.kernel.load(), state)
        self.assertEqual(self.content.kernel.state_path.read_bytes(), state_bytes)
        self.assertEqual(event_files(self.content), events)


if __name__ == "__main__":
    unittest.main()
