from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.errors import (
    ContractValidationError,
    ReviewSessionAlreadyCurrentError,
    ReviewSessionStaleError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ReviewSessionAuthoritativeRevisionTests(unittest.TestCase):
    def test_historical_revision_cannot_supersede_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="project-01")
            published = kernel.commit(
                command_id="publish-source",
                expected_revision=0,
                event_type="test.source-published",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        {"source_version": "content-v1"},
                    )
                },
            )
            source_ref = published.artifact_heads["content/reading-blueprint"]
            service = ReviewSessionService(kernel)
            first_ref, first_session, opened = service.open_or_resume(
                command_id="open-current-source",
                expected_revision=published.revision,
                review_type="content-full-deck",
                target_artifact_ref=source_ref,
                source_version="content-v1",
                source_revision=published.revision,
                open_policy="notify-only",
            )
            before = kernel.load()
            before_bytes = (Path(folder) / "kernel" / "state.json").read_bytes()
            before_events = sorted(kernel.events_root.glob("r*.json"))

            with self.assertRaises(ReviewSessionStaleError):
                service.open_or_resume(
                    command_id="open-forged-history",
                    expected_revision=opened.revision,
                    review_type="content-full-deck",
                    target_artifact_ref=source_ref,
                    source_version="content-v1",
                    source_revision=0,
                    open_policy="notify-only",
                )

            self.assertEqual(kernel.load(), before)
            self.assertEqual(
                (Path(folder) / "kernel" / "state.json").read_bytes(),
                before_bytes,
            )
            self.assertEqual(sorted(kernel.events_root.glob("r*.json")), before_events)
            current_ref = before.artifact_heads["review/session/content-full-deck"]
            self.assertEqual(current_ref, first_ref)
            current = kernel.artifacts.resolve(ArtifactReference.parse(current_ref))[
                "payload"
            ]
            self.assertEqual(
                current["review_session_id"], first_session["review_session_id"]
            )

    def test_invalid_lifecycle_operations_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            kernel = ProjectKernel.initialize(root, project_id="project-01")
            published = kernel.commit(
                command_id="publish-source",
                expected_revision=0,
                event_type="test.source-published",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        {"source_version": "content-v1"},
                    )
                },
            )
            source_ref = published.artifact_heads["content/reading-blueprint"]
            service = ReviewSessionService(kernel)
            _ref, session, opened = service.open_or_resume(
                command_id="open-current-source",
                expected_revision=published.revision,
                review_type="content-full-deck",
                target_artifact_ref=source_ref,
                source_version="content-v1",
                source_revision=published.revision,
                open_policy="notify-only",
            )

            def assert_zero_write(error_type, operation) -> None:
                before_state = kernel.load()
                before_bytes = (root / "kernel" / "state.json").read_bytes()
                before_events = sorted(kernel.events_root.glob("r*.json"))
                with self.assertRaises(error_type):
                    operation(before_state.revision)
                self.assertEqual(kernel.load(), before_state)
                self.assertEqual(
                    (root / "kernel" / "state.json").read_bytes(), before_bytes
                )
                self.assertEqual(
                    sorted(kernel.events_root.glob("r*.json")), before_events
                )

            assert_zero_write(
                ReviewSessionStaleError,
                lambda revision: service.open_or_resume(
                    command_id="stale-source-revision",
                    expected_revision=revision,
                    review_type="content-full-deck",
                    target_artifact_ref=source_ref,
                    source_version="content-v1",
                    source_revision=0,
                    open_policy="notify-only",
                ),
            )
            assert_zero_write(
                ReviewSessionStaleError,
                lambda revision: service.record_host_open_outcome(
                    command_id="wrong-session-id",
                    expected_revision=revision,
                    review_type="content-full-deck",
                    review_session_id="wrong-session",
                    outcome="failed",
                    recorded_at="2026-08-26T00:00:00+08:00",
                ),
            )
            assert_zero_write(
                ContractValidationError,
                lambda revision: service.record_host_open_receipt(
                    command_id="wrong-receipt-kind",
                    expected_revision=revision,
                    review_type="content-full-deck",
                    receipt_ref=source_ref,
                ),
            )
            assert_zero_write(
                ReviewSessionAlreadyCurrentError,
                lambda revision: service.open_or_resume(
                    command_id="incompatible-open-policy",
                    expected_revision=revision,
                    review_type="content-full-deck",
                    target_artifact_ref=source_ref,
                    source_version="content-v1",
                    source_revision=published.revision,
                    open_policy="foreground-if-waiting",
                ),
            )
            self.assertEqual(
                opened.review_session_ref("content-full-deck"),
                kernel.load().review_session_ref("content-full-deck"),
            )
            current_ref = kernel.load().review_session_ref("content-full-deck")
            current = kernel.artifacts.resolve(
                ArtifactReference.parse(current_ref)
            )["payload"]
            self.assertEqual(
                session["review_session_id"], current["review_session_id"]
            )


if __name__ == "__main__":
    unittest.main()
