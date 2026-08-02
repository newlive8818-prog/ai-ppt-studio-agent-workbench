from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_create_project_writes_only_managed_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            protected = base / "web-product"
            protected.mkdir()
            config = RuntimeConfig.create(
                runtime_root=runtime,
                source_repo_root=base / "source-repo",
                install_root=base / "installed-skill",
                upstream_root=protected,
            )
            manifest = ProjectStore(config, PathPolicy(config)).create(
                "智慧园区解决方案",
                source_context=protected,
            )
            project = Path(manifest.project_root)
            self.assertTrue(project.is_dir())
            self.assertEqual(project.parent, (runtime / "projects").resolve())
            self.assertTrue((project / "project.json").is_file())
            self.assertEqual(
                json.loads((project / "project.json").read_text("utf-8"))["name"],
                "智慧园区解决方案",
            )
            expected = {
                "sources",
                "managed-assets",
                "cognition",
                "blueprint",
                "visual",
                "scene-graph",
                "ppt",
                "renders",
                "reviews",
                "state",
                "events",
                "logs",
                "tasks",
                "context",
            }
            self.assertEqual(
                {path.name for path in project.iterdir() if path.is_dir()}, expected
            )
            self.assertEqual(list(protected.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
