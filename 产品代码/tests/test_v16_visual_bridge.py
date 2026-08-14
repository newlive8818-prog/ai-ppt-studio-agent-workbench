from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import (
    confirmed_g0,
    passing_visual_review,
    prepared_g2,
    prepared_visual_contracts,
    valid_visual_brief,
)


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
            self.assertEqual(state.revision, revision + 3)
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

            self.assertEqual(committed["snapshot"]["revision"], revision + 3)
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
            confirmed = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": saved_revision,
                    "gate": "G3",
                    "user_message_ref": "chat://message/bridge-g3-accepted",
                }
            )
            self.assertEqual(
                confirmed["result"]["snapshot"]["gate_state"]["gates"]["G3"],
                "passed",
            )


if __name__ == "__main__":
    unittest.main()
