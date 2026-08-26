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
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.planning_service import (
    ContentRevisionPlanningService,
)
from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.application.presales_content_service import (
    PresalesContentService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.domains.content.page_decisions import validate_page_decision
from ai_ppt_studio.domains.content.review_batches import (
    validate_content_review_batch,
)
from ai_ppt_studio.errors import (
    ContractValidationError,
    GateBlockedError,
    ReviewSourceStaleError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
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


def revision_plan(rereview_scope: list[str]) -> dict[str, list]:
    return {
        "direct_changes": ["S01"],
        "cross_slide_changes": [],
        "merge_or_delete": [],
        "evidence_downgrades": [],
        "sequence_changes": [],
        "preserved": [],
        "conflicts": [],
        "rereview_scope": rereview_scope,
    }


def submitted_review(
    kernel: ProjectKernel,
    choices: list[tuple[str, str]],
) -> tuple[str, dict, str]:
    _blueprint_ref, _session_ref, session, state = accepted_review(
        kernel, slide_count=len(choices)
    )
    for order, (choice, comment) in enumerate(choices, start=1):
        _decision_ref, _decision, state = ContentDecisionService(kernel).save(
            command_id=f"save-{order}-{choice}",
            expected_revision=state.revision,
            review_session_id=session["review_session_id"],
            source_version="content-v1",
            slide_id=f"S{order:02d}",
            decision=choice,
            comment=comment,
        )
    batch_ref, _batch, _state = ContentReviewBatchService(kernel).submit(
        command_id="submit-review",
        expected_revision=state.revision,
        review_session_id=session["review_session_id"],
        source_version="content-v1",
    )
    return session["review_session_id"], session, batch_ref


def artifact_payload(kernel: ProjectKernel, reference: str) -> dict:
    return dict(
        kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]
    )


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

    def test_all_approved_batch_cannot_start_revision_plan_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _session_id, _session, batch_ref = submitted_review(
                kernel, [("approved", "")]
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(ContractValidationError):
                ContentRevisionPlanningService(kernel).save_plan(
                    command_id="reject-plan-for-all-approved",
                    expected_revision=kernel.load().revision,
                    batch_ref=batch_ref,
                    source_version="content-v1",
                    plan=revision_plan(["all"]),
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_revision_plan_requires_full_deck_rereview_scope_zero_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _session_id, _session, batch_ref = submitted_review(
                kernel, [("modify", "请调整本页")]
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(ContractValidationError):
                ContentRevisionPlanningService(kernel).save_plan(
                    command_id="reject-partial-rereview",
                    expected_revision=kernel.load().revision,
                    batch_ref=batch_ref,
                    source_version="content-v1",
                    plan=revision_plan(["S01"]),
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_rejects_a_batch_whose_decision_is_not_the_current_head_zero_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _session_id, _session, _batch_ref = submitted_review(
                kernel, [("approved", "")]
            )
            decision_slot = "content/review/decision/S01"
            submitted_decision_ref = kernel.load().artifact_heads[decision_slot]
            submitted_decision = artifact_payload(kernel, submitted_decision_ref)
            kernel.commit(
                command_id="replace-current-decision-after-submit",
                expected_revision=kernel.load().revision,
                event_type="test.current-decision-replaced",
                artifact_updates={
                    decision_slot: (
                        "content-page-decision",
                        {
                            **submitted_decision,
                            "page_decision_id": "replacement-after-submit",
                            "supersedes_decision_ref": submitted_decision_ref,
                        },
                    )
                },
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).open_g0_review(
                    command_id="reject-non-current-batch-decision",
                    expected_revision=kernel.load().revision,
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_rejects_a_foreign_or_historical_current_session_zero_write(
        self,
    ) -> None:
        for label, overrides in (
            ("foreign-session", {"review_session_id": "foreign-session"}),
            ("historical-revision", {"revision": 0}),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _session_id, _session, _batch_ref = submitted_review(
                    kernel, [("approved", "")]
                )
                session_slot = "review/session/content-full-deck"
                current_session_ref = kernel.load().artifact_heads[session_slot]
                current_session = artifact_payload(kernel, current_session_ref)
                forged = validate_review_session(
                    {**current_session, **overrides}, trusted_receipts=True
                )
                kernel.commit(
                    command_id=f"forge-{label}",
                    expected_revision=kernel.load().revision,
                    event_type="test.current-content-session-forged",
                    artifact_updates={
                        session_slot: ("review-session", forged)
                    },
                )
                frozen = snapshot_bytes(kernel)

                with self.assertRaises(GateBlockedError):
                    PresalesContentService(kernel).open_g0_review(
                        command_id=f"reject-{label}",
                        expected_revision=kernel.load().revision,
                    )

                self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_revalidates_every_current_decision_snapshot_field_zero_write(
        self,
    ) -> None:
        cases = (
            ("project_id", "foreign-project"),
            ("review_session_id", "foreign-session"),
            ("slide_order", 2),
            ("slide_title_snapshot", "被篡改的标题快照"),
        )
        for field, value in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _session_id, _session, old_batch_ref = submitted_review(
                    kernel, [("approved", "")]
                )
                decision_slot = "content/review/decision/S01"
                old_decision_ref = kernel.load().artifact_heads[decision_slot]
                old_decision = artifact_payload(kernel, old_decision_ref)
                forged_decision = validate_page_decision(
                    {
                        **old_decision,
                        "page_decision_id": f"forged-{field}",
                        "supersedes_decision_ref": old_decision_ref,
                        field: value,
                    }
                )
                forged_decision_ref = str(
                    kernel.artifacts.reference_for(
                        "content-page-decision", forged_decision
                    )
                )
                old_batch = artifact_payload(kernel, old_batch_ref)
                forged_batch = validate_content_review_batch(
                    {
                        **old_batch,
                        "batch_id": f"batch-with-forged-{field}",
                        "decision_refs": [forged_decision_ref],
                        "supersedes_ref": old_batch_ref,
                    }
                )
                kernel.commit(
                    command_id=f"install-forged-{field}",
                    expected_revision=kernel.load().revision,
                    event_type="test.content-review-lineage-forged",
                    artifact_updates={
                        decision_slot: (
                            "content-page-decision",
                            forged_decision,
                        ),
                        "content/review-batch": (
                            "content-review-batch",
                            forged_batch,
                        ),
                    },
                )
                frozen = snapshot_bytes(kernel)

                with self.assertRaises(GateBlockedError):
                    PresalesContentService(kernel).open_g0_review(
                        command_id=f"reject-forged-{field}",
                        expected_revision=kernel.load().revision,
                    )

                self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_rejects_cross_session_decision_history_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _session_id, _session, old_batch_ref = submitted_review(
                kernel, [("approved", "")]
            )
            decision_slot = "content/review/decision/S01"
            old_decision_ref = kernel.load().artifact_heads[decision_slot]
            old_decision = artifact_payload(kernel, old_decision_ref)
            foreign_predecessor = validate_page_decision(
                {
                    **old_decision,
                    "page_decision_id": "foreign-predecessor",
                    "review_session_id": "foreign-session",
                    "supersedes_decision_ref": "",
                }
            )
            foreign_ref = str(
                kernel.artifacts.reference_for(
                    "content-page-decision", foreign_predecessor
                )
            )
            current_decision = validate_page_decision(
                {
                    **old_decision,
                    "page_decision_id": "current-with-foreign-history",
                    "supersedes_decision_ref": foreign_ref,
                }
            )
            current_ref = str(
                kernel.artifacts.reference_for(
                    "content-page-decision", current_decision
                )
            )
            old_batch = artifact_payload(kernel, old_batch_ref)
            current_batch = validate_content_review_batch(
                {
                    **old_batch,
                    "batch_id": "batch-with-foreign-decision-history",
                    "decision_refs": [current_ref],
                    "supersedes_ref": old_batch_ref,
                }
            )
            kernel.commit(
                command_id="install-cross-session-decision-history",
                expected_revision=kernel.load().revision,
                event_type="test.cross-session-decision-history",
                artifact_updates={
                    decision_slot: (
                        "content-page-decision",
                        current_decision,
                    ),
                    "content/review-batch": (
                        "content-review-batch",
                        current_batch,
                    ),
                },
                detached_artifacts=(
                    ("content-page-decision", foreign_predecessor),
                ),
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).open_g0_review(
                    command_id="reject-cross-session-decision-history",
                    expected_revision=kernel.load().revision,
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_rejects_malformed_or_failed_current_hard_gate_lineage_zero_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            _session_id, _session, _batch_ref = submitted_review(
                kernel, [("approved", "")]
            )
            state = kernel.load()
            acceptance_ref = state.artifact_heads["content/acceptance"]
            acceptance = artifact_payload(kernel, acceptance_ref)
            malformed_gate = {"overall_result": "failed"}
            malformed_gate_ref = str(
                kernel.artifacts.reference_for(
                    "content-hard-gate-record", malformed_gate
                )
            )
            forged_acceptance = {
                **acceptance,
                "evidence_gate_ref": malformed_gate_ref,
            }
            kernel.commit(
                command_id="install-failed-gate-lineage",
                expected_revision=state.revision,
                event_type="test.failed-gate-lineage-installed",
                artifact_updates={
                    "content/gate/evidence": (
                        "content-hard-gate-record",
                        malformed_gate,
                    ),
                    "content/acceptance": (
                        "content-acceptance",
                        forged_acceptance,
                    ),
                },
            )
            frozen = snapshot_bytes(kernel)

            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).open_g0_review(
                    command_id="reject-failed-gate-lineage",
                    expected_revision=kernel.load().revision,
                )

            self.assertEqual(snapshot_bytes(kernel), frozen)

    def test_g0_revalidates_batch_project_and_counts_zero_write(self) -> None:
        cases = (
            ("foreign-project", {"project_id": "foreign-project"}),
            (
                "false-counts",
                {
                    "counts": {
                        "approved": 0,
                        "modify": 1,
                        "evidence": 0,
                        "merge-or-delete": 0,
                    }
                },
            ),
        )
        for label, overrides in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
                _session_id, _session, batch_ref = submitted_review(
                    kernel, [("approved", "")]
                )
                batch = artifact_payload(kernel, batch_ref)
                forged = validate_content_review_batch(
                    {
                        **batch,
                        **overrides,
                        "batch_id": f"forged-{label}",
                        "supersedes_ref": batch_ref,
                    }
                )
                kernel.commit(
                    command_id=f"install-{label}-batch",
                    expected_revision=kernel.load().revision,
                    event_type="test.content-review-batch-forged",
                    artifact_updates={
                        "content/review-batch": (
                            "content-review-batch",
                            forged,
                        )
                    },
                )
                frozen = snapshot_bytes(kernel)

                with self.assertRaises(GateBlockedError):
                    PresalesContentService(kernel).open_g0_review(
                        command_id=f"reject-{label}-batch",
                        expected_revision=kernel.load().revision,
                    )

                self.assertEqual(snapshot_bytes(kernel), frozen)


if __name__ == "__main__":
    unittest.main()
