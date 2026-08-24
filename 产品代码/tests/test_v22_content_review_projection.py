from __future__ import annotations

import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import (  # noqa: E402
    ContentHardGateService,
)
from ai_ppt_studio.application.review_session_service import (  # noqa: E402
    ReviewSessionService,
)
from ai_ppt_studio.errors import ContractValidationError  # noqa: E402
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.kernel.transactions import ProjectKernel  # noqa: E402
from tests.test_v22_content_hard_gates import (  # noqa: E402
    build_blueprint,
    submit_gate_via_command,
)


def projection_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_review.projection_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 content review projection service") from exc
    candidate = getattr(module, "ContentReviewProjectionService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing ContentReviewProjectionService")
    return candidate


def decision_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_review.decision_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 content page-decision service") from exc
    candidate = getattr(module, "ContentPageDecisionService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing ContentPageDecisionService")
    return candidate


def review_ready_kernel(
    *, slide_count: int = 1
) -> tuple[ProjectKernel, str, dict[str, Any]]:
    root = Path(tempfile.mkdtemp())
    kernel = ProjectKernel.initialize(root, project_id="content-review-projection")
    blueprint_ref = build_blueprint(kernel, slide_count=slide_count)
    submit_gate_via_command(
        kernel,
        blueprint_ref,
        gate_type="evidence",
        command_prefix="projection-evidence",
    )
    submit_gate_via_command(
        kernel,
        blueprint_ref,
        gate_type="presales-reading",
        command_prefix="projection-reading",
    )
    ContentHardGateService(kernel).accept_current_content(
        command_id="projection-accept",
        expected_revision=kernel.load().revision,
    )
    blueprint = kernel.artifacts.resolve(
        ArtifactReference.parse(blueprint_ref)
    )["payload"]
    session, _state = ReviewSessionService(
        kernel,
        clock=lambda: "2026-08-23T00:00:00+00:00",
    ).open_or_resume(
        command_id="projection-open-review",
        expected_revision=kernel.load().revision,
        review_type="content-full-deck",
        target_artifact_ref=blueprint_ref,
        source_version=str(blueprint["source_version"]),
        target_revision=kernel.load().revision,
        open_policy="foreground-if-waiting",
    )
    return kernel, blueprint_ref, session


def save_current_decisions(
    kernel: ProjectKernel,
    *,
    blueprint_ref: str,
    review_session_id: str,
    review_batch_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    blueprint = kernel.artifacts.resolve(
        ArtifactReference.parse(blueprint_ref)
    )["payload"]
    service = decision_service_type()(kernel)
    for index, slide in enumerate(blueprint["slides"]):
        service.save(
            command_id=f"projection-save-{review_batch_id}-{index}",
            expected_revision=kernel.load().revision,
            review_session_id=review_session_id,
            review_batch_id=review_batch_id,
            slide_id=str(slide["slide_id"]),
            decision="approved",
            comment="",
        )
    decision_set_ref = str(kernel.load().artifact_heads["content/page-decisions"])
    decision_set = kernel.artifacts.resolve(
        ArtifactReference.parse(decision_set_ref)
    )["payload"]
    return dict(blueprint), copy.deepcopy(decision_set)


def rebind_current_lineage_to_foreign_blueprint_project(
    kernel: ProjectKernel,
    *,
    blueprint_ref: str,
) -> tuple[str, dict[str, Any]]:
    """Persist a structurally current but cross-project content lineage."""

    state = kernel.load()
    blueprint = copy.deepcopy(
        kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))["payload"]
    )
    blueprint["project_id"] = "different-content-review-project"
    foreign_blueprint_ref = str(
        kernel.artifacts.reference_for("reading-deck-blueprint", blueprint)
    )

    evidence = copy.deepcopy(
        kernel.artifacts.resolve(
            ArtifactReference.parse(state.artifact_heads["content/gate/evidence"])
        )["payload"]
    )
    evidence["input_source_version"] = foreign_blueprint_ref
    evidence["input_hash"] = ArtifactReference.parse(foreign_blueprint_ref).sha256
    evidence_ref = str(
        kernel.artifacts.reference_for("content-hard-gate-record", evidence)
    )

    reading = copy.deepcopy(
        kernel.artifacts.resolve(
            ArtifactReference.parse(
                state.artifact_heads["content/gate/presales-reading"]
            )
        )["payload"]
    )
    reading["input_source_version"] = foreign_blueprint_ref
    reading["input_hash"] = ArtifactReference.parse(foreign_blueprint_ref).sha256
    reading["evidence_gate_ref"] = evidence_ref
    reading_ref = str(
        kernel.artifacts.reference_for("content-hard-gate-record", reading)
    )

    acceptance = copy.deepcopy(
        kernel.artifacts.resolve(
            ArtifactReference.parse(state.artifact_heads["content/acceptance"])
        )["payload"]
    )
    acceptance["source_version"] = foreign_blueprint_ref
    acceptance["evidence_gate_ref"] = evidence_ref
    acceptance["presales_reading_gate_ref"] = reading_ref
    acceptance["hard_gate_refs"] = [evidence_ref, reading_ref]

    kernel.commit(
        command_id="projection-install-foreign-project-lineage",
        expected_revision=state.revision,
        event_type="test.content-review-foreign-project-lineage",
        artifact_updates={
            "content/reading-deck-blueprint": (
                "reading-deck-blueprint",
                blueprint,
            ),
            "content/gate/evidence": ("content-hard-gate-record", evidence),
            "content/gate/presales-reading": (
                "content-hard-gate-record",
                reading,
            ),
            "content/acceptance": ("content-acceptance", acceptance),
        },
    )
    session, _state = ReviewSessionService(
        kernel,
        clock=lambda: "2026-08-23T00:02:00+00:00",
    ).open_or_resume(
        command_id="projection-open-foreign-project-session",
        expected_revision=kernel.load().revision,
        review_type="content-full-deck",
        target_artifact_ref=foreign_blueprint_ref,
        source_version=str(blueprint["source_version"]),
        target_revision=kernel.load().revision,
        open_policy="foreground-if-waiting",
    )
    return foreign_blueprint_ref, session


