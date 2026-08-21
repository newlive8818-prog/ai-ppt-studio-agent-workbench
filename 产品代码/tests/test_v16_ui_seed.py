from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.workbench_bridge import dispatch


class V16UiSeedTests(unittest.TestCase):
    def test_seed_creates_an_isolated_schema3_project_for_all_three_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "seed-v16-ui-project.py"),
                    temp,
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            seeded = json.loads(result.stdout)
            project_root = Path(seeded["project_root"])
            self.assertIn("workspace_config", seeded)
            workspace_config = Path(seeded["workspace_config"])
            self.assertTrue(
                project_root.is_relative_to(Path(temp).resolve() / "projects")
            )
            self.assertTrue(workspace_config.is_file())
            self.assertEqual(
                seeded["evidence_identity"],
                "deterministic-contract-fixture-not-real-project-proof",
            )
            self.assertEqual(
                seeded["content_review_scenarios"],
                [
                    "content-producing",
                    "content-hard-gate-review",
                    "content-hard-gate-failed",
                    "content-hard-gate-repaired",
                    "ready-10",
                    "mixed-decisions-24",
                    "long-review-60",
                    "save-failure",
                    "source-conflict",
                    "submitted-frozen",
                    "plan-proposed",
                    "new-version-zero-decisions",
                ],
            )

            snapshot = dispatch(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project_root),
                    "workspace_config": str(workspace_config),
                }
            )["snapshot"]
            self.assertEqual(snapshot["schema_version"], "3.0")
            self.assertEqual(snapshot["workspace"]["active_space"], "delivery")
            self.assertEqual(
                len(snapshot["workspace"]["delivery"]["targets"]), 4
            )
            targets = snapshot["workspace"]["delivery"]["targets"]
            self.assertEqual(
                [item["status"] for item in targets],
                ["passed", "deferred", "deferred", "deferred"],
            )
            nonempty_hashes = {
                item["pptx_sha256"]
                for item in targets
                if item["pptx_sha256"]
            }
            self.assertEqual(nonempty_hashes, {seeded["pptx_sha256"]})
            self.assertEqual(
                [item["pptx_sha256"] for item in targets[1:]],
                ["", "", ""],
            )

            content = dispatch(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project_root),
                    "review_type": "content",
                    "workspace_config": str(workspace_config),
                }
            )["review"]
            visual = dispatch(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project_root),
                    "review_type": "visual",
                    "workspace_config": str(workspace_config),
                }
            )["review"]
            self.assertEqual(
                len([item for item in content["sections"] if item["anchor"].startswith("slide-")]),
                2,
            )
            self.assertEqual(
                [item["anchor"] for item in visual["sections"][:2]],
                ["visual-framework", "deck-design-system"],
            )
            self.assertEqual(
                len([item for item in visual["sections"] if item["anchor"].startswith("visual-slide-")]),
                2,
            )


if __name__ == "__main__":
    unittest.main()
