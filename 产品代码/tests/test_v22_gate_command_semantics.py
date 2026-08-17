from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ContractValidationError
from tests.v16_delivery_fixtures import (
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)
from tests.v16_visual_fixtures import (
    passing_visual_review,
    prepared_g2,
    prepared_visual_contracts,
)


def snapshot(service) -> tuple[int, dict[str, str], tuple[str, ...]]:
    state = service.kernel.load()
    return (
        state.revision,
        dict(state.artifact_heads),
        tuple(sorted(path.name for path in service.kernel.events_root.glob("*.json"))),
    )


def prepare_packaged_delivery(project: Path):
    delivery, revision, refs = prepared_delivery_ready(project, slide_count=3)
    package_ref = delivery.register_delivery_package(
        "command-semantics-package",
        revision,
        valid_package_payload(refs, package_artifacts(delivery, refs)),
    )
    return delivery, revision + 1, refs, package_ref


def sent_payload(refs: dict[str, object], package_ref: str) -> dict[str, object]:
    return {
        "delivery_type": "pptx",
        "build_ref": refs["build"],
        "package_ref": package_ref,
        "pptx_ref": refs["final_pptx"],
        "pptx_sha256": refs["pptx_sha256"],
        "artifact_refs": [package_ref, refs["final_pptx"]],
        "message_ref": "chat://message/pptx-sent",
        "send_status": "sent",
        "sent_at": "2026-08-15T09:00:00+08:00",
        "retry_of": "",
    }


class V22GateCommandSemanticsTests(unittest.TestCase):
    def assert_replay_and_collision(
        self,
        service,
        first,
        replay,
        collision,
    ) -> None:
        first_state = first()
        after_first = snapshot(service)
        replayed = replay()
        self.assertEqual(replayed, first_state)
        self.assertEqual(snapshot(service), after_first)
        with self.assertRaisesRegex(
            ContractValidationError, "Processed command has different semantics"
        ):
            collision()
        self.assertEqual(snapshot(service), after_first)

    def test_direct_chat_delivery_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs, package_ref = prepare_packaged_delivery(Path(temp))
            payload = sent_payload(refs, package_ref)
            self.assert_replay_and_collision(
                delivery,
                lambda: delivery.record_chat_delivery("send-once", revision, payload),
                lambda: delivery.record_chat_delivery("send-once", revision, payload),
                lambda: delivery.record_chat_delivery(
                    "send-once",
                    revision,
                    {**payload, "message_ref": "chat://message/different-send"},
                ),
            )

    def test_public_chat_delivery_excludes_generated_time_from_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs, package_ref = prepare_packaged_delivery(Path(temp))
            args = {
                "delivery_type": "pptx",
                "artifact_refs": [package_ref, refs["final_pptx"]],
                "message_ref": "chat://message/public-pptx-sent",
                "send_status": "sent",
                "retry_of": "",
            }
            self.assert_replay_and_collision(
                delivery,
                lambda: delivery.record_public_chat_delivery(
                    "public-send-once", revision, **args
                ),
                lambda: delivery.record_public_chat_delivery(
                    "public-send-once", revision, **args
                ),
                lambda: delivery.record_public_chat_delivery(
                    "public-send-once",
                    revision,
                    **{**args, "message_ref": "chat://message/public-changed"},
                ),
            )

    def test_g4_confirmation_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs, package_ref = prepare_packaged_delivery(Path(temp))
            sent = delivery.record_chat_delivery(
                "send-before-confirm", revision, sent_payload(refs, package_ref)
            )
            self.assert_replay_and_collision(
                delivery,
                lambda: delivery.confirm_g4(
                    "confirm-once",
                    sent.revision,
                    user_message_ref="chat://message/final-accepted",
                ),
                lambda: delivery.confirm_g4(
                    "confirm-once",
                    sent.revision,
                    user_message_ref="chat://message/final-accepted",
                ),
                lambda: delivery.confirm_g4(
                    "confirm-once",
                    sent.revision,
                    user_message_ref="chat://message/different-acceptance",
                ),
            )

    def test_direct_g4_reopen_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, _refs, _package_ref = prepare_packaged_delivery(Path(temp))
            self.assert_replay_and_collision(
                delivery,
                lambda: delivery.reopen_g4(
                    "reopen-once",
                    revision,
                    user_message_ref="chat://message/revise-slide-one",
                    impact_scope=["S01"],
                ),
                lambda: delivery.reopen_g4(
                    "reopen-once",
                    revision,
                    user_message_ref="chat://message/revise-slide-one",
                    impact_scope=["S01"],
                ),
                lambda: delivery.reopen_g4(
                    "reopen-once",
                    revision,
                    user_message_ref="chat://message/revise-slide-two",
                    impact_scope=["S02"],
                ),
            )

    def test_public_g4_reopen_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, _refs, _package_ref = prepare_packaged_delivery(Path(temp))
            self.assert_replay_and_collision(
                delivery,
                lambda: delivery.reopen_public_scope(
                    "public-reopen-once", revision, gate="G4", reason="整体重新检查"
                ),
                lambda: delivery.reopen_public_scope(
                    "public-reopen-once", revision, gate="G4", reason="整体重新检查"
                ),
                lambda: delivery.reopen_public_scope(
                    "public-reopen-once", revision, gate="G4", reason="改为局部检查"
                ),
            )

    def test_g3_confirmation_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, _refs = prepared_g2(Path(temp), slide_count=3)
            published = visual.publish_visual_review("publish-for-confirm", revision)
            self.assert_replay_and_collision(
                visual,
                lambda: visual.confirm_g3(
                    "confirm-g3-once",
                    published.revision,
                    user_message_ref="chat://message/visual-accepted",
                ),
                lambda: visual.confirm_g3(
                    "confirm-g3-once",
                    published.revision,
                    user_message_ref="chat://message/visual-accepted",
                ),
                lambda: visual.confirm_g3(
                    "confirm-g3-once",
                    published.revision,
                    user_message_ref="chat://message/different-visual-acceptance",
                ),
            )

    def test_internal_gate_has_exact_command_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_visual_contracts(Path(temp))
            convergence_ref = visual.register_convergence(
                "internal-gate-convergence",
                revision,
                {
                    "production_route": "strict-B",
                    "visual_contract_set_ref": refs["contracts"],
                    "producer_role": "visual-art-director",
                    "decision_summary": "锚点页覆盖关键页面家族和视觉风险",
                    "convergence_status": "passed",
                },
            )
            review_ref = visual.register_visual_review(
                "internal-gate-review",
                revision + 1,
                passing_visual_review(refs["contracts"]),
            )
            evidence = [convergence_ref, review_ref]
            self.assert_replay_and_collision(
                visual,
                lambda: visual.record_internal_gate(
                    "internal-g1-once",
                    revision + 2,
                    gate="G1",
                    reviewer_role="独立审美审查智能体",
                    acceptance_record_refs=evidence,
                ),
                lambda: visual.record_internal_gate(
                    "internal-g1-once",
                    revision + 2,
                    gate="G1",
                    reviewer_role="独立审美审查智能体",
                    acceptance_record_refs=evidence,
                ),
                lambda: visual.record_internal_gate(
                    "internal-g1-once",
                    revision + 2,
                    gate="G1",
                    reviewer_role="独立审美审查智能体",
                    acceptance_record_refs=[*evidence, evidence[0]],
                ),
            )


if __name__ == "__main__":
    unittest.main()
