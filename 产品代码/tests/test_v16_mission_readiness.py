from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import (
    ContractValidationError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


MISSION = {
    "topic": "经营一体化方案",
    "primary_audience": "客户决策者",
    "desired_judgment_or_action": "批准一期立项",
}

MATERIALS = {
    "sources": [
        {
            "source_id": "s1",
            "origin": "user-provided",
            "kind": "text",
            "locator": "inline://user-provided/s1",
            "sha256": "a" * 64,
        }
    ]
}


class MissionReadinessTests(unittest.TestCase):
    def test_formal_content_is_blocked_until_current_draft_is_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            materials_ref = service.register_materials("materials", 1, MATERIALS)

            with self.assertRaises(MissionNotConfirmedError):
                MissionReadinessPolicy(kernel).require_ready()

            confirmation_ref = service.confirm_mission(
                "confirm",
                2,
                mission_draft_ref=draft_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://confirm-current-task",
                user_message_ref="",
            )
            confirmation = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["mission_draft_ref"], draft_ref)
            self.assertEqual(confirmation["material_inventory_ref"], materials_ref)
            self.assertEqual(confirmation["material_mode"], "materials-provided")
            self.assertEqual(confirmation["revision"], 2)
            self.assertTrue(confirmation["confirmed_at"].endswith("+00:00"))

            readiness = MissionReadinessPolicy(kernel).require_ready()
            self.assertEqual(
                (readiness.mission_draft_ref, readiness.material_inventory_ref),
                (draft_ref, materials_ref),
            )

    def test_content_agent_action_cannot_bypass_python_readiness_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            materials_ref = service.register_materials("materials", 1, MATERIALS)
            commands = ProjectCommandService(kernel)
            before = kernel.load()

            with self.assertRaises(ContractValidationError):
                commands.request_agent_action(
                    "content-task",
                    2,
                    action_type="build-presales-strategy",
                    target_refs=[draft_ref, materials_ref],
                    instructions="构建售前策略。",
                )
            self.assertEqual(kernel.load(), before)

    def test_confirming_materials_mode_requires_the_current_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft("draft", 0, MISSION)

            with self.assertRaises(MaterialModeUnconfirmedError):
                service.confirm_mission(
                    "confirm-without-materials",
                    1,
                    mission_draft_ref=draft_ref,
                    material_mode="materials-provided",
                    material_inventory_ref="",
                    user_action_ref="test-user-action://confirm-current-task",
                    user_message_ref="",
                )

    def test_new_draft_or_material_identity_makes_old_confirmation_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            materials_ref = service.register_materials("materials", 1, MATERIALS)
            service.confirm_mission(
                "confirm",
                2,
                mission_draft_ref=draft_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://confirm-current-task",
                user_message_ref="",
            )
            changed_ref = service.save_mission_draft(
                "changed-draft",
                3,
                {**MISSION, "primary_audience": "客户经营与数字化决策团队"},
            )

            self.assertNotEqual(changed_ref, draft_ref)
            with self.assertRaises(MissionNotConfirmedError):
                MissionReadinessPolicy(kernel).require_ready()

    def test_explicit_no_materials_confirmation_enters_proposal_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            service = MissionMaterialService(kernel)
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            confirmation_ref = service.confirm_mission(
                "confirm-no-materials",
                1,
                mission_draft_ref=draft_ref,
                material_mode="no-materials-confirmed",
                material_inventory_ref="",
                user_action_ref="test-user-action://confirm-no-materials",
                user_message_ref="",
            )
            confirmation = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(
                confirmation["empty_material_identity"],
                MissionReadinessPolicy(kernel).empty_material_identity(draft_ref),
            )
            self.assertEqual(
                MissionReadinessPolicy(kernel).v22_material_mode(
                    has_evidence_gaps=False
                ),
                "proposal-led",
            )


if __name__ == "__main__":
    unittest.main()
