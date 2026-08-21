from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import WorkbenchValidationError


def make_project(base: Path, name: str = "测试项目"):
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    return ProjectService(config).create_project(name)


class ContextCompilerGovernanceTests(unittest.TestCase):
    def test_chief_context_contains_only_current_content_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            seeded = project.commit(
                command_id="seed-v22-content",
                expected_revision=project.load().revision,
                event_type="test.seeded",
                artifact_updates={
                    "mission/confirmation": ("mission-confirmation", {"material_mode": "materials-provided"}),
                    "materials": ("material-inventory", {"sources": [{"source_id": "s1"}]}),
                    "content/evidence-book": ("presales-evidence-book", {"source_version": "content-v1"}),
                    "visual/contract": ("visual-contract", {"secret": "visual-secret"}),
                    "content/framework-confirmation": ("content-framework-confirmation", {"secret": "legacy-secret"}),
                },
            )
            refs = [
                seeded.artifact_heads["mission/confirmation"],
                seeded.artifact_heads["materials"],
                seeded.artifact_heads["content/evidence-book"],
            ]
            pack = ContextCompiler(project).compile_role_task(
                role_id="presales-solution-chief",
                task_type="build-customer-decision-context",
                project_revision=seeded.revision,
                target_refs=refs,
                instructions="建立客户决策语境",
            )
            serialized = json.dumps(pack, ensure_ascii=False)
            self.assertEqual(pack["layers"]["current_content_refs"], refs)
            self.assertNotIn("framework", serialized)
            self.assertNotIn("desiredCustomerJudgment", serialized)
            self.assertNotIn("coreClaim", serialized)
            self.assertNotIn("visual-secret", serialized)
            self.assertNotIn("legacy-secret", serialized)
            self.assertIn("review_records", pack["layers"]["exclusions"])

    def test_hard_gate_context_isolated_from_producer_self_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            pack = ContextCompiler(project).compile_role_task(
                role_id="content-evidence-gate-reviewer",
                task_type="run-content-evidence-gate",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="只提交硬门记录",
            )
            self.assertIn("producer_self_evaluation", pack["layers"]["exclusions"])
            self.assertIn("raw_sibling_review_opinions", pack["layers"]["exclusions"])
            self.assertEqual(pack["layers"]["output_contract"]["allowed_kind"], "content-hard-gate-record")

    def test_formal_visual_tasks_enforce_strict_b(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            pack = ContextCompiler(project).compile_role_task(
                role_id="deck-designer",
                task_type="native-visual-design",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="",
            )
            self.assertEqual(pack["layers"]["governance"]["production_route"], "strict-B")

    def test_image_asset_task_requires_frozen_native_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            with self.assertRaises(WorkbenchValidationError):
                ContextCompiler(project).compile_role_task(
                    role_id="image-asset-producer",
                    task_type="generate-image-assets",
                    project_revision=project.load().revision,
                    target_refs=[],
                    instructions="",
                )

    def test_revision_and_unknown_role_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            with self.assertRaises(WorkbenchValidationError):
                compiler.compile_role_task(
                    role_id="presales-solution-chief",
                    task_type="build-presales-evidence-book",
                    project_revision=99,
                    target_refs=[],
                    instructions="",
                )
            with self.assertRaises(KeyError):
                compiler.compile_role_task(
                    role_id="nonexistent",
                    task_type="anything",
                    project_revision=project.load().revision,
                    target_refs=[],
                    instructions="",
                )


if __name__ == "__main__":
    unittest.main()
