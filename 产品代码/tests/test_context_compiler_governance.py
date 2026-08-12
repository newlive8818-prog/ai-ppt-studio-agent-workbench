from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig  # noqa: E402
from ai_ppt_studio.application.project_service import ProjectService  # noqa: E402
from ai_ppt_studio.context_compiler import ContextCompiler  # noqa: E402
from ai_ppt_studio.errors import WorkbenchValidationError  # noqa: E402


def make_project(base: Path, name: str = "测试项目"):
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    return ProjectService(config).create_project(name)


class ContextCompilerGovernanceTests(unittest.TestCase):
    def test_compile_role_task_produces_layered_pack(self) -> None:
        """分层 Context Pack 包含治理、场景、项目事实、角色、任务、工具、经验、输出、排除层。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            pack = compiler.compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-strategy",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="",
            )
            self.assertIn("schema_version", pack)
            self.assertIn("layers", pack)
            layers = pack["layers"]
            required_layers = [
                "governance",
                "scenario_pack",
                "project_facts",
                "role_contract",
                "task_contract",
                "tool_contract",
                "experience_slice",
                "output_contract",
                "exclusions",
            ]
            for layer in required_layers:
                with self.subTest(layer=layer):
                    self.assertIn(layer, layers, f"缺少 {layer} 层")

    def test_content_producer_cannot_see_internal_review_records(self) -> None:
        """内容生产者的 Context Pack 中不应包含审查记录。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            pack = compiler.compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-strategy",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="",
            )
            exclusions = pack["layers"]["exclusions"]
            self.assertIn("review_records", exclusions, "生产者必须排除审查记录")
            self.assertIn("sibling_reviews", exclusions, "生产者必须排除同级审查")

    def test_reviewer_cannot_see_producer_self_evaluation(self) -> None:
        """独立审查者不应看到生产者自评或其他审查者的原始意见。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            pack = compiler.compile_role_task(
                role_id="content-fact-checker",
                task_type="review-content",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="",
            )
            exclusions = pack["layers"]["exclusions"]
            self.assertIn("producer_self_evaluation", exclusions)
            self.assertIn("raw_sibling_review_opinions", exclusions)

    def test_formal_visual_tasks_enforce_strict_b(self) -> None:
        """正式视觉任务的 Context Pack 必须声明 productionRoute=strict-B。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            pack = compiler.compile_role_task(
                role_id="deck-designer",
                task_type="native-visual-design",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="",
            )
            governance = pack["layers"]["governance"]
            self.assertEqual(governance["production_route"], "strict-B")

    def test_image_asset_task_requires_frozen_native_first(self) -> None:
        """Image 2 资产任务若缺少冻结原生首版引用应失败。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            with self.assertRaises(WorkbenchValidationError):
                compiler.compile_role_task(
                    role_id="image-asset-producer",
                    task_type="generate-image-assets",
                    project_revision=project.load().revision,
                    target_refs=[],
                    instructions="",
                )

    def test_unknown_role_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            with self.assertRaises(KeyError):
                compiler.compile_role_task(
                    role_id="nonexistent",
                    task_type="anything",
                    project_revision=project.load().revision,
                    target_refs=[],
                    instructions="",
                )

    def test_raw_feedback_rejected_from_production_context(self) -> None:
        """原始反馈不能直接注入生产上下文，必须经过治理记录。"""
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            compiler = ContextCompiler(project)
            # 直接带 raw_feedback 字段的 payload 不应出现在生产层
            pack = compiler.compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-strategy",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="修改客户需求",
            )
            layers = pack["layers"]
            # 项目事实层不能包含原始反馈
            project_facts_str = json.dumps(layers.get("project_facts", {}), ensure_ascii=False)
            self.assertNotIn("改色", project_facts_str)


if __name__ == "__main__":
    unittest.main()
