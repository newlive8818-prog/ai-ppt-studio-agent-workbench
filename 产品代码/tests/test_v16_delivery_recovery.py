from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.presentation.targets import REQUIRED_TARGET_IDS
from ai_ppt_studio.errors import (
    ContractValidationError,
    GateBlockedError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_delivery_fixtures import (
    build_artifacts,
    package_artifacts,
    prepared_build,
    prepared_delivery_ready,
    prepared_qa,
    rich_g4_target_payload,
    valid_build_payload,
    valid_package_payload,
)


class V16DeliveryRecoveryTests(unittest.TestCase):
    def test_failed_attempt_and_repair_preserve_last_valid_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_build(Path(temp), slide_count=2)
            attempt_ref = str(
                delivery.kernel.artifacts.put(
                    "build-attempt",
                    {
                        "pptx_sha256": "8" * 64,
                        "slide_ids": refs["slide_ids"],
                        "status": "failed",
                    },
                )
            )
            invalid = {
                "attempt_ref": attempt_ref,
                "last_valid_build_ref": "artifact://presentation-build/" + "a" * 64,
                "target_slide_ids": ["s1"],
                "failure_code": "PRESENTATION_BUILD_FAILED",
                "failure_reason": "第 1 页对象构建失败",
                "retry_policy": "targeted-repair",
            }
            with self.assertRaises(ContractValidationError):
                delivery.record_failed_attempt("invalid-attempt", revision, invalid)
            self.assertEqual(
                delivery.kernel.load().artifact_heads["delivery/build"], refs["build"]
            )
            failed_ref = delivery.record_failed_attempt(
                "failed-attempt",
                revision,
                {**invalid, "last_valid_build_ref": refs["build"]},
            )
            self.assertTrue(failed_ref.startswith("artifact://failed-build-attempt/"))
            revision += 1
            with self.assertRaises(ContractValidationError):
                delivery.register_repair(
                    "invalid-repair",
                    revision,
                    {
                        "failed_attempt_ref": failed_ref,
                        "last_valid_build_ref": refs["build"],
                        "target_slide_ids": ["s1"],
                        "preserve_refs": [],
                        "failure_conditions": ["对象构建失败"],
                        "required_outcome": "第 1 页恢复并通过四门",
                        "review_route": ["PPT 工程审查智能体"],
                    },
                )
            repair_ref = delivery.register_repair(
                "repair",
                revision,
                {
                    "failed_attempt_ref": failed_ref,
                    "last_valid_build_ref": refs["build"],
                    "target_slide_ids": ["s1"],
                    "preserve_refs": [refs["build"]],
                    "failure_conditions": ["对象构建失败"],
                    "required_outcome": "第 1 页恢复并通过四门",
                    "review_route": ["PPT 工程审查智能体"],
                },
            )
            self.assertTrue(repair_ref.startswith("artifact://delivery-repair/"))
            self.assertEqual(
                delivery.kernel.load().artifact_heads["delivery/build"], refs["build"]
            )

    def test_reopened_g4_replaces_build_without_reusing_stale_downstream_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_delivery_ready(
                Path(temp), slide_count=2
            )
            package_ref = delivery.register_delivery_package(
                "stale-package",
                revision,
                valid_package_payload(refs, package_artifacts(delivery, refs)),
            )
            revision += 1
            sent = delivery.record_chat_delivery(
                "stale-chat-send",
                revision,
                {
                    "delivery_type": "pptx",
                    "build_ref": refs["build"],
                    "package_ref": package_ref,
                    "pptx_ref": refs["final_pptx"],
                    "pptx_sha256": refs["pptx_sha256"],
                    "artifact_refs": [package_ref, refs["final_pptx"]],
                    "message_ref": "chat://message/original-pptx-send",
                    "send_status": "sent",
                    "sent_at": "2026-08-09T14:00:00+08:00",
                    "retry_of": "",
                },
            )
            before_reopen = sent.artifact_heads
            reopened = delivery.reopen_g4(
                "reopen-delivery",
                sent.revision,
                user_message_ref="chat://message/revise-slide-one",
                impact_scope=["s1"],
            )
            self.assertEqual(reopened.gate_status["G4"], "open")
            self.assertEqual(reopened.artifact_heads["delivery/package"], package_ref)
            self.assertEqual(
                reopened.artifact_heads["chat-delivery/pptx"],
                before_reopen["chat-delivery/pptx"],
            )

            replacement_artifacts = build_artifacts(
                delivery,
                refs["slide_ids"],
                sha256=refs["pptx_sha256"],
            )
            replacement_ref = delivery.register_build(
                "replacement-build",
                reopened.revision,
                valid_build_payload(refs, replacement_artifacts),
            )
            state = delivery.kernel.load()
            self.assertEqual(
                delivery.kernel.artifacts.resolve(
                    ArtifactReference.parse(replacement_ref)
                )["payload"]["last_valid_build_ref"],
                refs["build"],
            )
            with self.assertRaises(GateBlockedError):
                delivery.finalize_delivery("stale-downstream-evidence", state.revision)
            self.assertEqual(delivery.kernel.load().revision, state.revision)
            for slide_id, qa_ref in zip(
                refs["slide_ids"], refs["slide_qa"], strict=True
            ):
                self.assertEqual(
                    state.artifact_heads[f"delivery/qa/slide/{slide_id}"], qa_ref
                )
            self.assertEqual(state.artifact_heads["delivery/package"], package_ref)

    def test_restore_build_creates_a_new_auditable_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_build(Path(temp), slide_count=2)
            replacement_artifacts = build_artifacts(
                delivery,
                refs["slide_ids"],
                sha256=refs["pptx_sha256"],
            )
            replacement_ref = delivery.register_build(
                "replacement-before-restore",
                revision,
                valid_build_payload(refs, replacement_artifacts),
            )
            restored_ref = delivery.restore_build(
                "restore-last-valid",
                revision + 1,
                source_build_ref=refs["build"],
            )
            self.assertNotEqual(restored_ref, refs["build"])
            self.assertNotEqual(restored_ref, replacement_ref)
            restored = delivery.kernel.artifacts.resolve(
                ArtifactReference.parse(restored_ref)
            )["payload"]
            self.assertEqual(restored["restored_from"], refs["build"])
            self.assertEqual(restored["last_valid_build_ref"], replacement_ref)
            self.assertEqual(restored["pptx_sha256"], refs["pptx_sha256"])
            self.assertEqual(
                delivery.kernel.artifacts.resolve(
                    ArtifactReference.parse(refs["build"])
                )["payload"]["pptx_sha256"],
                refs["pptx_sha256"],
            )

    def test_same_hash_target_retry_replaces_only_one_target_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_qa(Path(temp), slide_count=2)
            original: dict[str, str] = {}
            for target_id in REQUIRED_TARGET_IDS:
                original[target_id] = delivery.register_target_render_evidence(
                    f"initial-{target_id}",
                    revision,
                    rich_g4_target_payload(delivery, target_id, refs),
                )
                revision += 1
            retry_target = "macos-wps"
            retried_payload = rich_g4_target_payload(
                delivery, retry_target, refs
            )
            retried_payload["application_version"] = "WPS/test-retry-version"
            replacement_ref = delivery.register_target_render_evidence(
                "retry-macos-wps",
                revision,
                retried_payload,
            )
            revision += 1
            self.assertNotEqual(replacement_ref, original[retry_target])
            current = delivery.kernel.load().artifact_heads
            for target_id in REQUIRED_TARGET_IDS:
                expected = (
                    replacement_ref if target_id == retry_target else original[target_id]
                )
                self.assertEqual(
                    current[f"delivery/target-evidence/G4/{target_id}"], expected
                )
            ready = delivery.finalize_delivery("ready-after-target-retry", revision)
            self.assertEqual(ready.gate_status["G4"], "delivery-ready")

    def test_failed_chat_send_is_idempotent_and_revision_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_delivery_ready(
                Path(temp), slide_count=2
            )
            package_ref = delivery.register_delivery_package(
                "retry-package",
                revision,
                valid_package_payload(refs, package_artifacts(delivery, refs)),
            )
            revision += 1
            payload = {
                "delivery_type": "pptx",
                "build_ref": refs["build"],
                "package_ref": package_ref,
                "pptx_ref": refs["final_pptx"],
                "pptx_sha256": refs["pptx_sha256"],
                "artifact_refs": [package_ref, refs["final_pptx"]],
                "message_ref": "chat://message/failed-recoverable-send",
                "send_status": "failed",
                "sent_at": "2026-08-09T14:10:00+08:00",
                "retry_of": "",
            }
            failed = delivery.record_chat_delivery(
                "idempotent-failed-send", revision, payload
            )
            events_before = tuple(delivery.kernel.events_root.glob("*.json"))
            repeated = delivery.record_chat_delivery(
                "idempotent-failed-send", revision, payload
            )
            self.assertEqual(repeated.revision, failed.revision)
            self.assertEqual(
                tuple(delivery.kernel.events_root.glob("*.json")), events_before
            )
            receipt_ref = failed.artifact_heads["chat-delivery/pptx"]
            with self.assertRaises(RevisionConflictError):
                delivery.record_chat_delivery(
                    "stale-failed-send", revision, payload
                )
            current = delivery.kernel.load()
            self.assertEqual(current.revision, failed.revision)
            self.assertEqual(current.artifact_heads["delivery/build"], refs["build"])
            self.assertEqual(current.artifact_heads["chat-delivery/pptx"], receipt_ref)


if __name__ == "__main__":
    unittest.main()
