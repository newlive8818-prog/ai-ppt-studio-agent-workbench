from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.domains.content.contracts import validate_content_hard_gate_record
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError, WorkbenchValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel

NOW = "2026-08-15T00:00:00+08:00"


def check(result: str = "passed") -> dict:
    return {
        "check_id": "source-traceability",
        "applicability": "applicable",
        "result": result,
        "hard": True,
        "evidence_refs": ["artifact://reading-deck-blueprint/" + "a" * 64],
        "failure_reason": "来源身份错误" if result == "failed" else "",
    }


def record(result: str = "passed", reviewer_mode: str = "isolated-review-task") -> dict:
    return {
        "gate_type": "evidence",
        "input_source_version": "content-v1",
        "input_hash": "a" * 64,
        "reviewer_mode": reviewer_mode,
        "independent_agent_instance_id": "agent-1" if reviewer_mode == "independent-agent" else "",
        "context_pack_ref": "artifact://context-pack/" + "b" * 64,
        "context_pack_hash": "b" * 64,
        "output_ref": "artifact://agent-output/" + "c" * 64 if reviewer_mode == "independent-agent" else "",
        "deterministic_check_results": [check(result)],
        "semantic_check_results": [],
        "overall_result": result,
        "repair_requirements": [{"check_id": "source-traceability", "instruction": "修复来源身份"}] if result == "failed" else [],
        "reviewer_cannot_edit": True,
        "created_at": NOW,
    }


class ContentHardGateContractTests(unittest.TestCase):
    def test_any_applicable_hard_failure_forces_overall_failed(self) -> None:
        payload = record("failed")
        payload["deterministic_check_results"].extend(check("passed") for _ in range(20))
        self.assertEqual(validate_content_hard_gate_record(payload)["overall_result"], "failed")
        invalid = copy.deepcopy(payload)
        invalid["overall_result"] = "passed"
        with self.assertRaises(ContractValidationError):
            validate_content_hard_gate_record(invalid)

    def test_independent_agent_identity_requires_real_execution_evidence(self) -> None:
        self.assertEqual(validate_content_hard_gate_record(record(reviewer_mode="independent-agent"))["reviewer_mode"], "independent-agent")
        for missing in ("independent_agent_instance_id", "context_pack_hash", "input_hash", "output_ref"):
            invalid = record(reviewer_mode="independent-agent")
            invalid[missing] = ""
            with self.subTest(missing=missing), self.assertRaises(ContractValidationError):
                validate_content_hard_gate_record(invalid)

    def test_reviewer_cannot_write_the_blueprint(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            service = ContentHardGateService(kernel)
            before = kernel.load().revision
            with self.assertRaises(WorkbenchValidationError):
                service.commit_reviewer_output(
                    command_id="forbidden",
                    expected_revision=before,
                    reviewer_role_id="content-evidence-gate-reviewer",
                    artifact_kind="reading-deck-blueprint",
                    payload={},
                )
            self.assertEqual(kernel.load().revision, before)

    def test_legacy_acceptance_cannot_bypass_v22_hard_gates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            state = kernel.commit(
                command_id="current-v22",
                expected_revision=0,
                event_type="test.current-v22",
                artifact_updates={
                    "content/reading-blueprint": (
                        "reading-deck-blueprint",
                        {"source_version": "content-v1"},
                    )
                },
            )
            acceptance_ref = str(kernel.artifacts.put("content-acceptance", {"overall_result": "passed"}))
            blueprint_ref = str(kernel.artifacts.put("content-blueprint", {"acceptance_ref": acceptance_ref}))
            review_batch_ref = str(
                kernel.artifacts.put("content-review-batch", {"status": "submitted"})
            )
            with self.assertRaises(GateBlockedError):
                GateEvaluator(kernel).content_user_reviewable(
                    acceptance_ref, blueprint_ref, review_batch_ref
                )


if __name__ == "__main__":
    unittest.main()
