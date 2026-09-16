"""Substantive v2.2 migration of the historical content-acceptance regressions."""

from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    GateBlockedError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.material_finding_fixtures import source_inventory, bind_findings
from tests.test_v22_content_contracts import blueprint, decision_context, evidence_book
from tests.test_v22_content_repair_loop import build_content
from tests.test_v22_content_review_projection import accepted_review
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.v22_hard_gate_fixtures import semantic_checks


def authority_snapshot(kernel: ProjectKernel):
    events = tuple(sorted(path.name for path in kernel.events_root.glob("*.json")))
    objects = tuple(
        sorted(
            str(path.relative_to(kernel.artifacts.objects_root))
            for path in kernel.artifacts.objects_root.rglob("*.json")
        )
    )
    return kernel.load(), events, objects


def pass_content_gates(kernel: ProjectKernel) -> None:
    gates = ContentHardGateService(kernel)
    blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
    gates.run_evidence_gate(
        command_id="evidence-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=semantic_checks("evidence", blueprint_ref),
        reviewer_mode="isolated-review-task",
    )
    gates.run_presales_reading_gate(
        command_id="reading-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=semantic_checks("presales-reading", blueprint_ref),
        reviewer_mode="isolated-review-task",
    )


class V16ContentAcceptanceTests(unittest.TestCase):
    def test_direct_formal_stage_and_review_publication_fail_closed_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="direct-blocked")
            before = authority_snapshot(kernel)
            with self.assertRaises(WorkbenchValidationError):
                ContentHardGateService(kernel).commit_reviewer_output(
                    command_id="reviewer-cannot-edit",
                    expected_revision=0,
                    reviewer_role_id="content-evidence-gate-reviewer",
                    artifact_kind="reading-deck-blueprint",
                    payload={},
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_stage_and_review_reject_supplied_stale_framework_lineage_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="stale-lineage")
            first_blueprint_ref = build_content(kernel, "content-v1")
            first_blueprint = kernel.artifacts.resolve(
                ArtifactReference.parse(first_blueprint_ref)
            )["payload"]
            old_evidence_ref = first_blueprint["evidence_book_ref"]
            service = PresalesContentService(kernel)
            current = kernel.load()
            replacement = bind_findings(kernel, evidence_book())
            replacement["source_version"] = "content-v2"
            replacement["mission_confirmation_ref"] = current.artifact_heads[
                "mission/confirmation"
            ]
            replacement["material_inventory_ref"] = current.artifact_heads["materials"]
            service.build_evidence_book(
                "replace-evidence",
                current.revision,
                replacement,
            )
            stale_context = decision_context()
            stale_context["evidence_book_ref"] = old_evidence_ref
            before = authority_snapshot(kernel)
            with self.assertRaises(ArtifactReferenceError):
                service.build_decision_context(
                    "reject-stale-evidence",
                    kernel.load().revision,
                    stale_context,
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_acceptance_revalidates_every_current_content_chain_head_zero_write(self) -> None:
        slots = {
            "content/evidence-book": "presales-evidence-book",
            "content/decision-context": "customer-decision-context",
            "content/problem-solution-fit": "problem-solution-fit-map",
        }
        for slot, kind in slots.items():
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id="adversarial")
                build_content(kernel)
                current_ref = kernel.load().artifact_heads[slot]
                payload = kernel.artifacts.resolve(
                    ArtifactReference.parse(current_ref)
                )["payload"]
                state = kernel.commit(
                    command_id=f"tamper-{slot}",
                    expected_revision=kernel.load().revision,
                    event_type="test.current-content-lineage-tampered",
                    artifact_updates={slot: (f"not-{kind}", payload)},
                )
                before = authority_snapshot(kernel)
                with self.assertRaises(ArtifactReferenceError):
                    ContentHardGateService(kernel).run_evidence_gate(
                        command_id=f"reject-tampered-{slot}",
                        expected_revision=state.revision,
                        semantic_check_results=semantic_checks(
                            "evidence",
                            kernel.load().artifact_heads[
                                "content/reading-blueprint"
                            ],
                        ),
                        reviewer_mode="isolated-review-task",
                    )
                self.assertEqual(authority_snapshot(kernel), before)
                self.assertNotIn("content/acceptance", kernel.load().artifact_heads)

    def test_acceptance_rejects_wrong_kind_review_heads_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="review-kind")
            build_content(kernel)
            gates = ContentHardGateService(kernel)
            evidence_ref, _record, state = gates.run_evidence_gate(
                command_id="evidence-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence",
                    kernel.load().artifact_heads["content/reading-blueprint"],
                ),
                reviewer_mode="isolated-review-task",
            )
            payload = kernel.artifacts.resolve(
                ArtifactReference.parse(evidence_ref)
            )["payload"]
            state = kernel.commit(
                command_id="wrong-evidence-kind",
                expected_revision=state.revision,
                event_type="test.wrong-gate-kind",
                artifact_updates={
                    "content/gate/evidence": ("not-a-content-hard-gate-record", payload)
                },
            )
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                gates.run_presales_reading_gate(
                    command_id="reject-wrong-kind",
                    expected_revision=state.revision,
                    semantic_check_results=semantic_checks(
                        "presales-reading",
                        kernel.load().artifact_heads[
                            "content/reading-blueprint"
                        ],
                    ),
                    reviewer_mode="isolated-review-task",
                )
            self.assertEqual(authority_snapshot(kernel), before)
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)

    def test_formal_content_cannot_start_from_mission_readiness_alone(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="mission-only")
            mission = MissionMaterialService(kernel)
            draft_ref = mission.save_mission_draft(
                "mission",
                0,
                {
                    "topic": "经营一体化",
                    "primary_audience": "客户决策者",
                    "desired_judgment_or_action": "确认一期范围",
                },
            )
            mission.confirm_mission(
                "confirm",
                1,
                mission_draft_ref=draft_ref,
                material_mode="no-materials-confirmed",
                material_inventory_ref="",
                user_action_ref="test-user-action://mission-only",
                user_message_ref="",
            )
            premature = blueprint("proposal-led")
            premature["project_id"] = kernel.project_id
            before = authority_snapshot(kernel)
            with self.assertRaises(ArtifactReferenceError):
                PresalesContentService(kernel).build_reading_deck_blueprint(
                    "skip-four-content-objects",
                    kernel.load().revision,
                    premature,
                )
            self.assertEqual(authority_snapshot(kernel), before)
            self.assertNotIn("content/reading-blueprint", kernel.load().artifact_heads)

    def test_acceptance_requires_five_roles_and_chat_only_g0(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            acceptance = kernel.artifacts.resolve(
                ArtifactReference.parse(state.artifact_heads["content/acceptance"])
            )["payload"]
            self.assertEqual(
                set(acceptance),
                {
                    "source_version",
                    "reading_blueprint_ref",
                    "evidence_gate_ref",
                    "presales_reading_gate_ref",
                    "overall_result",
                    "accepted_at",
                },
            )
            self.assertNotIn("content/framework-confirmation", state.artifact_heads)
            self.assertNotIn(
                "content/full-deck-expansion-authorization",
                state.artifact_heads,
            )
            _decision_ref, _decision, state = ContentDecisionService(kernel).save(
                command_id="approve",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
            _batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
                command_id="submit",
                expected_revision=state.revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
            )
            service = PresalesContentService(kernel)
            state = service.open_g0_review(
                command_id="open-g0",
                expected_revision=state.revision,
            )
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    command_id="reject-non-chat-confirmation",
                    expected_revision=state.revision,
                    user_message_ref="review://approved",
                )
            self.assertEqual(authority_snapshot(kernel), before)
            context = service.gate_confirmation_context()
            confirmed = service.confirm_g0(
                command_id="confirm-g0",
                expected_revision=state.revision,
                **gate_confirmation_kwargs(
                    context,
                    identity_type="verified-message",
                    identity_ref="chat://message/verified-g0-confirmed",
                ),
            )
            self.assertEqual(confirmed.gate_status["G0"], "passed")
            self.assertEqual(confirmed.gate_status["G1"], "open")
            self.assertEqual(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(
                        confirmed.artifact_heads["gate/G0/confirmation"]
                    )
                )["payload"]["reading_blueprint_ref"],
                blueprint_ref,
            )

    def test_new_framework_invalidates_acceptance_without_additional_writes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="stale")
            first = build_content(kernel, "content-v1")
            pass_content_gates(kernel)
            self.assertIn("content/acceptance", kernel.load().artifact_heads)
            second = build_content(kernel, "content-v2")
            self.assertNotEqual(first, second)
            current = kernel.load()
            for slot in (
                "content/gate/evidence",
                "content/gate/presales-reading",
                "content/acceptance",
                "review/session/content-full-deck",
            ):
                self.assertNotIn(slot, current.artifact_heads)
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).open_g0_review(
                    command_id="reject-stale-acceptance",
                    expected_revision=current.revision,
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_missing_or_failed_review_blocks_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="missing")
            build_content(kernel)
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).open_g0_review(
                    command_id="missing-gates",
                    expected_revision=kernel.load().revision,
                )
            self.assertEqual(authority_snapshot(kernel), before)

        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="failed")
            blueprint_ref = build_content(kernel)
            gates = ContentHardGateService(kernel)
            _failed_ref, failed, _state = gates.run_evidence_gate(
                command_id="failed-evidence",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence",
                    blueprint_ref,
                    failed_check_id="unsupported-causality",
                ),
                reviewer_mode="isolated-review-task",
            )
            self.assertEqual(failed["overall_result"], "failed")
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                gates.run_presales_reading_gate(
                    command_id="reading-after-failed-evidence",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=semantic_checks(
                        "presales-reading", blueprint_ref
                    ),
                    reviewer_mode="isolated-review-task",
                )
            self.assertEqual(authority_snapshot(kernel), before)
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)


if __name__ == "__main__":
    unittest.main()
