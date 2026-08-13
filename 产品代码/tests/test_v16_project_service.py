from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.framework_discussion_service import (
    FrameworkDiscussionService,
)
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.errors import ContentWorkflowError, ProjectNotFoundError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.workbench_bridge import dispatch
from tests.v16_content_fixtures import complete_slide_draft_payload


TEST_SECRET = "test-only-full-deck-authorization-secret-32-bytes"


def _signed_assertion(context: dict[str, object]) -> str:
    issued_at = int(time.time())
    payload = {
        key: context[key]
        for key in (
            "project_id", "project_root", "scope_kind", "scope_id",
            "source_version", "evidence_refs", "challenge_id",
            "challenge_revision",
        )
    }
    payload.update({
        "identity_type": "host-action",
        "identity_ref": f"test-host-action://{uuid.uuid4()}",
        "nonce": str(uuid.uuid4()),
        "issued_at": issued_at,
        "expires_at": issued_at + 120,
    })
    encoded = base64.urlsafe_b64encode(json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(
        TEST_SECRET.encode(), encoded.encode("ascii"), hashlib.sha256
    ).digest()).decode().rstrip("=")
    return f"v1.{encoded}.{signature}"


def _framework_payload(mission_confirmation_ref: str, version: int = 1) -> dict:
    return {
        "framework_id": f"framework-v{version}",
        "mission_confirmation_ref": mission_confirmation_ref,
        "core_proposition": "先证明经营断点，再确认一期联合验证路径。",
        "persuasion_path": ["问题共识", "方案可信", "一期行动"],
        "chapters": [{
            "chapter_id": "C01", "title": "为何改变", "task": "建立问题共识",
            "expected_judgment": "需要跨系统治理", "transition": "进入建设原则",
        }],
        "structural_risks": ["定量收益证据不足"],
        "highest_impact_question": "是否以一期行动收束？",
        "status": "discussion",
    }


