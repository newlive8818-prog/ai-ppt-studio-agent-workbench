from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.errors import ProjectNotFoundError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.workbench_bridge import dispatch
from tests.v16_content_fixtures import complete_slide_draft_payload


def runtime_config(base: Path) -> tuple[RuntimeConfig, Path]:
    runtime = base / "runtime"
    source = base / "source"
    install = base / "install"
    upstream = base / "web"
    source.mkdir()
    install.mkdir()
    upstream.mkdir()
    config = RuntimeConfig.create(runtime, source, install, upstream)
    profile = runtime / "workspace.json"
    config.save(profile)
    return config, profile


class V16ProjectServiceTests(unittest.TestCase):
    def test_project_id_accepts_unicode_letters_but_rejects_path_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            projects = ProjectService(config)
            project_id = "v16-真实售前验收-经营一体化方案"
            created = projects.create_project("真实验收", project_id=project_id)
            self.assertEqual(created.project_id, project_id)
            self.assertEqual(created.project_root.name, project_id)

            from ai_ppt_studio.errors import ContractValidationError

            for invalid in (
                "../逃逸",
                "项目/子目录",
                ".hidden",
                "项目 名称",
                "项目\u0000名称",
                "a" * 97,
            ):
                with self.subTest(invalid=invalid), self.assertRaises(
                    ContractValidationError
                ):
                    projects.create_project("非法项目", project_id=invalid)

    def test_create_list_and_latest_project_are_schema3_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            projects = ProjectService(config)

            first = projects.create_project(
                "经营一体化验收", project_id="real-presales-v16"
            )
            second = projects.create_project(
                "经营一体化验收二版", project_id="real-presales-v16-b"
            )

            self.assertEqual(first.load().schema_version, "3.0")
            self.assertEqual(second.load().schema_version, "3.0")
            manifest_ref = first.load().artifact_heads["project/manifest"]
            manifest = first.artifacts.resolve(
                ArtifactReference.parse(manifest_ref)
            )["payload"]
            self.assertTrue(manifest["created_at"].endswith("+00:00"))
            self.assertEqual(projects.latest_project(), second.project_root)
            listed = projects.list_projects()
            self.assertEqual(
                [item["project_id"] for item in listed],
                ["real-presales-v16-b", "real-presales-v16"],
            )
            self.assertEqual(listed[0]["name"], "经营一体化验收二版")

    def test_default_public_route_selects_latest_schema3_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "默认项目", project_id="schema3-default"
            )

            result = dispatch(
                {
                    "operation": "get-project-snapshot",
                    "workspace_config": str(profile),
                }
            )

            self.assertEqual(result["snapshot"]["schema_version"], "3.0")
            self.assertEqual(
                result["selected_project_root"], str(kernel.project_root)
            )
            state = json.loads(
                (kernel.project_root / "kernel" / "state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("space_projections", state)

    def test_public_bridge_rejects_schema3_project_outside_managed_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            _config, profile = runtime_config(base)
            external = base / "external-schema3"
            ContentService.initialize(external, project_id="outside")

            with self.assertRaises(ProjectNotFoundError):
                dispatch(
                    {
                        "operation": "get-project-snapshot",
                        "workspace_config": str(profile),
                        "project_root": str(external),
                    }
                )

    def test_resolve_project_rejects_symlink_alias_inside_managed_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            projects = ProjectService(config)
            kernel = projects.create_project(
                "真实项目", project_id="schema3-real-project"
            )
            alias = projects.projects_root / "schema3-project-alias"
            alias.symlink_to(kernel.project_root, target_is_directory=True)

            with self.assertRaises(ProjectNotFoundError):
                projects.resolve_project(alias)

    def test_public_input_operations_commit_formal_schema3_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "输入链路", project_id="schema3-inputs"
            )
            project_root = str(kernel.project_root)

            mission = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 1,
                    "kind": "mission",
                    "payload": {
                        "topic": "经营一体化方案",
                        "primary_audience": "客户决策者",
                        "desired_judgment_or_action": "批准一期立项",
                    },
                }
            )["result"]
            mission_ref = mission["artifact_ref"]
            self.assertTrue(mission_ref.startswith("artifact://mission-draft/"))

            material = dispatch_v16(
                {
                    "operation": "add-material",
                    "project_root": project_root,
                    "expected_revision": 2,
                    "material_type": "text",
                    "value": "客户现有五套系统，跨系统流转存在三个断点。",
                    "label": "客户现状",
                }
            )["result"]
            material_ref = material["artifact_ref"]
            self.assertTrue(
                material_ref.startswith("artifact://material-inventory/")
            )
            self.assertEqual(
                material["snapshot"]["workspace"]["materials"]["source_count"],
                1,
            )

            confirmation = dispatch_v16(
                {
                    "operation": "confirm-mission",
                    "project_root": project_root,
                    "expected_revision": 3,
                    "mission_draft_ref": mission_ref,
                    "material_mode": "materials-provided",
                    "material_inventory_ref": material_ref,
                    "user_action_ref": "test-user-action://public-input-contract",
                }
            )["result"]
            self.assertTrue(
                confirmation["artifact_ref"].startswith(
                    "artifact://mission-confirmation/"
                )
            )
            self.assertEqual(
                confirmation["snapshot"]["contentIdentityMode"],
                "material-backed",
            )

            task = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": project_root,
                    "expected_revision": 4,
                    "action_type": "build-presales-strategy",
                    "target_refs": [mission_ref, material_ref],
                    "instructions": "先构建售前策略，不讨论视觉。",
                }
            )["result"]
            task_ref = task["artifact_ref"]
            self.assertTrue(task_ref.startswith("artifact://agent-task/"))
            self.assertEqual(task["task"]["role_id"], "presales-content-strategist")
            context_ref = task["task"]["context_pack_ref"]
            self.assertTrue(context_ref.startswith("artifact://context-pack/"))
            context = kernel.artifacts.resolve(
                ArtifactReference.parse(context_ref)
            )["payload"]
            self.assertEqual(context["schema_version"], "3.0")
            self.assertEqual(context["project_revision"], 4)
            self.assertEqual(
                context["layers"]["output_contract"]["reference_format"],
                "artifact://<kind>/<sha256>",
            )
            self.assertNotIn(
                "五套系统",
                json.dumps(context, ensure_ascii=False),
            )

            decision = dispatch_v16(
                {
                    "operation": "submit-human-decision",
                    "project_root": project_root,
                    "expected_revision": 5,
                    "target_ref": task_ref,
                    "choice": "继续推进",
                    "feedback": "保持内容优先。",
                }
            )["result"]
            self.assertEqual(decision["snapshot"]["revision"], 6)
            self.assertIn("继续推进", decision["follow_up_message"])
            self.assertTrue(
                decision["decision_ref"].startswith("artifact://human-decision/")
            )

    def test_committed_artifact_completes_the_matching_agent_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "任务结果绑定", project_id="schema3-task-result"
            )
            project_root = str(kernel.project_root)
            mission_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 1,
                    "kind": "mission",
                    "payload": {
                        "topic": "经营一体化方案",
                        "primary_audience": "客户决策者",
                        "desired_judgment_or_action": "批准一期立项",
                    },
                }
            )["result"]["artifact_ref"]
            material_ref = dispatch_v16(
                {
                    "operation": "add-material",
                    "project_root": project_root,
                    "expected_revision": 2,
                    "material_type": "text",
                    "value": "用户仅提供了验收任务说明。",
                    "label": "任务说明",
                }
            )["result"]["artifact_ref"]
            dispatch_v16(
                {
                    "operation": "confirm-mission",
                    "project_root": project_root,
                    "expected_revision": 3,
                    "mission_draft_ref": mission_ref,
                    "material_mode": "materials-provided",
                    "material_inventory_ref": material_ref,
                    "user_action_ref": "test-user-action://task-result-contract",
                }
            )
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": project_root,
                    "expected_revision": 4,
                    "action_type": "build-presales-strategy",
                    "target_refs": [mission_ref, material_ref],
                    "instructions": "只依据用户材料形成策略。",
                }
            )["result"]

            task_id = requested["task"]["task_id"]
            self.assertEqual(
                requested["snapshot"]["artifacts"][f"agent/task/{task_id}"],
                requested["artifact_ref"],
            )
            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 5,
                    "kind": "content-blueprint",
                    "task_id": task_id,
                    "payload": {
                        "artifact_type": "presales-content-strategy",
                        "mission_ref": mission_ref,
                        "material_inventory_ref": material_ref,
                        "content_identity_mode": "material-backed",
                        "decision_stage": "方案建议",
                        "core_tension": "待联合验证",
                    },
                }
            )["result"]

            active_task_ref = committed["snapshot"]["artifacts"][
                "agent/task/active"
            ]
            active_task = kernel.artifacts.resolve(
                ArtifactReference.parse(active_task_ref)
            )["payload"]
            self.assertEqual(committed["snapshot"]["revision"], 7)
            self.assertEqual(active_task["task_id"], task_id)
            self.assertEqual(active_task["status"], "completed")
            self.assertEqual(active_task["progress"], {
                "stage": "completed",
                "done": 1,
                "total": 1,
            })
            self.assertEqual(
                active_task["result_refs"], [committed["artifact_ref"]]
            )

    def test_public_artifact_route_reaches_every_content_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "内容链路", project_id="schema3-content-route"
            )
            project_root = str(kernel.project_root)
            mission_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 1,
                    "kind": "mission",
                    "payload": {
                        "topic": "经营一体化方案",
                        "primary_audience": "客户决策者",
                        "desired_judgment_or_action": "批准一期立项",
                    },
                }
            )["result"]["artifact_ref"]
            material_ref = dispatch_v16(
                {
                    "operation": "add-material",
                    "project_root": project_root,
                    "expected_revision": 2,
                    "material_type": "text",
                    "value": "五套系统彼此割裂。",
                    "label": "现状材料",
                }
            )["result"]["artifact_ref"]
            dispatch_v16(
                {
                    "operation": "confirm-mission",
                    "project_root": project_root,
                    "expected_revision": 3,
                    "mission_draft_ref": mission_ref,
                    "material_mode": "materials-provided",
                    "material_inventory_ref": material_ref,
                    "user_action_ref": "test-user-action://content-route-contract",
                }
            )

            strategy_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 4,
                    "kind": "content-blueprint",
                    "payload": {
                        "artifact_type": "presales-content-strategy",
                        "mission_ref": mission_ref,
                        "material_inventory_ref": material_ref,
                        "content_identity_mode": "material-backed",
                        "decision_stage": "立项",
                        "core_tension": "系统割裂",
                    },
                }
            )["result"]["artifact_ref"]
            claim_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 5,
                    "kind": "content-blueprint",
                    "payload": {
                        "artifact_type": "claim-evidence-map",
                        "strategy_ref": strategy_ref,
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "status": "supported",
                                "evidence_refs": [material_ref],
                            }
                        ],
                    },
                }
            )["result"]["artifact_ref"]
            argument_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 6,
                    "kind": "content-blueprint",
                    "payload": {
                        "artifact_type": "deck-argument-map",
                        "strategy_ref": strategy_ref,
                        "claim_evidence_map_ref": claim_ref,
                        "chapters": [
                            {"chapter_id": "ch1", "task": "建立问题共识"}
                        ],
                    },
                }
            )["result"]["artifact_ref"]
            draft_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 7,
                    "kind": "content-blueprint",
                    "payload": {
                        "artifact_type": "slide-draft-set",
                        **complete_slide_draft_payload(
                            argument_map_ref=argument_ref,
                            material_ref=material_ref,
                            slide_id_prefix="s",
                        ),
                    },
                }
            )["result"]["artifact_ref"]

            self.assertTrue(strategy_ref.startswith("artifact://presales-content-strategy/"))
            self.assertTrue(claim_ref.startswith("artifact://claim-evidence-map/"))
            self.assertTrue(argument_ref.startswith("artifact://deck-argument-map/"))
            self.assertTrue(draft_ref.startswith("artifact://slide-draft-set/"))

    def test_public_actions_bind_all_five_isolated_content_reviewers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "五角色内容审查", project_id="five-content-reviewers"
            )
            project_root = str(kernel.project_root)
            content = ContentService(kernel)
            mission_ref = content.save_mission_draft(
                "reviewers:draft",
                1,
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户决策者",
                    "desired_judgment_or_action": "批准一期立项",
                },
            )
            materials_ref = content.register_materials(
                "reviewers:materials", 2, {
                    "sources": [
                        {
                            "source_id": "review-source",
                            "origin": "user-provided",
                            "kind": "text",
                            "locator": "inline://user-provided/review-source",
                            "sha256": "d" * 64,
                        }
                    ]
                }
            )
            content.confirm_mission(
                "reviewers:confirm",
                3,
                mission_draft_ref=mission_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://reviewer-binding-contract",
                user_message_ref="",
            )
            target_ref = kernel.load().artifact_heads["project/manifest"]
            actions = {
                "review-content-presales": "presales-content-reviewer",
                "review-content-decision-maker": "audience-decision-reviewer",
                "review-content-evidence": "content-fact-checker",
                "review-content-narrative": "argument-logic-reviewer",
                "review-content-editorial": "reading-experience-reviewer",
            }

            revision = 4
            for action, role_id in actions.items():
                result = dispatch_v16(
                    {
                        "operation": "request-agent-action",
                        "project_root": project_root,
                        "expected_revision": revision,
                        "command_id": f"task:{action}",
                        "action_type": action,
                        "target_refs": [target_ref],
                        "instructions": "独立审查当前内容，不读取其他审查结论。",
                    }
                )["result"]
                self.assertEqual(result["task"]["role_id"], role_id)
                revision += 1
                self.assertEqual(result["snapshot"]["revision"], revision)


if __name__ == "__main__":
    unittest.main()
