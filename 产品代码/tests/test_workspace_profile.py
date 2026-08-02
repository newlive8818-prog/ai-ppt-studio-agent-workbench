from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig


class WorkspaceProfileTests(unittest.TestCase):
    def test_cli_uses_workspace_profile_without_repeated_roots(self) -> None:
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
                        "protected_roots": [
                            str(web),
                            str(base / "repo"),
                            str(base / "install"),
                        ],
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_ppt_studio",
                    "--workspace-config",
                    str(profile),
                    "init",
                    "--name",
                    "方案",
                ],
                cwd=web,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(Path(payload["project"]["project_root"]).is_relative_to((base / "runtime").resolve()))
            self.assertEqual(list(web.iterdir()), [])

    def test_profile_maps_existing_workspace_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            profile = base / "workspace.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "workspace_root": str(base / "runtime"),
                        "source_repository": str(base / "repo"),
                        "future_install_root": str(base / "install"),
                        "protected_roots": [str(base / "web")],
                    }
                ),
                encoding="utf-8",
            )
            config = RuntimeConfig.from_workspace_file(profile)
            self.assertEqual(config.runtime_root, (base / "runtime").resolve())
            self.assertEqual(config.upstream_root, (base / "web").resolve())


if __name__ == "__main__":
    unittest.main()