class ContentReviewProjectionTests(unittest.TestCase):
    def test_current_v22_ready_lineage_projects_without_legacy_authorizations(self) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))

        state = kernel.load()
        self.assertNotIn("content/framework-confirmation", state.artifact_heads)
        self.assertNotIn("content/full-deck-expansion", state.artifact_heads)

        projection = projection_service_type()(kernel).project(
            review_session_id=str(session["review_session_id"])
        )

        self.assertEqual(projection["surface"], "content-full-deck")
        self.assertEqual(projection["source_version"], blueprint_ref)
        self.assertEqual(
            projection["review_session"]["review_session_id"],
            session["review_session_id"],
        )
        self.assertEqual(
            projection["review_progress"]["total"],
            len(
                kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))[
                    "payload"
                ]["slides"]
            ),
        )
        self.assertEqual(projection["review_progress"]["completed"], 0)
        self.assertEqual(projection["gate_status"], "content-review-ready")

    def test_projection_rejects_missing_current_acceptance(self) -> None:
        kernel, _blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        kernel.commit(
            command_id="remove-acceptance",
            expected_revision=kernel.load().revision,
            event_type="test.acceptance-removed",
            artifact_updates={},
            artifact_removals=("content/acceptance",),
        )

        with self.assertRaisesRegex(ContractValidationError, "content/acceptance"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )

    def test_projection_rejects_session_for_a_different_logical_source_version(self) -> None:
        kernel, blueprint_ref, _session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        wrong_session, _state = ReviewSessionService(
            kernel,
            clock=lambda: "2026-08-23T00:01:00+00:00",
        ).open_or_resume(
            command_id="open-wrong-source-session",
            expected_revision=kernel.load().revision,
            review_type="content-full-deck",
            target_artifact_ref=blueprint_ref,
            source_version="wrong-logical-source-version",
            target_revision=kernel.load().revision,
            open_policy="foreground-if-waiting",
        )

        with self.assertRaisesRegex(ContractValidationError, "session"):
            projection_service_type()(kernel).project(
                review_session_id=str(wrong_session["review_session_id"])
            )

    def test_projection_rejects_current_content_slot_with_visual_session_payload(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        # Preserve the original identity head; only the current content slot is malformed.
        malformed = {**copy.deepcopy(session), "review_type": "visual-professional"}
        kernel.commit(
            command_id="test-set-content-slot-to-visual-session",
            expected_revision=kernel.load().revision,
            event_type="test.content-review-session-wrong-type",
            artifact_updates={
                "review/session/current/content-full-deck": ("review-session", malformed)
            },
        )

        with self.assertRaisesRegex(
            ContractValidationError, "review_type.*content-full-deck"
        ):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )
        self.assertEqual(
            kernel.load().artifact_heads["content/reading-deck-blueprint"],
            blueprint_ref,
        )

    def test_projection_rejects_current_content_slot_with_another_project_session_payload(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        # Preserve the original identity head; only the current content slot is malformed.
        malformed = {**copy.deepcopy(session), "project_id": "another-project"}
        kernel.commit(
            command_id="test-set-content-slot-to-another-project-session",
            expected_revision=kernel.load().revision,
            event_type="test.content-review-session-wrong-project",
            artifact_updates={
                "review/session/current/content-full-deck": ("review-session", malformed)
            },
        )

        with self.assertRaisesRegex(ContractValidationError, "project_id.*current project"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )
        self.assertEqual(
            kernel.load().artifact_heads["content/reading-deck-blueprint"],
            blueprint_ref,
        )

    def test_projection_rejects_current_slot_that_no_longer_matches_session_identity_head(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        # Retain the real session identity head and attach a different identity only to current.
        malformed = {
            **copy.deepcopy(session),
            "review_session_id": "content-session-not-in-identity-head",
        }
        kernel.commit(
            command_id="test-set-content-slot-to-unbound-session-identity",
            expected_revision=kernel.load().revision,
            event_type="test.content-review-session-identity-mismatch",
            artifact_updates={
                "review/session/current/content-full-deck": ("review-session", malformed)
            },
        )

        with self.assertRaisesRegex(ContractValidationError, "identity head"):
            projection_service_type()(kernel).project(
                review_session_id=str(malformed["review_session_id"])
            )
        self.assertEqual(
            kernel.load().artifact_heads["content/reading-deck-blueprint"],
            blueprint_ref,
        )

    def test_projection_rejects_current_lineage_with_another_blueprint_project(
        self,
    ) -> None:
        kernel, blueprint_ref, _session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        _foreign_ref, foreign_session = rebind_current_lineage_to_foreign_blueprint_project(
            kernel,
            blueprint_ref=blueprint_ref,
        )

        with self.assertRaisesRegex(
            ContractValidationError, "ReadingDeckBlueprint.*project"
        ):
            projection_service_type()(kernel).project(
                review_session_id=str(foreign_session["review_session_id"])
            )

    def test_projection_rejects_presales_reading_record_in_evidence_gate_slot(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel()
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        state = kernel.load()
        reading = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(
                    state.artifact_heads["content/gate/presales-reading"]
                )
            )["payload"]
        )
        wrong_evidence_ref = str(
            kernel.artifacts.reference_for("content-hard-gate-record", reading)
        )
        replacement_reading = copy.deepcopy(reading)
        replacement_reading["evidence_gate_ref"] = wrong_evidence_ref
        replacement_reading_ref = str(
            kernel.artifacts.reference_for(
                "content-hard-gate-record", replacement_reading
            )
        )
        acceptance = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(state.artifact_heads["content/acceptance"])
            )["payload"]
        )
        acceptance["source_version"] = blueprint_ref
        acceptance["evidence_gate_ref"] = wrong_evidence_ref
        acceptance["presales_reading_gate_ref"] = replacement_reading_ref
        acceptance["hard_gate_refs"] = [
            wrong_evidence_ref,
            replacement_reading_ref,
        ]
        kernel.commit(
            command_id="projection-install-reading-record-in-evidence-slot",
            expected_revision=state.revision,
            event_type="test.content-review-gate-type-slot-mismatch",
            artifact_updates={
                "content/gate/evidence": (
                    "content-hard-gate-record",
                    reading,
                ),
                "content/gate/presales-reading": (
                    "content-hard-gate-record",
                    replacement_reading,
                ),
                "content/acceptance": ("content-acceptance", acceptance),
            },
        )
        before = kernel.load()
        before_events = len(list(kernel.events_root.glob("r*.json")))

        with self.assertRaisesRegex(ContractValidationError, "evidence.*gate_type"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )

        self.assertEqual(kernel.load().revision, before.revision)
        self.assertEqual(kernel.load().artifact_heads, before.artifact_heads)
        self.assertEqual(len(list(kernel.events_root.glob("r*.json"))), before_events)

    def test_projection_rejects_decision_set_from_a_different_source_version(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        _blueprint, decision_set = save_current_decisions(
            kernel,
            blueprint_ref=blueprint_ref,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="projection-source-bound-batch",
        )
        decision_set["source_version"] = (
            "artifact://reading-deck-blueprint/" + "0" * 64
        )
        before = kernel.load()
        kernel.commit(
            command_id="projection-install-cross-source-decision-set",
            expected_revision=before.revision,
            event_type="test.content-review-decision-set-cross-source",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
        )

        with self.assertRaisesRegex(ContractValidationError, "decision set.*current"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )

    def test_projection_rejects_decision_with_a_different_review_batch(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        _blueprint, decision_set = save_current_decisions(
            kernel,
            blueprint_ref=blueprint_ref,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="projection-batch-bound-batch",
        )
        first_row = decision_set["decision_refs"][0]
        decision = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(str(first_row["decision_ref"]))
            )["payload"]
        )
        decision["review_batch_id"] = "another-content-review-batch"
        replacement_ref = str(
            kernel.artifacts.reference_for("content-page-decision", decision)
        )
        decision_set["decision_refs"][0]["decision_ref"] = replacement_ref
        before = kernel.load()
        kernel.commit(
            command_id="projection-install-cross-batch-page-decision",
            expected_revision=before.revision,
            event_type="test.content-review-page-decision-cross-batch",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
            detached_artifacts=(("content-page-decision", decision),),
        )

        with self.assertRaisesRegex(ContractValidationError, "decision.*lineage"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )

    def test_projection_rejects_decision_row_that_disagrees_with_page_payload(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        blueprint, decision_set = save_current_decisions(
            kernel,
            blueprint_ref=blueprint_ref,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="projection-row-bound-batch",
        )
        first_row = decision_set["decision_refs"][0]
        decision = copy.deepcopy(
            kernel.artifacts.resolve(
                ArtifactReference.parse(str(first_row["decision_ref"]))
            )["payload"]
        )
        decision["slide_id"] = str(blueprint["slides"][1]["slide_id"])
        decision["slide_order"] = int(blueprint["slides"][1]["order"])
        decision["slide_title_snapshot"] = str(
            blueprint["slides"][1]["neutral_title"]
        )
        replacement_ref = str(
            kernel.artifacts.reference_for("content-page-decision", decision)
        )
        decision_set["decision_refs"][0]["decision_ref"] = replacement_ref
        before = kernel.load()
        kernel.commit(
            command_id="projection-install-row-payload-mismatch",
            expected_revision=before.revision,
            event_type="test.content-review-decision-row-payload-mismatch",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
            detached_artifacts=(("content-page-decision", decision),),
        )

        with self.assertRaisesRegex(ContractValidationError, "decision.*lineage"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )

    def test_projection_rejects_decision_set_that_is_not_the_current_deck_map(
        self,
    ) -> None:
        kernel, blueprint_ref, session = review_ready_kernel(slide_count=2)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        _blueprint, decision_set = save_current_decisions(
            kernel,
            blueprint_ref=blueprint_ref,
            review_session_id=str(session["review_session_id"]),
            review_batch_id="projection-deck-map-batch",
        )
        decision_set["decision_refs"] = decision_set["decision_refs"][:1]
        decision_set["expected_slide_count"] = 1
        before = kernel.load()
        kernel.commit(
            command_id="projection-install-incomplete-decision-set",
            expected_revision=before.revision,
            event_type="test.content-review-decision-set-incomplete-map",
            artifact_updates={
                "content/page-decisions": (
                    "content-page-decision-set",
                    decision_set,
                )
            },
        )

        with self.assertRaisesRegex(ContractValidationError, "decision set.*deck"):
            projection_service_type()(kernel).project(
                review_session_id=str(session["review_session_id"])
            )


if __name__ == "__main__":
    unittest.main()
