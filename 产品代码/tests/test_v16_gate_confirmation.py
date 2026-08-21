from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContentWorkflowError, GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_content_acceptance import register_reviews
from tests.test_v16_content_chain import build_ready_draft
from tests.v16_visual_fixtures import (
    apply_all_approved_content_review,
    prepared_g2,
    valid_visual_brief,
)
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.host_confirmation_fixtures import signed_gate_assertion


def accepted_content(
    service: ContentService,
    *,
    mission_user_action_ref: str = "test-user-action://mission-confirmed",
    mission_user_message_ref: str = "",
) -> tuple[int, str]:
    revision, draft_ref, _refs = build_ready_draft(
        service,
        mission_user_action_ref=mission_user_action_ref,
        mission_user_message_ref=mission_user_message_ref,
    )
    revision = register_reviews(service, revision, draft_ref)
    accepted = service.accept_content("accept", revision)
    apply_all_approved_content_review(service, accepted.blueprint_ref)
    return service.kernel.load().revision, accepted.blueprint_ref


class V16GateConfirmationTests(unittest.TestCase):
    def test_legacy_g0_confirmation_can_be_host_upgraded_without_reopening_visual_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=2)
            before = visual.kernel.load()
            original_confirmation_ref = before.artifact_heads["gate/G0/confirmation"]
            original_confirmation = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(original_confirmation_ref)
            )["payload"]
            legacy_confirmation = {
                "gate": "G0",
                "content_acceptance_ref": original_confirmation[
                    "content_acceptance_ref"
                ],
                "content_blueprint_ref": original_confirmation[
                    "content_blueprint_ref"
                ],
                "user_message_ref": "chat://message/legacy-real-g0-confirmation",
            }
            legacy_state = visual.kernel.commit(
                command_id="simulate-pre-host-assertion-g0-confirmation",
                expected_revision=revision,
                event_type="test.legacy-g0-confirmation-restored",
                artifact_updates={
                    "gate/G0/confirmation": ("g0-confirmation", legacy_confirmation)
                },
            )
            frozen_visual_heads = {
                slot: value
                for slot, value in legacy_state.artifact_heads.items()
                if slot.startswith("visual/") or slot == "gate/G2/lineage"
            }
            content = ContentService(visual.kernel)

            context = content.gate_confirmation_context("G0")
            self.assertEqual(
                context["confirmation_mode"], "legacy-credential-upgrade"
            )
            self.assertEqual(
                context["legacy_confirmation_ref"],
                legacy_state.artifact_heads["gate/G0/confirmation"],
            )
            upgraded = content.confirm_g0(
                "host-upgrade-legacy-g0-confirmation",
                legacy_state.revision,
                **gate_confirmation_kwargs(context),
            )

            self.assertEqual(upgraded.gate_status, legacy_state.gate_status)
            self.assertEqual(upgraded.gate_status["G2"], "passed")
            self.assertEqual(
                {
                    slot: value
                    for slot, value in upgraded.artifact_heads.items()
                    if slot.startswith("visual/") or slot == "gate/G2/lineage"
                },
                frozen_visual_heads,
            )
            upgraded_ref = upgraded.artifact_heads["gate/G0/confirmation"]
            self.assertNotEqual(upgraded_ref, context["legacy_confirmation_ref"])
            payload = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(upgraded_ref)
            )["payload"]
            self.assertEqual(
                payload["supersedes_confirmation_ref"],
                context["legacy_confirmation_ref"],
            )
            self.assertEqual(
                payload["confirmation_mode"], "legacy-credential-upgrade"
            )
            self.assertTrue(payload["host_assertion_sha256"])

            with self.assertRaises(GateBlockedError) as raised:
                content.gate_confirmation_context("G0")
            self.assertIn("gate-not-user-reviewable", raised.exception.missing_evidence)

    def test_legacy_g0_upgrade_rejects_confirmation_with_diverged_content_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, _refs = prepared_g2(Path(temp), slide_count=2)
            state = visual.kernel.load()
            original_ref = state.artifact_heads["gate/G0/confirmation"]
            original = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(original_ref)
            )["payload"]
            legacy_confirmation = {
                "gate": "G0",
                "content_acceptance_ref": original["content_acceptance_ref"],
                "content_blueprint_ref": "artifact://content-blueprint/"
                + "f" * 64,
                "user_message_ref": "chat://message/legacy-wrong-blueprint",
            }
            diverged = visual.kernel.commit(
                command_id="simulate-diverged-legacy-g0-confirmation",
                expected_revision=revision,
                event_type="test.diverged-legacy-g0-confirmation",
                artifact_updates={
                    "gate/G0/confirmation": ("g0-confirmation", legacy_confirmation)
                },
            )

            with self.assertRaises(GateBlockedError) as raised:
                ContentService(visual.kernel).gate_confirmation_context("G0")

            self.assertIn("gate-not-user-reviewable", raised.exception.missing_evidence)
            self.assertEqual(visual.kernel.load().revision, diverged.revision)

    def test_mission_confirmation_identity_cannot_be_replayed_for_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(
                service,
                mission_user_action_ref="",
                mission_user_message_ref="chat://message/item-35",
            )

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "replayed-mission-confirmation",
                    revision,
                    user_message_ref="chat://message/item-35",
                )

            state = service.kernel.load()
            self.assertEqual(state.revision, revision)
            self.assertEqual(state.gate_status["G0"], "user-reviewable")
            self.assertNotIn("gate/G0/confirmation", state.artifact_heads)

    def test_model_supplied_message_reference_is_not_trusted_gate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "fabricated-message",
                    revision,
                    user_message_ref="chat://message/model-invented",
                )

            self.assertEqual(service.kernel.load().revision, revision)

    def test_raw_python_gate_entry_rejects_agent_forged_action_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "agent-forged-authority",
                    revision,
                    user_action_ref="agent-forged://accepted",
                    source_version=context["source_version"],
                    challenge_id=context["challenge_id"],
                    challenge_revision=context["challenge_revision"],
                )

            state = service.kernel.load()
            self.assertEqual(state.revision, revision)
            self.assertEqual(state.gate_status["G0"], "user-reviewable")
            self.assertNotIn("gate/G0/confirmation", state.artifact_heads)

    def test_gate_confirmation_rejects_action_and_message_double_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "double-identity",
                    revision,
                    user_action_ref="host-elicitation://claimed-action",
                    user_message_ref="chat://message/claimed-message",
                    source_version=context["source_version"],
                    challenge_id=context["challenge_id"],
                    challenge_revision=context["challenge_revision"],
                )

            self.assertEqual(service.kernel.load().revision, revision)

    def test_host_confirmation_is_bound_to_current_g0_challenge_and_consumed_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            consumed_before = len(
                service.kernel.load().consumed_user_confirmations
            )

            confirmed = service.confirm_g0(
                "host-confirmed-g0",
                revision,
                **gate_confirmation_kwargs(context),
            )

            self.assertEqual(confirmed.gate_status["G0"], "passed")
            self.assertEqual(confirmed.gate_status["G1"], "open")
            confirmation_ref = confirmed.artifact_heads["gate/G0/confirmation"]
            confirmation = service.kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
            self.assertEqual(confirmation["source_version"], blueprint_ref)
            self.assertEqual(confirmation["challenge_id"], context["challenge_id"])
            self.assertEqual(
                confirmation["challenge_revision"], context["challenge_revision"]
            )
            self.assertEqual(
                len(confirmed.consumed_user_confirmations),
                consumed_before + 1,
            )

    def test_signed_assertion_is_bound_to_project_gate_source_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as first_temp, tempfile.TemporaryDirectory() as second_temp:
            first = ContentService.initialize(Path(first_temp), project_id="p1")
            first_revision, _first_blueprint = accepted_content(first)
            first_context = first.gate_confirmation_context("G0")
            assertion = signed_gate_assertion(first_context)

            second = ContentService.initialize(Path(second_temp), project_id="p2")
            second_revision, _second_blueprint = accepted_content(second)
            second_context = second.gate_confirmation_context("G0")

            with self.assertRaises(GateBlockedError):
                second.confirm_g0(
                    "cross-project-assertion-replay",
                    second_revision,
                    host_confirmation_assertion=assertion,
                    source_version=second_context["source_version"],
                    challenge_id=second_context["challenge_id"],
                    challenge_revision=second_context["challenge_revision"],
                )

            self.assertEqual(second.kernel.load().revision, second_revision)
            self.assertEqual(first.kernel.load().revision, first_revision)

    def test_tampered_host_assertion_is_rejected_without_business_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            assertion = signed_gate_assertion(context)
            tampered = assertion[:-1] + ("A" if assertion[-1] != "A" else "B")

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "tampered-assertion",
                    revision,
                    host_confirmation_assertion=tampered,
                    source_version=context["source_version"],
                    challenge_id=context["challenge_id"],
                    challenge_revision=context["challenge_revision"],
                )

            self.assertEqual(service.kernel.load().revision, revision)

    def test_host_assertion_identity_is_single_use_even_after_gate_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            identity_ref = "test-host-confirmation://single-use-g0"
            assertion = signed_gate_assertion(
                context, identity_ref=identity_ref
            )
            first = service.confirm_g0(
                "first-assertion-use",
                revision,
                host_confirmation_assertion=assertion,
                source_version=context["source_version"],
                challenge_id=context["challenge_id"],
                challenge_revision=context["challenge_revision"],
            )
            reopened = service.reopen_g0(
                "reopen-after-first-assertion-use",
                first.revision,
                reason="验证宿主断言不可重放",
            )
            new_context = service.gate_confirmation_context("G0")
            replay = signed_gate_assertion(
                new_context, identity_ref=identity_ref
            )

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "replayed-signed-assertion",
                    reopened.revision,
                    host_confirmation_assertion=replay,
                    source_version=new_context["source_version"],
                    challenge_id=new_context["challenge_id"],
                    challenge_revision=new_context["challenge_revision"],
                )

            self.assertEqual(service.kernel.load().revision, reopened.revision)

    def test_stale_g0_challenge_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            service.kernel.commit(
                command_id="unrelated-current-revision-change",
                expected_revision=revision,
                event_type="test.revision-advanced",
                artifact_updates={
                    "test/evidence": ("test-evidence", {"current": True})
                },
            )

            with self.assertRaises(GateBlockedError):
                service.confirm_g0(
                    "stale-g0",
                    revision + 1,
                    **gate_confirmation_kwargs(context),
                )

            self.assertEqual(service.kernel.load().revision, revision + 1)

    def test_reopen_g0_atomically_locks_and_removes_downstream_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            confirmed = service.confirm_g0(
                "host-confirmed-g0",
                revision,
                **gate_confirmation_kwargs(context),
            )
            _policy_ref, policy_state = ReleaseTargetPolicyService(
                service.kernel
            ).bind_current_policy(
                "bind-policy-for-g0-reopen-regression",
                confirmed.revision,
            )
            visual = VisualService(service.kernel)
            brief_ref = visual.register_visual_brief(
                "visual-brief",
                policy_state.revision,
                valid_visual_brief(blueprint_ref),
            )
            commands = ProjectCommandService(service.kernel)
            task_ref, task, before = commands.request_agent_action(
                "downstream-agent-task",
                service.kernel.load().revision,
                action_type="design-deck-system",
                target_refs=[brief_ref],
                instructions="制作当前内容版本的 Deck Design System。",
            )
            object_path = service.kernel.artifacts.resolve(
                ArtifactReference.parse(brief_ref)
            )["payload"]
            self.assertTrue(object_path)
            self.assertEqual(before.artifact_heads["agent/task/active"], task_ref)

            reopened = service.reopen_g0(
                "reopen-g0",
                before.revision,
                reason="恢复误用任务确认造成的越权视觉生产",
            )

            self.assertEqual(reopened.revision, before.revision + 1)
            self.assertEqual(reopened.gate_status["G0"], "user-reviewable")
            for gate in ("G1", "G2", "G3", "G4"):
                self.assertEqual(reopened.gate_status[gate], "locked")
            for slot in (
                "gate/G0/confirmation",
                "visual/brief",
                "agent/task/active",
            ):
                self.assertNotIn(slot, reopened.artifact_heads)
            invalidated_ref = reopened.artifact_heads[
                f"agent/task/{task['task_id']}"
            ]
            invalidated = service.kernel.artifacts.resolve(
                ArtifactReference.parse(invalidated_ref)
            )["payload"]
            self.assertEqual(invalidated["status"], "invalidated")
            self.assertEqual(invalidated["invalidated_by_gate"], "G0")
            self.assertEqual(
                service.kernel.artifacts.resolve(
                    ArtifactReference.parse(brief_ref)
                )["payload"]["content_blueprint_ref"],
                blueprint_ref,
            )

    def test_republishing_content_atomically_invalidates_current_visual_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            context = service.gate_confirmation_context("G0")
            confirmed = service.confirm_g0(
                "host-confirmed-g0",
                revision,
                **gate_confirmation_kwargs(context),
            )
            _policy_ref, policy_state = ReleaseTargetPolicyService(
                service.kernel
            ).bind_current_policy(
                "bind-policy-for-content-republish-regression",
                confirmed.revision,
            )
            visual = VisualService(service.kernel)
            visual.register_visual_brief(
                "visual-brief-before-content-change",
                policy_state.revision,
                valid_visual_brief(blueprint_ref),
            )
            commands = ProjectCommandService(service.kernel)
            _task_ref, task, _task_state = commands.request_agent_action(
                "visual-task-before-content-change",
                service.kernel.load().revision,
                action_type="design-deck-system",
                target_refs=[
                    service.kernel.load().artifact_heads["visual/brief"]
                ],
                instructions="制作当前内容版本的 Deck Design System。",
            )
            before = service.kernel.load()

            with self.assertRaises(ContentWorkflowError) as caught:
                service.accept_content(
                    "accept-current-content-again",
                    before.revision,
                )

            self.assertEqual(
                caught.exception.code, "CONTENT_BATCH_PLAN_NOT_CONFIRMED"
            )
            self.assertEqual(service.kernel.load(), before)
            self.assertIn("gate/G0/confirmation", before.artifact_heads)
            self.assertIn("visual/brief", before.artifact_heads)
            self.assertEqual(
                before.artifact_heads["agent/task/active"],
                before.artifact_heads[f"agent/task/{task['task_id']}"],
            )

    def test_g0_can_be_reopened_again_after_a_new_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, _blueprint_ref = accepted_content(service)
            first_context = service.gate_confirmation_context("G0")
            first = service.confirm_g0(
                "first-confirmation",
                revision,
                **gate_confirmation_kwargs(first_context),
            )
            reopened = service.reopen_g0(
                "first-reopen",
                first.revision,
                reason="第一次内容回退",
            )
            second_context = service.gate_confirmation_context("G0")
            second = service.confirm_g0(
                "second-confirmation",
                reopened.revision,
                **gate_confirmation_kwargs(second_context),
            )

            reopened_again = service.reopen_g0(
                "second-reopen",
                second.revision,
                reason="第二次内容回退",
            )

            self.assertEqual(reopened_again.gate_status["G0"], "user-reviewable")
            self.assertEqual(reopened_again.revision, second.revision + 1)


if __name__ == "__main__":
    unittest.main()
