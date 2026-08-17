from __future__ import annotations

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import blueprint, decision_context, evidence_book, fit_map


def build_content(
    kernel: ProjectKernel, source_version: str = "content-v1", slide_count: int = 1
) -> str:
    state = kernel.load()
    if not state.artifact_heads.get("mission/confirmation"):
        state = kernel.commit(
            command_id="seed",
            expected_revision=state.revision,
            event_type="test.seeded",
            artifact_updates={
                "mission/confirmation": ("mission-confirmation", {"material_mode": "materials-provided"}),
                "materials": ("material-inventory", {"sources": [{"source_id": "s1"}]}),
            },
        )
    service = PresalesContentService(kernel)
    evidence = evidence_book()
    evidence["source_version"] = source_version
    evidence["mission_confirmation_ref"] = state.artifact_heads["mission/confirmation"]
    evidence["material_inventory_ref"] = state.artifact_heads["materials"]
    evidence_ref = service.build_evidence_book(f"evidence-{source_version}", state.revision, evidence)
    context = decision_context()
    context["evidence_book_ref"] = evidence_ref
    context_ref = service.build_decision_context(f"context-{source_version}", kernel.load().revision, context)
    mapping = fit_map()
    mapping["evidence_book_ref"] = evidence_ref
    mapping["decision_context_ref"] = context_ref
    mapping_ref = service.build_problem_solution_fit(f"fit-{source_version}", kernel.load().revision, mapping)
    deck = blueprint()
    deck["project_id"] = kernel.project_id
    deck["source_version"] = source_version
    deck["evidence_book_ref"] = evidence_ref
    deck["decision_context_ref"] = context_ref
    deck["problem_solution_fit_ref"] = mapping_ref
    template = deck["slides"][0]
    deck["slides"] = []
    for order in range(1, slide_count + 1):
        slide = deepcopy(template)
        slide.update(
            slide_id=f"S{order:02d}",
            order=order,
            material_views=[
                {
                    **material,
                    "material_view_id": f"S{order:02d}-M{index:02d}",
                    "asset_ref": f"review-assets/content/S{order:02d}-M{index:02d}.png",
                    "page_number": material["page_number"] + order - 1,
                    "purpose": (
                        material["purpose"]
                        if slide_count == 1
                        else f"{material['purpose']}（S{order:02d}）"
                    ),
                }
                for index, material in enumerate(template["material_views"], start=1)
            ],
            neutral_title=(
                template["neutral_title"]
                if slide_count == 1
                else f"当前流程断点与证据边界 {order}"
            ),
        )
        if slide_count > 1:
            slide.update(
                previous_relation="开篇" if order == 1 else f"承接 S{order - 1:02d}",
                next_relation="收束" if order == slide_count else f"进入 S{order + 1:02d}",
            )
        deck["slides"].append(slide)
    return service.build_reading_deck_blueprint(f"deck-{source_version}", kernel.load().revision, deck)


class ContentRepairLoopTests(unittest.TestCase):
    def test_fixture_slides_are_deeply_independent_and_single_slide_keeps_relations(self) -> None:
        original = PresalesContentService.build_reading_deck_blueprint

        with tempfile.TemporaryDirectory() as folder:
            captured: dict[str, dict] = {}

            def capture(service, command_id, expected_revision, payload):
                captured["payload"] = payload
                return original(service, command_id, expected_revision, payload)

            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            with patch.object(PresalesContentService, "build_reading_deck_blueprint", new=capture):
                build_content(kernel, slide_count=3)
            slides = captured["payload"]["slides"]
            for field in (
                "visible_copy_blocks",
                "identity_labels",
                "evidence_bindings",
                "material_views",
                "analysis_or_proposal_blocks",
                "solution_mapping_refs",
                "reading_quality",
            ):
                self.assertIsNot(slides[0][field], slides[1][field], field)
            self.assertIsNot(slides[0]["visible_copy_blocks"][0], slides[1]["visible_copy_blocks"][0])

        with tempfile.TemporaryDirectory() as folder:
            captured = {}
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            with patch.object(PresalesContentService, "build_reading_deck_blueprint", new=capture):
                build_content(kernel, slide_count=1)
            single = captured["payload"]["slides"][0]
            template = blueprint()["slides"][0]
            self.assertEqual(single["previous_relation"], template["previous_relation"])
            self.assertEqual(single["next_relation"], template["next_relation"])

    def test_failed_gate_requires_chief_repair_and_both_current_gates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="p1")
            first = build_content(kernel)
            gates = ContentHardGateService(kernel)
            failed_ref, failed, _ = gates.run_evidence_gate(
                command_id="evidence-failed",
                expected_revision=kernel.load().revision,
                semantic_check_results=[{
                    "check_id": "semantic-causality",
                    "applicability": "applicable",
                    "result": "failed",
                    "hard": True,
                    "evidence_refs": [first],
                    "failure_reason": "存在无证因果跳跃",
                }],
                reviewer_mode="isolated-review-task",
            )
            self.assertEqual(failed["overall_result"], "failed")
            self.assertNotIn("content/acceptance", kernel.load().artifact_heads)
            with self.assertRaises(GateBlockedError):
                gates.run_presales_reading_gate(
                    command_id="reading-too-early",
                    expected_revision=kernel.load().revision,
                    semantic_check_results=[],
                    reviewer_mode="isolated-review-task",
                )

            second = build_content(kernel, "content-v2")
            self.assertNotEqual(first, second)
            current = kernel.load()
            self.assertNotIn("content/gate/evidence", current.artifact_heads)
            self.assertNotIn("content/acceptance", current.artifact_heads)

            gates.run_evidence_gate(
                command_id="evidence-passed",
                expected_revision=current.revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            _reading_ref, reading, accepted = gates.run_presales_reading_gate(
                command_id="reading-passed",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            self.assertEqual(reading["overall_result"], "passed")
            acceptance_ref = accepted.artifact_heads["content/acceptance"]
            acceptance = kernel.artifacts.resolve(ArtifactReference.parse(acceptance_ref))["payload"]
            self.assertEqual(acceptance["source_version"], "content-v2")
            self.assertEqual(acceptance["reading_blueprint_ref"], second)
            self.assertEqual(acceptance["overall_result"], "passed")


if __name__ == "__main__":
    unittest.main()