def _save_confirm_authorize(kernel, mission_confirmation_ref: str, version: int = 1):
    workflow = FrameworkDiscussionService(kernel)
    framework_ref, _ = workflow.save_draft(
        f"framework:{version}", kernel.load().revision,
        _framework_payload(mission_confirmation_ref, version),
    )
    context = workflow.confirmation_context()
    confirmation_ref, _ = workflow.confirm_framework(
        f"framework-confirm:{version}", kernel.load().revision, framework_ref,
        str(context["challenge_id"]), int(context["challenge_revision"]),
        _signed_assertion(context),
    )
    context = workflow.expansion_authorization_context()
    authorization_ref, _ = workflow.authorize_full_deck_expansion(
        f"framework-authorize:{version}", kernel.load().revision, framework_ref,
        str(context["challenge_id"]), int(context["challenge_revision"]),
        _signed_assertion(context),
    )
    return framework_ref, confirmation_ref, authorization_ref


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
    def setUp(self) -> None:
        self.host_secret = patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        )
        self.host_secret.start()
        self.addCleanup(self.host_secret.stop)

    def test_framework_action_precedes_full_deck_authorization_and_rejection_is_write_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("framework gate")
            content = ContentService(kernel)
            mission_ref = content.save_mission_draft(
                "mission", 1, {
                    "topic": "经营一体化", "primary_audience": "客户决策者",
                    "desired_judgment_or_action": "批准一期验证",
                }
            )
            mission_confirmation_ref = content.confirm_mission(
                "mission-confirm", 2, mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://mission", user_message_ref="",
            )
            command = ProjectCommandService(kernel)
            target = kernel.load().artifact_heads["project/manifest"]
            _ref, task, state = command.request_agent_action(
                "framework-task", 3, action_type="build-content-framework",
                target_refs=[mission_ref, mission_confirmation_ref],
                instructions="先规划章节框架",
            )
            self.assertEqual(task["action_type"], "build-content-framework")
            self.assertEqual(state.revision, 4)

            before = kernel.load()
            events_before = tuple(kernel.events_root.iterdir())
            objects_before = tuple(kernel.artifacts.objects_root.rglob("*"))
            with self.assertRaises(ContentWorkflowError) as caught:
                command.request_agent_action(
                    "full-deck-too-early", before.revision,
                    action_type="build-presales-strategy", target_refs=[target],
                    instructions="展开逐页内容",
                )
            self.assertEqual(caught.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED")
            self.assertEqual(kernel.load(), before)
            self.assertEqual(tuple(kernel.events_root.iterdir()), events_before)
            self.assertEqual(tuple(kernel.artifacts.objects_root.rglob("*")), objects_before)

            framework_ref, confirmation_ref, authorization_ref = (
                _save_confirm_authorize(kernel, mission_confirmation_ref)
            )
            _ref, _task, authorized = command.request_agent_action(
                "full-deck-authorized", kernel.load().revision,
                action_type="build-presales-strategy", target_refs=[target],
                instructions="展开逐页内容",
            )
            context_ref = authorized.artifact_heads[
                f"agent/context/{hashlib.sha256(b'full-deck-authorized').hexdigest()}"
            ]
            context = kernel.artifacts.resolve(ArtifactReference.parse(context_ref))["payload"]
            self.assertEqual(context["layers"]["content_workflow"], {
                "framework_ref": framework_ref,
                "framework_confirmation_ref": confirmation_ref,
                "full_deck_expansion_authorization_ref": authorization_ref,
                "review_batch_ref": "", "batch_revision_plan_ref": "",
                "batch_plan_confirmation_ref": "",
            })

            for batch_action in (
                "propose-content-batch-revision-plan",
                "apply-content-batch-revision",
            ):
                before_batch = kernel.load()
                events_before_batch = tuple(kernel.events_root.iterdir())
                objects_before_batch = tuple(
                    kernel.artifacts.objects_root.rglob("*")
                )
                with self.subTest(action=batch_action):
                    with self.assertRaises(
                        ContentWorkflowError
                    ) as batch_error:
                        command.request_agent_action(
                            f"registered-but-unavailable:{batch_action}",
                            before_batch.revision,
                            action_type=batch_action,
                            target_refs=[target],
                            instructions="后续批次合同尚未实现",
                        )
                self.assertEqual(
                    batch_error.exception.code, "CONTENT_REVIEW_CONFLICT"
                )
                self.assertEqual(kernel.load(), before_batch)
                self.assertEqual(
                    tuple(kernel.events_root.iterdir()), events_before_batch
                )
                self.assertEqual(
                    tuple(kernel.artifacts.objects_root.rglob("*")),
                    objects_before_batch,
                )

            _expand_ref, expand_task, _expand_state = (
                command.request_agent_action(
                    "expand-authorized-blueprint", kernel.load().revision,
                    action_type="expand-full-content-blueprint",
                    target_refs=[target], instructions="按已授权框架展开全篇",
                )
            )
            self.assertEqual(
                expand_task["role_id"], "deck-narrative-architect"
            )

            FrameworkDiscussionService(kernel).save_draft(
                "replacement-framework", kernel.load().revision,
                _framework_payload(mission_confirmation_ref, 2),
            )
            with self.assertRaises(ContentWorkflowError) as stale:
                command.request_agent_action(
                    "full-deck-stale", kernel.load().revision,
                    action_type="build-slide-draft-set", target_refs=[target],
                    instructions="不应放行",
                )
            self.assertEqual(stale.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED")

    def test_expand_full_blueprint_is_registered_but_requires_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("expand gate")
            content = ContentService(kernel)
            mission_ref = content.save_mission_draft(
                "mission", 1, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                },
            )
            content.confirm_mission(
                "confirm", 2, mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://expand", user_message_ref="",
            )
            target = kernel.load().artifact_heads["project/manifest"]
            before = kernel.load()
            with self.assertRaises(ContentWorkflowError) as caught:
                ProjectCommandService(kernel).request_agent_action(
                    "expand-too-early", before.revision,
                    action_type="expand-full-content-blueprint",
                    target_refs=[target], instructions="不应放行",
                )
            self.assertEqual(
                caught.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED"
            )
            self.assertEqual(kernel.load(), before)

    def test_framework_action_rejects_formal_or_unknown_content_targets_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("framework targets")
            content = ContentService(kernel)
            mission_ref = content.save_mission_draft(
                "mission", 1, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                },
            )
            content.confirm_mission(
                "confirm", 2, mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://framework-targets",
                user_message_ref="",
            )
            forbidden = str(kernel.artifacts.put(
                "slide-draft-set", {"slides": ["formal-page"]}
            ))
            unknown = str(kernel.artifacts.put(
                "content-blueprint", {"pages": ["formal-page"]}
            ))
            commands = ProjectCommandService(kernel)
            for target in (forbidden, unknown):
                before = kernel.load()
                events_before = tuple(kernel.events_root.iterdir())
                with self.subTest(target=target):
                    with self.assertRaises(ContentWorkflowError) as caught:
                        commands.request_agent_action(
                            f"reject-target:{target[-8:]}", before.revision,
                            action_type="build-content-framework",
                            target_refs=[target], instructions="不应泄露逐页内容",
                        )
                self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")
                self.assertEqual(kernel.load(), before)
                self.assertEqual(tuple(kernel.events_root.iterdir()), events_before)

    def test_identical_framework_reset_cannot_replay_old_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("identical reset")
            content = ContentService(kernel)
            mission_ref = content.save_mission_draft(
                "mission", 1, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                },
            )
            mission_confirmation = content.confirm_mission(
                "confirm", 2, mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://identical-reset",
                user_message_ref="",
            )
            framework_ref, confirmation_ref, authorization_ref = (
                _save_confirm_authorize(kernel, mission_confirmation)
            )
            confirmation_payload = kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            authorization_payload = kernel.artifacts.resolve(
                ArtifactReference.parse(authorization_ref)
            )["payload"]
            same_ref, _ = FrameworkDiscussionService(kernel).save_draft(
                "identical-framework-reset", kernel.load().revision,
                _framework_payload(mission_confirmation),
            )
            self.assertEqual(same_ref, framework_ref)
            kernel.commit(
                command_id="restore-old-confirmation-heads",
                expected_revision=kernel.load().revision,
                event_type="test.restore-old-confirmation-heads",
                artifact_updates={
                    "content/framework-confirmation": (
                        "content-framework-confirmation", confirmation_payload
                    ),
                    "content/full-deck-expansion-authorization": (
                        "full-deck-expansion-authorization", authorization_payload
                    ),
                },
            )
            before = kernel.load()
            with self.assertRaises(ContentWorkflowError) as caught:
                ProjectCommandService(kernel).request_agent_action(
                    "replayed-old-authorization", before.revision,
                    action_type="build-presales-strategy",
                    target_refs=[kernel.load().artifact_heads["project/manifest"]],
                    instructions="不应放行",
                )
            self.assertEqual(
                caught.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED"
            )
            self.assertEqual(kernel.load(), before)

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
                    "action_type": "build-content-framework",
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
            mission_confirmation_ref = kernel.load().artifact_heads[
                "mission/confirmation"
            ]
            _save_confirm_authorize(kernel, mission_confirmation_ref)
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": project_root,
                    "expected_revision": 7,
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
                    "expected_revision": 8,
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
            self.assertEqual(committed["snapshot"]["revision"], 10)
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
            mission_confirmation_ref = kernel.load().artifact_heads[
                "mission/confirmation"
            ]
            _save_confirm_authorize(kernel, mission_confirmation_ref)

            strategy_ref = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": project_root,
                    "expected_revision": 7,
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
                    "expected_revision": 8,
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
                    "expected_revision": 9,
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
                    "expected_revision": 10,
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
            mission_confirmation_ref = content.confirm_mission(
                "reviewers:confirm",
                3,
                mission_draft_ref=mission_ref,
                material_mode="materials-provided",
                material_inventory_ref=materials_ref,
                user_action_ref="test-user-action://reviewer-binding-contract",
                user_message_ref="",
            )
            _save_confirm_authorize(kernel, mission_confirmation_ref)
            target_ref = kernel.load().artifact_heads["project/manifest"]
            actions = {
                "review-content-presales": "presales-content-reviewer",
                "review-content-decision-maker": "audience-decision-reviewer",
                "review-content-evidence": "content-fact-checker",
                "review-content-narrative": "argument-logic-reviewer",
                "review-content-editorial": "reading-experience-reviewer",
            }

            revision = 7
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
