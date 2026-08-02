from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.artifact_store import ArtifactStore
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.models import ArtifactKind
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore
from ai_ppt_studio.workbench_store import WorkbenchStore


class WorkbenchStoreTests(unittest.TestCase):
    def make_project(self, base: Path) -> tuple[Path, PathPolicy]:
        runtime = base / "runtime"
        protected = base / "web"
        protected.mkdir()
        config = RuntimeConfig.create(
            runtime_root=runtime,
            source_repo_root=base / "repo",
            install_root=base / "install",
            upstream_root=protected,
        )
        policy = PathPolicy(config)
        manifest = ProjectStore(config, policy).create("智慧园区解决方案")
        project = Path(manifest.project_root)
        StateStore(project, policy).initialize()
        return project, policy

    def test_ensure_adds_v2_projection_without_rewriting_legacy_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = self.make_project(Path(temp))
            legacy_before = (project / "state" / "state.json").read_text("utf-8")

            snapshot = WorkbenchStore(project, policy).ensure()

            self.assertEqual(snapshot.schema_version, "2.0")
            self.assertEqual(snapshot.revision, 0)
            self.assertEqual(snapshot.active_space, "overview")
            self.assertTrue((project / "cognition" / "map.json").is_file())
            self.assertTrue((project / "state" / "workbench.json").is_file())
            self.assertEqual(
                (project / "state" / "state.json").read_text("utf-8"),
                legacy_before,
            )

    def test_reopen_is_idempotent_and_uses_latest_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = self.make_project(Path(temp))
            artifacts = ArtifactStore(project, policy)
            artifacts.save(
                ArtifactKind.MISSION,
                {
                    "title": "智慧园区运营中台解决方案",
                    "audience": "园区管委会领导与信息化负责人",
                    "goal": "确认一期建设路径并启动项目",
                    "context": "阅读优先的售前解决方案汇报",
                },
            )
            artifacts.save(
                ArtifactKind.CONTENT_BLUEPRINT,
                {
                    "title": "智慧园区运营中台解决方案",
                    "audience": "园区管委会领导与信息化负责人",
                    "goal": "确认一期建设路径并启动项目",
                    "narrative_thesis": "连接既有系统，形成统一运营闭环。",
                    "slides": [
                        {
                            "slide_id": "S01",
                            "title": "从分散系统走向统一闭环",
                            "purpose": "建立共识",
                            "claim": "连接比替换更重要",
                            "visible_content": ["不推倒重来"],
                            "speaker_notes": "先连接关键系统。",
                            "source_refs": [],
                            "material_refs": [],
                        }
                    ],
                },
            )

            first = WorkbenchStore(project, policy).ensure()
            second = WorkbenchStore(project, policy).ensure()

            self.assertEqual(first.as_dict(), second.as_dict())
            self.assertEqual(first.project["name"], "智慧园区解决方案")
            self.assertEqual(
                first.cognition_map["delivery_goal"],
                "确认一期建设路径并启动项目",
            )
            self.assertEqual(
                first.cognition_map["audiences"],
                ["园区管委会领导与信息化负责人"],
            )
            self.assertIn("连接既有系统", first.cognition_map["ai_judgment"])
            self.assertEqual(first.artifacts["content-blueprint"]["version"], 1)
            self.assertEqual(first.gate_state["current_gate"], "G0")

    def test_missing_mission_becomes_explicit_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = self.make_project(Path(temp))

            snapshot = WorkbenchStore(project, policy).ensure()

            self.assertEqual(snapshot.cognition_map["delivery_goal"], "尚未确认交付目标")
            self.assertEqual(snapshot.current_decision["target_ref"], "mission://goal")
            self.assertEqual(snapshot.current_decision["status"], "needs-user")
            self.assertIn("汇报目标", snapshot.cognition_map["uncertainty"])

    def test_projection_files_are_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = self.make_project(Path(temp))
            WorkbenchStore(project, policy).ensure()
            for relative in ("cognition/map.json", "state/workbench.json"):
                payload = json.loads((project / relative).read_text("utf-8"))
                self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main()
