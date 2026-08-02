from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tree_digest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = f"symlink:{os.readlink(path)}"
        elif path.is_file():
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            result[relative] = "directory"
    return result


class IsolationAcceptanceTests(unittest.TestCase):
    def test_full_foundation_flow_never_mutates_protected_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            upstream = base / "web-product"
            originals = base / "original-materials"
            runtime = base / "managed-runtime"
            upstream.mkdir()
            originals.mkdir()
            (upstream / "baseline.md").write_text(
                "权威 Web 产品基线", encoding="utf-8"
            )
            source = originals / "需求.txt"
            source.write_text("建设统一运营平台", encoding="utf-8")
            upstream_before = tree_digest(upstream)
            originals_before = tree_digest(originals)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            common = [
                "--runtime-root",
                str(runtime),
                "--source-repo-root",
                str(base / "source-repo"),
                "--install-root",
                str(base / "install"),
                "--upstream-root",
                str(upstream),
                "--protect",
                str(originals),
            ]
            created = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_ppt_studio",
                    *common,
                    "init",
                    "--name",
                    "纵向切片",
                ],
                cwd=upstream,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            project = json.loads(created.stdout)["project"]["project_root"]
            imported = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_ppt_studio",
                    *common,
                    "import",
                    "--project",
                    project,
                    "--source",
                    str(source),
                    "--mode",
                    "copy",
                ],
                cwd=originals,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(tree_digest(upstream), upstream_before)
            self.assertEqual(tree_digest(originals), originals_before)
            self.assertTrue(Path(project).is_relative_to(runtime.resolve()))
            self.assertEqual(
                [path for path in runtime.rglob("*") if path.is_symlink()], []
            )


if __name__ == "__main__":
    unittest.main()
