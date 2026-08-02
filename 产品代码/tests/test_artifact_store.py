from __future__ import annotations

import sys
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.artifact_store import ArtifactStore
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ArtifactValidationError
from ai_ppt_studio.models import ArtifactKind
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


def content_blueprint(title: str) -> dict[str, object]:
    return {
        "title": title,
        "audience": "园区管委会决策者",
        "goal": "确认分阶段建设路径",
        "chapters": [{"title": "从问题到方案", "slide_ids": ["S01"]}],
        "slides": [
            {
                "slide_id": "S01",
                "title": "客户为什么现在需要建设",
                "purpose": "建立紧迫性",
                "claim": "分散系统已经阻碍跨部门协同",
                "visible_content": ["系统分散", "协同成本高"],
                "speaker_notes": "结合会议纪要说明现状。",
                "source_refs": ["sources/source-1.json"],
                "material_refs": ["source-1"],
            }
        ],
    }


class ArtifactStoreTests(unittest.TestCase):
    def make_store(self, base: Path) -> ArtifactStore:
        config = RuntimeConfig.create(
            base / "runtime", base / "repo", base / "install", base / "web"
        )
        policy = PathPolicy(config)
        project = ProjectStore(config, policy).create("版本测试")
        return ArtifactStore(Path(project.project_root), policy)

    def test_save_creates_immutable_versions_and_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(Path(temp))
            first = store.save(
                ArtifactKind.CONTENT_BLUEPRINT, content_blueprint("V1")
            )
            second = store.save(
                ArtifactKind.CONTENT_BLUEPRINT, content_blueprint("V2")
            )
            self.assertEqual(first.version, 1)
            self.assertEqual(second.version, 2)
            self.assertEqual(
                store.latest(ArtifactKind.CONTENT_BLUEPRINT).payload["title"],
                "V2",
            )
            self.assertTrue(Path(first.path).is_file())
            self.assertNotEqual(first.path, second.path)
            self.assertEqual(
                store.list_latest()[ArtifactKind.CONTENT_BLUEPRINT.value].version,
                2,
            )

    def test_content_blueprint_rejects_missing_semantic_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(Path(temp))
            with self.assertRaises(ArtifactValidationError):
                store.save(
                    ArtifactKind.CONTENT_BLUEPRINT,
                    {"title": "缺少听众和逐页内容", "slides": []},
                )

    def test_cli_saves_and_shows_latest_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            web = base / "web"
            web.mkdir()
            profile = base / "workspace.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "workspace_root": str(base / "runtime"),
                        "source_repository": str(base / "repo"),
                        "future_install_root": str(base / "install"),
                        "protected_roots": [str(web)],
                    }
                ),
                encoding="utf-8",
            )
            payload_path = base / "content.json"
            payload_path.write_text(
                json.dumps(content_blueprint("CLI V1"), ensure_ascii=False),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            prefix = [
                sys.executable,
                "-m",
                "ai_ppt_studio",
                "--workspace-config",
                str(profile),
            ]
            created = subprocess.run(
                [*prefix, "init", "--name", "CLI 方案"],
                cwd=web,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            project = json.loads(created.stdout)["project"]["project_root"]
            saved = subprocess.run(
                [
                    *prefix,
                    "save-artifact",
                    "--project",
                    project,
                    "--kind",
                    ArtifactKind.CONTENT_BLUEPRINT.value,
                    "--input",
                    str(payload_path),
                ],
                cwd=web,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(saved.returncode, 0, saved.stderr)
            shown = subprocess.run(
                [
                    *prefix,
                    "show-artifact",
                    "--project",
                    project,
                    "--kind",
                    ArtifactKind.CONTENT_BLUEPRINT.value,
                ],
                cwd=web,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(json.loads(shown.stdout)["artifact"]["payload"]["title"], "CLI V1")


if __name__ == "__main__":
    unittest.main()
