from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.application.project_service import ProjectService
from scripts.acceptance.prepare_real_project import prepare_real_project


class RealProjectAcceptanceTests(unittest.TestCase):
    def test_prepares_idempotent_schema3_project_only_in_managed_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config = RuntimeConfig.create(
                base / "runtime", base / "repo", base / "install", base / "web"
            )
            mission = {
                "topic": "经营一体化解决方案",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准一期立项",
            }
            secret_material = "仅用于外部运行数据的客户断点材料-92f6"

            first = prepare_real_project(
                config,
                project_id="v16-real-presales",
                name="v1.6 真实售前验收",
                mission=mission,
                text_materials=[("客户材料", secret_material)],
            )
            second = prepare_real_project(
                config,
                project_id="v16-real-presales",
                name="v1.6 真实售前验收",
                mission=mission,
                text_materials=[("客户材料", secret_material)],
            )

            project = Path(first["project_root"])
            self.assertTrue(project.is_relative_to(config.runtime_root / "projects"))
            state = json.loads(
                (project / "kernel" / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["schema_version"], "3.0")
            self.assertEqual(first["revision"], second["revision"])
            self.assertIn("mission/draft", state["artifact_heads"])
            self.assertNotIn("mission", state["artifact_heads"])
            self.assertNotIn("mission/confirmation", state["artifact_heads"])
            self.assertIn("materials", state["artifact_heads"])
            draft_ref = state["artifact_heads"]["mission/draft"]
            from ai_ppt_studio.kernel.references import ArtifactReference
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            draft = ProjectKernel(
                project, project_id=state["project_id"]
            ).artifacts.resolve(ArtifactReference.parse(draft_ref))["payload"]
            self.assertEqual(draft["status"], "confirmable")
            self.assertFalse(any(secret_material in path.read_text(encoding="utf-8", errors="ignore") for path in ROOT.rglob("*.json")))

    def test_refuses_to_migrate_a_legacy_mission_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config = RuntimeConfig.create(
                base / "runtime", base / "repo", base / "install", base / "web"
            )
            kernel = ProjectService(config).create_project(
                "旧合同项目", project_id="legacy-mission-project"
            )
            mission = {
                "topic": "经营一体化解决方案",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准一期立项",
            }
            before = kernel.commit(
                command_id="legacy-mission-fixture",
                expected_revision=kernel.load().revision,
                event_type="legacy.mission-registered",
                artifact_updates={"mission": ("mission-brief", mission)},
            )

            with self.assertRaises(ContractValidationError):
                prepare_real_project(
                    config,
                    project_id="legacy-mission-project",
                    name="旧合同项目",
                    mission=mission,
                )

            after = kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertIn("mission", after.artifact_heads)
            self.assertNotIn("mission/draft", after.artifact_heads)
            self.assertNotIn("mission/confirmation", after.artifact_heads)


if __name__ == "__main__":
    unittest.main()
