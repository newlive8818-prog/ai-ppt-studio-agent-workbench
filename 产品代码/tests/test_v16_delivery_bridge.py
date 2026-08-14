from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_delivery_fixtures import (
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)


class V16DeliveryBridgeTests(unittest.TestCase):
    def test_task_bound_delivery_result_is_one_atomic_revision_and_replays_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            delivery, revision, refs = prepared_delivery_ready(
                project, slide_count=2
            )
            payload = {
                **valid_package_payload(refs, package_artifacts(delivery, refs)),
                "artifact_type": "delivery-package",
            }
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "atomic-delivery-task",
                "action_type": "coordinate-delivery",
                "target_refs": [refs["build"]],
                "instructions": "组织当前最终交付包。",
            })["result"]
            task_id = requested["task"]["task_id"]
            event_count = len(tuple(delivery.kernel.events_root.iterdir()))
            committed = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "atomic-delivery-result",
                "kind": "delivery",
                "task_id": task_id,
                "payload": payload,
            })["result"]
            self.assertEqual(committed["snapshot"]["revision"], revision + 2)
            self.assertEqual(
                len(tuple(delivery.kernel.events_root.iterdir())), event_count + 1
            )
            task = delivery.kernel.artifacts.resolve(ArtifactReference.parse(
                committed["snapshot"]["artifacts"][f"agent/task/{task_id}"]
            ))["payload"]
            self.assertEqual(task["status"], "completed")
            self.assertEqual(task["result_refs"], [committed["artifact_ref"]])
            events = tuple(delivery.kernel.events_root.iterdir())

            replayed = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "atomic-delivery-result",
                "kind": "delivery",
                "task_id": task_id,
                "payload": payload,
            })["result"]
            self.assertEqual(replayed, committed)
            self.assertEqual(tuple(delivery.kernel.events_root.iterdir()), events)

    def test_existing_public_operations_cover_package_chat_projection_g4_and_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            delivery, revision, refs = prepared_delivery_ready(
                project, slide_count=2
            )
            package_payload = {
                **valid_package_payload(
                    refs, package_artifacts(delivery, refs)
                ),
                "artifact_type": "delivery-package",
            }
            packaged = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "kind": "delivery",
                    "payload": package_payload,
                }
            )
            package_ref = packaged["result"]["artifact_ref"]
            self.assertTrue(package_ref.startswith("artifact://delivery-package/"))
            revision = packaged["result"]["snapshot"]["revision"]

            sent = dispatch_v16(
                {
                    "operation": "record-chat-delivery",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "delivery_type": "pptx",
                    "artifact_refs": [package_ref, refs["final_pptx"]],
                    "message_ref": "chat://message/bridge-pptx-sent",
                    "send_status": "sent",
                    "retry_of": "",
                }
            )
            revision = sent["result"]["snapshot"]["revision"]
            self.assertEqual(
                sent["result"]["snapshot"]["gate_state"]["gates"]["G4"],
                "user-reviewable",
            )

            projected = dispatch_v16(
                {
                    "operation": "get-delivery-status-projection",
                    "project_root": str(project),
                }
            )
            projection = projected["delivery"]
            self.assertEqual(
                set(projection),
                {
                    "phase",
                    "slides",
                    "quality_gates",
                    "highest_blocker",
                    "targets",
                    "hash_identity",
                    "chat_send",
                },
            )
            self.assertEqual(projection["phase"], "user-reviewable")
            self.assertEqual(projection["slides"], {"completed": 2, "total": 2})
            self.assertEqual(
                projection["quality_gates"],
                {
                    "semantic": "passed",
                    "aesthetic": "passed",
                    "engineering": "passed",
                    "target_render": "passed",
                },
            )
            self.assertIsNone(projection["highest_blocker"])
            self.assertEqual(len(projection["targets"]), 4)
            self.assertEqual(
                {target["status"] for target in projection["targets"]},
                {"passed"},
            )
            self.assertEqual(projection["hash_identity"], refs["pptx_sha256"])
            self.assertEqual(projection["chat_send"]["status"], "sent")
            self.assertNotIn("page_images", str(projection))
            self.assertNotIn("contact_sheet", str(projection))
            self.assertNotIn("download", str(projection))

            accepted = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "gate": "G4",
                    "user_message_ref": "chat://message/bridge-final-accepted",
                }
            )
            revision = accepted["result"]["snapshot"]["revision"]
            self.assertEqual(
                accepted["result"]["snapshot"]["gate_state"]["gates"]["G4"],
                "passed",
            )
            reopened = dispatch_v16(
                {
                    "operation": "reopen-scope",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "gate": "G4",
                    "reason": "用户要求修改最终成稿",
                }
            )
            self.assertEqual(
                reopened["result"]["snapshot"]["gate_state"]["gates"]["G4"],
                "open",
            )
            self.assertEqual(
                reopened["result"]["snapshot"]["artifacts"]["delivery/package"],
                package_ref,
            )

    def test_unsupported_legacy_delivery_write_fails_without_revision_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            delivery, revision, _refs = prepared_delivery_ready(
                project, slide_count=2
            )
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision,
                        "kind": "delivery",
                        "payload": {
                            "artifact_type": "legacy-v15-delivery",
                            "status": "passed",
                        },
                    }
                )
            self.assertEqual(delivery.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
