from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ai_ppt_studio", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_init_and_status_emit_machine_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            protected = base / "web"
            protected.mkdir()
            runtime = base / "runtime"
            common = (
                "--runtime-root",
                str(runtime),
                "--source-repo-root",
                str(base / "repo"),
                "--install-root",
                str(base / "install"),
                "--upstream-root",
                str(protected),
            )
            created = self.run_cli(
                *common, "init", "--name", "测试方案", cwd=protected
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            payload = json.loads(created.stdout)
            self.assertEqual(payload["ok"], True)
            project_root = payload["project"]["project_root"]
            status = self.run_cli(
                *common, "status", "--project", project_root, cwd=protected
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["state"]["current_gate"], "G0")
            self.assertEqual(list(protected.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
