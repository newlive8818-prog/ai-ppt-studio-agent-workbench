from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.review.contracts import (
    review_session_identity,
    validate_review_session,
)
from ai_ppt_studio.application.review_session_service import (
    ReviewSessionService,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def valid_session() -> dict[str, object]:
    return {
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
        "host_notification_status": "pending",
        "ai_receipt_status": "pending",
        "created_at": "2026-08-23T00:00:00+00:00",
        "last_opened_at": None,
        "submitted_at": None,
    }


def kernel_with_target(root: Path) -> tuple[ProjectKernel, str]:
    kernel = ProjectKernel.initialize(root, project_id="project-01")
    target = {"title": "完整内容审核", "slides": [{"slide_id": "s1"}]}
    state = kernel.commit(
        command_id="seed-target-v1",
        expected_revision=0,
        event_type="test.target-created",
        artifact_updates={
            "content/reading-deck-blueprint": (
                "reading-deck-blueprint",
                target,
            )
        },
    )
    return kernel, state.artifact_heads["content/reading-deck-blueprint"]


class ReviewSessionContractTests(unittest.TestCase):
    def test_valid_session_round_trips_and_identity_is_stable(self) -> None:
        payload = valid_session()
        self.assertEqual(validate_review_session(payload), payload)
        self.assertEqual(
            review_session_identity(payload),
            (
                "project-01",
                "content-full-deck",
                payload["target_artifact_ref"],
                "content-v3",
                17,
            ),
        )

    def test_rejects_invalid_review_type_status_and_future_revision(self) -> None:
        for field, value in (
            ("review_type", "content-evidence"),
            ("status", "approved"),
            ("open_policy", "auto-open"),
            ("host_open_status", "assumed-open"),
            ("persistence_status", "received"),
            ("host_notification_status", "assumed-sent"),
            ("ai_receipt_status", "assumed-received"),
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = value
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)
        with self.assertRaises(ContractValidationError):
            validate_review_session(valid_session(), current_revision=16)

    def test_requires_target_source_and_timestamp_fields(self) -> None:
        for field in (
            "review_session_id",
            "target_artifact_ref",
            "source_version",
            "created_at",
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = ""
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)


class ReviewSessionServiceTests(unittest.TestCase):
    def _open_session(
        self,
        kernel: ProjectKernel,
        target_ref: str,
        *,
        open_policy: str = "foreground-if-waiting",
    ) -> tuple[ReviewSessionService, dict[str, object], object]:
        service = ReviewSessionService(
            kernel,
            clock=lambda: "2026-08-23T00:00:00+00:00",
        )
        session, state = service.open_or_resume(
            command_id=f"open-{open_policy}",
            expected_revision=1,
            review_type="content-full-deck",
            target_artifact_ref=target_ref,
            source_version="content-v1",
            target_revision=1,
            open_policy=open_policy,
        )
        return service, session, state

    def test_same_identity_reopens_without_a_second_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            service = ReviewSessionService(
                kernel,
                clock=lambda: "2026-08-23T00:00:00+00:00",
            )
            first, first_state = service.open_or_resume(
                command_id="open-1",
                expected_revision=1,
                review_type="content-full-deck",
                target_artifact_ref=target_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="foreground-if-waiting",
            )
            resumed, resumed_state = service.open_or_resume(
                command_id="open-2",
                expected_revision=first_state.revision,
                review_type="content-full-deck",
                target_artifact_ref=target_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="foreground-if-waiting",
            )
            self.assertEqual(resumed, first)
            self.assertEqual(resumed_state.revision, first_state.revision)
            self.assertEqual(len(tuple(kernel.events_root.iterdir())), 2)

    def test_new_identity_atomically_supersedes_old_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, first_ref = kernel_with_target(Path(temp))
            service = ReviewSessionService(
                kernel,
                clock=lambda: "2026-08-23T00:00:00+00:00",
            )
            first, state = service.open_or_resume(
                command_id="open-v1",
                expected_revision=1,
                review_type="content-full-deck",
                target_artifact_ref=first_ref,
                source_version="content-v1",
                target_revision=1,
                open_policy="notify-only",
            )
            state = kernel.commit(
                command_id="seed-target-v2",
                expected_revision=state.revision,
                event_type="test.target-updated",
                artifact_updates={
                    "content/reading-deck-blueprint": (
                        "reading-deck-blueprint",
                        {"title": "v2", "slides": [{"slide_id": "s1"}]},
                    )
                },
            )
            second_ref = state.artifact_heads[
                "content/reading-deck-blueprint"
            ]
            second, final = service.open_or_resume(
                command_id="open-v2",
                expected_revision=state.revision,
                review_type="content-full-deck",
                target_artifact_ref=second_ref,
                source_version="content-v2",
                target_revision=state.revision,
                open_policy="notify-only",
            )
            old = kernel.artifacts.resolve(
                ArtifactReference.parse(
                    final.artifact_heads[
                        f"review/session/{first['review_session_id']}"
                    ]
                )
            )["payload"]
            self.assertEqual(old["status"], "superseded")
            self.assertNotEqual(
                second["review_session_id"], first["review_session_id"]
            )
            self.assertEqual(
                final.artifact_heads[
                    "review/session/current/content-full-deck"
                ],
                final.artifact_heads[
                    f"review/session/{second['review_session_id']}"
                ],
            )

    def test_read_only_evidence_never_creates_a_business_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            with self.assertRaises(ContractValidationError):
                ReviewSessionService(kernel).open_or_resume(
                    command_id="open-evidence",
                    expected_revision=1,
                    review_type="content-evidence",
                    target_artifact_ref=target_ref,
                    source_version="content-v1",
                    target_revision=1,
                    open_policy="foreground-if-waiting",
                )
            self.assertFalse(
                any(
                    slot.startswith("review/session/")
                    for slot in kernel.load().artifact_heads
                )
            )

    def test_receipt_dimensions_are_independent_and_evidence_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            service, session, state = self._open_session(kernel, target_ref)
            opened, state = service.record_host_open_receipt(
                command_id="host-open",
                expected_revision=state.revision,
                review_session_id=str(session["review_session_id"]),
                result="opened",
                receipt_ref="host-receipt://open/001",
            )
            self.assertEqual(opened["host_open_status"], "opened")
            self.assertEqual(
                opened["host_notification_status"], "not-requested"
            )
            self.assertEqual(opened["ai_receipt_status"], "pending")

            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                service.record_ai_receipt(
                    command_id="forged-ai-receipt",
                    expected_revision=before.revision,
                    review_session_id=str(session["review_session_id"]),
                    result="received",
                    receipt_ref="",
                )
            self.assertEqual(kernel.load(), before)

            notified, state = service.record_host_notification_receipt(
                command_id="host-notification",
                expected_revision=state.revision,
                review_session_id=str(session["review_session_id"]),
                result="sent",
                receipt_ref="host-receipt://notification/001",
            )
            self.assertEqual(notified["host_open_status"], "opened")
            self.assertEqual(notified["host_notification_status"], "sent")
            self.assertEqual(notified["ai_receipt_status"], "pending")

            received, _state = service.record_ai_receipt(
                command_id="ai-receipt",
                expected_revision=state.revision,
                review_session_id=str(session["review_session_id"]),
                result="received",
                receipt_ref="ai-receipt://001",
            )
            self.assertEqual(received["host_open_status"], "opened")
            self.assertEqual(received["host_notification_status"], "sent")
            self.assertEqual(received["ai_receipt_status"], "received")

    def test_submit_keeps_session_current_and_does_not_infer_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            service, session, state = self._open_session(
                kernel,
                target_ref,
                open_policy="notify-only",
            )
            submitted, final = service.mark_submitted(
                command_id="submit-review",
                expected_revision=state.revision,
                review_session_id=str(session["review_session_id"]),
            )
            self.assertEqual(submitted["status"], "submitted")
            self.assertEqual(
                submitted["submitted_at"], "2026-08-23T00:00:00+00:00"
            )
            self.assertEqual(submitted["host_open_status"], "not-requested")
            self.assertEqual(
                submitted["host_notification_status"], "pending"
            )
            self.assertEqual(submitted["ai_receipt_status"], "pending")
            self.assertEqual(
                final.artifact_heads[
                    "review/session/current/content-full-deck"
                ],
                final.artifact_heads[
                    f"review/session/{session['review_session_id']}"
                ],
            )

    def test_explicit_supersede_clears_current_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, target_ref = kernel_with_target(Path(temp))
            service, session, state = self._open_session(kernel, target_ref)
            superseded, final = service.supersede_current(
                command_id="supersede-review",
                expected_revision=state.revision,
                review_type="content-full-deck",
            )
            self.assertIsNotNone(superseded)
            self.assertEqual(superseded["status"], "superseded")
            self.assertNotIn(
                "review/session/current/content-full-deck",
                final.artifact_heads,
            )
            historical_ref = final.artifact_heads[
                f"review/session/{session['review_session_id']}"
            ]
            historical = kernel.artifacts.resolve(
                ArtifactReference.parse(historical_ref)
            )["payload"]
            self.assertEqual(historical["status"], "superseded")


if __name__ == "__main__":
    unittest.main()
