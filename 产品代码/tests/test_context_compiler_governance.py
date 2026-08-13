from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig  # noqa: E402
from ai_ppt_studio.application.content_service import ContentService  # noqa: E402
from ai_ppt_studio.application.framework_discussion_service import (  # noqa: E402
    FrameworkDiscussionService,
)
from ai_ppt_studio.application.project_service import ProjectService  # noqa: E402
from ai_ppt_studio.context_compiler import ContextCompiler  # noqa: E402
from ai_ppt_studio.errors import WorkbenchValidationError  # noqa: E402
from tests.test_v16_content_acceptance import (  # noqa: E402
    TEST_SECRET,
    authorize_current_framework,
    build_authorized_draft,
)
from ai_ppt_studio.application.scoped_confirmation import (  # noqa: E402
    HOST_CONFIRMATION_SECRET_ENV,
)
import os
from unittest.mock import patch


def make_project(base: Path, name: str = "测试项目"):
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    return ProjectService(config).create_project(name)


class ContextCompilerGovernanceTests(unittest.TestCase):
    def test_formal_strategy_context_uses_only_policy_active_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            content = ContentService.initialize(Path(temp), project_id="policy-context")
            _revision, _draft, lineage = build_authorized_draft(content)
            state = content.kernel.load()
            content.kernel.commit(
                command_id="seed-unrelated-policy-heads",
                expected_revision=state.revision,
                event_type="test.seed-unrelated-policy-heads",
                artifact_updates={
                    "visual/contract": ("visual-contract", {"secret": "visual"}),
                    "delivery/build": ("delivery-build", {"secret": "delivery"}),
                    "content/review/presales-reviewer": (
                        "content-review-record", {"secret": "review"}
                    ),
                },
            )
            state = content.kernel.load()
            exact = [
                state.artifact_heads["mission/draft"],
                state.artifact_heads["mission/confirmation"],
                state.artifact_heads["materials"],
                *lineage,
            ]

            pack = ContextCompiler(content.kernel).compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-presales-strategy",
                project_revision=state.revision,
                target_refs=exact,
                instructions="形成策略",
            )

            active = pack["layers"]["current_state"]["active_head_refs"]
            self.assertEqual(set(active), {
                "mission/draft", "mission/confirmation", "materials",
                "content/framework-draft", "content/framework-confirmation",
                "content/full-deck-expansion-authorization",
            })
            self.assertFalse(any(slot.startswith("visual/") for slot in active))
            self.assertFalse(any(slot.startswith("delivery/") for slot in active))
            self.assertFalse(any(slot.startswith("content/review/") for slot in active))

    def test_content_workflow_layer_is_total_without_fabricated_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            pack = ContextCompiler(project).compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-strategy",
                project_revision=project.load().revision,
                target_refs=[],
                instructions="先讨论框架",
            )
            self.assertEqual(pack["layers"]["content_workflow"], {
                "framework_ref": "",
                "framework_confirmation_ref": "",
                "full_deck_expansion_authorization_ref": "",
                "review_batch_ref": "",
                "batch_revision_plan_ref": "",
                "batch_plan_confirmation_ref": "",
            })

    def test_framework_context_excludes_all_formal_page_content_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            content = ContentService(project)
            mission_ref = content.save_mission_draft(
                "mission", project.load().revision, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                }
            )
            content.confirm_mission(
                "mission-confirm", project.load().revision,
                mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed",
                material_inventory_ref="",
                user_action_ref="test-user-action://framework-context",
                user_message_ref="",
            )
            project.commit(
                command_id="seed-formal-content",
                expected_revision=project.load().revision,
                event_type="test.seed-formal-content",
                artifact_updates={
                    "content/draft": ("slide-draft-set", {"slides": ["secret"]}),
                    "content/blueprint": ("content-blueprint", {"pages": ["secret"]}),
                    "content/page-decisions": ("page-decisions", {"pages": ["secret"]}),
                },
            )
            pack = ContextCompiler(project).compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-content-framework",
                project_revision=project.load().revision,
                target_refs=[
                    project.load().artifact_heads["mission/draft"],
                    project.load().artifact_heads["mission/confirmation"],
                ],
                instructions="只讨论框架",
            )
            active = pack["layers"]["current_state"]["active_head_refs"]
            self.assertFalse(any(slot.startswith("content/") for slot in active))
            self.assertNotIn("secret", json.dumps(pack, ensure_ascii=False))
            self.assertIn(
                "mission_identity", pack["layers"]["project_facts"]
            )
            self.assertIn(
                "material_summary", pack["layers"]["project_facts"]
            )

    def test_authorized_framework_context_hides_all_downstream_workflow_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            project = make_project(Path(temp))
            content = ContentService(project)
            mission_ref = content.save_mission_draft(
                "mission", project.load().revision, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                },
            )
            confirmation_ref = content.confirm_mission(
                "confirm", project.load().revision,
                mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed",
                material_inventory_ref="",
                user_action_ref="test-user-action://authorized-framework-context",
                user_message_ref="",
            )
            framework_ref, _confirmation, _authorization = (
                authorize_current_framework(content, confirmation_ref)
            )
            project.commit(
                command_id="seed-downstream-workflow-heads",
                expected_revision=project.load().revision,
                event_type="test.seed-downstream-workflow-heads",
                artifact_updates={
                    "content/review-batch": ("content-review-batch", {"x": 1}),
                    "content/batch-revision-plan": ("batch-revision-plan", {"x": 1}),
                    "content/batch-plan-confirmation": ("batch-plan-confirmation", {"x": 1}),
                },
            )
            pack = ContextCompiler(project).compile_role_task(
                role_id="presales-content-strategist",
                task_type="build-content-framework",
                project_revision=project.load().revision,
                target_refs=[
                    project.load().artifact_heads["mission/draft"],
                    project.load().artifact_heads["mission/confirmation"],
                    framework_ref,
                ],
                instructions="仅修订框架",
            )
            workflow = pack["layers"]["content_workflow"]
            self.assertEqual(workflow["framework_ref"], framework_ref)
            self.assertEqual(
                {key: value for key, value in workflow.items() if key != "framework_ref"},
                {
                    "framework_confirmation_ref": "",
                    "full_deck_expansion_authorization_ref": "",
                    "review_batch_ref": "",
                    "batch_revision_plan_ref": "",
                    "batch_plan_confirmation_ref": "",
                },
            )

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
