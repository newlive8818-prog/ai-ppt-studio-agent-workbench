from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.project_service import ProjectCommandService, ProjectService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
    WorkbenchValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v22_visual_review_service import seed_visual_review
from tests.v16_visual_fixtures import prepared_g1_anchor


def make_project(base: Path):
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    return ProjectService(config).create_project("v23-presentations-handoff")


class V23PresentationsHandoffTests(unittest.TestCase):
    VISUAL_HANDOFF_FIELDS = {
        "task_id",
        "handoff_version",
        "compiler_version",
        "visual_compilation_plan_ref",
        "reading_blueprint_ref",
        "visual_brief_ref",
        "deck_design_system_ref",
        "visual_contract_set_ref",
        "release_target_policy_ref",
        "source_version",
        "source_revision",
        "reading_blueprint",
        "visual_brief",
        "deck_design_system",
        "slide_visual_contracts",
        "compilation_slides",
        "required_target_ids",
        "deferred_target_ids",
        "output_paths",
        "result_expected_revision",
        "authorization_scope",
        "authoring_contract",
        "evidence_contract",
    }

    def test_anchor_slide_set_is_bound_to_the_current_compilation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, _revision, refs = prepared_g1_anchor(Path(temp), slide_count=3)
            state = visual.kernel.load()
            anchor = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(refs["anchors"])
            )["payload"]
            self.assertEqual(
                anchor["visual_compilation_plan_ref"],
                state.artifact_heads["visual/compilation-plan"],
            )

    def test_anchor_registration_rejects_missing_or_unresolvable_plan_ref(self) -> None:
        for value in (None, "artifact://visual-compilation-plan/" + "0" * 64):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                visual, revision, refs = prepared_g1_anchor(Path(temp), slide_count=3)
                anchor = copy.deepcopy(
                    visual.kernel.artifacts.resolve(
                        ArtifactReference.parse(refs["anchors"])
                    )["payload"]
                )
                if value is None:
                    anchor.pop("visual_compilation_plan_ref", None)
                else:
                    anchor["visual_compilation_plan_ref"] = value
                with self.assertRaises(
                    (
                        ArtifactReferenceError,
                        ContractValidationError,
                        WorkbenchValidationError,
                    )
                ):
                    visual.register_anchor_set(
                        f"invalid-anchor-{str(value)[:8]}",
                        revision,
                        anchor,
                    )

    def test_g2_rejects_an_anchor_bound_to_a_different_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            kernel = ProjectKernel.initialize(Path(temp), project_id="v23-g2-anchor-plan")
            _design_ref, anchor_ref, _contract_ref, _session_ref, _session, state = seed_visual_review(kernel)
            anchor = copy.deepcopy(
                kernel.artifacts.resolve(ArtifactReference.parse(anchor_ref))["payload"]
            )
            wrong_plan_ref = str(
                kernel.artifacts.put(
                    "visual-compilation-plan",
                    {"artifact_type": "visual-compilation-plan", "identity": "wrong-plan"},
                )
            )
            anchor["visual_compilation_plan_ref"] = wrong_plan_ref
            kernel.commit(
                command_id="v23-forge-anchor-plan",
                expected_revision=state.revision,
                event_type="test.v23-forge-anchor-plan",
                artifact_updates={"visual/anchors": ("anchor-slide-set", anchor)},
            )
            with self.assertRaises(GateBlockedError) as error:
                GateEvaluator(kernel).validate_current_g2_evidence()
            self.assertTrue(
                {
                    "anchor-compilation-plan-mismatch",
                    "visual-compilation-plan-missing-or-stale",
                }.intersection(error.exception.missing_evidence)
            )

    def test_image2_requires_the_current_plan_not_only_native_first_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g1_anchor(Path(temp), slide_count=3)
            state = visual.kernel.load()
            visual.kernel.commit(
                command_id="v23-remove-plan-before-image2",
                expected_revision=state.revision,
                event_type="test.v23-remove-plan-before-image2",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            with self.assertRaises(WorkbenchValidationError):
                ContextCompiler(visual.kernel).compile_role_task(
                    role_id="image-asset-producer",
                    task_type="generate-image-assets",
                    project_revision=revision + 1,
                    target_refs=[],
                    instructions="",
                )

    def test_build_native_first_accepts_only_the_exact_current_plan_target(self) -> None:
        invalid_target_builder = (
            lambda refs: [],
            lambda refs: [refs["contracts"]],
            lambda refs: [refs["plan"], refs["contracts"]],
            lambda refs: [refs["old_plan"]],
        )
        for index, build_targets in enumerate(invalid_target_builder):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
                current_plan_ref = visual.kernel.load().artifact_heads[
                    "visual/compilation-plan"
                ]
                old_plan_ref = str(
                    visual.kernel.artifacts.put(
                        "visual-compilation-plan", {"identity": "old-plan"}
                    )
                )
                target_refs = build_targets(
                    {**refs, "plan": current_plan_ref, "old_plan": old_plan_ref}
                )
                with self.assertRaisesRegex(
                    (ArtifactReferenceError, ContractValidationError),
                    "build-native-first requires the exact current visual compilation plan",
                ):
                    dispatch_v16(
                        {
                            "operation": "request-agent-action",
                            "project_root": str(project),
                            "expected_revision": revision,
                            "command_id": f"v23-invalid-native-first-{index}",
                            "action_type": "build-native-first",
                            "target_refs": target_refs,
                            "instructions": "只构建当前三页锚点。",
                        }
                    )
                self.assertEqual(visual.kernel.load().revision, revision)
                self.assertNotIn("agent/task/active", visual.kernel.load().artifact_heads)

    def test_native_anchor_set_cannot_be_committed_without_its_agent_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            before = visual.kernel.load()
            before_events = tuple(visual.kernel.events_root.iterdir())
            with self.assertRaisesRegex(
                ContractValidationError,
                "native-anchor-set requires its build-native-first task_id",
            ):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision,
                        "command_id": "v23-taskless-native-anchor-set",
                        "kind": "native-anchor-set",
                        "payload": anchor,
                    }
                )
            after = visual.kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.artifact_heads, before.artifact_heads)
            self.assertEqual(tuple(visual.kernel.events_root.iterdir()), before_events)

    def test_build_native_first_task_retains_one_current_plan_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g1_anchor(project, slide_count=3)
            current_plan_ref = visual.kernel.load().artifact_heads[
                "visual/compilation-plan"
            ]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-valid-native-first",
                    "action_type": "build-native-first",
                    "target_refs": [current_plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            self.assertEqual(requested["task"]["target_refs"], [current_plan_ref])

    def test_build_native_first_result_preflight_rejects_a_removed_current_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            current_plan_ref = visual.kernel.load().artifact_heads[
                "visual/compilation-plan"
            ]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-stale-native-first-task",
                    "action_type": "build-native-first",
                    "target_refs": [current_plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            task_id = requested["task"]["task_id"]
            before = visual.kernel.load()
            visual.kernel.commit(
                command_id="v23-remove-plan-after-native-first-task",
                expected_revision=before.revision,
                event_type="test.v23-remove-plan-after-native-first-task",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=task_id,
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=before.revision + 1,
                )

    def test_build_native_first_result_preflight_rejects_a_payload_plan_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            current_plan_ref = visual.kernel.load().artifact_heads[
                "visual/compilation-plan"
            ]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-mismatch-native-first-task",
                    "action_type": "build-native-first",
                    "target_refs": [current_plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            task_id = requested["task"]["task_id"]
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            anchor["visual_compilation_plan_ref"] = str(
                visual.kernel.artifacts.put(
                    "visual-compilation-plan", {"identity": "wrong-plan"}
                )
            )
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=task_id,
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=revision + 1,
                )

    def test_build_native_first_context_contains_a_closed_visual_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-context-handoff",
                    "action_type": "build-native-first",
                    "target_refs": [plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            task = requested["task"]
            context = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(task["context_pack_ref"])
            )["payload"]
            handoff = context["layers"]["visual_handoff"]
            self.assertEqual(set(handoff), self.VISUAL_HANDOFF_FIELDS)
            self.assertEqual(handoff["task_id"], task["task_id"])
            self.assertRegex(handoff["task_id"], re.compile(r"^[0-9a-f]{64}$"))
            self.assertEqual(
                handoff["visual_compilation_plan_ref"], plan_ref
            )
            self.assertEqual(
                handoff["result_expected_revision"], revision + 1
            )
            self.assertEqual(
                handoff["authorization_scope"],
                {
                    "action_type": "build-native-first",
                    "allowed_result_kind": "native-anchor-set",
                    "required_anchor_count": 3,
                    "authorizing_gate": "G1-passed",
                    "whole_deck_build_forbidden": True,
                    "gate_advance_forbidden": True,
                },
            )
            self.assertEqual(
                handoff["authoring_contract"],
                {
                    "pptx_tool": "Codex Presentations only",
                    "implementation": "@oai/artifact-tool JavaScript ES module",
                    "semantic_objects_native": True,
                    "whole_slide_bitmap_forbidden": True,
                    "baked_factual_text_forbidden": True,
                    "connectors_before_nodes": True,
                    "separate_replaceable_image_layers": True,
                    "target_application": "macos-powerpoint",
                    "source_notes": "[Sources] blocks required in speaker notes",
                },
            )
            self.assertEqual(
                handoff["evidence_contract"],
                {
                    "render_every_slide": True,
                    "inspect_every_slide_full_size": True,
                    "montage_is_rhythm_only": True,
                    "overflow_check_required": True,
                    "editability_check_required": True,
                    "target_powerpoint_check_separate": True,
                    "user_visual_judgment_separate": True,
                },
            )
            output_paths = handoff["output_paths"]
            for path_value in output_paths.values():
                output = Path(path_value)
                self.assertTrue(output.is_absolute())
                self.assertEqual(output, output.resolve())
                self.assertTrue(output.is_relative_to(project.resolve()))
                self.assertIn(task["task_id"], output.parts)
                self.assertFalse(output.exists())
            def assert_no_forbidden_key(value: object) -> None:
                if isinstance(value, dict):
                    for key, nested in value.items():
                        self.assertNotIn(
                            key,
                            {
                                "visible_copy_blocks",
                                "speaker_notes",
                                "facts",
                                "data",
                                "source_text",
                                "core_claim",
                                "page_title",
                                "slide_order",
                            },
                        )
                        assert_no_forbidden_key(nested)
                elif isinstance(value, list):
                    for nested in value:
                        assert_no_forbidden_key(nested)

            assert_no_forbidden_key(handoff)

    def test_build_native_first_context_rejects_missing_current_plan_before_task_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            state = visual.kernel.load()
            visual.kernel.commit(
                command_id="v23-remove-plan-before-context",
                expected_revision=state.revision,
                event_type="test.v23-remove-plan-before-context",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            with self.assertRaises(WorkbenchValidationError):
                ContextCompiler(visual.kernel).compile_role_task(
                    role_id="native-first-engineer",
                    task_type="build-native-first",
                    project_revision=revision + 1,
                    target_refs=[plan_ref],
                    instructions="只构建当前三页锚点。",
                    task_id="a" * 64,
                )

    def test_build_native_first_handoff_source_revision_survives_unrelated_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            first = ContextCompiler(visual.kernel).compile_role_task(
                role_id="native-first-engineer",
                task_type="build-native-first",
                project_revision=revision,
                target_refs=[plan_ref],
                instructions="只构建当前三页锚点。",
                task_id="b" * 64,
            )
            source_revision = first["layers"]["visual_handoff"]["source_revision"]
            visual.kernel.commit(
                command_id="v23-unrelated-after-handoff",
                expected_revision=revision,
                event_type="test.v23-unrelated-after-handoff",
                artifact_updates={"unrelated": ("probe", {"identity": "unrelated"})},
            )
            second = ContextCompiler(visual.kernel).compile_role_task(
                role_id="native-first-engineer",
                task_type="build-native-first",
                project_revision=revision + 1,
                target_refs=[plan_ref],
                instructions="只构建当前三页锚点。",
                task_id="c" * 64,
            )
            self.assertEqual(
                second["layers"]["visual_handoff"]["source_revision"],
                source_revision,
            )

    def test_build_native_first_handoff_rejects_malformed_task_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            with self.assertRaises(WorkbenchValidationError):
                ContextCompiler(visual.kernel).compile_role_task(
                    role_id="native-first-engineer",
                    task_type="build-native-first",
                    project_revision=revision,
                    target_refs=[plan_ref],
                    instructions="只构建当前三页锚点。",
                    task_id="not-a-task-id",
                )

    def test_build_native_first_result_preflight_rejects_context_handoff_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-context-identity-drift",
                    "action_type": "build-native-first",
                    "target_refs": [plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            task_id = requested["task"]["task_id"]
            task_ref = visual.kernel.load().artifact_heads[f"agent/task/{task_id}"]
            task = copy.deepcopy(
                visual.kernel.artifacts.resolve(ArtifactReference.parse(task_ref))["payload"]
            )
            context = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(task["context_pack_ref"])
                )["payload"]
            )
            context["layers"]["visual_handoff"]["task_id"] = "d" * 64
            forged_context_ref = str(
                visual.kernel.artifacts.put("context-pack", context)
            )
            task["context_pack_ref"] = forged_context_ref
            state = visual.kernel.load()
            visual.kernel.commit(
                command_id="v23-forge-context-handoff-identity",
                expected_revision=state.revision,
                event_type="test.v23-forge-context-handoff-identity",
                artifact_updates={
                    "agent/context/" + task_id: ("context-pack", context),
                    "agent/task/active": ("agent-task", task),
                    "agent/task/" + task_id: ("agent-task", task),
                },
            )
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=task_id,
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=state.revision + 1,
                )

    def test_build_native_first_result_preflight_rejects_protocol_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-protocol-version-drift",
                    "action_type": "build-native-first",
                    "target_refs": [plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            with patch(
                "ai_ppt_studio.context_compiler.COMPILER_VERSION",
                "visual-semantic-compiler/v2",
            ), self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=requested["task"]["task_id"],
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=revision + 1,
                )

    def test_build_native_first_result_preflight_rejects_handoff_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-handoff-contract-drift",
                    "action_type": "build-native-first",
                    "target_refs": [plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            task_id = requested["task"]["task_id"]
            task_ref = visual.kernel.load().artifact_heads[f"agent/task/{task_id}"]
            task = copy.deepcopy(
                visual.kernel.artifacts.resolve(ArtifactReference.parse(task_ref))["payload"]
            )
            context = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(task["context_pack_ref"])
                )["payload"]
            )
            context["layers"]["visual_handoff"]["authorization_scope"][
                "whole_deck_build_forbidden"
            ] = False
            state = visual.kernel.load()
            context["layers"]["visual_handoff"]["result_expected_revision"] = (
                state.revision + 1
            )
            forged_context_ref = str(visual.kernel.artifacts.put("context-pack", context))
            task["context_pack_ref"] = forged_context_ref
            visual.kernel.commit(
                command_id="v23-forge-handoff-contract",
                expected_revision=state.revision,
                event_type="test.v23-forge-handoff-contract",
                artifact_updates={
                    f"agent/context/{task_id}": ("context-pack", context),
                    "agent/task/active": ("agent-task", task),
                    f"agent/task/{task_id}": ("agent-task", task),
                },
            )
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=task_id,
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=state.revision + 1,
                )

    def test_build_native_first_result_preflight_rechecks_output_path_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            plan_ref = visual.kernel.load().artifact_heads["visual/compilation-plan"]
            requested = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": "v23-output-path-symlink-drift",
                    "action_type": "build-native-first",
                    "target_refs": [plan_ref],
                    "instructions": "只构建当前三页锚点。",
                }
            )["result"]
            anchors_root = project / "delivery" / "anchors"
            anchors_root.parent.mkdir(parents=True, exist_ok=True)
            anchors_root.symlink_to(Path(outside), target_is_directory=True)
            anchor = copy.deepcopy(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["anchors"])
                )["payload"]
            )
            with self.assertRaises(ContractValidationError):
                ProjectCommandService(visual.kernel).preflight_noncontent_agent_result(
                    task_id=requested["task"]["task_id"],
                    request_kind="native-anchor-set",
                    payload=anchor,
                    expected_revision=revision + 1,
                )

    def test_image_asset_write_rejects_missing_current_compilation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g1_anchor(project, slide_count=3)
            visual.kernel.commit(
                command_id="v23-remove-plan-before-image-write",
                expected_revision=revision,
                event_type="test.v23-remove-plan-before-image-write",
                artifact_updates={},
                artifact_removals=("visual/compilation-plan",),
            )
            before = visual.kernel.load()
            before_events = tuple(visual.kernel.events_root.iterdir())
            with self.assertRaises(ContractValidationError):
                visual.register_image_asset_pack(
                    "v23-image-write-without-plan",
                    before.revision,
                    {
                        "anchor_slide_set_ref": refs["anchors"],
                        "asset_kind": "non-semantic",
                        "independent_layers": True,
                        "contains_text": False,
                        "contains_numbers": False,
                        "contains_business_relationships": False,
                        "simulates_real_evidence": False,
                        "whole_slide_master": False,
                    },
                )
            after = visual.kernel.load()
            self.assertEqual(after.revision, before.revision)
            self.assertNotIn("visual/image-assets", after.artifact_heads)
            self.assertEqual(tuple(visual.kernel.events_root.iterdir()), before_events)


if __name__ == "__main__":
    unittest.main()
