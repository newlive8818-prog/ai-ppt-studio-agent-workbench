from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import GateBlockedError, ReviewSourceStaleError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_review_projection import accepted_review
from tests.test_v22_content_repair_loop import build_content


def snapshot_bytes(kernel: ProjectKernel) -> tuple[bytes, tuple, tuple]:
    events = tuple(
        (path.name, path.read_bytes())
        for path in sorted(kernel.events_root.glob("*.json"))
    )
    artifacts = tuple(
        (str(path.relative_to(kernel.artifacts.objects_root)), path.read_bytes())
        for path in sorted(kernel.artifacts.objects_root.rglob("*.json"))
    )
    return kernel.state_path.read_bytes(), events, artifacts


class ContentReviewRuntimeG0Tests(unittest.TestCase):
    def test_content_session_requires_exact_current_c2_acceptance_zero_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            kernel = ProjectKernel.initialize(project_root, project_id="p1")
            blueprint_ref = build_content(kernel)
            publication_revision = kernel.load().revision
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(GateBlockedError):
                dispatch_v16(
                    {
                        "operation": "open-or-resume-review-session",
                        "project_root": str(project_root),
                        "command_id": "open-before-content-acceptance",
                        "expected_revision": kernel.load().revision,
                        "review_type": "content-full-deck",
                        "target_artifact_ref": blueprint_ref,
                        "source_version": "content-v1",
                        "source_revision": publication_revision,
                        "open_policy": "foreground-if-waiting",
                    }
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)
            self.assertNotIn(
                "review/session/content-full-deck", kernel.load().artifact_heads
            )

    def test_persisted_content_session_requires_authoritative_publication_revision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            forged = validate_review_session(
                {**session, "revision": 0}, trusted_receipts=True
            )
            state = kernel.commit(
                command_id="forge-content-session-revision",
                expected_revision=state.revision,
                event_type="test.forged-content-session-revision",
                artifact_updates={
                    "review/session/content-full-deck": (
                        "review-session",
                        forged,
                    )
                },
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(ReviewSourceStaleError):
                ContentReviewProjectionService(kernel).project(
                    session["review_session_id"]
                )
            with self.assertRaises(ReviewSourceStaleError):
                ContentDecisionService(kernel).save(
                    command_id="save-through-forged-session-revision",
                    expected_revision=state.revision,
                    review_session_id=session["review_session_id"],
                    source_version="content-v1",
                    slide_id="S01",
                    decision="approved",
                    comment="",
                )
            self.assertEqual(snapshot_bytes(kernel), frozen)


if __name__ == "__main__":
    unittest.main()
