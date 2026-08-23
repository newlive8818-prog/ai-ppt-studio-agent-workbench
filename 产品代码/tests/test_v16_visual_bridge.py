from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v16_visual_fixtures import (
    confirmed_g0,
    passing_visual_review,
    prepared_g1_anchor,
    prepared_g2,
    prepared_visual_contracts,
    valid_visual_brief,
)
from tests.host_confirmation_fixtures import signed_gate_assertion


class V16VisualBridgeTests(unittest.TestCase):
    def test_concurrent_task_bound_visual_result_is_semantically_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "concurrent-visual-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "形成视觉方向。",
            })["result"]
            task_id = requested["task"]["task_id"]
            base = {
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "concurrent-visual-result",
                "kind": "visual-brief",
                "task_id": task_id,
            }
            barrier = threading.Barrier(2)

            def commit(payload: dict) -> tuple[str, str]:
                barrier.wait()
                try:
                    result = dispatch_v16({**base, "payload": payload})["result"]
                    return "success", result["artifact_ref"]
                except ContractValidationError:
                    return "conflict", ""

            changed = valid_visual_brief(blueprint_ref)
            changed["design_proposition"] = "并发竞争的另一语义"
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(
                    commit,
                    (valid_visual_brief(blueprint_ref), changed),
                ))
            self.assertEqual(sorted(status for status, _ in outcomes), [
                "conflict", "success"
            ])
            state = content.kernel.load()
            self.assertEqual(state.revision, revision + 2)
            task = content.kernel.artifacts.resolve(ArtifactReference.parse(
                state.artifact_heads[f"agent/task/{task_id}"]
            ))["payload"]
            winning_ref = next(ref for status, ref in outcomes if status == "success")
            self.assertEqual(task["result_refs"], [winning_ref])

    def test_task_bound_visual_result_completes_and_binds_the_agent_task(self) -> None:
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
                    "expected_revision": revision + 1,
                    "command_id": "visual-task-result",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )["result"]

            self.assertEqual(committed["snapshot"]["revision"], revision + 2)
            task_ref = committed["snapshot"]["artifacts"][f"agent/task/{task_id}"]
            task = content.kernel.artifacts.resolve(
                ArtifactReference.parse(task_ref)
            )["payload"]
            self.assertEqual(task["status"], "completed")
            self.assertEqual(task["result_refs"], [committed["artifact_ref"]])
            events = tuple(content.kernel.events_root.iterdir())
            retried = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision + 1,
                    "command_id": "visual-task-result",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )["result"]
            self.assertEqual(retried, committed)
            self.assertEqual(tuple(content.kernel.events_root.iterdir()), events)
            for forbidden_kind, forbidden_payload in (
                (
                    "mission",
                    {
                        "topic": "越权",
                        "primary_audience": "越权",
                        "desired_judgment_or_action": "越权",
                    },
                ),
                (
                    "material-findings",
                    {"artifact_type": "material-inventory", "sources": []},
                ),
                (
                    "content-blueprint",
                    {"artifact_type": "raw-feedback", "feedback": "越权"},
                ),
            ):
                with self.subTest(kind=forbidden_kind), self.assertRaises(
                    ContractValidationError
                ):
                    dispatch_v16(
                        {
                            "operation": "commit-artifact",
                            "project_root": str(project),
                            "expected_revision": revision + 1,
                            "command_id": f"forbidden-{forbidden_kind}",
                            "kind": forbidden_kind,
                            "task_id": task_id,
                            "payload": forbidden_payload,
                        }
                    )
                self.assertEqual(tuple(content.kernel.events_root.iterdir()), events)
            for wrong_visual_payload in (
                {
                    "artifact_type": "image-asset-pack",
                    "asset_kind": "decorative",
                },
                {
                    "artifact_type": "visual-review-record",
                    "stage": "G1",
                    "checks": [],
                },
            ):
                with self.subTest(payload=wrong_visual_payload), self.assertRaises(
                    ContractValidationError
                ):
                    dispatch_v16(
                        {
                            "operation": "commit-artifact",
                            "project_root": str(project),
                            "expected_revision": revision + 1,
                            "command_id": "wrong-shared-visual-contract",
                            "kind": "visual-contract",
                            "task_id": task_id,
                            "payload": wrong_visual_payload,
                        }
                    )
                self.assertEqual(tuple(content.kernel.events_root.iterdir()), events)
            changed = valid_visual_brief(blueprint_ref)
            changed["design_proposition"] = "同一命令不得改写视觉命题"
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision + 1,
                        "command_id": "visual-task-result",
                        "kind": "visual-brief",
                        "task_id": task_id,
                        "payload": changed,
                    }
                )
            self.assertEqual(tuple(content.kernel.events_root.iterdir()), events)

            newer = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision + 2,
                "command_id": "newer-visual-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "新的任务保持排队。",
            })["result"]
            newer_task_id = newer["task"]["task_id"]
            before_replay = content.kernel.load()
            replay_events = tuple(content.kernel.events_root.iterdir())
            replay_objects = tuple(content.kernel.artifacts.objects_root.rglob("*"))
            historical = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "visual-task-result",
                "kind": "visual-brief",
                "task_id": task_id,
                "payload": valid_visual_brief(blueprint_ref),
            })["result"]
            self.assertEqual(historical["artifact_ref"], committed["artifact_ref"])
            self.assertEqual(historical["snapshot"]["revision"], before_replay.revision)
            self.assertEqual(content.kernel.load(), before_replay)
            self.assertEqual(tuple(content.kernel.events_root.iterdir()), replay_events)
            self.assertEqual(
                tuple(content.kernel.artifacts.objects_root.rglob("*")),
                replay_objects,
            )
            active = content.kernel.artifacts.resolve(ArtifactReference.parse(
                before_replay.artifact_heads["agent/task/active"]
            ))["payload"]
            self.assertEqual(active["task_id"], newer_task_id)
            self.assertEqual(active["status"], "queued")

            changed_historical = valid_visual_brief(blueprint_ref)
            changed_historical["design_proposition"] = "历史命令语义已改变"
            with self.assertRaises(ContractValidationError):
                dispatch_v16({
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision + 1,
                    "command_id": "visual-task-result",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": changed_historical,
                })
            self.assertEqual(content.kernel.load(), before_replay)
            self.assertEqual(tuple(content.kernel.events_root.iterdir()), replay_events)

            newer_payload = valid_visual_brief(blueprint_ref)
            newer_payload["design_proposition"] = "任务 B 已覆盖当前视觉简报 head"
            newer_result = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": before_replay.revision,
                "command_id": "newer-visual-result",
                "kind": "visual-brief",
                "task_id": newer_task_id,
                "payload": newer_payload,
            })["result"]
            after_newer_result = content.kernel.load()
            self.assertEqual(
                after_newer_result.artifact_heads["visual/brief"],
                newer_result["artifact_ref"],
            )
            completed_replay_events = tuple(content.kernel.events_root.iterdir())
            completed_replay_objects = tuple(
                content.kernel.artifacts.objects_root.rglob("*")
            )
            historical_after_supersession = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "visual-task-result",
                "kind": "visual-brief",
                "task_id": task_id,
                "payload": valid_visual_brief(blueprint_ref),
            })["result"]
            self.assertEqual(
                historical_after_supersession["artifact_ref"],
                committed["artifact_ref"],
            )
            self.assertEqual(content.kernel.load(), after_newer_result)
            self.assertEqual(
                content.kernel.load().artifact_heads["visual/brief"],
                newer_result["artifact_ref"],
            )
            self.assertEqual(
                tuple(content.kernel.events_root.iterdir()),
                completed_replay_events,
            )
            self.assertEqual(
                tuple(content.kernel.artifacts.objects_root.rglob("*")),
                completed_replay_objects,
            )
            active_completed = content.kernel.artifacts.resolve(
                ArtifactReference.parse(
                    after_newer_result.artifact_heads["agent/task/active"]
                )
            )["payload"]
            self.assertEqual(active_completed["task_id"], newer_task_id)
            self.assertEqual(active_completed["status"], "completed")
            with self.assertRaises(ContractValidationError):
                dispatch_v16({
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision + 1,
                    "command_id": "visual-task-result",
                    "kind": "visual-brief",
                    "task_id": task_id,
                    "payload": changed_historical,
                })
            self.assertEqual(content.kernel.load(), after_newer_result)
            self.assertEqual(
                tuple(content.kernel.events_root.iterdir()),
                completed_replay_events,
            )

    def test_task_bound_visual_result_failure_is_zero_write_and_task_stays_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            content, revision, blueprint_ref = confirmed_g0(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "atomic-visual-task",
                "action_type": "design-deck-system",
                "target_refs": [blueprint_ref],
                "instructions": "形成视觉方向。",
            })["result"]
            task_id = requested["task"]["task_id"]
            before = content.kernel.load()
            events = tuple(content.kernel.events_root.iterdir())
            objects = tuple(content.kernel.artifacts.objects_root.rglob("*"))
            real_commit = ProjectKernel.commit

            def fail_result_transaction(kernel: ProjectKernel, **kwargs):
                if kwargs.get("command_id") == "atomic-visual-result":
                    raise OSError("injected atomic result failure")
                return real_commit(kernel, **kwargs)

            with patch.object(ProjectKernel, "commit", fail_result_transaction):
                with self.assertRaisesRegex(OSError, "injected atomic result failure"):
                    dispatch_v16({
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": before.revision,
                        "command_id": "atomic-visual-result",
                        "kind": "visual-brief",
                        "task_id": task_id,
                        "payload": valid_visual_brief(blueprint_ref),
                    })

            self.assertEqual(content.kernel.load(), before)
            self.assertEqual(tuple(content.kernel.events_root.iterdir()), events)
            self.assertEqual(
                tuple(content.kernel.artifacts.objects_root.rglob("*")), objects
            )
            task = content.kernel.artifacts.resolve(ArtifactReference.parse(
                before.artifact_heads[f"agent/task/{task_id}"]
            ))["payload"]
            self.assertEqual(task["status"], "queued")
            self.assertNotIn("visual/brief", before.artifact_heads)

            retried = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": before.revision,
                "command_id": "atomic-visual-result",
                "kind": "visual-brief",
                "task_id": task_id,
                "payload": valid_visual_brief(blueprint_ref),
            })["result"]
            self.assertEqual(retried["snapshot"]["revision"], before.revision + 1)
            self.assertEqual(
                len(tuple(content.kernel.events_root.iterdir())), len(events) + 1
            )

    def test_visual_reviewer_task_cannot_write_the_other_reviewer_slot(self) -> None:
        cases = (
            (
                "review-visual-engineering", "engineering-review",
                "aesthetic", "visual-aesthetic-reviewer",
            ),
            (
                "review-visual-aesthetic", "aesthetic-review",
                "engineering", "visual-engineering-reviewer",
            ),
        )
        for action, label, wrong_kind, wrong_role in cases:
            with self.subTest(action=action), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                visual, revision, refs = prepared_g1_anchor(project, slide_count=2)
                requested = dispatch_v16({
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "command_id": f"{label}-task",
                    "action_type": action,
                    "target_refs": [str(refs["anchors"])],
                    "instructions": "独立检查当前视觉结果。",
                })["result"]
                before = visual.kernel.load()
                events = tuple(visual.kernel.events_root.iterdir())
                objects = tuple(visual.kernel.artifacts.objects_root.rglob("*"))
                payload = passing_visual_review(
                    str(refs["anchors"]),
                    stage="G2",
                    reviewer_kind=wrong_kind,
                    reviewer_role=wrong_role,
                )
                payload["artifact_type"] = "visual-review-record"
                with self.assertRaises(ContractValidationError):
                    dispatch_v16({
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision + 1,
                        "command_id": f"{label}-result",
                        "kind": "visual-contract",
                        "task_id": requested["task"]["task_id"],
                        "payload": payload,
                    })
                self.assertEqual(visual.kernel.load(), before)
                self.assertEqual(tuple(visual.kernel.events_root.iterdir()), events)
                self.assertEqual(
                    tuple(visual.kernel.artifacts.objects_root.rglob("*")), objects
                )
                task = visual.kernel.artifacts.resolve(ArtifactReference.parse(
                    before.artifact_heads["agent/task/active"]
                ))["payload"]
                self.assertEqual(task["status"], "queued")

    def test_public_agent_dispatch_freezes_visual_actions_after_g2_and_g3(self) -> None:
        visual_actions = (
            "design-deck-system",
            "design-slide-visuals",
            "build-native-first",
            "generate-image-assets",
            "review-visual-aesthetic",
            "review-visual-engineering",
            "verify-target-render",
        )
        for stage in ("G2-passed", "G3-user-reviewable"):
            for action in visual_actions:
                with (
                    self.subTest(stage=stage, action=action),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    project = Path(temp)
                    visual, revision, refs = prepared_g2(
                        project, slide_count=2
                    )
                    if stage == "G3-user-reviewable":
                        revision = visual.publish_visual_review(
                            "publish-visual-review", revision
                        ).revision
                    with self.assertRaises(GateBlockedError):
                        dispatch_v16(
                            {
                                "operation": "request-agent-action",
                                "project_root": str(project),
                                "expected_revision": revision,
                                "command_id": f"frozen-{stage}-{action}",
                                "action_type": action,
                                "target_refs": [refs["blueprint"]],
                                "instructions": "继续视觉生产。",
                            }
                        )
                    state = visual.kernel.load()
                    self.assertEqual(state.revision, revision)
                    self.assertNotIn("agent/task/active", state.artifact_heads)

    def test_existing_commit_and_internal_gate_operations_route_to_visual_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            _content, revision, blueprint_ref = confirmed_g0(project)
            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "kind": "visual-brief",
                    "payload": valid_visual_brief(blueprint_ref),
                }
            )
            self.assertIn(
                "visual/brief",
                committed["result"]["snapshot"]["artifacts"],
            )

        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_visual_contracts(project)
            convergence_ref = visual.register_convergence(
                "bridge-convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "视觉命题与页面家族已收敛",
                    "convergence_status": "passed",
                },
            )
            review_ref = visual.register_visual_review(
                "bridge-g1-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            passed = dispatch_v16(
                {
                    "operation": "record-internal-gate",
                    "project_root": str(project),
                    "expected_revision": revision + 2,
                    "gate": "G1",
                    "reviewer_role": "独立审美审查智能体",
                    "acceptance_record_refs": [convergence_ref, review_ref],
                }
            )
            self.assertEqual(
                passed["result"]["snapshot"]["gate_state"]["gates"]["G1"],
                "passed",
            )

    def test_visual_projection_marks_and_g3_use_existing_public_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, _refs = prepared_g2(project, slide_count=2)
            published = visual.publish_visual_review("bridge-publish", revision)
            source_version = published.artifact_heads["visual/contract"]
            projection = dispatch_v16(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project),
                    "review_type": "visual",
                }
            )
            self.assertEqual(
                projection["review"]["source_version"], source_version
            )
            saved = dispatch_v16(
                {
                    "operation": "save-review-marks",
                    "project_root": str(project),
                    "expected_revision": published.revision,
                    "review_type": "visual",
                    "source_version": source_version,
                    "marks": [
                        {
                            "mark_id": "bridge-visual-mark",
                            "field_anchor": "visual-slide-s1-visible-copy",
                            "exact_text": "三条断点",
                            "prefix": "五套系统",
                            "suffix": "",
                            "comment": "增强证据层级",
                        }
                    ],
                }
            )
            saved_revision = saved["result"]["snapshot"]["revision"]
            self.assertEqual(
                saved["result"]["snapshot"]["gate_state"]["gates"]["G3"],
                "user-reviewable",
            )
            context = dispatch_v16(
                {
                    "operation": "get-gate-confirmation-context",
                    "project_root": str(project),
                    "gate": "G3",
                }
            )["confirmation_context"]
            confirmed = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": saved_revision,
                    "gate": "G3",
                    "host_confirmation_assertion": signed_gate_assertion(context),
                    "source_version": context["source_version"],
                    "challenge_id": context["challenge_id"],
                    "challenge_revision": context["challenge_revision"],
                }
            )
            self.assertEqual(
                confirmed["result"]["snapshot"]["gate_state"]["gates"]["G3"],
                "passed",
            )

    def test_public_reopen_scope_routes_g3_to_visual_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            visual, revision, refs = prepared_g2(project, slide_count=2)
            published = visual.publish_visual_review("bridge-publish", revision)
            contract_ref = published.artifact_heads["visual/contract"]

            reopened = dispatch_v16(
                {
                    "operation": "reopen-scope",
                    "project_root": str(project),
                    "expected_revision": published.revision,
                    "gate": "G3",
                    "reason": "用户要求调整整套视觉合同",
                }
            )["result"]["snapshot"]

            self.assertEqual(reopened["gate_state"]["gates"]["G0"], "passed")
            self.assertEqual(reopened["gate_state"]["gates"]["G1"], "open")
            for gate in ("G2", "G3", "G4"):
                self.assertEqual(
                    reopened["gate_state"]["gates"][gate], "locked"
                )
            self.assertFalse(
                any(slot.startswith("visual/") for slot in reopened["artifacts"])
            )
            self.assertIn("gate/G3/reopen", reopened["artifacts"])
            self.assertNotIn("gate/G2/lineage", reopened["artifacts"])
            self.assertEqual(
                visual.kernel.artifacts.resolve(
                    ArtifactReference.parse(contract_ref)
                )["payload"]["status"],
                "user-reviewable",
            )

            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": reopened["revision"],
                    "kind": "visual-brief",
                    "payload": valid_visual_brief(refs["blueprint"]),
                }
            )
            self.assertIn(
                "visual/brief", committed["result"]["snapshot"]["artifacts"]
            )

            task = dispatch_v16(
                {
                    "operation": "request-agent-action",
                    "project_root": str(project),
                    "expected_revision": committed["result"]["snapshot"]["revision"],
                    "command_id": "new-visual-task-after-g3-reopen",
                    "action_type": "design-deck-system",
                    "target_refs": [committed["result"]["artifact_ref"]],
                    "instructions": "按重开后的视觉 brief 重新设计。",
                }
            )["result"]
            self.assertEqual(task["task"]["status"], "queued")
            self.assertIn("agent/task/active", task["snapshot"]["artifacts"])


if __name__ == "__main__":
    unittest.main()
