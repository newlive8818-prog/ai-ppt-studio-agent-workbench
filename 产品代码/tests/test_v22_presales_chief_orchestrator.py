from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.presales_chief_orchestrator import (
    PresalesChiefOrchestrator,
)
from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import (
    blueprint,
    decision_context,
    evidence_book,
    fit_map,
)
from tests.test_v22_content_domain_service import authority_snapshot


def confirmed_kernel(folder: str, *, has_materials: bool) -> ProjectKernel:
    kernel = ProjectKernel.initialize(Path(folder), project_id="chief-project")
    mission = MissionMaterialService(kernel)
    draft_ref = mission.save_mission_draft(
        "mission-draft",
        0,
        {
            "topic": "经营一体化方案",
            "primary_audience": "客户决策团队",
            "desired_judgment_or_action": "确认联合验证范围",
        },
    )
    material_ref = ""
    if has_materials:
        material_ref = mission.register_materials(
            "materials",
            kernel.load().revision,
            {
                "sources": [
                    {
                        "source_id": "source-1",
                        "origin": "user-provided",
                        "kind": "text",
                        "locator": "inline://source-1",
                        "sha256": "a" * 64,
                    }
                ]
            },
        )
    mission.confirm_mission(
        "mission-confirmation",
        kernel.load().revision,
        mission_draft_ref=draft_ref,
        material_mode="materials-provided" if has_materials else "no-materials-confirmed",
        material_inventory_ref=material_ref,
        user_action_ref="test-user-action://confirm-chief-mission",
        user_message_ref="",
    )
    return kernel


def payloads_for(kernel: ProjectKernel, mode: str) -> list[dict]:
    state = kernel.load()
    evidence = evidence_book(mode)
    if mode == "material-backed":
        evidence["evidence_gaps"] = []
    evidence["mission_confirmation_ref"] = state.artifact_heads[
        "mission/confirmation"
    ]
    evidence["material_inventory_ref"] = state.artifact_heads.get("materials", "")
    return [evidence, decision_context(), fit_map(mode), blueprint(mode)]


def bind_current_refs(kernel: ProjectKernel, payload: dict) -> dict:
    value = copy.deepcopy(payload)
    heads = kernel.load().artifact_heads
    if "evidence_book_ref" in value:
        value["evidence_book_ref"] = heads["content/evidence-book"]
    if "decision_context_ref" in value:
        value["decision_context_ref"] = heads["content/decision-context"]
    if "problem_solution_fit_ref" in value:
        value["problem_solution_fit_ref"] = heads[
            "content/problem-solution-fit"
        ]
    if "project_id" in value:
        value["project_id"] = kernel.project_id
    return value


def build_complete_chain(kernel: ProjectKernel, mode: str = "material-backed") -> PresalesChiefOrchestrator:
    chief = PresalesChiefOrchestrator(kernel)
    for index, payload in enumerate(payloads_for(kernel, mode)):
        chief.advance(
            command_id=f"complete-{index}",
            expected_revision=kernel.load().revision,
            payload=bind_current_refs(kernel, payload),
        )
    return chief


def fail_evidence_gate(kernel: ProjectKernel, command_id: str) -> str:
    failed_ref, record, _state = ContentHardGateService(kernel).run_evidence_gate(
        command_id=command_id,
        expected_revision=kernel.load().revision,
        semantic_check_results=[
            {
                "check_id": "semantic-causality",
                "applicability": "applicable",
                "result": "failed",
                "hard": True,
                "evidence_refs": [
                    kernel.load().artifact_heads["content/reading-blueprint"]
                ],
                "failure_reason": "存在无证因果跳跃",
            }
        ],
        reviewer_mode="isolated-review-task",
    )
    assert record["overall_result"] == "failed"
    return failed_ref


