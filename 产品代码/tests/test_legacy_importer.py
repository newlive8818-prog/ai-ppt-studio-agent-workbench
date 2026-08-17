from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.adapters.legacy.importer import LegacyProjectImporter
from ai_ppt_studio.adapters.legacy.content_v16 import read_legacy_content
from ai_ppt_studio.adapters.legacy.framework_v16 import (
    validate_legacy_framework_draft,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class LegacyImporterTests(unittest.TestCase):
    def test_legacy_framework_validator_is_read_only_and_rejects_page_content(self) -> None:
        payload = {
            "framework_id": "legacy-framework-1",
            "mission_confirmation_ref": "artifact://mission-confirmation/" + "a" * 64,
            "core_proposition": "旧项目结构命题",
            "persuasion_path": ["先说明问题", "再说明路径"],
            "chapters": [{
                "chapter_id": "c1",
                "title": "现状",
                "task": "说明边界",
                "expected_judgment": "理解边界",
                "transition": "进入方案",
            }],
            "structural_risks": ["材料不足"],
            "highest_impact_question": "是否需要补充材料？",
            "status": "discussion",
        }
        self.assertEqual(validate_legacy_framework_draft(payload), payload)
        with self.assertRaises(ContractValidationError):
            validate_legacy_framework_draft({**payload, "slides": []})

    def test_legacy_content_reader_never_changes_heads_gates_or_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="legacy-read")
            payload = {"source_version": "legacy-v1"}
            reference = kernel.artifacts.reference_for("content-blueprint", payload)
            kernel.commit(
                command_id="seed-detached-legacy",
                expected_revision=0,
                event_type="test.legacy-seeded",
                artifact_updates={},
                detached_artifacts=(("content-blueprint", payload),),
            )
            before = kernel.load()
            projection = read_legacy_content(kernel, str(reference))
            after = kernel.load()
            self.assertEqual(projection["identity"], "legacy-read-only")
            self.assertTrue(projection["requires_v22_migration_and_hard_gates"])
            self.assertEqual(after, before)

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
