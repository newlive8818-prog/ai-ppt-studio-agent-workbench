from __future__ import annotations

import copy
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.content import contracts  # noqa: E402
from ai_ppt_studio.errors import (  # noqa: E402
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.kernel.transactions import ProjectKernel  # noqa: E402
from ai_ppt_studio.application.presales_content_service import (  # noqa: E402
    PresalesContentService,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator  # noqa: E402
from ai_ppt_studio.application.project_service import (  # noqa: E402
    ProjectCommandService,
)
from tests.test_v22_content_contracts import (  # noqa: E402
    valid_blueprint,
    valid_decision_context,
    valid_evidence_book,
    valid_fit_map,
)


def hard_gate_validator() -> Callable[[dict[str, Any]], dict[str, Any]]:
    candidate = getattr(contracts, "validate_content_hard_gate_record", None)
    if not callable(candidate):
        raise AssertionError("missing v2.2 ContentHardGateRecord validator")
    return candidate


def hard_gate_service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.content_hard_gate_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 ContentHardGateService") from exc
    candidate = getattr(module, "ContentHardGateService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing v2.2 ContentHardGateService")
    return candidate


def build_blueprint(
    kernel: ProjectKernel, *, mode: str = "mixed-evidence", slide_count: int = 1
) -> str:
    service = PresalesContentService(kernel)
    book_ref = service.build_presales_evidence_book(
        command_id="book",
        expected_revision=kernel.load().revision,
        actor_role_id="presales-solution-chief",
        material_mode=mode,
        payload=valid_evidence_book(mode),
    )
    decision = valid_decision_context()
    decision["evidence_book_ref"] = book_ref
    decision_ref = service.build_customer_decision_context(
        command_id="decision",
        expected_revision=kernel.load().revision,
        actor_role_id="presales-solution-chief",
        evidence_book_ref=book_ref,
        payload=decision,
    )
    fit_ref = service.build_problem_solution_fit(
        command_id="fit",
        expected_revision=kernel.load().revision,
        actor_role_id="presales-solution-chief",
        evidence_book_ref=book_ref,
        decision_context_ref=decision_ref,
        payload=valid_fit_map(),
    )
    blueprint = valid_blueprint(mode)
    if slide_count < 1:
        raise ValueError("slide_count must be positive")
    first_slide = blueprint["slides"][0]
    blueprint["slides"] = []
    for order in range(1, slide_count + 1):
        slide = copy.deepcopy(first_slide)
        slide["slide_id"] = f"slide-{order}"
        slide["order"] = order
        slide["neutral_title"] = f"经营审批协同的一期讨论范围（第 {order} 页）"
        slide["previous_relation"] = "开篇" if order == 1 else "承接上一页讨论"
        slide["next_relation"] = (
            "下一页展开当前问题和证据缺口"
            if order < slide_count
            else "本稿结束"
        )
        blueprint["slides"].append(slide)
    blueprint.update(
        {
            "project_id": kernel.project_id,
            "evidence_book_ref": book_ref,
            "decision_context_ref": decision_ref,
            "problem_solution_fit_ref": fit_ref,
        }
    )
    return service.build_reading_blueprint(
        command_id="blueprint",
        expected_revision=kernel.load().revision,
        actor_role_id="presales-solution-chief",
        material_mode=mode,
        evidence_book_ref=book_ref,
        decision_context_ref=decision_ref,
        problem_solution_fit_ref=fit_ref,
        payload=blueprint,
    )


def valid_gate_record(
    source_ref: str,
    *,
    gate_type: str = "evidence",
    result: str = "passed",
    reviewer_mode: str = "isolated-review-task",
    context_pack_ref: str = "artifact://context-pack/" + "d" * 64,
    independent_agent_instance_id: str = "agent-instance-1",
    review_output_ref: str = "artifact://review-output/" + "c" * 64,
    evidence_gate_ref: str = "artifact://content-hard-gate-record/" + "e" * 64,
) -> dict[str, Any]:
    role = (
        "content-evidence-gate-reviewer"
        if gate_type == "evidence"
        else "content-presales-reading-gate-reviewer"
    )
    failed = result == "failed"
    criteria = {
        "evidence": (
            "source-resolution",
            "excluded-materials",
            "content-identity",
            "diagnosis-traceability",
            "selective-evidence",
            "causal-leap",
            "unsupported-capability-result-or-commitment",
            "problem-requirement-solution-traceability",
            "material-mode-honesty",
        ),
        "presales-reading": (
            "customer-decision-stance",
            "current-state-and-problem-completeness",
            "symptom-cause-impact-constraint-unknown",
            "problem-requirement-solution-mapping",
            "neutral-title",
            "no-conclusion-first",
            "independent-reading-without-notes",
            "deck-coherence",
            "meaningless-repetition",
            "boundaries-risks-validation-and-next-actions",
        ),
    }[gate_type]
    checks = []
    for index, criterion_id in enumerate(criteria):
        check_failed = failed and index == 0
        checks.append(
            {
                "criterion_id": criterion_id,
                "applicability": "applicable",
                "result": "failed" if check_failed else "passed",
                "evidence_refs": [source_ref],
                "failure_reason": "来源身份不完整" if check_failed else "",
                "repair_requirement": "补齐来源和身份" if check_failed else "",
            }
        )
    record: dict[str, Any] = {
        "gate_type": gate_type,
        "input_source_version": source_ref,
        "input_hash": ArtifactReference.parse(source_ref).sha256,
        "reviewer_role_id": role,
        "reviewer_mode": reviewer_mode,
        "context_pack_ref": context_pack_ref,
        "context_sha256": ArtifactReference.parse(context_pack_ref).sha256,
        "deterministic_check_results": checks[:4],
        "semantic_check_results": checks[4:],
        "repair_requirements": ["补齐来源和身份"] if failed else [],
        "overall_result": result,
        "reviewer_cannot_edit": True,
        "created_at": "2026-08-23T00:00:00+00:00",
    }
    if gate_type == "presales-reading":
        record["evidence_gate_ref"] = evidence_gate_ref
    if reviewer_mode == "independent-agent":
        record.update(
            {
                "independent_agent_instance_id": independent_agent_instance_id,
                "review_output_ref": review_output_ref,
            }
        )
    return record


def valid_gate_record_for_kernel(
    kernel: ProjectKernel,
    source_ref: str,
    **kwargs: Any,
) -> dict[str, Any]:
    context_ref = str(
        kernel.artifacts.put(
            "context-pack",
            {"project_id": kernel.project_id, "purpose": "hard-gate-test"},
        )
    )
    return valid_gate_record(
        source_ref,
        context_pack_ref=context_ref,
        **kwargs,
    )


def gate_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *payload["deterministic_check_results"],
        *payload["semantic_check_results"],
    ]


def submit_gate_via_command(
    kernel: ProjectKernel,
    blueprint_ref: str,
    *,
    gate_type: str,
    command_prefix: str,
    result: str = "passed",
) -> str:
    action = (
        "run-content-evidence-gate"
        if gate_type == "evidence"
        else "run-content-presales-reading-gate"
    )
    evidence_ref = kernel.load().artifact_heads.get("content/gate/evidence", "")
    targets = [blueprint_ref]
    if gate_type == "presales-reading":
        targets.append(evidence_ref)
    commands = ProjectCommandService(kernel)
    _task_ref, task, _state = commands.request_agent_action(
        f"{command_prefix}:request",
        kernel.load().revision,
        action_type=action,
        target_refs=targets,
        instructions=f"test {gate_type} hard gate",
    )
    payload = valid_gate_record(
        blueprint_ref,
        gate_type=gate_type,
        result=result,
        context_pack_ref=task["context_pack_ref"],
        evidence_gate_ref=evidence_ref,
    )
    result_ref, _state = commands.commit_noncontent_agent_result(
        command_id=f"{command_prefix}:commit",
        expected_revision=kernel.load().revision,
        task_id=task["task_id"],
        request_kind="content-hard-gate-record",
        raw_request_payload=payload,
    )
    return result_ref


class ContentHardGateContractTests(unittest.TestCase):
    def test_each_gate_requires_its_complete_criterion_set(self) -> None:
        source = "artifact://reading-deck-blueprint/" + "a" * 64
        for gate_type in ("evidence", "presales-reading"):
            payload = valid_gate_record(source, gate_type=gate_type)
            missing = payload["semantic_check_results"].pop()["criterion_id"]
            with self.subTest(gate_type=gate_type, missing=missing), self.assertRaisesRegex(
                ContractValidationError, "criterion"
            ):
                hard_gate_validator()(payload)

    def test_any_applicable_hard_failure_forces_overall_failed(self) -> None:
        payload = valid_gate_record("artifact://reading-deck-blueprint/" + "a" * 64)
        payload["deterministic_check_results"][0].update(
            {
                "result": "failed",
                "failure_reason": "存在因果跳跃",
                "repair_requirement": "降级为诊断假设",
            }
        )
        payload["repair_requirements"] = ["降级为诊断假设"]
        payload["overall_result"] = "passed"
        with self.assertRaisesRegex(ContractValidationError, "overall_result"):
            hard_gate_validator()(payload)

    def test_overall_result_allows_only_passed_or_failed(self) -> None:
        payload = valid_gate_record("artifact://reading-deck-blueprint/" + "a" * 64)
        payload["overall_result"] = "warning"
        with self.assertRaises(ContractValidationError):
            hard_gate_validator()(payload)

    def test_independent_agent_mode_requires_all_execution_evidence(self) -> None:
        source = "artifact://reading-deck-blueprint/" + "a" * 64
        required = (
            "independent_agent_instance_id",
            "context_pack_ref",
            "context_sha256",
            "input_hash",
            "review_output_ref",
        )
        for field in required:
            payload = valid_gate_record(source, reviewer_mode="independent-agent")
            del payload[field]
            with self.subTest(field=field), self.assertRaisesRegex(
                ContractValidationError, field
            ):
                hard_gate_validator()(payload)

    def test_isolated_review_task_does_not_claim_independent_agent(self) -> None:
        payload = valid_gate_record(
            "artifact://reading-deck-blueprint/" + "a" * 64,
            reviewer_mode="isolated-review-task",
        )
        result = hard_gate_validator()(payload)
        self.assertEqual(result["reviewer_mode"], "isolated-review-task")
        self.assertNotIn("independent_agent_instance_id", result)

    def test_record_preserves_authoritative_audit_fields(self) -> None:
        payload = valid_gate_record(
            "artifact://reading-deck-blueprint/" + "a" * 64
        )
        result = hard_gate_validator()(payload)
        for field in (
            "input_source_version",
            "input_hash",
            "context_pack_ref",
            "context_sha256",
            "deterministic_check_results",
            "semantic_check_results",
            "reviewer_cannot_edit",
            "created_at",
        ):
            with self.subTest(field=field):
                self.assertIn(field, result)
        self.assertIs(result["reviewer_cannot_edit"], True)

    def test_malformed_artifact_reference_fields_are_contract_errors(self) -> None:
        source = "artifact://reading-deck-blueprint/" + "a" * 64
        cases = (
            ("input_source_version", "not-an-artifact-reference", False),
            ("context_pack_ref", "not-an-artifact-reference", False),
            ("review_output_ref", "not-an-artifact-reference", True),
        )
        for field, value, independent in cases:
            payload = valid_gate_record(
                source,
                reviewer_mode=(
                    "independent-agent" if independent else "isolated-review-task"
                ),
            )
            payload[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ContractValidationError, field
            ):
                hard_gate_validator()(payload)

    def test_created_at_requires_timezone_aware_timestamp(self) -> None:
        source = "artifact://reading-deck-blueprint/" + "a" * 64
        for value in ("2026-08-23", "2026-08-23T10:00:00"):
            payload = valid_gate_record(source)
            payload["created_at"] = value
            with self.subTest(value=value), self.assertRaisesRegex(
                ContractValidationError, "created_at"
            ):
                hard_gate_validator()(payload)


class ContentHardGateServiceTests(unittest.TestCase):
    def test_v22_blueprint_blocks_legacy_acceptance_from_opening_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="no-legacy-bypass")
            build_blueprint(kernel)
            acceptance_ref = str(
                kernel.artifacts.put(
                    "content-acceptance", {"overall_result": "passed"}
                )
            )
            blueprint_ref = str(
                kernel.artifacts.put(
                    "content-blueprint", {"acceptance_ref": acceptance_ref}
                )
            )
            with self.assertRaises(GateBlockedError) as raised:
                GateEvaluator(kernel).content_user_reviewable(
                    acceptance_ref, blueprint_ref
                )
            self.assertIn(
                "content-acceptance-not-current", raised.exception.missing_evidence
            )

    def test_project_command_round_trip_persists_real_gate_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-command")
            blueprint_ref = build_blueprint(kernel)
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-evidence-gate",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="独立检查事实与证据硬门",
            )
            result_ref, state = commands.commit_noncontent_agent_result(
                command_id="commit-evidence-gate",
                expected_revision=kernel.load().revision,
                task_id=task["task_id"],
                request_kind="content-hard-gate-record",
                raw_request_payload=valid_gate_record(
                    blueprint_ref,
                    gate_type="evidence",
                    context_pack_ref=task["context_pack_ref"],
                ),
            )
            self.assertEqual(state.artifact_heads["content/gate/evidence"], result_ref)
            completed = commands.resolve_agent_task(task["task_id"])
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["role_id"], "content-evidence-gate-reviewer")

    def test_project_command_round_trip_persists_presales_reading_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="reading-command")
            blueprint_ref = build_blueprint(kernel)
            evidence_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="reading-roundtrip-evidence",
            )
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-reading-gate",
                kernel.load().revision,
                action_type="run-content-presales-reading-gate",
                target_refs=[blueprint_ref, evidence_ref],
                instructions="独立检查售前阅读与客户立场硬门",
            )
            result_ref, state = commands.commit_noncontent_agent_result(
                command_id="commit-reading-gate",
                expected_revision=kernel.load().revision,
                task_id=task["task_id"],
                request_kind="content-hard-gate-record",
                raw_request_payload=valid_gate_record(
                    blueprint_ref,
                    gate_type="presales-reading",
                    context_pack_ref=task["context_pack_ref"],
                    evidence_gate_ref=evidence_ref,
                ),
            )
            self.assertEqual(
                state.artifact_heads["content/gate/presales-reading"], result_ref
            )
            completed = commands.resolve_agent_task(task["task_id"])
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(
                completed["role_id"],
                "content-presales-reading-gate-reviewer",
            )

    def test_presales_reading_gate_requires_current_evidence_gate_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="reading-order")
            blueprint_ref = build_blueprint(kernel)
            before = kernel.load()
            with self.assertRaisesRegex(ContractValidationError, "evidence"):
                ProjectCommandService(kernel).request_agent_action(
                    "reading-before-evidence",
                    before.revision,
                    action_type="run-content-presales-reading-gate",
                    target_refs=[blueprint_ref],
                    instructions="不应提前运行",
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_reading_gate_submit_rechecks_evidence_after_task_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="reading-toctou")
            blueprint_ref = build_blueprint(kernel)
            evidence_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="toctou-evidence-pass",
            )
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-reading-before-evidence-change",
                kernel.load().revision,
                action_type="run-content-presales-reading-gate",
                target_refs=[blueprint_ref, evidence_ref],
                instructions="提交时必须再次检查事实硬门",
            )
            failed_record = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(evidence_ref))[
                    "payload"
                ]
            )
            failed_record["deterministic_check_results"][0].update(
                {
                    "result": "failed",
                    "failure_reason": "并发事实变化",
                    "repair_requirement": "重跑事实硬门",
                }
            )
            failed_record["overall_result"] = "failed"
            failed_record["repair_requirements"] = ["重跑事实硬门"]
            kernel.commit(
                command_id="simulate-evidence-became-failed",
                expected_revision=kernel.load().revision,
                event_type="test.concurrent-evidence-change",
                artifact_updates={
                    "content/gate/evidence": (
                        "content-hard-gate-record",
                        failed_record,
                    )
                },
            )
            before = kernel.load()
            with self.assertRaises(GateBlockedError):
                commands.commit_noncontent_agent_result(
                    command_id="reject-reading-after-evidence-change",
                    expected_revision=before.revision,
                    task_id=task["task_id"],
                    request_kind="content-hard-gate-record",
                    raw_request_payload=valid_gate_record(
                        blueprint_ref,
                        gate_type="presales-reading",
                        context_pack_ref=task["context_pack_ref"],
                        evidence_gate_ref=evidence_ref,
                    ),
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_independent_agent_claims_must_match_real_task_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-provenance")
            blueprint_ref = build_blueprint(kernel)
            output_ref = str(
                kernel.artifacts.put(
                    "review-output", {"result": "independent gate output"}
                )
            )
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-independent-gate",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="独立检查",
            )
            payload = valid_gate_record(
                blueprint_ref,
                gate_type="evidence",
                reviewer_mode="independent-agent",
                context_pack_ref=task["context_pack_ref"],
                independent_agent_instance_id=task["task_id"],
                review_output_ref=output_ref,
            )
            false_context_ref = str(
                kernel.artifacts.put(
                    "context-pack",
                    {"project_id": kernel.project_id, "purpose": "wrong-task"},
                )
            )
            payload["context_pack_ref"] = false_context_ref
            payload["context_sha256"] = ArtifactReference.parse(
                false_context_ref
            ).sha256
            before = kernel.load()
            with self.assertRaises(ContractValidationError):
                commands.commit_noncontent_agent_result(
                    command_id="reject-false-provenance",
                    expected_revision=before.revision,
                    task_id=task["task_id"],
                    request_kind="content-hard-gate-record",
                    raw_request_payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_official_route_rejects_independent_mode_without_execution_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="no-fake-independent")
            blueprint_ref = build_blueprint(kernel)
            output_ref = str(
                kernel.artifacts.put(
                    "review-output",
                    {
                        "task_id": "self-reported",
                        "result": "passed",
                    },
                )
            )
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-no-fake-independent",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="没有真实执行回执时必须降级为隔离审查任务",
            )
            payload = valid_gate_record(
                blueprint_ref,
                gate_type="evidence",
                reviewer_mode="independent-agent",
                context_pack_ref=task["context_pack_ref"],
                independent_agent_instance_id=task["task_id"],
                review_output_ref=output_ref,
            )
            before = kernel.load()
            with self.assertRaisesRegex(
                ContractValidationError, "isolated-review-task"
            ):
                commands.commit_noncontent_agent_result(
                    command_id="reject-no-execution-receipt",
                    expected_revision=before.revision,
                    task_id=task["task_id"],
                    request_kind="content-hard-gate-record",
                    raw_request_payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_hard_gate_task_cannot_use_generic_completion_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-generic-complete")
            blueprint_ref = build_blueprint(kernel)
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-generic-completion-bypass",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="必须经受控结果事务完成",
            )
            arbitrary_ref = str(
                kernel.artifacts.put("review-output", {"result": "self-reported"})
            )
            before = kernel.load()
            with self.assertRaisesRegex(
                ContractValidationError, "controlled result"
            ):
                commands.complete_agent_task(
                    "reject-generic-completion-bypass",
                    before.revision,
                    task_id=task["task_id"],
                    result_ref=arbitrary_ref,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_gate_reviewer_cannot_submit_reading_blueprint_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-no-edit")
            blueprint_ref = build_blueprint(kernel)
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-gate-no-edit",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="只审查，不编辑",
            )
            before = kernel.load()
            payload = valid_blueprint("mixed-evidence")
            payload["artifact_type"] = "reading-deck-blueprint"
            with self.assertRaises(ContractValidationError):
                commands.commit_noncontent_agent_result(
                    command_id="reviewer-write-blueprint",
                    expected_revision=before.revision,
                    task_id=task["task_id"],
                    request_kind="content-blueprint",
                    raw_request_payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_each_reviewer_can_write_only_its_gate_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-project")
            blueprint_ref = build_blueprint(kernel)
            evidence_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="each-reviewer-evidence",
            )
            reading_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="presales-reading",
                command_prefix="each-reviewer-reading",
            )
            state = kernel.load()
            self.assertEqual(state.artifact_heads["content/gate/evidence"], evidence_ref)
            self.assertEqual(
                state.artifact_heads["content/gate/presales-reading"], reading_ref
            )

    def test_gate_record_rejects_unresolvable_evidence_refs_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-evidence")
            blueprint_ref = build_blueprint(kernel)
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-invalid-evidence",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="拒绝不可解析证据",
            )
            payload = valid_gate_record(
                blueprint_ref,
                gate_type="evidence",
                context_pack_ref=task["context_pack_ref"],
            )
            payload["deterministic_check_results"][0]["evidence_refs"] = [
                "artifact://missing-evidence/" + "f" * 64
            ]
            before = kernel.load()
            with self.assertRaises(ArtifactReferenceError):
                hard_gate_service_type()(kernel).submit_record(
                    command_id="unresolvable-evidence",
                    expected_revision=before.revision,
                    actor_role_id="content-evidence-gate-reviewer",
                    agent_task_id=task["task_id"],
                    payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_wrong_reviewer_role_is_stable_zero_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="gate-authority")
            blueprint_ref = build_blueprint(kernel)
            commands = ProjectCommandService(kernel)
            _task_ref, task, _state = commands.request_agent_action(
                "request-authority-check",
                kernel.load().revision,
                action_type="run-content-evidence-gate",
                target_refs=[blueprint_ref],
                instructions="验证 reviewer authority",
            )
            payload = valid_gate_record(
                blueprint_ref,
                gate_type="evidence",
                context_pack_ref=task["context_pack_ref"],
            )
            before = kernel.load()
            with self.assertRaisesRegex(WorkbenchValidationError, "reviewer"):
                hard_gate_service_type()(kernel).submit_record(
                    command_id="wrong-reviewer",
                    expected_revision=before.revision,
                    actor_role_id="content-presales-reading-gate-reviewer",
                    agent_task_id=task["task_id"],
                    payload=payload,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_acceptance_requires_both_current_gate_records_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="accept-project")
            blueprint_ref = build_blueprint(kernel)
            service = hard_gate_service_type()(kernel)
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="accept-evidence",
            )
            with self.assertRaises(GateBlockedError):
                service.accept_current_content(
                    command_id="accept-too-early",
                    expected_revision=kernel.load().revision,
                )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="presales-reading",
                command_prefix="accept-reading",
            )
            acceptance_ref = service.accept_current_content(
                command_id="accept",
                expected_revision=kernel.load().revision,
            )
            acceptance = kernel.artifacts.resolve(
                ArtifactReference.parse(acceptance_ref)
            )["payload"]
            self.assertEqual(acceptance["source_version"], blueprint_ref)
            self.assertEqual(acceptance["overall_result"], "passed")

    def test_acceptance_rejects_gate_heads_without_completed_reviewer_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="no-direct-bypass")
            blueprint_ref = build_blueprint(kernel)
            service = hard_gate_service_type()(kernel)
            before = kernel.load()
            with self.assertRaisesRegex(
                WorkbenchValidationError, "AgentTask"
            ):
                service.submit_record(
                    command_id="reject-direct-bypass",
                    expected_revision=before.revision,
                    actor_role_id="content-evidence-gate-reviewer",
                    payload=valid_gate_record_for_kernel(
                        kernel, blueprint_ref, gate_type="evidence"
                    ),
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_acceptance_requires_reading_gate_exact_evidence_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="accept-lineage")
            blueprint_ref = build_blueprint(kernel)
            first_evidence_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="lineage-evidence-first",
            )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="presales-reading",
                command_prefix="lineage-reading",
            )
            second_evidence_ref = submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="lineage-evidence-second",
            )
            self.assertNotEqual(first_evidence_ref, second_evidence_ref)
            with self.assertRaises(GateBlockedError) as raised:
                hard_gate_service_type()(kernel).accept_current_content(
                    command_id="reject-mixed-lineage",
                    expected_revision=kernel.load().revision,
                )
            self.assertIn(
                "evidence-predecessor-mismatch",
                raised.exception.missing_evidence,
            )

    def test_acceptance_command_replay_returns_original_result_after_head_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="accept-replay")
            blueprint_ref = build_blueprint(kernel)
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="replay-evidence",
            )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="presales-reading",
                command_prefix="replay-reading",
            )
            service = hard_gate_service_type()(kernel)
            accept_revision = kernel.load().revision
            original_ref = service.accept_current_content(
                command_id="accept-replay-command",
                expected_revision=accept_revision,
            )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="replay-new-evidence",
            )
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)
            replayed_ref = service.accept_current_content(
                command_id="accept-replay-command",
                expected_revision=accept_revision,
            )
            self.assertEqual(replayed_ref, original_ref)

    def test_acceptance_replay_rejects_unrelated_processed_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="accept-collision")
            blueprint_ref = build_blueprint(kernel)
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="collision-evidence",
            )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="presales-reading",
                command_prefix="collision-reading",
            )
            service = hard_gate_service_type()(kernel)
            service.accept_current_content(
                command_id="real-acceptance-command",
                expected_revision=kernel.load().revision,
            )
            unrelated_revision = kernel.load().revision
            kernel.commit(
                command_id="unrelated-command",
                expected_revision=unrelated_revision,
                event_type="unrelated.event",
                artifact_updates={},
            )
            submit_gate_via_command(
                kernel,
                blueprint_ref,
                gate_type="evidence",
                command_prefix="collision-new-evidence",
            )
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)
            with self.assertRaisesRegex(
                ContractValidationError, "different semantics"
            ):
                service.accept_current_content(
                    command_id="unrelated-command",
                    expected_revision=unrelated_revision,
                )


if __name__ == "__main__":
    unittest.main()