class PresalesChiefOrchestratorTests(unittest.TestCase):
    def test_projection_is_closed_and_follows_the_four_object_chain(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            unconfirmed = ProjectKernel.initialize(Path(folder), project_id="unconfirmed")
            projection = PresalesChiefOrchestrator(unconfirmed).inspect()
            self.assertEqual(projection["state"], "mission-not-ready")
            self.assertEqual(projection["next_operation"], "")
            self.assertEqual(projection["stop"]["code"], "MISSION_NOT_CONFIRMED")

        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = PresalesChiefOrchestrator(kernel)
            payloads = payloads_for(kernel, "material-backed")
            expected = (
                ("reconstructing-evidence", "build-presales-evidence-book"),
                ("building-decision-context", "build-customer-decision-context"),
                (
                    "diagnosing-problem-solution-fit",
                    "build-problem-solution-fit",
                ),
                ("drafting-reading-deck", "build-reading-deck-blueprint"),
            )
            exact_keys = {
                "project_id",
                "revision",
                "state",
                "material_mode",
                "current_refs",
                "next_operation",
                "target_refs",
                "repair",
                "stop",
            }
            for index, (state, operation) in enumerate(expected):
                projection = chief.inspect()
                self.assertEqual(set(projection), exact_keys)
                self.assertEqual((projection["state"], projection["next_operation"]), (state, operation))
                value = bind_current_refs(kernel, payloads[index])
                chief.advance(
                    command_id=f"step-{index}",
                    expected_revision=kernel.load().revision,
                    payload=value,
                )
            complete = chief.inspect()
            self.assertEqual(complete["state"], "ready-for-independent-gates")
            self.assertEqual(complete["next_operation"], "")
            self.assertEqual(complete["stop"]["code"], "")
            self.assertNotIn("gate", complete)
            self.assertNotIn("review", complete)
            self.assertNotIn("host_notification", complete)
            self.assertNotIn("ai_receipt", complete)

    def test_three_material_modes_advance_deterministically(self) -> None:
        for mode, has_materials in (
            ("material-backed", True),
            ("mixed-evidence", True),
            ("proposal-led", False),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                kernel = confirmed_kernel(folder, has_materials=has_materials)
                chief = PresalesChiefOrchestrator(kernel)
                results = []
                for index, raw_payload in enumerate(payloads_for(kernel, mode)):
                    before_revision = kernel.load().revision
                    result = chief.advance(
                        command_id=f"{mode}-{index}",
                        expected_revision=before_revision,
                        payload=bind_current_refs(kernel, raw_payload),
                    )
                    results.append(result)
                    self.assertEqual(kernel.load().revision, before_revision + 1)
                    self.assertEqual(
                        ArtifactReference.parse(result["created_ref"]).kind,
                        (
                            "presales-evidence-book",
                            "customer-decision-context",
                            "problem-solution-fit-map",
                            "reading-deck-blueprint",
                        )[index],
                    )
                self.assertEqual(
                    results[-1]["projection"]["state"],
                    "ready-for-independent-gates",
                )
                self.assertEqual(
                    results[-1]["projection"]["material_mode"], mode
                )
                heads = kernel.load().artifact_heads
                self.assertNotIn("content/framework-confirmation", heads)
                self.assertNotIn(
                    "content/full-deck-expansion-authorization", heads
                )

    def test_advance_rejections_and_replay_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = PresalesChiefOrchestrator(kernel)
            evidence = payloads_for(kernel, "material-backed")[0]

            wrong_mode = copy.deepcopy(evidence)
            wrong_mode["material_mode"] = "mixed-evidence"
            before = authority_snapshot(kernel)
            with self.assertRaises(ContractValidationError):
                chief.advance(
                    command_id="wrong-mode",
                    expected_revision=kernel.load().revision,
                    payload=wrong_mode,
                )
            self.assertEqual(authority_snapshot(kernel), before)

            later_payload = fit_map()
            before = authority_snapshot(kernel)
            with self.assertRaises(ContractValidationError):
                chief.advance(
                    command_id="skip",
                    expected_revision=kernel.load().revision,
                    payload=later_payload,
                )
            self.assertEqual(authority_snapshot(kernel), before)

            before = authority_snapshot(kernel)
            with self.assertRaises(RevisionConflictError):
                chief.advance(
                    command_id="stale",
                    expected_revision=kernel.load().revision - 1,
                    payload=evidence,
                )
            self.assertEqual(authority_snapshot(kernel), before)

            original_revision = kernel.load().revision
            first = chief.advance(
                command_id="evidence",
                expected_revision=original_revision,
                payload=evidence,
            )
            after_first = authority_snapshot(kernel)
            replay = chief.advance(
                command_id="evidence",
                expected_revision=original_revision,
                payload=copy.deepcopy(evidence),
            )
            self.assertEqual(replay["created_ref"], first["created_ref"])
            self.assertEqual(authority_snapshot(kernel), after_first)

            changed = copy.deepcopy(evidence)
            changed["generated_at"] = "2026-08-17T00:00:00+08:00"
            with self.assertRaisesRegex(
                ContractValidationError, "different semantics"
            ):
                chief.advance(
                    command_id="evidence",
                    expected_revision=kernel.load().revision,
                    payload=changed,
                )
            self.assertEqual(authority_snapshot(kernel), after_first)

    def test_failed_gate_enables_only_bounded_blueprint_repair(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = build_complete_chain(kernel)
            failure_ref = fail_evidence_gate(kernel, "gate-failed-0")

            projection = chief.inspect()
            self.assertEqual(projection["state"], "chief-repair")
            self.assertEqual(
                projection["next_operation"], "repair-reading-deck-blueprint"
            )
            self.assertEqual(projection["repair"]["failure_refs"], [failure_ref])
            self.assertEqual(projection["repair"]["attempts_used"], 0)
            self.assertEqual(projection["repair"]["attempts_remaining"], 3)

            for attempt in range(1, 4):
                current_ref = kernel.load().artifact_heads[
                    "content/reading-blueprint"
                ]
                repaired = copy.deepcopy(
                    kernel.artifacts.resolve(ArtifactReference.parse(current_ref))[
                        "payload"
                    ]
                )
                repaired["hard_gate_refs"] = [failure_ref]
                repaired["repair_history"].append(
                    {
                        "attempt_id": f"repair-{attempt}",
                        "failure_refs": [failure_ref],
                    }
                )
                result = chief.repair_blueprint(
                    command_id=f"repair-command-{attempt}",
                    expected_revision=kernel.load().revision,
                    payload=repaired,
                )
                self.assertEqual(
                    result["operation"], "repair-reading-deck-blueprint"
                )
                self.assertNotIn(
                    "content/gate/evidence", kernel.load().artifact_heads
                )
                if attempt == 1:
                    after_repair = authority_snapshot(kernel)
                    replay = chief.repair_blueprint(
                        command_id="repair-command-1",
                        expected_revision=result["projection"]["revision"] - 1,
                        payload=copy.deepcopy(repaired),
                    )
                    self.assertEqual(replay["created_ref"], result["created_ref"])
                    self.assertEqual(authority_snapshot(kernel), after_repair)
                    with self.assertRaises(ContractValidationError):
                        chief.advance(
                            command_id="repair-command-1",
                            expected_revision=kernel.load().revision,
                            payload=copy.deepcopy(repaired),
                        )
                    self.assertEqual(authority_snapshot(kernel), after_repair)
                failure_ref = fail_evidence_gate(
                    kernel, f"gate-failed-{attempt}"
                )

            exhausted = chief.inspect()
            self.assertEqual(exhausted["state"], "governed-stop")
            self.assertEqual(
                exhausted["stop"]["code"], "REPAIR_ATTEMPTS_EXHAUSTED"
            )
            self.assertEqual(exhausted["repair"]["attempts_used"], 3)
            self.assertEqual(exhausted["repair"]["attempts_remaining"], 0)
            before = authority_snapshot(kernel)
            current = kernel.artifacts.resolve(
                ArtifactReference.parse(
                    kernel.load().artifact_heads["content/reading-blueprint"]
                )
            )["payload"]
            with self.assertRaisesRegex(
                ContractValidationError, "repair attempts are exhausted"
            ):
                chief.repair_blueprint(
                    command_id="repair-command-4",
                    expected_revision=kernel.load().revision,
                    payload=copy.deepcopy(current),
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_invalid_repairs_are_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = build_complete_chain(kernel)
            current_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            base = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(current_ref))[
                    "payload"
                ]
            )
            before = authority_snapshot(kernel)
            no_gate = copy.deepcopy(base)
            no_gate["repair_history"] = [
                {"attempt_id": "repair-1", "failure_refs": [current_ref]}
            ]
            with self.assertRaises(ContractValidationError):
                chief.repair_blueprint(
                    command_id="repair-without-failure",
                    expected_revision=kernel.load().revision,
                    payload=no_gate,
                )
            self.assertEqual(authority_snapshot(kernel), before)

            failure_ref = fail_evidence_gate(kernel, "repair-invalid-gate")
            base["hard_gate_refs"] = [failure_ref]
            invalid_histories = (
                [],
                [
                    {"attempt_id": "same", "failure_refs": [failure_ref]},
                    {"attempt_id": "same", "failure_refs": [failure_ref]},
                ],
                [
                    {
                        "attempt_id": "repair-1",
                        "failure_refs": [current_ref],
                    }
                ],
                [
                    {
                        "attempt_id": "repair-1",
                        "failure_refs": [failure_ref],
                        "gate_result": "passed",
                    }
                ],
            )
            for index, history in enumerate(invalid_histories):
                invalid = copy.deepcopy(base)
                invalid["repair_history"] = history
                before = authority_snapshot(kernel)
                with self.subTest(history=index), self.assertRaises(
                    ContractValidationError
                ):
                    chief.repair_blueprint(
                        command_id=f"invalid-repair-{index}",
                        expected_revision=kernel.load().revision,
                        payload=invalid,
                    )
                self.assertEqual(authority_snapshot(kernel), before)

    def test_blueprint_build_and_repair_command_identities_cannot_cross(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = build_complete_chain(kernel)
            current_ref = kernel.load().artifact_heads["content/reading-blueprint"]
            ordinary = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(current_ref))[
                    "payload"
                ]
            )
            before = authority_snapshot(kernel)
            with self.assertRaises(ContractValidationError):
                chief.repair_blueprint(
                    command_id="complete-3",
                    expected_revision=kernel.load().revision,
                    payload=ordinary,
                )
            self.assertEqual(authority_snapshot(kernel), before)

    def test_initial_blueprint_rejects_repair_and_gate_claims_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = PresalesChiefOrchestrator(kernel)
            payloads = payloads_for(kernel, "material-backed")
            for index in range(3):
                chief.advance(
                    command_id=f"initial-{index}",
                    expected_revision=kernel.load().revision,
                    payload=bind_current_refs(kernel, payloads[index]),
                )
            ordinary = bind_current_refs(kernel, payloads[3])
            fake_gate = "artifact://content-hard-gate-record/" + "f" * 64
            invalid_values = (
                {"repair_history": [{"not": "a repair record"}]},
                {
                    "repair_history": [
                        {
                            "attempt_id": "forged-attempt",
                            "failure_refs": [fake_gate],
                        }
                    ]
                },
                {"hard_gate_refs": [fake_gate]},
                {"hard_gate_refs": [fake_gate, fake_gate]},
            )
            for index, changes in enumerate(invalid_values):
                value = copy.deepcopy(ordinary)
                value.update(changes)
                before = authority_snapshot(kernel)
                with self.subTest(case=index), self.assertRaises(
                    ContractValidationError
                ):
                    chief.advance(
                        command_id=f"forged-blueprint-{index}",
                        expected_revision=kernel.load().revision,
                        payload=value,
                    )
                self.assertEqual(authority_snapshot(kernel), before)

    def test_consultant_capability_is_truthful_bounded_and_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = confirmed_kernel(folder, has_materials=True)
            chief = build_complete_chain(kernel)
            projection = chief.inspect()
            self.assertNotIn("consultant", projection)
            target = projection["current_refs"]["reading_blueprint"]
            before = authority_snapshot(kernel)
            result = chief.consultant_capability(
                risk_area="data-security",
                question="请识别当前方案中的数据安全风险边界。",
                target_refs=[target],
            )
            self.assertEqual(
                result,
                {
                    "status": "unavailable",
                    "code": "CONSULTANT_RUNTIME_UNAVAILABLE",
                    "requested_role": "presales-risk-specialist/data-security",
                    "write_authority": "none",
                    "target_refs": [target],
                },
            )
            self.assertEqual(authority_snapshot(kernel), before)
            self.assertFalse(
                any(
                    slot.startswith("agent/")
                    for slot in kernel.load().artifact_heads
                )
            )

            invalid_requests = (
                ("Data Security", "有效问题", [target]),
                ("data-security", " ", [target]),
                ("data-security", "x" * 501, [target]),
                ("data-security", "有效问题", [target, target]),
                (
                    "data-security",
                    "有效问题",
                    ["artifact://reading-deck-blueprint/" + "f" * 64],
                ),
                ("data-security", "有效问题", ["not-a-ref"]),
            )
            for index, (risk_area, question, targets) in enumerate(
                invalid_requests
            ):
                before = authority_snapshot(kernel)
                with self.subTest(request=index), self.assertRaises(
                    ContractValidationError
                ):
                    chief.consultant_capability(
                        risk_area=risk_area,
                        question=question,
                        target_refs=targets,
                    )
                self.assertEqual(authority_snapshot(kernel), before)

if __name__ == "__main__":
    unittest.main()
