"""Migration guards for the retired v1.6 content chain.

The filename is retained so the historical regression slot keeps protecting the
product, but every assertion targets the single v2.2 evidence-first chain.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import blueprint, decision_context, evidence_book, fit_map


class V16ContentChainMigrationTests(unittest.TestCase):
    def test_retired_content_writers_are_physically_absent(self) -> None:
        for module in (
            "ai_ppt_studio.application.content_service",
            "ai_ppt_studio.application.content_review_service",
            "ai_ppt_studio.application.framework_discussion_service",
        ):
            with self.subTest(module=module):
                self.assertIsNone(importlib.util.find_spec(module))

    def test_v22_chain_writes_only_four_authoritative_objects_then_two_hard_gates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="迁移项目")
            state = kernel.commit(
                command_id="seed",
                expected_revision=0,
                event_type="test.seeded",
                artifact_updates={
                    "mission/confirmation": (
                        "mission-confirmation",
                        {"material_mode": "materials-provided"},
                    ),
                    "materials": (
                        "material-inventory",
                        {"sources": [{"source_id": "source-1"}]},
                    ),
                },
            )
            service = PresalesContentService(kernel)

            evidence = evidence_book()
            evidence["mission_confirmation_ref"] = state.artifact_heads["mission/confirmation"]
            evidence["material_inventory_ref"] = state.artifact_heads["materials"]
            evidence_ref = service.build_evidence_book("evidence", state.revision, evidence)

            context = decision_context()
            context["evidence_book_ref"] = evidence_ref
            context_ref = service.build_decision_context(
                "context", kernel.load().revision, context
            )

            mapping = fit_map()
            mapping["evidence_book_ref"] = evidence_ref
            mapping["decision_context_ref"] = context_ref
            mapping_ref = service.build_problem_solution_fit(
                "mapping", kernel.load().revision, mapping
            )

            deck = blueprint()
            deck.update(
                project_id=kernel.project_id,
                evidence_book_ref=evidence_ref,
                decision_context_ref=context_ref,
                problem_solution_fit_ref=mapping_ref,
            )
            deck_ref = service.build_reading_deck_blueprint(
                "blueprint", kernel.load().revision, deck
            )
            gates = ContentHardGateService(kernel)
            gates.run_evidence_gate(
                command_id="evidence-gate",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )
            gates.run_presales_reading_gate(
                command_id="reading-gate",
                expected_revision=kernel.load().revision,
                semantic_check_results=[],
                reviewer_mode="isolated-review-task",
            )

            final = kernel.load()
            self.assertEqual(
                set(final.artifact_heads).intersection(
                    {
                        "content/evidence-book",
                        "content/decision-context",
                        "content/problem-solution-fit",
                        "content/reading-blueprint",
                    }
                ),
                {
                    "content/evidence-book",
                    "content/decision-context",
                    "content/problem-solution-fit",
                    "content/reading-blueprint",
                },
            )
            self.assertNotIn("content/framework-confirmation", final.artifact_heads)
            self.assertNotIn(
                "content/full-deck-expansion-authorization", final.artifact_heads
            )
            acceptance = kernel.artifacts.resolve(
                ArtifactReference.parse(final.artifact_heads["content/acceptance"])
            )["payload"]
            self.assertEqual(acceptance["reading_blueprint_ref"], deck_ref)
            self.assertEqual(acceptance["overall_result"], "passed")


if __name__ == "__main__":
    unittest.main()
