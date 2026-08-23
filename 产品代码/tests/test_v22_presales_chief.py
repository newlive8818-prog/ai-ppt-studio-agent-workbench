from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (  # noqa: E402
    ArtifactReferenceError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.kernel.transactions import ProjectKernel  # noqa: E402
from tests.test_v22_content_contracts import (  # noqa: E402
    MATERIAL_MODES,
    valid_blueprint,
    valid_decision_context,
    valid_evidence_book,
    valid_fit_map,
)


def service_type() -> type[Any]:
    try:
        module = importlib.import_module(
            "ai_ppt_studio.application.presales_content_service"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError("missing v2.2 PresalesContentService") from exc
    candidate = getattr(module, "PresalesContentService", None)
    if not isinstance(candidate, type):
        raise AssertionError("missing v2.2 PresalesContentService")
    return candidate


def proposal_led_blueprint() -> dict[str, Any]:
    payload = valid_blueprint("proposal-led")
    slide = payload["slides"][0]
    slide["visible_copy_blocks"] = [
        {
            "block_id": "copy-diagnosis",
            "role": "body",
            "text": "诊断假设：流程信息可能缺少统一承载。",
        },
        {
            "block_id": "copy-proposal",
            "role": "body",
            "text": "方案建议：先验证单一审批场景。",
        },
        {
            "block_id": "copy-question",
            "role": "body",
            "text": "验证问题：哪些角色参与当前审批？",
        },
        {
            "block_id": "copy-action",
            "role": "body",
            "text": "联合动作：共同确认一期场景清单。",
        },
    ]
    slide["identity_labels"] = ["诊断假设", "方案建议", "待联合验证"]
    slide["evidence_bindings"][0]["supports_block_refs"] = [
        "copy-diagnosis",
        "copy-proposal",
        "copy-question",
        "copy-action",
    ]
    return payload


class PresalesChiefServiceTests(unittest.TestCase):
    def _build_chain(
        self, kernel: ProjectKernel, mode: str
    ) -> tuple[Any, dict[str, str]]:
        service = service_type()(kernel)
        book_ref = service.build_presales_evidence_book(
            command_id=f"{mode}:book",
            expected_revision=kernel.load().revision,
            actor_role_id="presales-solution-chief",
            material_mode=mode,
            payload=valid_evidence_book(mode),
        )
        decision = valid_decision_context()
        decision["evidence_book_ref"] = book_ref
        decision_ref = service.build_customer_decision_context(
            command_id=f"{mode}:decision",
            expected_revision=kernel.load().revision,
            actor_role_id="presales-solution-chief",
            evidence_book_ref=book_ref,
            payload=decision,
        )
        fit_ref = service.build_problem_solution_fit(
            command_id=f"{mode}:fit",
            expected_revision=kernel.load().revision,
            actor_role_id="presales-solution-chief",
            evidence_book_ref=book_ref,
            decision_context_ref=decision_ref,
            payload=valid_fit_map(),
        )
        blueprint = (
            proposal_led_blueprint()
            if mode == "proposal-led"
            else valid_blueprint(mode)
        )
        blueprint.update(
            {
                "project_id": kernel.project_id,
                "evidence_book_ref": book_ref,
                "decision_context_ref": decision_ref,
                "problem_solution_fit_ref": fit_ref,
            }
        )
        blueprint_ref = service.build_reading_blueprint(
            command_id=f"{mode}:blueprint",
            expected_revision=kernel.load().revision,
            actor_role_id="presales-solution-chief",
            material_mode=mode,
            evidence_book_ref=book_ref,
            decision_context_ref=decision_ref,
            problem_solution_fit_ref=fit_ref,
            payload=blueprint,
        )
        return service, {
            "book": book_ref,
            "decision": decision_ref,
            "fit": fit_ref,
            "blueprint": blueprint_ref,
        }

    def test_all_material_modes_write_the_four_object_chain_in_order(self) -> None:
        for mode in MATERIAL_MODES:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                kernel = ProjectKernel.initialize(Path(temp), project_id=f"project-{mode}")
                _service, refs = self._build_chain(kernel, mode)
                state = kernel.load()
                self.assertEqual(state.revision, 4)
                self.assertEqual(
                    state.artifact_heads["content/presales-evidence-book"],
                    refs["book"],
                )
                self.assertEqual(
                    state.artifact_heads["content/customer-decision-context"],
                    refs["decision"],
                )
                self.assertEqual(
                    state.artifact_heads["content/problem-solution-fit-map"],
                    refs["fit"],
                )
                self.assertEqual(
                    state.artifact_heads["content/reading-deck-blueprint"],
                    refs["blueprint"],
                )
                blueprint = kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["blueprint"])
                )["payload"]
                self.assertEqual(blueprint["material_mode"], mode)
                self.assertEqual(blueprint["evidence_book_ref"], refs["book"])
                self.assertEqual(blueprint["decision_context_ref"], refs["decision"])
                self.assertEqual(blueprint["problem_solution_fit_ref"], refs["fit"])

    def test_proposal_led_chain_contains_safe_forward_work_not_customer_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="proposal-project")
            _service, refs = self._build_chain(kernel, "proposal-led")
            payload = kernel.artifacts.resolve(
                ArtifactReference.parse(refs["blueprint"])
            )["payload"]
            semantic = json.dumps(payload, ensure_ascii=False)
            for required in ("诊断假设", "方案建议", "验证问题", "联合动作"):
                self.assertIn(required, semantic)
            for prohibited in ("客户当前已经", "成功案例", "保证实现", "效果承诺"):
                self.assertNotIn(prohibited, semantic)

    def test_each_downstream_write_requires_the_exact_current_upstream_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="lineage-project")
            service = service_type()(kernel)
            book_ref = service.build_presales_evidence_book(
                command_id="book",
                expected_revision=0,
                actor_role_id="presales-solution-chief",
                material_mode="mixed-evidence",
                payload=valid_evidence_book("mixed-evidence"),
            )
            before = kernel.load()
            decision = valid_decision_context()
            decision["evidence_book_ref"] = book_ref
            stale_ref = "artifact://presales-evidence-book/" + "0" * 64
            with self.assertRaises(ArtifactReferenceError):
                service.build_customer_decision_context(
                    command_id="stale-decision",
                    expected_revision=before.revision,
                    actor_role_id="presales-solution-chief",
                    evidence_book_ref=stale_ref,
                    payload=decision,
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)

    def test_gate_reviewer_cannot_write_content_and_failure_is_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="authority-project")
            before = kernel.load()
            with self.assertRaisesRegex(
                WorkbenchValidationError, "presales-solution-chief"
            ):
                service_type()(kernel).build_presales_evidence_book(
                    command_id="reviewer-write",
                    expected_revision=before.revision,
                    actor_role_id="content-evidence-gate-reviewer",
                    material_mode="material-backed",
                    payload=valid_evidence_book("material-backed"),
                )
            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)


if __name__ == "__main__":
    unittest.main()
