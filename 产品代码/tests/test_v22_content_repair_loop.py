from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.presales_content_service import (  # noqa: E402
    PresalesContentService,
)
from ai_ppt_studio.application.project_service import (  # noqa: E402
    ProjectCommandService,
)
from ai_ppt_studio.errors import (  # noqa: E402
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.kernel.transactions import ProjectKernel  # noqa: E402
from tests.test_v22_content_contracts import valid_blueprint  # noqa: E402
from tests.test_v22_content_hard_gates import (  # noqa: E402
    build_blueprint,
    hard_gate_service_type,
    submit_gate_via_command,
)


class ContentRepairLoopTests(unittest.TestCase):
    def test_project_command_round_trip_runs_real_chief_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-command")
            old_blueprint_ref = build_blueprint(kernel)
            submit_gate_via_command(
                kernel,
                old_blueprint_ref,
                gate_type="evidence",
                command_prefix="repair-command-evidence-pass",
            )
            submit_gate_via_command(
                kernel,
                old_blueprint_ref,
                gate_type="presales-reading",
                command_prefix="repair-command-reading-pass",
            )
            failed_gate_ref = submit_gate_via_command(
                kernel,
                old_blueprint_ref,
                gate_type="evidence",
                command_prefix="repair-command-evidence-fail",
                result="failed",
            )
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-repair",
                kernel.load().revision,
                action_type="repair-reading-deck-blueprint",
                target_refs=[old_blueprint_ref, failed_gate_ref],
                instructions="严格按失败硬门要求修复完整阅读稿",
            )
            repaired = copy.deepcopy(
                kernel.artifacts.resolve(
                    ArtifactReference.parse(old_blueprint_ref)
                )["payload"]
            )
            repaired.update(
                {
                    "artifact_type": "reading-deck-blueprint",
                    "source_version": "source-version-command-repair",
                    "hard_gate_refs": [failed_gate_ref],
                    "repair_history": [
                        {
                            "source_version": old_blueprint_ref,
                            "failed_gate_refs": [failed_gate_ref],
                            "repair_summary": "按事实硬门补齐来源身份",
                            "new_source_version": "source-version-command-repair",
                        }
                    ],
                }
            )
            result_ref, state = commands.commit_noncontent_agent_result(
                command_id="commit-repair",
                expected_revision=kernel.load().revision,
                task_id=task["task_id"],
                request_kind="content-blueprint",
                raw_request_payload=repaired,
            )
            self.assertEqual(
                state.artifact_heads["content/reading-deck-blueprint"], result_ref
            )
            self.assertNotIn("content/gate/evidence", state.artifact_heads)
            self.assertEqual(
                commands.resolve_agent_task(task["task_id"])["status"], "completed"
            )

    def test_failed_gate_requires_new_source_version_and_clears_old_gate_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-project")
            old_blueprint_ref = build_blueprint(kernel)
            failed_gate_ref = submit_gate_via_command(
                kernel,
                old_blueprint_ref,
                gate_type="evidence",
                command_prefix="direct-repair-evidence-fail",
                result="failed",
            )
            old_payload = kernel.artifacts.resolve(
                ArtifactReference.parse(old_blueprint_ref)
            )["payload"]
            repaired = copy.deepcopy(old_payload)
            repaired["source_version"] = "source-version-2"
            repaired["repair_history"] = [
                {
                    "source_version": old_blueprint_ref,
                    "failed_gate_refs": [failed_gate_ref],
                    "repair_summary": "补齐来源和身份边界",
                    "new_source_version": "source-version-2",
                }
            ]
            repaired["hard_gate_refs"] = [failed_gate_ref]
            new_ref = PresalesContentService(kernel).repair_reading_blueprint(
                command_id="repair",
                expected_revision=kernel.load().revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=old_blueprint_ref,
                failed_gate_refs=[failed_gate_ref],
                payload=repaired,
            )
            state = kernel.load()
            self.assertNotEqual(new_ref, old_blueprint_ref)
            self.assertEqual(
                state.artifact_heads["content/reading-deck-blueprint"], new_ref
            )
            self.assertNotIn("content/gate/evidence", state.artifact_heads)
            self.assertNotIn("content/gate/presales-reading", state.artifact_heads)
            self.assertNotIn("content/acceptance", state.artifact_heads)

    def test_repair_rejects_nonfailed_or_stale_gate_record_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-blocked")
            blueprint_ref = build_blueprint(kernel)
            passed_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="blocked-repair-evidence-pass",
            )
            payload = valid_blueprint("mixed-evidence")
            old_payload = kernel.artifacts.resolve(
                ArtifactReference.parse(blueprint_ref)
            )["payload"]
            payload.update(
                {
                    "project_id": kernel.project_id,
                    "source_version": "source-version-2",
                    "evidence_book_ref": old_payload["evidence_book_ref"],
                    "decision_context_ref": old_payload["decision_context_ref"],
                    "problem_solution_fit_ref": old_payload[
                        "problem_solution_fit_ref"
                    ],
                    "hard_gate_refs": [passed_ref],
                    "repair_history": [
                        {
                            "source_version": blueprint_ref,
                            "failed_gate_refs": [passed_ref],
                            "repair_summary": "不应执行",
                            "new_source_version": "source-version-2",
                        }
                    ],
                }
            )
            before = kernel.load()
            with self.assertRaises(GateBlockedError):
                PresalesContentService(kernel).repair_reading_blueprint(
                    command_id="invalid-repair",
                    expected_revision=before.revision,
                    actor_role_id="presales-solution-chief",
                    source_blueprint_ref=blueprint_ref,
                    failed_gate_refs=[passed_ref],
                    payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_second_repair_requires_append_only_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-history")
            first_ref = build_blueprint(kernel)
            first_failed_ref = submit_gate_via_command(
                kernel,
                first_ref,
                gate_type="evidence",
                command_prefix="history-first-fail",
                result="failed",
            )
            service = PresalesContentService(kernel)
            first_payload = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(first_ref))["payload"]
            )
            first_payload["source_version"] = "source-version-2"
            first_payload["hard_gate_refs"] = [first_failed_ref]
            first_payload["repair_history"] = [
                {
                    "source_version": first_ref,
                    "failed_gate_refs": [first_failed_ref],
                    "repair_summary": "第一轮补齐来源",
                    "new_source_version": "source-version-2",
                }
            ]
            second_ref = service.repair_reading_blueprint(
                command_id="repair-history-first",
                expected_revision=kernel.load().revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=first_ref,
                failed_gate_refs=[first_failed_ref],
                payload=first_payload,
            )
            second_failed_ref = submit_gate_via_command(
                kernel,
                second_ref,
                gate_type="evidence",
                command_prefix="history-second-fail",
                result="failed",
            )
            truncated = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(second_ref))["payload"]
            )
            truncated["source_version"] = "source-version-3"
            truncated["hard_gate_refs"] = [second_failed_ref]
            truncated["repair_history"] = [
                {
                    "source_version": second_ref,
                    "failed_gate_refs": [second_failed_ref],
                    "repair_summary": "第二轮故意截断旧历史",
                    "new_source_version": "source-version-3",
                }
            ]
            before = kernel.load()
            with self.assertRaisesRegex(ContractValidationError, "append-only"):
                service.repair_reading_blueprint(
                    command_id="repair-history-truncated",
                    expected_revision=before.revision,
                    actor_role_id="presales-solution-chief",
                    source_blueprint_ref=second_ref,
                    failed_gate_refs=[second_failed_ref],
                    payload=truncated,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_second_repair_rejects_reused_logical_source_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-version-reuse")
            first_ref = build_blueprint(kernel)
            original = kernel.artifacts.resolve(
                ArtifactReference.parse(first_ref)
            )["payload"]
            original_source_version = original["source_version"]
            first_failed_ref = submit_gate_via_command(
                kernel,
                first_ref,
                gate_type="evidence",
                command_prefix="reuse-first-fail",
                result="failed",
            )
            service = PresalesContentService(kernel)
            first_payload = copy.deepcopy(original)
            first_payload["source_version"] = "source-version-2"
            first_payload["hard_gate_refs"] = [first_failed_ref]
            first_payload["repair_history"] = [
                {
                    "source_version": first_ref,
                    "failed_gate_refs": [first_failed_ref],
                    "repair_summary": "第一轮修复",
                    "new_source_version": "source-version-2",
                }
            ]
            second_ref = service.repair_reading_blueprint(
                command_id="repair-reuse-first",
                expected_revision=kernel.load().revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=first_ref,
                failed_gate_refs=[first_failed_ref],
                payload=first_payload,
            )
            second_failed_ref = submit_gate_via_command(
                kernel,
                second_ref,
                gate_type="evidence",
                command_prefix="reuse-second-fail",
                result="failed",
            )
            reused = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(second_ref))["payload"]
            )
            reused["source_version"] = original_source_version
            reused["hard_gate_refs"] = [second_failed_ref]
            reused["repair_history"] = list(reused["repair_history"]) + [
                {
                    "source_version": second_ref,
                    "failed_gate_refs": [second_failed_ref],
                    "repair_summary": "故意复用第一版逻辑版本",
                    "new_source_version": original_source_version,
                }
            ]
            before = kernel.load()
            with self.assertRaisesRegex(ContractValidationError, "source_version"):
                service.repair_reading_blueprint(
                    command_id="repair-version-reused",
                    expected_revision=before.revision,
                    actor_role_id="presales-solution-chief",
                    source_blueprint_ref=second_ref,
                    failed_gate_refs=[second_failed_ref],
                    payload=reused,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_repair_command_replay_returns_its_original_blueprint_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-replay")
            first_ref = build_blueprint(kernel)
            first_failed_ref = submit_gate_via_command(
                kernel,
                first_ref,
                gate_type="evidence",
                command_prefix="repair-replay-first-fail",
                result="failed",
            )
            service = PresalesContentService(kernel)
            first_payload = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(first_ref))["payload"]
            )
            first_payload["source_version"] = "source-version-2"
            first_payload["hard_gate_refs"] = [first_failed_ref]
            first_payload["repair_history"] = [
                {
                    "source_version": first_ref,
                    "failed_gate_refs": [first_failed_ref],
                    "repair_summary": "第一轮修复",
                    "new_source_version": "source-version-2",
                }
            ]
            first_revision = kernel.load().revision
            repaired_ref = service.repair_reading_blueprint(
                command_id="repair-replay-command",
                expected_revision=first_revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=first_ref,
                failed_gate_refs=[first_failed_ref],
                payload=first_payload,
            )
            second_failed_ref = submit_gate_via_command(
                kernel,
                repaired_ref,
                gate_type="evidence",
                command_prefix="repair-replay-second-fail",
                result="failed",
            )
            second_payload = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(repaired_ref))["payload"]
            )
            second_payload["source_version"] = "source-version-3"
            second_payload["hard_gate_refs"] = [second_failed_ref]
            second_payload["repair_history"] = list(second_payload["repair_history"]) + [
                {
                    "source_version": repaired_ref,
                    "failed_gate_refs": [second_failed_ref],
                    "repair_summary": "第二轮修复",
                    "new_source_version": "source-version-3",
                }
            ]
            latest_ref = service.repair_reading_blueprint(
                command_id="repair-replay-later-command",
                expected_revision=kernel.load().revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=repaired_ref,
                failed_gate_refs=[second_failed_ref],
                payload=second_payload,
            )
            self.assertNotEqual(latest_ref, repaired_ref)
            replayed_ref = service.repair_reading_blueprint(
                command_id="repair-replay-command",
                expected_revision=first_revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=first_ref,
                failed_gate_refs=[first_failed_ref],
                payload=first_payload,
            )
            self.assertEqual(replayed_ref, repaired_ref)

    def test_repair_command_replay_rejects_changed_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="repair-collision")
            blueprint_ref = build_blueprint(kernel)
            failed_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="repair-collision-fail",
                result="failed",
            )
            service = PresalesContentService(kernel)
            payload = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))["payload"]
            )
            payload["source_version"] = "source-version-2"
            payload["hard_gate_refs"] = [failed_ref]
            payload["repair_history"] = [
                {
                    "source_version": blueprint_ref,
                    "failed_gate_refs": [failed_ref],
                    "repair_summary": "首次修复",
                    "new_source_version": "source-version-2",
                }
            ]
            revision = kernel.load().revision
            service.repair_reading_blueprint(
                command_id="repair-collision-command",
                expected_revision=revision,
                actor_role_id="presales-solution-chief",
                source_blueprint_ref=blueprint_ref,
                failed_gate_refs=[failed_ref],
                payload=payload,
            )
            changed = copy.deepcopy(payload)
            changed["slides"][0]["speaker_notes"] = "更换为另一套语义"
            with self.assertRaisesRegex(
                ContractValidationError, "different semantics"
            ):
                service.repair_reading_blueprint(
                    command_id="repair-collision-command",
                    expected_revision=revision,
                    actor_role_id="presales-solution-chief",
                    source_blueprint_ref=blueprint_ref,
                    failed_gate_refs=[failed_ref],
                    payload=changed,
                )


if __name__ == "__main__":
    unittest.main()
