from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.adapters.legacy.importer import LegacyProjectImporter
from ai_ppt_studio.kernel.transactions import ProjectKernel


class LegacyImporterTests(unittest.TestCase):
    def test_imports_verifiable_payloads_without_copying_pass_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            legacy = base / "legacy"
            legacy.mkdir()
            (legacy / "project.json").write_text(
                json.dumps(
                    {
                        "project_id": "legacy-1",
                        "name": "旧项目",
                        "schema_version": "2.0",
                    }
                ),
                encoding="utf-8",
            )
            (legacy / "state.json").write_text(
                json.dumps({"gates": {"G0": "passed", "G1": "passed"}}),
                encoding="utf-8",
            )
            (legacy / "mission.json").write_text(
                json.dumps(
                    {"goal": "确认一期方案", "audience": "客户决策者"}
                ),
                encoding="utf-8",
            )
            destination = base / "new"
            report = LegacyProjectImporter().import_project(legacy, destination)
            state = ProjectKernel(destination, project_id="legacy-1").load()
            self.assertEqual(state.schema_version, "3.0")
            self.assertEqual(state.gate_status["G0"], "open")
            self.assertIn("mission", state.artifact_heads)
            self.assertIn(
                "legacy pass states were not imported", report.warnings
            )
            self.assertEqual(
                json.loads((legacy / "state.json").read_text())["gates"]["G0"],
                "passed",
            )


if __name__ == "__main__":
    unittest.main()
