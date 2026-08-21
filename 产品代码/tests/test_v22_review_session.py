from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import ContractValidationError, ReviewSourceStaleError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel

NOW = "2026-08-15T00:00:00+08:00"


def publish_source(
    kernel: ProjectKernel,
    *,
    command_id: str,
    slot: str,
    kind: str,
    source_version: str,
):
    return kernel.commit(
        command_id=command_id,
        expected_revision=kernel.load().revision,
        event_type="test.source-published",
        artifact_updates={slot: (kind, {"source_version": source_version})},
    )


def receipt(
    kernel: ProjectKernel,
    *,
    command_id: str,
    kind: str,
    session_id: str,
    status: str,
) -> str:
    state = kernel.commit(
        command_id=command_id,
        expected_revision=kernel.load().revision,
        event_type="test.receipt-recorded",
        artifact_updates={
            f"test/receipt/{command_id}": (
                kind,
                {
                    "review_session_id": session_id,
                    "status": status,
                    "recorded_at": NOW,
                },
            )
        },
    )
    return state.artifact_heads[f"test/receipt/{command_id}"]


class ReviewSessionContractTests(unittest.TestCase):
    def test_minimum_contract_rejects_forged_or_invalid_state(self) -> None:
        payload = {
            "review_session_id": "content-session-01",
            "review_type": "content-full-deck",
            "project_id": "project-01",
            "target_artifact_ref": "artifact://reading-deck-blueprint/" + "a" * 64,
            "source_version": "content-v3",
            "revision": 17,
            "status": "ready",
            "open_policy": "notify-only",
            "host_open_status": "not-requested",
            "persistence_status": "saved",
            "host_notification_status": "not-requested",
            "ai_receipt_status": "pending",
            "created_at": NOW,
            "last_opened_at": None,
            "submitted_at": None,
        }
        self.assertEqual(validate_review_session(payload), payload)
        for change in (
            {"review_type": "evidence"},
            {"target_artifact_ref": ""},
            {"host_open_status": "opened"},
            {"host_notification_status": "sent"},
            {"ai_receipt_status": "received"},
        ):
            with self.subTest(change=change), self.assertRaises(
                ContractValidationError
            ):
                validate_review_session({**payload, **change})

    def test_advanced_receipt_states_require_their_authoritative_refs(self) -> None:
        payload = {
            "review_session_id": "visual-session-01",
            "review_type": "visual-professional",
            "project_id": "project-01",
            "target_artifact_ref": "artifact://visual-contract/" + "a" * 64,
            "source_version": "visual-v3",
            "revision": 17,
            "status": "ready",
            "open_policy": "notify-only",
            "host_open_status": "not-requested",
            "persistence_status": "saved",
            "host_notification_status": "not-requested",
            "ai_receipt_status": "pending",
            "created_at": NOW,
            "last_opened_at": None,
            "submitted_at": None,
        }
        cases = (
            (
                {
                    "status": "opened",
                    "host_open_status": "opened",
                    "last_opened_at": NOW,
                },
                "host_open_receipt_ref",
                "artifact://review-host-open-receipt/" + "b" * 64,
            ),
            (
                {"host_notification_status": "sent"},
                "host_notification_receipt_ref",
                "artifact://review-host-notification-receipt/" + "c" * 64,
            ),
            (
                {"ai_receipt_status": "received"},
                "ai_receipt_ref",
                "artifact://review-ai-receipt/" + "d" * 64,
            ),
        )
        for advanced, receipt_field, receipt_ref in cases:
            with self.subTest(receipt_field=receipt_field):
                candidate = {**payload, **advanced}
                with self.assertRaises(ContractValidationError):
                    validate_review_session(candidate, trusted_receipts=True)
                self.assertEqual(
                    validate_review_session(
                        {**candidate, receipt_field: receipt_ref},
                        trusted_receipts=True,
                    )[receipt_field],
                    receipt_ref,
                )


class ReviewSessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.kernel = ProjectKernel.initialize(self.root, project_id="project-01")
        state = publish_source(
            self.kernel,
            command_id="source-v3",
            slot="content/reading-blueprint",
            kind="reading-deck-blueprint",
            source_version="content-v3",
        )
        self.source_ref = state.artifact_heads["content/reading-blueprint"]
        self.service = ReviewSessionService(self.kernel)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def open(self, command_id: str = "open-v3"):
        state = self.kernel.load()
        return self.service.open_or_resume(
            command_id=command_id,
            expected_revision=state.revision,
            review_type="content-full-deck",
            target_artifact_ref=self.source_ref,
            source_version="content-v3",
            source_revision=1,
            open_policy="notify-only",
        )

    def test_reopen_is_unique_and_new_source_atomically_supersedes(self) -> None:
        first_ref, first, first_state = self.open()
        repeated_ref, repeated, repeated_state = self.open("open-v3-again")
        self.assertEqual((repeated_ref, repeated), (first_ref, first))
        self.assertEqual(repeated_state.revision, first_state.revision)
        self.assertEqual(
            [
                slot
                for slot in repeated_state.artifact_heads
                if slot.startswith("review/session/")
            ],
            ["review/session/content-full-deck"],
        )

        published = publish_source(
            self.kernel,
            command_id="source-v4",
            slot="content/reading-blueprint",
            kind="reading-deck-blueprint",
            source_version="content-v4",
        )
        next_ref = published.artifact_heads["content/reading-blueprint"]
        with self.assertRaises(ReviewSourceStaleError):
            self.service.open_or_resume(
                command_id="stale-open",
                expected_revision=published.revision,
                review_type="content-full-deck",
                target_artifact_ref=self.source_ref,
                source_version="content-v3",
                source_revision=1,
                open_policy="notify-only",
            )
        second_ref, second, committed = self.service.open_or_resume(
            command_id="open-v4",
            expected_revision=published.revision,
            review_type="content-full-deck",
            target_artifact_ref=next_ref,
            source_version="content-v4",
            source_revision=published.revision,
            open_policy="notify-only",
        )
        self.assertNotEqual(second_ref, first_ref)
        self.assertNotEqual(second["review_session_id"], first["review_session_id"])
        event = (
            self.kernel.events_root / f"r{committed.revision:08d}.json"
        ).read_text(encoding="utf-8")
        self.assertIn("detached_artifact_refs", event)
        self.assertEqual(
            committed.artifact_heads["review/session/content-full-deck"], second_ref
        )

    def test_receipts_and_submission_are_separate_authoritative_facts(self) -> None:
        session_ref, session, _ = self.open()
        open_ref = receipt(
            self.kernel,
            command_id="host-open",
            kind="review-host-open-receipt",
            session_id=session["review_session_id"],
            status="opened",
        )
        session_ref, session, _ = self.service.record_host_open_receipt(
            command_id="apply-host-open",
            expected_revision=self.kernel.load().revision,
            review_type="content-full-deck",
            receipt_ref=open_ref,
        )
        self.assertEqual(session["host_open_status"], "opened")
        self.assertEqual(session["last_opened_at"], NOW)

        notification_ref = receipt(
            self.kernel,
            command_id="host-notification",
            kind="review-host-notification-receipt",
            session_id=session["review_session_id"],
            status="sent",
        )
        session_ref, session, _ = self.service.record_host_notification_receipt(
            command_id="apply-host-notification",
            expected_revision=self.kernel.load().revision,
            review_type="content-full-deck",
            receipt_ref=notification_ref,
        )
        self.assertEqual(session["host_notification_status"], "sent")

        session_ref, session, _ = self.service.mark_submitted(
            command_id="submit-review",
            expected_revision=self.kernel.load().revision,
            review_type="content-full-deck",
            submitted_at=NOW,
        )
        self.assertEqual(session["status"], "submitted")
        self.assertEqual(
            self.kernel.load().artifact_heads["review/session/content-full-deck"],
            session_ref,
        )

        ai_ref = receipt(
            self.kernel,
            command_id="ai-receipt",
            kind="review-ai-receipt",
            session_id=session["review_session_id"],
            status="received",
        )
        _, session, _ = self.service.record_ai_receipt(
            command_id="apply-ai-receipt",
            expected_revision=self.kernel.load().revision,
            review_type="content-full-deck",
            receipt_ref=ai_ref,
        )
        self.assertEqual(session["ai_receipt_status"], "received")
        self.assertEqual(session["status"], "submitted")

    def test_bridge_host_open_is_created_and_bound_atomically_with_replay(self) -> None:
        _, session, opened = self.open()
        kwargs = {
            "command_id": "bridge-host-open",
            "expected_revision": opened.revision,
            "review_type": "content-full-deck",
            "review_session_id": session["review_session_id"],
            "bridge_session_id": "bridge-session-01",
            "recorded_at": NOW,
        }
        session_ref, recorded, committed = self.service.record_bridge_host_open(
            **kwargs
        )
        self.assertEqual(recorded["status"], "opened")
        self.assertEqual(recorded["host_open_status"], "opened")
        self.assertEqual(recorded["last_opened_at"], NOW)
        receipt_ref = recorded["host_open_receipt_ref"]
        receipt_payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(receipt_ref)
        )["payload"]
        self.assertEqual(receipt_payload["bridge_session_id"], "bridge-session-01")
        self.assertEqual(
            receipt_payload["review_session_id"], session["review_session_id"]
        )

        replay_ref, replayed, replay_state = self.service.record_bridge_host_open(
            **kwargs
        )
        self.assertEqual((replay_ref, replayed), (session_ref, recorded))
        self.assertEqual(replay_state.revision, committed.revision)

        before_conflict = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.record_bridge_host_open(
                **{
                    **kwargs,
                    "expected_revision": before_conflict.revision,
                    "bridge_session_id": "different-bridge-session",
                }
            )
        self.assertEqual(self.kernel.load(), before_conflict)

    def test_rejects_future_revision_and_evidence_auxiliary_session(self) -> None:
        before = self.kernel.load()
        with self.assertRaises(ContractValidationError):
            self.service.open_or_resume(
                command_id="future",
                expected_revision=before.revision,
                review_type="content-full-deck",
                target_artifact_ref=self.source_ref,
                source_version="content-v3",
                source_revision=before.revision + 1,
                open_policy="notify-only",
            )
        with self.assertRaises(ContractValidationError):
            self.service.open_or_resume(
                command_id="evidence",
                expected_revision=before.revision,
                review_type="evidence",
                target_artifact_ref=self.source_ref,
                source_version="content-v3",
                source_revision=1,
                open_policy="notify-only",
            )
        self.assertEqual(self.kernel.load(), before)

    def test_rejects_non_authoritative_source_revision_without_superseding(self) -> None:
        first_ref, first_session, opened = self.open()
        before = self.kernel.load()

        with self.assertRaisesRegex(
            ContractValidationError,
            "source_revision must equal the current target publication revision",
        ):
            self.service.open_or_resume(
                command_id="open-v3-with-forged-history",
                expected_revision=opened.revision,
                review_type="content-full-deck",
                target_artifact_ref=self.source_ref,
                source_version="content-v3",
                source_revision=0,
                open_policy="notify-only",
            )

        self.assertEqual(self.kernel.load(), before)
        current_ref = before.artifact_heads["review/session/content-full-deck"]
        self.assertEqual(current_ref, first_ref)
        current = self.kernel.artifacts.resolve(
            ArtifactReference.parse(current_ref)
        )["payload"]
        self.assertEqual(current["review_session_id"], first_session["review_session_id"])

    def test_bridge_exposes_session_write_and_status_read_without_raw_state(self) -> None:
        request = {
            "operation": "open-or-resume-review-session",
            "project_root": str(self.root),
            "command_id": "bridge-open",
            "expected_revision": self.kernel.load().revision,
            "review_type": "content-full-deck",
            "target_artifact_ref": self.source_ref,
            "source_version": "content-v3",
            "source_revision": 1,
            "open_policy": "notify-only",
        }
        opened = dispatch_v16(request)
        self.assertTrue(opened["ok"])
        self.assertEqual(opened["result"]["session"]["status"], "ready")
        projected = dispatch_v16(
            {"operation": "get-project-user-status", "project_root": str(self.root)}
        )
        self.assertEqual(projected["status"]["status"], "AI 正在处理")
        self.assertTrue(
            ArtifactReference.parse(opened["result"]["session_ref"])
        )

    def test_bridge_records_browser_open_with_an_internal_exact_operation(self) -> None:
        opened = dispatch_v16(
            {
                "operation": "open-or-resume-review-session",
                "project_root": str(self.root),
                "command_id": "bridge-open-session",
                "expected_revision": self.kernel.load().revision,
                "review_type": "content-full-deck",
                "target_artifact_ref": self.source_ref,
                "source_version": "content-v3",
                "source_revision": 1,
                "open_policy": "notify-only",
            }
        )
        session = opened["result"]["session"]
        recorded = dispatch_v16(
            {
                "operation": "record-review-bridge-host-open",
                "project_root": str(self.root),
                "expected_revision": opened["result"]["snapshot"]["revision"],
                "review_type": "content-full-deck",
                "review_session_id": session["review_session_id"],
                "bridge_session_id": "bridge-session-01",
                "recorded_at": NOW,
            }
        )
        self.assertEqual(recorded["result"]["session"]["status"], "opened")
        self.assertEqual(
            recorded["result"]["session"]["host_open_status"], "opened"
        )
