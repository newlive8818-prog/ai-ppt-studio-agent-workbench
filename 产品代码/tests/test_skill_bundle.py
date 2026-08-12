from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_skill_bundle import build_bundle


class SkillBundleTests(unittest.TestCase):
    def test_bundle_runs_without_source_repository_on_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = build_bundle(ROOT, base / "bundle")
            runtime_root = base / "runtime"
            protected = base / "protected"
            protected.mkdir()
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "ai_ppt_runtime.py"),
                    "--runtime-root",
                    str(runtime_root),
                    "--source-repo-root",
                    str(base / "unavailable-source"),
                    "--install-root",
                    str(bundle),
                    "--upstream-root",
                    str(protected),
                    "preflight",
                ],
                cwd=protected,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["ok"], True)
            self.assertEqual(
                payload["capabilities"],
                {
                    "runtime_foundation": True,
                    "content_blueprint": True,
                    "visual_conception": True,
                    "image2": True,
                    "presentations": True,
                    "ppt_compilation": True,
                    "delivery_validation": True,
                    "experience_evolution": True,
                },
            )
            evolution = payload["capability_evidence"]["experience_evolution"]
            self.assertTrue(evolution["ready"])
            self.assertIn("evaluate", evolution["operations"])
            self.assertFalse(evolution["stable_kernel_auto_mutation"])
            self.assertEqual(
                (bundle / "runtime" / "VERSION").read_text(encoding="utf-8").strip(),
                "0.4.0",
            )


if __name__ == "__main__":
    unittest.main()
