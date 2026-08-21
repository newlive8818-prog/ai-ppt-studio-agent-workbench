from pathlib import Path
import tempfile
import unittest

from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.errors import ContractValidationError
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

            with self.assertRaisesRegex(
                ContractValidationError,
                "source_revision must equal the current target publication revision",
            ):
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
            current_ref = before.artifact_heads["review/session/content-full-deck"]
            self.assertEqual(current_ref, first_ref)
            current = kernel.artifacts.resolve(ArtifactReference.parse(current_ref))[
                "payload"
            ]
            self.assertEqual(
                current["review_session_id"], first_session["review_session_id"]
            )


if __name__ == "__main__":
    unittest.main()
