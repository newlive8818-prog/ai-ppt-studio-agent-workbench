from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (
    ContractValidationError,
    ContentWorkflowError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
from ai_ppt_studio.application.content_review.projection_service import ContentReviewProjectionService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.domains.content.contracts import validate_reading_deck_blueprint
from ai_ppt_studio.domains.content.page_decisions import (
    DECISIONS,
    normalize_decision,
    validate_page_decision as validate_v22_page_decision,
)
from ai_ppt_studio.domains.content.review_batches import validate_content_review_batch
from tests.test_v22_content_contracts import blueprint as v22_blueprint
from tests.test_v22_content_repair_loop import build_content as build_v22_content


def artifact_ref(kind: str, marker: str = "a") -> str:
    return f"artifact://{kind}/{marker * 64}"


def authority_snapshot_v22(kernel):
    return (
        kernel.load(),
        tuple(sorted(path.name for path in kernel.events_root.glob("*.json"))),
        tuple(
            sorted(
                str(path.relative_to(kernel.artifacts.objects_root))
                for path in kernel.artifacts.objects_root.rglob("*.json")
            )
        ),
    )


def accepted_v22_review(kernel, slide_count: int = 1):
    blueprint_ref = build_v22_content(kernel, slide_count=slide_count)
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


def valid_v22_decision(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "page_decision_id": "page-decision-1",
        "project_id": "project-1",
        "review_session_id": "content-full-deck-session-1",
        "source_version": "content-v1",
        "reading_blueprint_ref": artifact_ref("reading-deck-blueprint"),
        "slide_id": "S01",
        "slide_order": 1,
        "slide_title_snapshot": "当前流程断点与证据边界",
        "decision": "approved",
        "comment": "",
        "status": "completed",
        "saved_at": "2026-08-15T09:30:00+00:00",
        "supersedes_decision_ref": "",
    }
    payload.update(updates)
    return payload


def valid_v22_batch(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "batch_id": "content-review-batch-1",
        "project_id": "project-1",
        "review_session_id": "content-full-deck-session-1",
        "source_version": "content-v1",
        "reading_blueprint_ref": artifact_ref("reading-deck-blueprint"),
        "slide_ids": ["S01"],
        "decision_refs": [artifact_ref("content-page-decision", "b")],
        "counts": {
            "approved": 1,
            "modify": 0,
            "evidence": 0,
            "merge-or-delete": 0,
        },
        "status": "submitted",
        "immutable_after_submit": True,
        "submitted_at": "2026-08-15T09:35:00+00:00",
        "withdrawn_at": "",
        "supersedes_ref": "",
    }
    payload.update(updates)
    return payload


def approve_v22(
    kernel,
    session: dict,
    slide_id: str,
    *,
    command_id: str | None = None,
):
    return ContentDecisionService(kernel).save(
        command_id=command_id or f"approve-{slide_id}",
        expected_revision=kernel.load().revision,
        review_session_id=session["review_session_id"],
        source_version=session["source_version"],
        slide_id=slide_id,
        decision="approved",
        comment="",
    )


class PageDecisionContractTests(unittest.TestCase):
    def test_content_blueprint_has_one_closed_formal_envelope(self) -> None:
        payload = v22_blueprint()
        self.assertEqual(validate_reading_deck_blueprint(payload), payload)
        for malformed in (
            {key: value for key, value in payload.items() if key != "slides"},
            {**payload, "unknown": "not-closed"},
            {**payload, "slides": []},
            {**payload, "material_mode": "proposal-only"},
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(malformed)
    def test_visible_copy_snapshot_has_a_closed_exact_schema(self) -> None:
        payload = v22_blueprint()
        block = payload["slides"][0]["visible_copy_blocks"][0]
        for malformed_block in (
            {key: value for key, value in block.items() if key != "text"},
            {**block, "unknown": "not-closed"},
            {**block, "text": "   "},
            {**block, "identity": "unlabelled"},
        ):
            malformed = copy.deepcopy(payload)
            malformed["slides"][0]["visible_copy_blocks"] = [malformed_block]
            with self.subTest(block=malformed_block):
                with self.assertRaises(ContractValidationError):
                    validate_reading_deck_blueprint(malformed)
    def test_four_decisions_are_exact_and_approved_discards_comment(self) -> None:
        self.assertEqual(
            DECISIONS,
            {"approved", "modify", "evidence", "merge-or-delete"},
        )
        for decision in DECISIONS:
            comment = " 将本页改为证据链 " if decision != "approved" else "忽略"
            choice, normalized = normalize_decision(decision, comment)
            self.assertEqual(choice, decision)
            self.assertEqual(
                normalized,
                "" if decision == "approved" else "将本页改为证据链",
            )
        for decision in ("", "delete", "approved-and-modify"):
            with self.assertRaises(ContractValidationError):
                normalize_decision(decision, "意见")
    def test_required_comments_trim_whitespace_and_enforce_unicode_limit(self) -> None:
        for decision in DECISIONS - {"approved"}:
            with self.subTest(decision=decision):
                with self.assertRaises(ContractValidationError):
                    normalize_decision(decision, "   ")
        self.assertEqual(
            normalize_decision("modify", " 意" * 600)[1],
            (" 意" * 600).strip(),
        )
        with self.assertRaises(ContractValidationError):
            normalize_decision("modify", "意" * 1201)
    def test_identity_reference_timestamp_and_unknown_fields_fail_closed(self) -> None:
        self.assertEqual(
            validate_v22_page_decision(valid_v22_decision()),
            valid_v22_decision(),
        )
        for malformed in (
            {**valid_v22_decision(), "unknown": "not-closed"},
            {
                **valid_v22_decision(),
                "reading_blueprint_ref": artifact_ref("wrong-kind"),
            },
            {**valid_v22_decision(), "saved_at": "not-a-time"},
            {
                **valid_v22_decision(),
                "supersedes_decision_ref": artifact_ref("wrong-kind"),
            },
            {**valid_v22_decision(), "slide_order": True},
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ContractValidationError):
                    validate_v22_page_decision(malformed)
    def test_decision_set_accepts_draft_or_frozen_and_rejects_duplicates(self) -> None:
        submitted = validate_content_review_batch(valid_v22_batch())
        self.assertEqual(submitted["status"], "submitted")
        withdrawn = validate_content_review_batch(
            valid_v22_batch(
                status="withdrawn",
                withdrawn_at="2026-08-15T09:40:00+00:00",
                supersedes_ref=artifact_ref("content-review-batch", "c"),
            )
        )
        self.assertEqual(withdrawn["status"], "withdrawn")
        duplicate = valid_v22_batch(
            slide_ids=["S01", "S01"],
            decision_refs=[
                artifact_ref("content-page-decision", "b"),
                artifact_ref("content-page-decision", "c"),
            ],
            counts={
                "approved": 2,
                "modify": 0,
                "evidence": 0,
                "merge-or-delete": 0,
            },
        )
        for malformed in (
            duplicate,
            valid_v22_batch(immutable_after_submit=False),
            {**valid_v22_batch(), "unknown": "not-closed"},
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ContractValidationError):
                    validate_content_review_batch(malformed)
class ContentReviewServiceTests(unittest.TestCase):
    def test_atomic_save_snapshots_full_authoritative_slide_and_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_v22_review(kernel)
            before_gates = dict(state.gate_status)
            decision_ref, decision, committed = ContentDecisionService(kernel).save(
                command_id="save-S01",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment=" 补充当前证据边界 ",
            )
            self.assertEqual(decision["reading_blueprint_ref"], blueprint_ref)
            self.assertEqual(
                decision["slide_title_snapshot"],
                "当前流程断点与证据边界",
            )
            self.assertEqual(decision["comment"], "补充当前证据边界")
            self.assertEqual(committed.gate_status, before_gates)
            self.assertEqual(
                committed.artifact_heads["content/reading-blueprint"],
                blueprint_ref,
            )
            self.assertNotIn("content/review-batch", committed.artifact_heads)
            self.assertEqual(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(decision_ref)
                )["payload"],
                decision,
            )
    def test_replacement_supersedes_only_same_slide_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(
                kernel, 2
            )
            first_ref, first, _state = approve_v22(kernel, session, "S01")
            second_ref, second, _state = ContentDecisionService(kernel).save(
                command_id="replace-S01",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment="调整第一页",
            )
            third_ref, third, state = approve_v22(kernel, session, "S02")
            self.assertEqual(second["supersedes_decision_ref"], first_ref)
            self.assertEqual(third["supersedes_decision_ref"], "")
            self.assertEqual(
                state.artifact_heads["content/review/decision/S01"],
                second_ref,
            )
            self.assertEqual(
                state.artifact_heads["content/review/decision/S02"],
                third_ref,
            )
            self.assertEqual(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(first_ref)
                )["payload"],
                first,
            )
    def test_progress_uses_all_authoritative_slides_and_completes_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(
                kernel, 3
            )
            projection = ContentReviewProjectionService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(
                projection["progress"],
                {"completed": 0, "total": 3, "remaining": 3, "unsaved": 0},
            )
            for slide_id in ("S03", "S01", "S02"):
                approve_v22(kernel, session, slide_id)
            projection = ContentReviewProjectionService(kernel).project(
                session["review_session_id"]
            )
            self.assertEqual(
                [row["slide_id"] for row in projection["decisions"]],
                ["S01", "S02", "S03"],
            )
            self.assertEqual(projection["progress"]["remaining"], 0)
    def test_stale_source_wrong_kind_unknown_slide_and_revision_conflict_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_v22_review(kernel)
            service = ContentDecisionService(kernel)
            cases = (
                (
                    ReviewSourceStaleError,
                    {**session, "source_version": "content-v0"},
                    "S01",
                    state.revision,
                ),
                (
                    ReviewSourceStaleError,
                    {**session, "review_session_id": "wrong-session"},
                    "S01",
                    state.revision,
                ),
                (ContractValidationError, session, "UNKNOWN", state.revision),
                (RevisionConflictError, session, "S01", state.revision - 1),
            )
            for error, scoped, slide_id, revision in cases:
                before = authority_snapshot_v22(kernel)
                with self.subTest(error=error.__name__):
                    with self.assertRaises(error):
                        service.save(
                            command_id=f"reject-{error.__name__}",
                            expected_revision=revision,
                            review_session_id=scoped["review_session_id"],
                            source_version=scoped["source_version"],
                            slide_id=slide_id,
                            decision="modify",
                            comment="保留草稿",
                        )
                self.assertEqual(authority_snapshot_v22(kernel), before)
    def test_kernel_commit_failure_leaves_no_detached_page_objects(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_v22_review(kernel)
            before = authority_snapshot_v22(kernel)
            with patch.object(
                kernel,
                "commit",
                side_effect=RuntimeError("disk unavailable"),
            ):
                with self.assertRaises(RuntimeError):
                    ContentDecisionService(kernel).save(
                        command_id="atomic-failure",
                        expected_revision=state.revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                        slide_id="S01",
                        decision="approved",
                        comment="",
                    )
            self.assertEqual(authority_snapshot_v22(kernel), before)
    def test_same_batch_is_required_until_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(
                kernel, 2
            )
            approve_v22(kernel, session, "S01")
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ReviewSourceStaleError):
                ContentDecisionService(kernel).save(
                    command_id="wrong-session",
                    expected_revision=kernel.load().revision,
                    review_session_id="another-session",
                    source_version="content-v1",
                    slide_id="S02",
                    decision="approved",
                    comment="",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            approve_v22(kernel, session, "S02")
            self.assertEqual(
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )["progress"]["completed"],
                2,
            )
    def test_unresolvable_historical_source_set_cannot_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            first_ref, _first, _state = approve_v22(kernel, session, "S01")
            path = kernel.artifacts.path_for(ArtifactReference.parse(first_ref))
            original = path.read_bytes()
            before = authority_snapshot_v22(kernel)
            try:
                path.write_text("{}", encoding="utf-8")
                with self.assertRaises(ContractValidationError):
                    ContentDecisionService(kernel).save(
                        command_id="reject-corrupt-history",
                        expected_revision=kernel.load().revision,
                        review_session_id=session["review_session_id"],
                        source_version="content-v1",
                        slide_id="S01",
                        decision="modify",
                        comment="不能丢弃损坏历史",
                    )
                self.assertEqual(authority_snapshot_v22(kernel), before)
            finally:
                path.write_bytes(original)
    def test_minimal_malformed_historical_blueprint_cannot_be_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, _session, _state = accepted_v22_review(kernel)
            path = kernel.artifacts.path_for(
                ArtifactReference.parse(blueprint_ref)
            )
            original = path.read_bytes()
            before = authority_snapshot_v22(kernel)
            try:
                path.write_text("{}", encoding="utf-8")
                with self.assertRaises(ContractValidationError):
                    build_v22_content(kernel, "content-v2")
                self.assertEqual(authority_snapshot_v22(kernel), before)
            finally:
                path.write_bytes(original)
    def test_minimal_malformed_current_blueprint_is_not_reviewable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            path = kernel.artifacts.path_for(
                ArtifactReference.parse(blueprint_ref)
            )
            original = path.read_bytes()
            before = authority_snapshot_v22(kernel)
            try:
                path.write_text("{}", encoding="utf-8")
                with self.assertRaises(ContractValidationError):
                    ContentReviewProjectionService(kernel).project(
                        session["review_session_id"]
                    )
                self.assertEqual(authority_snapshot_v22(kernel), before)
            finally:
                path.write_bytes(original)
    def test_structurally_complete_unpublished_blueprint_is_not_history(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            detached_payload = v22_blueprint()
            detached_payload["project_id"] = kernel.project_id
            detached = str(
                kernel.artifacts.put(
                    "reading-deck-blueprint",
                    detached_payload,
                )
            )
            self.assertNotEqual(detached, blueprint_ref)
            decision_ref, decision, _state = approve_v22(kernel, session, "S01")
            self.assertEqual(decision["reading_blueprint_ref"], blueprint_ref)
            self.assertNotEqual(decision["reading_blueprint_ref"], detached)
            self.assertTrue(
                decision_ref.startswith("artifact://content-page-decision/")
            )
    def test_ambiguous_or_corrupt_blueprint_publication_receipt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_v22_review(kernel)
            forged = {
                **session,
                "target_artifact_ref": artifact_ref(
                    "reading-deck-blueprint", "f"
                ),
            }
            kernel.commit(
                command_id="forge-session-target",
                expected_revision=state.revision,
                event_type="test.forged-session",
                artifact_updates={
                    "review/session/content-full-deck": (
                        "review-session",
                        forged,
                    )
                },
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ReviewSourceStaleError):
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            self.assertEqual(
                kernel.load().artifact_heads["content/reading-blueprint"],
                blueprint_ref,
            )
    def test_transaction_chronology_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            event_path = (
                kernel.events_root / f"r{kernel.load().revision:08d}.json"
            )
            original = event_path.read_bytes()
            payload = json.loads(original)
            payload["revision"] = payload["revision"] + 10
            event_path.write_text(json.dumps(payload), encoding="utf-8")
            before = authority_snapshot_v22(kernel)
            try:
                with self.assertRaises(ContractValidationError):
                    approve_v22(kernel, session, "S01")
                self.assertEqual(authority_snapshot_v22(kernel), before)
            finally:
                event_path.write_bytes(original)
    def test_current_blueprint_chain_mismatches_are_zero_write(self) -> None:
        for slot, kind in (
            ("content/evidence-book", "presales-evidence-book"),
            ("content/decision-context", "customer-decision-context"),
            ("content/problem-solution-fit", "problem-solution-fit-map"),
        ):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _blueprint_ref, _session_ref, session, state = accepted_v22_review(
                    kernel
                )
                current_ref = state.artifact_heads[slot]
                payload = kernel.artifacts.resolve(
                    ArtifactReference.parse(current_ref)
                )["payload"]
                kernel.commit(
                    command_id=f"tamper-{slot}",
                    expected_revision=state.revision,
                    event_type="test.tampered-current-content",
                    artifact_updates={slot: (f"not-{kind}", payload)},
                )
                before = authority_snapshot_v22(kernel)
                with self.assertRaises(ContractValidationError):
                    approve_v22(kernel, session, "S01")
                self.assertEqual(authority_snapshot_v22(kernel), before)
    def test_frozen_decision_set_rejects_changes_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            approve_v22(kernel, session, "S01")
            ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContentWorkflowError):
                ContentDecisionService(kernel).save(
                    command_id="reject-frozen",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="modify",
                    comment="不应写入",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
    def test_forged_snapshot_that_differs_from_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            first_ref, first, state = approve_v22(kernel, session, "S01")
            forged = {**first, "slide_title_snapshot": "伪造标题"}
            kernel.commit(
                command_id="forge-decision-snapshot",
                expected_revision=state.revision,
                event_type="test.forged-decision",
                artifact_updates={
                    "content/review/decision/S01": (
                        "content-page-decision",
                        forged,
                    )
                },
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContentWorkflowError):
                ContentReviewBatchService(kernel).submit(
                    command_id="reject-forged-snapshot",
                    expected_revision=kernel.load().revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            self.assertEqual(
                kernel.load().artifact_heads["content/reading-blueprint"],
                blueprint_ref,
            )
            self.assertTrue(
                first_ref.startswith("artifact://content-page-decision/")
            )
    def test_snapshot_with_unknown_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, _state = accepted_v22_review(kernel)
            first_ref, first, state = approve_v22(kernel, session, "S01")
            kernel.commit(
                command_id="unknown-decision-field",
                expected_revision=state.revision,
                event_type="test.unknown-decision-field",
                artifact_updates={
                    "content/review/decision/S01": (
                        "content-page-decision",
                        {**first, "unknown": "must-fail"},
                    )
                },
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContractValidationError):
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            self.assertTrue(
                first_ref.startswith("artifact://content-page-decision/")
            )
    def test_persisted_page_decision_requires_every_exact_canonical_field(self) -> None:
        for missing in tuple(valid_v22_decision()):
            with self.subTest(missing=missing):
                malformed = valid_v22_decision()
                malformed.pop(missing)
                with self.assertRaises(ContractValidationError):
                    validate_v22_page_decision(malformed)
    def test_command_replay_is_exact_and_semantic_collision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_v22_review(kernel)
            args = {
                "command_id": "save-once",
                "expected_revision": state.revision,
                "review_session_id": session["review_session_id"],
                "source_version": "content-v1",
                "slide_id": "S01",
                "decision": "modify",
                "comment": "调整证据表达",
            }
            service = ContentDecisionService(kernel)
            first = service.save(**args)
            after = authority_snapshot_v22(kernel)
            self.assertEqual(service.save(**args), first)
            self.assertEqual(authority_snapshot_v22(kernel), after)
            with self.assertRaises(ContractValidationError):
                service.save(
                    **{
                        **args,
                        "decision": "evidence",
                        "comment": "补证据",
                    }
                )
            self.assertEqual(authority_snapshot_v22(kernel), after)
    def test_historical_replay_returns_a_time_result_after_b_and_c(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_v22_review(
                kernel, 2
            )
            service = ContentDecisionService(kernel)
            args = {
                "command_id": "decision-a",
                "expected_revision": state.revision,
                "review_session_id": session["review_session_id"],
                "source_version": "content-v1",
                "slide_id": "S01",
                "decision": "approved",
                "comment": "",
            }
            first_ref, first, _first_state = service.save(**args)
            service.save(
                command_id="decision-b",
                expected_revision=kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="modify",
                comment="后续修改",
            )
            approve_v22(
                kernel,
                session,
                "S02",
                command_id="decision-c",
            )
            before = authority_snapshot_v22(kernel)
            replay_ref, replay, replay_state = service.save(**args)
            self.assertEqual((replay_ref, replay), (first_ref, first))
            self.assertEqual(replay_state, kernel.load())
            self.assertEqual(authority_snapshot_v22(kernel), before)
    def test_new_blueprint_starts_a_new_source_bound_set_and_old_snapshot_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            first_blueprint, _session_ref, session, _state = accepted_v22_review(kernel)
            first_ref, first, _state = approve_v22(kernel, session, "S01")
            second_blueprint = build_v22_content(kernel, "content-v2")
            second_blueprint_publication_revision = kernel.load().revision
            gates = ContentHardGateService(kernel)
            gates.run_evidence_gate(
                command_id="evidence-v2",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            gates.run_presales_reading_gate(
                command_id="reading-v2",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            state = kernel.load()
            _new_session_ref, new_session, _state = ReviewSessionService(
                kernel
            ).open_or_resume(
                command_id="open-v2",
                expected_revision=state.revision,
                review_type="content-full-deck",
                target_artifact_ref=second_blueprint,
                source_version="content-v2",
                source_revision=second_blueprint_publication_revision,
                open_policy="foreground-if-waiting",
            )
            projection = ContentReviewProjectionService(kernel).project(
                new_session["review_session_id"]
            )
            self.assertEqual(projection["decisions"], [])
            self.assertNotEqual(first_blueprint, second_blueprint)
            self.assertEqual(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(first_ref)
                )["payload"],
                first,
            )
if __name__ == "__main__":
    unittest.main()
