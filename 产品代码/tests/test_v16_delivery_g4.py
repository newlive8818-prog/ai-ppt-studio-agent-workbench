from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_delivery_fixtures import (
    build_artifacts,
    package_artifacts,
    prepared_build,
    prepared_delivery_ready,
    prepared_g3,
    prepared_qa,
    rich_g4_target_payload,
    valid_build_payload,
    valid_package_payload,
    valid_deck_qa,
    valid_slide_qa,
)
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


class V16DeliveryG4Tests(unittest.TestCase):
    def test_full_deck_build_may_have_a_new_hash_after_g2_anchor_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_g3(Path(temp), slide_count=2)
            final_artifacts = build_artifacts(
                delivery,
                refs["slide_ids"],
                sha256="9" * 64,
            )

            build_ref = delivery.register_build(
                "full-deck-with-new-hash",
                revision,
                valid_build_payload(refs, final_artifacts),
            )

            self.assertTrue(build_ref.startswith("artifact://presentation-build/"))
            self.assertNotEqual(final_artifacts["pptx_sha256"], refs["pptx_sha256"])

    def test_slide_and_deck_qa_are_binary_complete_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_build(Path(temp), slide_count=2)
            scored = valid_slide_qa(delivery, refs, "s1")
            scored["score"] = 96
            with self.assertRaises(ContractValidationError):
                delivery.register_slide_qa("scored-slide", revision, scored)
            self.assertEqual(delivery.kernel.load().revision, revision)

            failed = valid_slide_qa(delivery, refs, "s1", result="failed")
            failed_ref = delivery.register_slide_qa(
                "failed-slide", revision, failed
            )
            self.assertTrue(failed_ref.startswith("artifact://slide-qa/"))
            revision += 1
            slide_qa_refs = []
            for slide_id in refs["slide_ids"]:
                slide_qa_refs.append(
                    delivery.register_slide_qa(
                        f"passed-{slide_id}",
                        revision,
                        valid_slide_qa(delivery, refs, slide_id),
                    )
                )
                revision += 1

            invalid_deck = valid_deck_qa(delivery, refs, slide_qa_refs)
            invalid_deck["slide_qa_refs"] = slide_qa_refs[:-1]
            with self.assertRaises(ContractValidationError):
                delivery.register_deck_qa("partial-deck", revision, invalid_deck)
            scored_deck = valid_deck_qa(delivery, refs, slide_qa_refs)
            scored_deck["average"] = 100
            with self.assertRaises(ContractValidationError):
                delivery.register_deck_qa("scored-deck", revision, scored_deck)
            failed_deck = copy.deepcopy(
                valid_deck_qa(delivery, refs, slide_qa_refs)
            )
            failed_deck["coherence_result"] = "failed"
            failed_deck["overall_result"] = "failed"
            failed_deck["failure_reason"] = "整套节奏断裂"
            failed_deck["repair_instruction"] = "调整过渡页后整套复验"
            failed_ref = delivery.register_deck_qa(
                "failed-deck", revision, failed_deck
            )
            self.assertTrue(failed_ref.startswith("artifact://deck-qa/"))
            revision += 1
            deck_ref = delivery.register_deck_qa(
                "passed-deck",
                revision,
                valid_deck_qa(delivery, refs, slide_qa_refs),
            )
            self.assertTrue(deck_ref.startswith("artifact://deck-qa/"))

    def test_delivery_ready_requires_new_full_deck_macos_powerpoint_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_qa(Path(temp), slide_count=2)
            with self.assertRaises(GateBlockedError):
                delivery.finalize_delivery("early-finalize", revision)
            invalid = rich_g4_target_payload(
                delivery, "macos-powerpoint", refs
            )
            invalid["slide_checks"] = invalid["slide_checks"][:-1]
            with self.assertRaises(ContractValidationError):
                delivery.register_target_render_evidence(
                    "partial-target", revision, invalid
                )
            wrong_stage = rich_g4_target_payload(
                delivery, "macos-powerpoint", refs
            )
            wrong_stage["stage"] = "G2"
            with self.assertRaises(ContractValidationError):
                delivery.register_target_render_evidence(
                    "anchor-stage-target", revision, wrong_stage
                )
            g2_mac_ref = delivery.kernel.load().artifact_heads[
                "visual/target-evidence/G2/macos-powerpoint"
            ]
            self.assertNotEqual(
                g2_mac_ref,
                delivery.kernel.load().artifact_heads.get(
                    "delivery/target-evidence/G4/macos-powerpoint"
                ),
            )
            mac_ref = delivery.register_target_render_evidence(
                "g4-target-macos-powerpoint",
                revision,
                rich_g4_target_payload(delivery, "macos-powerpoint", refs),
            )
            ready = delivery.finalize_delivery(
                "delivery-ready", revision + 1
            )
            self.assertEqual(ready.gate_status["G4"], "delivery-ready")
            self.assertEqual(
                ready.artifact_heads["delivery/target-evidence/G4/macos-powerpoint"],
                mac_ref,
            )
            for deferred in ("macos-wps", "windows-powerpoint", "windows-wps"):
                self.assertNotIn(
                    f"delivery/target-evidence/G4/{deferred}",
                    ready.artifact_heads,
                )

    def test_deferred_g4_wps_evidence_cannot_substitute_for_required_mac(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_qa(Path(temp), slide_count=2)
            delivery.register_target_render_evidence(
                "g4-deferred-wps",
                revision,
                rich_g4_target_payload(delivery, "macos-wps", refs),
            )
            with self.assertRaises(GateBlockedError) as raised:
                delivery.finalize_delivery("wps-cannot-substitute", revision + 1)
            self.assertIn("missing-target:macos-powerpoint", raised.exception.missing_evidence)

    def test_package_chat_send_and_explicit_user_message_are_separate_g4_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_delivery_ready(
                Path(temp), slide_count=2
            )
            artifacts = package_artifacts(delivery, refs)
            font_report = delivery.kernel.artifacts.resolve(
                ArtifactReference.parse(artifacts["font_platform_report"])
            )["payload"]
            self.assertEqual(font_report["targets"], ["macos-powerpoint"])
            self.assertEqual(
                font_report["deferred_targets"],
                ["macos-wps", "windows-powerpoint", "windows-wps"],
            )
            self.assertEqual(
                font_report["release_target_policy_ref"],
                refs["release_target_policy_ref"],
            )
            invalid_package = valid_package_payload(refs, artifacts)
            invalid_package["target_evidence_refs"] = refs[
                "g4_target_evidence"
            ][:-1]
            with self.assertRaises(ContractValidationError):
                delivery.register_delivery_package(
                    "partial-package", revision, invalid_package
                )
            package_ref = delivery.register_delivery_package(
                "delivery-package",
                revision,
                valid_package_payload(refs, artifacts),
            )
            package = delivery.kernel.artifacts.resolve(
                ArtifactReference.parse(package_ref)
            )["payload"]
            self.assertEqual(
                package["release_target_policy_ref"],
                refs["release_target_policy_ref"],
            )
            self.assertEqual(
                package["target_evidence_refs"], refs["g4_target_evidence"]
            )
            revision += 1
            failed = delivery.record_chat_delivery(
                "failed-chat-send",
                revision,
                {
                    "delivery_type": "pptx",
                    "build_ref": refs["build"],
                    "package_ref": package_ref,
                    "pptx_ref": refs["final_pptx"],
                    "pptx_sha256": refs["pptx_sha256"],
                    "artifact_refs": [package_ref, refs["final_pptx"]],
                    "message_ref": "chat://message/pptx-send-failed",
                    "send_status": "failed",
                    "sent_at": "2026-08-09T13:00:00+08:00",
                    "retry_of": "",
                },
            )
            self.assertEqual(failed.gate_status["G4"], "delivery-ready")
            sent = delivery.record_chat_delivery(
                "successful-chat-send",
                failed.revision,
                {
                    "delivery_type": "pptx",
                    "build_ref": refs["build"],
                    "package_ref": package_ref,
                    "pptx_ref": refs["final_pptx"],
                    "pptx_sha256": refs["pptx_sha256"],
                    "artifact_refs": [package_ref, refs["final_pptx"]],
                    "message_ref": "chat://message/pptx-sent",
                    "send_status": "sent",
                    "sent_at": "2026-08-09T13:01:00+08:00",
                    "retry_of": failed.artifact_heads["chat-delivery/pptx"],
                },
            )
            self.assertEqual(sent.gate_status["G4"], "user-reviewable")
            with self.assertRaises(GateBlockedError):
                delivery.confirm_g4(
                    "invalid-g4",
                    sent.revision,
                    user_message_ref="review://downloaded/pptx",
                )
            self.assertEqual(delivery.kernel.load().revision, sent.revision)
            from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy

            context = GateConfirmationPolicy(delivery.kernel).context("G4")
            accepted = delivery.confirm_g4(
                "accepted-g4",
                sent.revision,
                **gate_confirmation_kwargs(context),
            )
            self.assertEqual(accepted.gate_status["G4"], "passed")


if __name__ == "__main__":
    unittest.main()
