from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.presales_chief_orchestrator import (
    PresalesChiefOrchestrator,
)
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError, WorkbenchValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v22_content_domain_service import authority_snapshot
from tests.test_v22_presales_chief_orchestrator import (
    build_complete_chain,
    confirmed_kernel,
)
from tests.v22_hard_gate_fixtures import semantic_checks


class ContentHardGateServiceTests(unittest.TestCase):
    def test_projection_follows_two_current_source_gates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            gates = ContentHardGateService(kernel)
            not_ready = gates.inspect()
            self.assertEqual(not_ready["state"], "content-not-ready")
            self.assertEqual(not_ready["stop"]["code"], "CONTENT_BLUEPRINT_NOT_READY")

            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            evidence_ready = gates.inspect()
            exact_keys = {
                "project_id",
                "revision",
                "state",
                "source_version",
                "blueprint_ref",
                "evidence_gate_ref",
                "presales_reading_gate_ref",
                "acceptance_ref",
                "next_operation",
                "failure_refs",
                "repair_requirements",
                "stop",
            }
            self.assertEqual(set(evidence_ready), exact_keys)
            self.assertEqual(evidence_ready["state"], "evidence-gate-review")
            evidence_ref, _record, _state = gates.run_evidence_gate(
                command_id="evidence-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks("evidence", blueprint_ref),
                reviewer_mode="isolated-review-task",
            )
            reading_ready = gates.inspect()
            self.assertEqual(reading_ready["state"], "presales-reading-gate-review")
            self.assertEqual(reading_ready["evidence_gate_ref"], evidence_ref)
            reading_ref, _record, _state = gates.run_presales_reading_gate(
                command_id="reading-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks("presales-reading", blueprint_ref),
                reviewer_mode="isolated-review-task",
            )
            complete = gates.inspect()
            self.assertEqual(complete["state"], "content-user-reviewable")
            self.assertEqual(complete["presales_reading_gate_ref"], reading_ref)
            self.assertTrue(complete["acceptance_ref"])
            self.assertEqual(complete["stop"]["code"], "")

    def test_malformed_current_blueprint_governs_stop_and_cannot_pass_checks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            current_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            malformed = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(current_ref))["payload"]
            )
            malformed["slides"][0]["neutral_title"] = "本方案必然成功"
            malformed["slides"][0]["reading_quality"][
                "independently_readable"
            ] = False
            state = kernel.commit(
                command_id="seed-malformed-current-blueprint",
                expected_revision=kernel.load().revision,
                event_type="test.seed-malformed-current-blueprint",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        malformed,
                    )
                },
            )
            malformed_ref = state.artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            projection = gates.inspect()
            self.assertEqual(projection["state"], "governed-stop")
            self.assertEqual(projection["stop"]["code"], "CONTENT_CHAIN_INCONSISTENT")
            before = authority_snapshot(kernel)
            with self.assertRaises(ContractValidationError):
                gates.run_evidence_gate(
                    command_id="reject-malformed-current-blueprint",
                    expected_revision=state.revision,
                    semantic_check_results=semantic_checks(
                        "evidence", malformed_ref
                    ),
                    reviewer_mode="isolated-review-task",
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_failure_exposes_exact_requirements_without_reviewer_edit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            failure_ref, record, _state = gates.run_evidence_gate(
                command_id="evidence-fail",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence",
                    blueprint_ref,
                    failed_check_id="unsupported-causality",
                ),
                reviewer_mode="isolated-review-task",
            )
            self.assertEqual(record["overall_result"], "failed")
            self.assertEqual(
                record["repair_requirements"],
                [
                    {
                        "check_id": "unsupported-causality",
                        "instruction": "unsupported-causality requires chief repair",
                    }
                ],
            )
            projection = gates.inspect()
            self.assertEqual(projection["state"], "chief-repair")
            self.assertEqual(projection["failure_refs"], [failure_ref])
            self.assertEqual(
                projection["repair_requirements"], record["repair_requirements"]
            )
            with self.assertRaises(GateBlockedError):
                gates.run_presales_reading_gate(
                    command_id="reading-blocked",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=semantic_checks(
                        "presales-reading", blueprint_ref
                    ),
                    reviewer_mode="isolated-review-task",
                )

    def test_semantic_coverage_and_reviewer_mode_fail_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            invalid_sets = (
                [],
                semantic_checks("evidence", blueprint_ref)[:-1],
                [
                    *semantic_checks("evidence", blueprint_ref),
                    copy.deepcopy(semantic_checks("evidence", blueprint_ref)[0]),
                ],
            )
            for index, values in enumerate(invalid_sets):
                before = authority_snapshot(kernel)
                with self.subTest(case=index), self.assertRaises(
                    ContractValidationError
                ):
                    gates.run_evidence_gate(
                        command_id=f"invalid-semantic-{index}",
                        expected_revision=kernel.load().revision,
                        semantic_check_results=values,
                        reviewer_mode="isolated-review-task",
                    )
                self.assertEqual(authority_snapshot(kernel), before)
            before = authority_snapshot(kernel)
            with self.assertRaisesRegex(
                WorkbenchValidationError, "INDEPENDENT_REVIEW_RUNTIME_UNAVAILABLE"
            ):
                gates.run_evidence_gate(
                    command_id="fake-independent",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=semantic_checks("evidence", blueprint_ref),
                    reviewer_mode="independent-agent",
                    independent_agent_instance_id="fake-agent",
                    output_ref="artifact://agent-output/" + "f" * 64,
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_exact_replay_changed_semantics_and_cross_gate_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            values = semantic_checks("evidence", blueprint_ref)
            original_revision = kernel.load().revision
            first = gates.run_evidence_gate(
                command_id="semantic-command",
                expected_revision=original_revision,
                semantic_check_results=values,
                reviewer_mode="isolated-review-task",
            )
            after = authority_snapshot(kernel)
            replay = gates.run_evidence_gate(
                command_id="semantic-command",
                expected_revision=original_revision,
                semantic_check_results=copy.deepcopy(values),
                reviewer_mode="isolated-review-task",
            )
            self.assertEqual(replay[0], first[0])
            self.assertEqual(authority_snapshot(kernel), after)
            changed = copy.deepcopy(values)
            changed[0]["result"] = "failed"
            changed[0]["failure_reason"] = "changed"
            with self.assertRaisesRegex(
                ContractValidationError, "different semantics"
            ):
                gates.run_evidence_gate(
                    command_id="semantic-command",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=changed,
                    reviewer_mode="isolated-review-task",
                )
            with self.assertRaises(ContractValidationError):
                gates.run_presales_reading_gate(
                    command_id="semantic-command",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=semantic_checks(
                        "presales-reading", blueprint_ref
                    ),
                    reviewer_mode="isolated-review-task",
                )
            self.assertEqual(authority_snapshot(kernel), after)

    def test_committed_reviewer_output_exact_replay_accepts_original_revision(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            _seed_ref, record, _state = gates.run_evidence_gate(
                command_id="seed-reviewer-record",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks("evidence", blueprint_ref),
                reviewer_mode="isolated-review-task",
            )
            original_revision = kernel.load().revision
            first = gates.commit_reviewer_output(
                command_id="commit-reviewer-record",
                expected_revision=original_revision,
                reviewer_role_id="content-evidence-gate-reviewer",
                artifact_kind="content-hard-gate-record",
                payload=copy.deepcopy(record),
            )
            after = authority_snapshot(kernel)
            replay = gates.commit_reviewer_output(
                command_id="commit-reviewer-record",
                expected_revision=original_revision,
                reviewer_role_id="content-evidence-gate-reviewer",
                artifact_kind="content-hard-gate-record",
                payload=copy.deepcopy(record),
            )
            self.assertEqual(replay[0], first[0])
            self.assertEqual(authority_snapshot(kernel), after)

    def test_committed_reading_output_requires_current_passed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            blueprint_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            gates = ContentHardGateService(kernel)
            gates.run_evidence_gate(
                command_id="initial-evidence-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks("evidence", blueprint_ref),
                reviewer_mode="isolated-review-task",
            )
            _reading_ref, reading_record, _state = gates.run_presales_reading_gate(
                command_id="initial-reading-pass",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "presales-reading", blueprint_ref
                ),
                reviewer_mode="isolated-review-task",
            )
            gates.run_evidence_gate(
                command_id="current-evidence-failed",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence",
                    blueprint_ref,
                    failed_check_id="unsupported-causality",
                ),
                reviewer_mode="isolated-review-task",
            )
            failed_state = kernel.load()
            self.assertNotIn("content/gate/presales-reading", failed_state.artifact_heads)
            self.assertNotIn("content/acceptance", failed_state.artifact_heads)
            before = authority_snapshot(kernel)
            with self.assertRaises(GateBlockedError):
                gates.commit_reviewer_output(
                    command_id="reject-reading-after-failed-evidence",
                    expected_revision=failed_state.revision,
                    reviewer_role_id="content-presales-reading-gate-reviewer",
                    artifact_kind="content-hard-gate-record",
                    payload=copy.deepcopy(reading_record),
                )
            self.assertEqual(authority_snapshot(kernel), before)
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)

    def test_chief_repair_invalidates_gates_and_requires_exact_current_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = build_complete_chain(kernel)
            gates = ContentHardGateService(kernel)
            original_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            failed_ref, _record, _state = gates.run_evidence_gate(
                command_id="evidence-failed-before-repair",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence",
                    original_ref,
                    failed_check_id="unsupported-causality",
                ),
                reviewer_mode="isolated-review-task",
            )
            current = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(original_ref))["payload"]
            )
            current["slides"][0]["speaker_notes"] += " 已按硬门要求修复因果边界。"
            current["hard_gate_refs"] = [failed_ref]
            current["repair_history"].append(
                {"attempt_id": "repair-1", "failure_refs": [failed_ref]}
            )
            repaired = chief.repair_blueprint(
                command_id="chief-repair-1",
                expected_revision=kernel.load().revision,
                payload=current,
            )
            repaired_ref = repaired["created_ref"]
            self.assertNotEqual(repaired_ref, original_ref)
            repaired_state = kernel.load()
            self.assertNotIn("content/gate/evidence", repaired_state.artifact_heads)
            self.assertNotIn("content/gate/presales-reading", repaired_state.artifact_heads)
            self.assertNotIn("content/acceptance", repaired_state.artifact_heads)
            self.assertEqual(gates.inspect()["state"], "evidence-gate-review")

            with self.assertRaises(ContractValidationError):
                gates.run_evidence_gate(
                    command_id="reject-old-blueprint-semantics",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=semantic_checks("evidence", original_ref),
                    reviewer_mode="isolated-review-task",
                )
            evidence_ref, _evidence, _state = gates.run_evidence_gate(
                command_id="rerun-evidence-after-repair",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks("evidence", repaired_ref),
                reviewer_mode="isolated-review-task",
            )
            reading_ref, _reading, accepted = gates.run_presales_reading_gate(
                command_id="rerun-reading-after-repair",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "presales-reading", repaired_ref
                ),
                reviewer_mode="isolated-review-task",
            )
            acceptance_ref = accepted.artifact_heads["content/acceptance"]
            acceptance = kernel.artifacts.resolve(
                ArtifactReference.parse(acceptance_ref)
            )["payload"]
            self.assertEqual(acceptance["reading_blueprint_ref"], repaired_ref)
            self.assertEqual(acceptance["evidence_gate_ref"], evidence_ref)
            self.assertEqual(acceptance["presales_reading_gate_ref"], reading_ref)
            self.assertEqual(gates.inspect()["state"], "content-user-reviewable")

    def test_reading_gate_rejects_historical_same_version_evidence_hash(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            build_complete_chain(kernel)
            first_blueprint_ref = kernel.load().artifact_heads[
                "content/reading-blueprint"
            ]
            gates = ContentHardGateService(kernel)
            old_gate_ref, old_record, _state = gates.run_evidence_gate(
                command_id="old-evidence",
                expected_revision=kernel.load().revision,
                semantic_check_results=semantic_checks(
                    "evidence", first_blueprint_ref
                ),
                reviewer_mode="isolated-review-task",
            )
            current_blueprint = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(first_blueprint_ref))[
                    "payload"
                ]
            )
            current_blueprint["slides"][0]["speaker_notes"] += " 新版本"
            current_blueprint["hard_gate_refs"] = [old_gate_ref]
            current_blueprint["repair_history"] = [
                {
                    "attempt_id": "same-version-repair",
                    "failure_refs": [old_gate_ref],
                }
            ]
            # Seed a same-source replacement to isolate the C2 hash check.
            state = kernel.commit(
                command_id="same-source-replacement",
                expected_revision=kernel.load().revision,
                event_type="test.same-source-replacement",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        current_blueprint,
                    ),
                    "content/gate/evidence": (
                        "content-hard-gate-record",
                        old_record,
                    ),
                },
            )
            new_ref = state.artifact_heads["content/reading-blueprint"]
            self.assertNotEqual(new_ref, first_blueprint_ref)
            before = authority_snapshot(kernel)
            with self.assertRaises(ContractValidationError):
                gates.run_presales_reading_gate(
                    command_id="reject-same-version-old-hash",
                    expected_revision=state.revision,
                    semantic_check_results=semantic_checks(
                        "presales-reading", new_ref
                    ),
                    reviewer_mode="isolated-review-task",
                )
            self.assertEqual(authority_snapshot(kernel), before)


if __name__ == "__main__":
    unittest.main()
