from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_service import (
    ACTION_ROLES,
    NONCONTENT_RESULT_CONTRACTS,
    ProjectService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    MissionNotConfirmedError,
    ProjectNotFoundError,
    ReviewSourceStaleError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.role_registry import RoleRegistry
from ai_ppt_studio.workbench_bridge import dispatch
from tests.test_v16_content_page_decisions import (
    accepted_v22_review,
    authority_snapshot_v22,
)
from tests.test_v22_content_repair_loop import build_content as build_v22_content
from tests.test_v22_content_contracts import (
    blueprint as v22_blueprint,
    decision_context as v22_decision_context,
    evidence_book as v22_evidence_book,
    fit_map as v22_fit_map,
)
from tests.v16_visual_fixtures import confirmed_g0, valid_visual_brief


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
    def test_framework_action_precedes_full_deck_authorization_and_rejection_is_write_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("framework gate")
            command = ProjectCommandService(kernel)
            target = kernel.load().artifact_heads["project/manifest"]
            before = authority_snapshot_v22(kernel)
            for action in (
                "build-content-framework",
                "build-presales-strategy",
                "expand-full-content-blueprint",
                "build-slide-draft-set",
            ):
                with self.subTest(action=action), self.assertRaises(
                    ContractValidationError
                ):
                    command.request_agent_action(
                        f"removed:{action}",
                        kernel.load().revision,
                        action_type=action,
                        target_refs=[target],
                        instructions="旧内容动作不得恢复",
                    )
                self.assertEqual(authority_snapshot_v22(kernel), before)
            blueprint_ref = build_v22_content(kernel)
            self.assertEqual(
                kernel.load().artifact_heads["content/reading-blueprint"],
                blueprint_ref,
            )

    def test_content_action_requires_exact_current_policy_targets_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("exact targets")
            commands = ProjectCommandService(kernel)
            manifest_ref = kernel.load().artifact_heads["project/manifest"]
            detached = str(
                kernel.artifacts.put("project-manifest", {"name": "detached"})
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ArtifactReferenceError):
                commands.request_agent_action(
                    "invalid-detached-target",
                    kernel.load().revision,
                    action_type="review-visual-aesthetic",
                    target_refs=[detached],
                    instructions="只允许当前 head",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            _task_ref, task, _state = commands.request_agent_action(
                "valid-exact-target",
                kernel.load().revision,
                action_type="review-visual-aesthetic",
                target_refs=[manifest_ref],
                instructions="审查当前目标",
            )
            self.assertEqual(task["target_refs"], [manifest_ref])

    def test_expand_full_blueprint_is_registered_but_requires_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("expand gate")
            target = kernel.load().artifact_heads["project/manifest"]
            before = authority_snapshot_v22(kernel)
            self.assertNotIn("expand-full-content-blueprint", ACTION_ROLES)
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(kernel).request_agent_action(
                    "removed-expand",
                    kernel.load().revision,
                    action_type="expand-full-content-blueprint",
                    target_refs=[target], instructions="不应放行",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)

    def test_framework_action_rejects_formal_or_unknown_content_targets_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("framework targets")
            commands = ProjectCommandService(kernel)
            target = kernel.load().artifact_heads["project/manifest"]
            before = authority_snapshot_v22(kernel)
            for action in (
                "build-content-framework",
                "build-presales-strategy",
                "build-slide-draft-set",
            ):
                with self.subTest(action=action), self.assertRaises(
                    ContractValidationError
                ):
                    commands.request_agent_action(
                        f"reject-action:{action}",
                        kernel.load().revision,
                        action_type=action,
                        target_refs=[target],
                        instructions="不得恢复旧内容动作",
                    )
                self.assertEqual(authority_snapshot_v22(kernel), before)

    def test_identical_framework_reset_cannot_replay_old_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("identical reset")
            first_ref, old_session_ref, old_session, _state = accepted_v22_review(
                kernel
            )
            second_ref = build_v22_content(kernel, "content-v2")
            self.assertNotEqual(second_ref, first_ref)
            state = kernel.load()
            self.assertNotIn("content/gate/evidence", state.artifact_heads)
            self.assertNotIn("content/gate/presales-reading", state.artifact_heads)
            self.assertNotIn("content/acceptance", state.artifact_heads)
            self.assertNotIn("review/session/content-full-deck", state.artifact_heads)
            self.assertEqual(
                kernel.artifacts.resolve(ArtifactReference.parse(old_session_ref))[
                    "payload"
                ],
                old_session,
            )
            with self.assertRaises(ReviewSourceStaleError):
                ReviewSessionService(kernel).open_or_resume(
                    command_id="replay-old-session",
                    expected_revision=state.revision,
                    review_type="content-full-deck",
                    target_artifact_ref=first_ref,
                    source_version="content-v1",
                    source_revision=state.revision,
                    open_policy="foreground-if-waiting",
                )

    def test_missing_latest_framework_reset_event_cannot_reenable_old_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("missing reset event")
            latest_event = kernel.events_root / f"r{kernel.load().revision:08d}.json"
            original = latest_event.read_bytes()
            event = json.loads(original)
            event["revision"] += 1
            latest_event.write_text(json.dumps(event), encoding="utf-8")
            before = authority_snapshot_v22(kernel)
            try:
                with self.assertRaises(ContractValidationError):
                    ProjectCommandService(kernel).request_agent_action(
                        "event-gap-action",
                        kernel.load().revision,
                        action_type="review-visual-aesthetic",
                        target_refs=[kernel.load().artifact_heads["project/manifest"]],
                        instructions="事务回执损坏时不得写入",
                    )
                self.assertEqual(authority_snapshot_v22(kernel), before)
            finally:
                latest_event.write_bytes(original)

    def test_old_confirmation_plus_fresh_authorization_cannot_bypass_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("fresh auth stale confirmation")
            content = MissionMaterialService(kernel)
            mission_ref = content.save_mission_draft(
                "mission", 1, {
                    "topic": "经营一体化", "primary_audience": "决策者",
                    "desired_judgment_or_action": "批准一期",
                },
            )
            content.confirm_mission(
                "confirm", 2, mission_draft_ref=mission_ref,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://fresh-auth", user_message_ref="",
            )
            self.assertEqual(
                MissionReadinessPolicy(kernel).require_ready().mission_draft_ref,
                mission_ref,
            )
            content.save_mission_draft(
                "replacement-mission",
                kernel.load().revision,
                {
                    "topic": "经营一体化",
                    "primary_audience": "客户经营与数字化决策团队",
                    "desired_judgment_or_action": "批准一期验证",
                },
            )
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(MissionNotConfirmedError):
                MissionReadinessPolicy(kernel).require_ready()
            self.assertEqual(authority_snapshot_v22(kernel), before)

    def test_new_project_binds_manifest_and_release_policy_in_revision_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))

            kernel = ProjectService(config).create_project(
                "Policy test", project_id="policy-test"
            )
            state = kernel.load()

            self.assertEqual(state.revision, 1)
            self.assertTrue(
                state.artifact_heads["project/manifest"].startswith(
                    "artifact://project-manifest/"
                )
            )
            policy_ref = state.artifact_heads["release/target-policy"]
            self.assertTrue(policy_ref.startswith("artifact://release-target-policy/"))
            policy = kernel.artifacts.resolve(ArtifactReference.parse(policy_ref))
            self.assertEqual(policy["payload"]["required_target_ids"], ["macos-powerpoint"])

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
            ProjectKernel.initialize(external, project_id="outside")

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
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": project_root,
                        "expected_revision": 1,
                        "kind": "mission",
                        "payload": {"topic": "禁止通用写入"},
                    }
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            mission = dispatch_v16(
                {
                    "operation": "save-mission-draft",
                    "project_root": project_root,
                    "expected_revision": 1,
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
            self.assertNotIn("workspace", material["snapshot"])

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
            self.assertEqual(confirmation["snapshot"]["contentMode"], "material-backed")

            task = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": project_root,
                    "expected_revision": 4,
                    "action_type": "review-visual-aesthetic",
                    "target_refs": [kernel.load().artifact_heads["project/manifest"]],
                    "instructions": "仅创建当前视觉审查任务。",
                }
            )["result"]
            task_ref = task["artifact_ref"]
            self.assertTrue(task_ref.startswith("artifact://agent-task/"))
            self.assertEqual(task["task"]["role_id"], "visual-aesthetic-reviewer")
            context_ref = task["task"]["context_pack_ref"]
            self.assertTrue(context_ref.startswith("artifact://context-pack/"))
            context = kernel.artifacts.resolve(
                ArtifactReference.parse(context_ref)
            )["payload"]
            self.assertEqual(context["schema_version"], "3.0")
            self.assertEqual(context["project_revision"], 4)
            self.assertEqual(
                context["layers"]["role_contract"]["role_id"],
                "visual-aesthetic-reviewer",
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
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "visual-task",
                    "action_type": "design-deck-system",
                    "target_refs": [blueprint_ref],
                    "instructions": "形成视觉方向。",
                }
            )["result"]
            task_id = requested["task"]["task_id"]
            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "command_id": "visual-task-result",
                    "expected_revision": revision + 1,
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )["result"]
            active_task_ref = committed["snapshot"]["artifacts"][
                "agent/task/active"
            ]
            active_task = content.kernel.artifacts.resolve(
                ArtifactReference.parse(active_task_ref)
            )["payload"]
            self.assertEqual(committed["snapshot"]["revision"], revision + 2)
            self.assertEqual(active_task["task_id"], task_id)
            self.assertEqual(active_task["status"], "completed")
            self.assertEqual(
                active_task["result_refs"], [committed["artifact_ref"]]
            )
            after = authority_snapshot_v22(content.kernel)
            retried = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "command_id": "visual-task-result",
                    "expected_revision": revision + 1,
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )["result"]
            self.assertEqual(retried, committed)
            self.assertEqual(authority_snapshot_v22(content.kernel), after)
            changed = valid_visual_brief(blueprint_ref)
            changed["design_proposition"] = "同一命令不得改写视觉命题"
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "command_id": "visual-task-result",
                        "expected_revision": revision + 1,
                        "kind": "visual-brief",
                        "task_id": task_id,
                        "payload": changed,
                    }
                )
            self.assertEqual(authority_snapshot_v22(content.kernel), after)

    def test_stale_agent_result_after_content_source_replacement_is_rejected_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "stale-v1-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "生成 v1 视觉方向",
            })["result"]
            task_id = requested["task"]["task_id"]
            build_v22_content(content.kernel, "content-v2")
            before = authority_snapshot_v22(content.kernel)
            self.assertNotIn("agent/task/active", before[0].artifact_heads)
            self.assertNotIn(f"agent/task/{task_id}", before[0].artifact_heads)
            with self.assertRaises(ContractValidationError):
                dispatch_v16({
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": content.kernel.load().revision,
                    "command_id": "commit-stale-v1-result",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                })
            self.assertEqual(authority_snapshot_v22(content.kernel), before)

    def test_content_action_requires_canonical_target_order_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("canonical targets")
            state = kernel.load()
            targets = [
                state.artifact_heads["release/target-policy"],
                state.artifact_heads["project/manifest"],
            ]
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(kernel).request_agent_action(
                    "duplicate-targets",
                    state.revision,
                    action_type="review-visual-aesthetic",
                    target_refs=[targets[0], targets[0]],
                    instructions="重复目标不得进入任务合同。",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)
            _ref, task, _state = ProjectCommandService(kernel).request_agent_action(
                "canonical-targets",
                state.revision,
                action_type="review-visual-aesthetic",
                target_refs=targets,
                instructions="保留调用方的精确目标顺序。",
            )
            self.assertEqual(task["target_refs"], targets)

    def test_content_task_result_type_and_task_id_are_mandatory_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "result-contract-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "形成视觉方向",
            })["result"]
            task_id = requested["task"]["task_id"]
            attempts = (
                {
                    "command_id": "wrong-task-id",
                    "kind": "visual-brief",
                    "task_id": "not-the-active-task",
                    "payload": valid_visual_brief(blueprint_ref),
                },
                {
                    "command_id": "visual-task-to-content",
                    "kind": "reading-deck-blueprint",
                    "task_id": task_id,
                    "payload": {"artifact_type": "reading-deck-blueprint"},
                },
                {
                    "command_id": "formal-content-without-task",
                    "kind": "reading-deck-blueprint",
                    "payload": {"artifact_type": "reading-deck-blueprint"},
                },
            )
            for attempt in attempts:
                before = authority_snapshot_v22(content.kernel)
                with self.subTest(command_id=attempt["command_id"]), self.assertRaises(
                    ContractValidationError
                ):
                    dispatch_v16({
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": content.kernel.load().revision,
                        **attempt,
                    })
                self.assertEqual(authority_snapshot_v22(content.kernel), before)

    def test_content_actions_without_direct_result_contract_fail_closed(self) -> None:
        self.assertEqual(set(ACTION_ROLES), set(NONCONTENT_RESULT_CONTRACTS))
        removed = {
            "build-content-framework",
            "build-presales-strategy",
            "expand-full-content-blueprint",
            "repair-content",
            "aggregate-content-reviews",
        }
        self.assertTrue(removed.isdisjoint(ACTION_ROLES))
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project("framework direct result")
            before = authority_snapshot_v22(kernel)
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(kernel).request_agent_action(
                    "removed-framework-action",
                    kernel.load().revision,
                    action_type="build-content-framework",
                    target_refs=[kernel.load().artifact_heads["project/manifest"]],
                    instructions="旧内容任务不得创建。",
                )
            self.assertEqual(authority_snapshot_v22(kernel), before)

    def test_atomic_content_result_rejects_reused_command_identity_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "active-result-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "形成视觉方向",
            })["result"]
            task_id = requested["task"]["task_id"]
            before = authority_snapshot_v22(content.kernel)
            with self.assertRaises(ContractValidationError):
                dispatch_v16({
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": content.kernel.load().revision,
                    "command_id": "active-result-task",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                })
            self.assertEqual(authority_snapshot_v22(content.kernel), before)
            active = content.kernel.artifacts.resolve(ArtifactReference.parse(
                content.kernel.load().artifact_heads["agent/task/active"]
            ))["payload"]
            self.assertEqual(active["status"], "queued")

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
                    "operation": "save-mission-draft",
                    "project_root": project_root,
                    "expected_revision": 1,
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
                    "material_type": "bytes",
                    "data_base64": __import__("base64").b64encode("五套系统彼此割裂。".encode()).decode(),
                    "filename": "source.txt",
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
            from tests.material_finding_fixtures import replace_refs
            source = kernel.artifacts.resolve(ArtifactReference.parse(material_ref))["payload"]["sources"][0]
            finding_ref = dispatch_v16({"operation": "add-material", "project_root": project_root,
                "expected_revision": kernel.load().revision, "material_type": "finding",
                "material_inventory_ref": material_ref, "source_id": source["source_id"],
                "source_sha256": source["sha256"], "source_location": {"kind": "whole-source"},
                "content_kind": "text", "exclusion_mode": "scope"})["result"]["artifact_ref"]
            evidence = replace_refs(v22_evidence_book(), finding_ref, "unused")
            evidence["mission_confirmation_ref"] = mission_confirmation_ref
            evidence["material_inventory_ref"] = material_ref
            evidence_ref = dispatch_v16(
                {
                    "operation": "build-presales-evidence-book",
                    "project_root": project_root,
                    "command_id": "build-evidence",
                    "expected_revision": kernel.load().revision,
                    "payload": evidence,
                }
            )["result"]["artifact_ref"]
            context = v22_decision_context()
            context["evidence_book_ref"] = evidence_ref
            context_ref = dispatch_v16(
                {
                    "operation": "build-customer-decision-context",
                    "project_root": project_root,
                    "command_id": "build-context",
                    "expected_revision": kernel.load().revision,
                    "payload": context,
                }
            )["result"]["artifact_ref"]
            mapping = replace_refs(v22_fit_map(), finding_ref, "unused")
            mapping["evidence_book_ref"] = evidence_ref
            mapping["decision_context_ref"] = context_ref
            mapping_ref = dispatch_v16(
                {
                    "operation": "build-problem-solution-fit",
                    "project_root": project_root,
                    "command_id": "build-fit",
                    "expected_revision": kernel.load().revision,
                    "payload": mapping,
                }
            )["result"]["artifact_ref"]
            deck = replace_refs(v22_blueprint(), finding_ref, "unused")
            deck.update(
                {
                    "project_id": kernel.project_id,
                    "evidence_book_ref": evidence_ref,
                    "decision_context_ref": context_ref,
                    "problem_solution_fit_ref": mapping_ref,
                }
            )
            deck_ref = dispatch_v16(
                {
                    "operation": "build-reading-deck-blueprint",
                    "project_root": project_root,
                    "command_id": "build-deck",
                    "expected_revision": kernel.load().revision,
                    "payload": deck,
                }
            )["result"]["artifact_ref"]
            state = kernel.load()
            self.assertEqual(
                [
                    state.artifact_heads["content/evidence-book"],
                    state.artifact_heads["content/decision-context"],
                    state.artifact_heads["content/problem-solution-fit"],
                    state.artifact_heads["content/reading-blueprint"],
                ],
                [evidence_ref, context_ref, mapping_ref, deck_ref],
            )

    def test_public_actions_bind_all_five_isolated_content_reviewers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _profile = runtime_config(base)
            kernel = ProjectService(config).create_project(
                "五角色内容审查", project_id="five-content-reviewers"
            )
            registry = RoleRegistry.default()
            self.assertEqual(
                {role.role_id for role in registry.by_group("content")},
                {
                    "presales-solution-chief",
                    "content-evidence-gate-reviewer",
                    "content-presales-reading-gate-reviewer",
                },
            )
            removed_actions = {
                "review-content-presales",
                "review-content-decision-maker",
                "review-content-evidence",
                "review-content-narrative",
                "review-content-editorial",
            }
            self.assertTrue(removed_actions.isdisjoint(ACTION_ROLES))
            current_reviewers = {
                "review-visual-aesthetic": "visual-aesthetic-reviewer",
                "review-visual-engineering": "visual-engineering-reviewer",
                "verify-target-render": "target-render-verifier",
            }
            target = kernel.load().artifact_heads["project/manifest"]
            for action, role_id in current_reviewers.items():
                _ref, task, _state = ProjectCommandService(kernel).request_agent_action(
                    f"task:{action}",
                    kernel.load().revision,
                    action_type=action,
                    target_refs=[target],
                    instructions="独立审查当前目标。",
                )
                self.assertEqual(task["role_id"], role_id)


if __name__ == "__main__":
    unittest.main()
