from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.errors import (
    ContentWorkflowError,
    MaterialModeUnconfirmedError,
    MissionNotConfirmedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_content_acceptance import (
    TEST_SECRET,
    authorize_current_framework,
)
from tests.v16_content_fixtures import publish_content_stage


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
            service = ContentService.initialize(Path(temp), project_id="p1")
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            materials_ref = service.register_materials("materials", 1, MATERIALS)

            with self.assertRaises(ContentWorkflowError) as caught:
                service.register_content_stage(
                    "blocked-strategy",
                    2,
                    "strategy",
                    {
                        "mission_ref": draft_ref,
                        "material_inventory_ref": materials_ref,
                        "content_identity_mode": "material-backed",
                        "decision_stage": "立项",
                        "core_tension": "系统割裂",
                    },
                )
            self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")

            confirmation_ref = service.confirm_mission(
                "confirm",
                2,
                mission_draft_ref=draft_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://confirm-current-task",
                user_message_ref="",
            )
            confirmation = service.kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["mission_draft_ref"], draft_ref)
            self.assertEqual(confirmation["material_inventory_ref"], materials_ref)
            self.assertEqual(confirmation["material_mode"], "materials-provided")
            self.assertEqual(confirmation["revision"], 2)
            self.assertTrue(confirmation["confirmed_at"].endswith("+00:00"))

            with patch.dict(
                os.environ,
                {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
                clear=False,
            ):
                authorize_current_framework(service, confirmation_ref)

            strategy_ref = publish_content_stage(
                service,
                "strategy",
                "strategy",
                {
                    "mission_ref": draft_ref,
                    "material_inventory_ref": materials_ref,
                    "content_identity_mode": "material-backed",
                    "decision_stage": "立项",
                    "core_tension": "系统割裂",
                },
            )
            self.assertTrue(
                strategy_ref.startswith("artifact://presales-content-strategy/")
            )

    def test_content_agent_action_cannot_bypass_python_readiness_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            draft_ref = service.save_mission_draft("draft", 0, MISSION)
            materials_ref = service.register_materials("materials", 1, MATERIALS)
            commands = ProjectCommandService(service.kernel)

            with self.assertRaises(MissionNotConfirmedError):
                commands.request_agent_action(
                    "content-task",
                    2,
                    action_type="build-presales-strategy",
                    target_refs=[draft_ref, materials_ref],
                    instructions="构建售前策略。",
                )

    def test_confirming_materials_mode_requires_the_current_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
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
            service = ContentService.initialize(Path(temp), project_id="p1")
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

            with self.assertRaises(ContentWorkflowError) as caught:
                service.register_content_stage(
                    "stale-confirmation",
                    4,
                    "strategy",
                    {
                        "mission_ref": changed_ref,
                        "material_inventory_ref": materials_ref,
                        "content_identity_mode": "material-backed",
                        "decision_stage": "立项",
                        "core_tension": "系统割裂",
                    },
                )
            self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")

    def test_explicit_no_materials_confirmation_enters_proposal_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
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
            confirmation = service.kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            empty_identity = confirmation["empty_material_identity"]
            with patch.dict(
                os.environ,
                {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
                clear=False,
            ):
                authorize_current_framework(service, confirmation_ref)

            strategy_ref = publish_content_stage(
                service,
                "proposal-strategy",
                "strategy",
                {
                    "mission_ref": draft_ref,
                    "empty_material_identity": empty_identity,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": [
                        "diagnostic-hypothesis",
                        "solution-recommendation",
                        "joint-validation-required",
                    ],
                    "decision_stage": "方案建议",
                    "core_tension": "诊断假设：经营流程可能存在跨系统断点",
                },
            )
            self.assertTrue(
                strategy_ref.startswith("artifact://presales-content-strategy/")
            )


if __name__ == "__main__":
    unittest.main()
