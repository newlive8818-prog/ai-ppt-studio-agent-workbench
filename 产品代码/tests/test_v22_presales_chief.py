from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.errors import MaterialModeUnconfirmedError, MissionNotConfirmedError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_contracts import blueprint, decision_context, evidence_book, fit_map


class PresalesChiefServiceTests(unittest.TestCase):
    def test_formal_content_requires_the_current_confirmed_mission_and_material_identity(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="readiness")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft(
                "draft",
                0,
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户决策团队",
                    "desired_judgment_or_action": "确认联合验证范围",
                },
            )
            policy = MissionReadinessPolicy(kernel)
            with self.assertRaises(MissionNotConfirmedError):
                policy.require_ready()
            with self.assertRaises(MaterialModeUnconfirmedError):
                service.confirm_mission(
                    "missing-materials",
                    kernel.load().revision,
                    mission_draft_ref=draft_ref,
                    material_mode="materials-provided",
                    material_inventory_ref="",
                    user_action_ref="test-user-action://confirm",
                    user_message_ref="",
                )
            materials_ref = service.register_materials(
                "materials",
                kernel.load().revision,
                {"sources": [{
                    "source_id": "s1",
                    "origin": "user-provided",
                    "kind": "text",
                    "locator": "inline://s1",
                    "sha256": "a" * 64,
                }]},
            )
            service.confirm_mission(
                "confirm",
                kernel.load().revision,
                mission_draft_ref=draft_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://confirm",
                user_message_ref="",
            )
            self.assertEqual(policy.v22_material_mode(has_evidence_gaps=False), "material-backed")

            service.save_mission_draft(
                "new-draft",
                kernel.load().revision,
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户经营与数字化决策团队",
                    "desired_judgment_or_action": "确认联合验证范围",
                },
            )
            with self.assertRaises(MissionNotConfirmedError):
                policy.require_ready()

    def test_new_material_identity_invalidates_the_old_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            kernel = ProjectKernel.initialize(Path(folder), project_id="materials")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft(
                "draft",
                0,
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户决策团队",
                    "desired_judgment_or_action": "确认联合验证范围",
                },
            )
            first_ref = service.register_materials(
                "materials-v1",
                kernel.load().revision,
                {"sources": [{
                    "source_id": "s1",
                    "origin": "user-provided",
                    "kind": "text",
                    "locator": "inline://s1",
                    "sha256": "a" * 64,
                }]},
            )
            confirmation_ref = service.confirm_mission(
                "confirm",
                kernel.load().revision,
                mission_draft_ref=draft_ref,
                material_mode="materials-provided",
                material_inventory_ref=first_ref,
                user_action_ref="test-user-action://confirm",
                user_message_ref="",
            )
            service.register_materials(
                "materials-v2",
                kernel.load().revision,
                {"sources": [{
                    "source_id": "s2",
                    "origin": "user-provided",
                    "kind": "text",
                    "locator": "inline://s2",
                    "sha256": "b" * 64,
                }]},
            )
            self.assertNotIn("mission/confirmation", kernel.load().artifact_heads)
            self.assertEqual(
                kernel.artifacts.resolve(ArtifactReference.parse(confirmation_ref))["kind"],
                "mission-confirmation",
            )
            with self.assertRaises(MissionNotConfirmedError):
                MissionReadinessPolicy(kernel).require_ready()

    def test_trusted_mission_boundary_maps_to_three_v22_modes(self) -> None:
        for has_materials, gaps, expected in (
            (False, False, "proposal-led"),
            (True, False, "material-backed"),
            (True, True, "mixed-evidence"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id=f"mode-{expected}")
                service = MissionMaterialService(kernel)
                draft = service.save_mission_draft(
                    "draft",
                    0,
                    {
                        "topic": "经营一体化方案",
                        "primary_audience": "客户决策团队",
                        "desired_judgment_or_action": "确认联合验证范围",
                    },
                )
                materials = ""
                if has_materials:
                    materials = service.register_materials(
                        "materials",
                        kernel.load().revision,
                        {"sources": [{
                            "source_id": "s1",
                            "origin": "user-provided",
                            "kind": "text",
                            "locator": "inline://s1",
                            "sha256": "a" * 64,
                        }]},
                    )
                service.confirm_mission(
                    "confirm",
                    kernel.load().revision,
                    mission_draft_ref=draft,
                    material_mode="materials-provided" if has_materials else "no-materials-confirmed",
                    material_inventory_ref=materials,
                    user_action_ref="test-user-action://confirm",
                    user_message_ref="",
                )
                self.assertEqual(
                    MissionReadinessPolicy(kernel).v22_material_mode(
                        has_evidence_gaps=gaps
                    ),
                    expected,
                )

    def test_three_material_modes_write_the_four_objects_without_legacy_gates(self) -> None:
        for mode in ("material-backed", "mixed-evidence", "proposal-led"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                kernel = ProjectKernel.initialize(Path(folder), project_id=f"project-{mode}")
                updates = {
                    "mission/confirmation": ("mission-confirmation", {"material_mode": mode})
                }
                if mode != "proposal-led":
                    updates["materials"] = ("material-inventory", {"sources": [{"source_id": "s1"}]})
                state = kernel.commit(
                    command_id="seed",
                    expected_revision=0,
                    event_type="test.seeded",
                    artifact_updates=updates,
                )
                mission_ref = state.artifact_heads["mission/confirmation"]
                material_ref = state.artifact_heads.get("materials", "")
                service = PresalesContentService(kernel)

                evidence = evidence_book(mode)
                evidence["mission_confirmation_ref"] = mission_ref
                evidence["material_inventory_ref"] = material_ref
                evidence_ref = service.build_evidence_book("evidence", state.revision, evidence)

                context = decision_context()
                context["evidence_book_ref"] = evidence_ref
                context_ref = service.build_decision_context("context", kernel.load().revision, context)

                mapping = fit_map()
                mapping["evidence_book_ref"] = evidence_ref
                mapping["decision_context_ref"] = context_ref
                mapping_ref = service.build_problem_solution_fit("fit", kernel.load().revision, mapping)

                deck = blueprint(mode)
                deck["project_id"] = kernel.project_id
                deck["evidence_book_ref"] = evidence_ref
                deck["decision_context_ref"] = context_ref
                deck["problem_solution_fit_ref"] = mapping_ref
                deck_ref = service.build_reading_deck_blueprint("deck", kernel.load().revision, deck)

                final = kernel.load()
                self.assertEqual(final.artifact_heads["content/reading-blueprint"], deck_ref)
                self.assertNotIn("content/framework-confirmation", final.artifact_heads)
                self.assertNotIn("content/full-deck-expansion-authorization", final.artifact_heads)
                self.assertEqual(
                    kernel.artifacts.resolve(ArtifactReference.parse(deck_ref))["payload"]["material_mode"],
                    mode,
                )


if __name__ == "__main__":
    unittest.main()
