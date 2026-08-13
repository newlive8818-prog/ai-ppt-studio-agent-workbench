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

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.framework_discussion_service import (
    FrameworkDiscussionService,
)
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.errors import ContentWorkflowError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.gates import issue_gate_mutation


TEST_SECRET = "test-only-scoped-confirmation-secret-32-bytes-minimum"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def signed_assertion(
    context: dict[str, object],
    *,
    identity_type: str = "host-action",
    identity_ref: str | None = None,
    overrides: dict[str, object] | None = None,
) -> str:
    issued_at = int(time.time())
    payload = {
        "project_id": context["project_id"],
        "project_root": context["project_root"],
        "scope_kind": context["scope_kind"],
        "scope_id": context["scope_id"],
        "source_version": context["source_version"],
        "evidence_refs": context["evidence_refs"],
        "challenge_id": context["challenge_id"],
        "challenge_revision": context["challenge_revision"],
        "identity_type": identity_type,
        "identity_ref": identity_ref or f"test-host-action://{uuid.uuid4()}",
        "nonce": str(uuid.uuid4()),
        "issued_at": issued_at,
        "expires_at": issued_at + 120,
    }
    payload.update(overrides or {})
    payload_segment = _encode(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        TEST_SECRET.encode("utf-8"),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"v1.{payload_segment}.{_encode(signature)}"


def valid_framework(mission_confirmation_ref: str, *, version: int = 1) -> dict:
    return {
        "framework_id": f"framework-v{version}",
        "mission_confirmation_ref": mission_confirmation_ref,
        "core_proposition": "先证明经营断点，再确认一期联合验证路径。",
        "persuasion_path": ["形成问题共识", "建立方案可信度", "促成一期行动"],
        "chapters": [
            {
                "chapter_id": "C01",
                "title": "为什么现在需要改变",
                "task": "把分散系统问题转成经营判断。",
                "expected_judgment": "现状需要跨系统治理。",
                "transition": "从问题共识进入建设原则。",
            }
        ],
        "structural_risks": ["现有材料尚不能证明定量收益。"],
        "highest_impact_question": "是否将一期决策作为全篇收束点？",
        "status": "discussion",
    }


class FrameworkDiscussionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.secret = patch.dict(
            os.environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        )
        self.secret.start()
        self.addCleanup(self.secret.stop)
        content = ContentService.initialize(Path(self.temp.name), project_id="p1")
        draft_ref = content.save_mission_draft(
            "mission-draft",
            0,
            {
                "topic": "经营一体化方案",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准一期联合验证",
            },
        )
        self.mission_confirmation_ref = content.confirm_mission(
            "mission-confirm",
            1,
            mission_draft_ref=draft_ref,
            material_mode="no-materials-confirmed",
            material_inventory_ref="",
            user_action_ref="test-user-action://mission-confirmed",
            user_message_ref="",
        )
        self.kernel = content.kernel
        self.service = FrameworkDiscussionService(self.kernel)

    def _save(self, *, version: int = 1) -> tuple[str, object]:
        state = self.kernel.load()
        return self.service.save_draft(
            command_id=f"framework-save-{version}",
            expected_revision=state.revision,
            payload=valid_framework(
                self.mission_confirmation_ref,
                version=version,
            ),
        )

    def _confirm(self, framework_ref: str, *, identity_ref: str = ""):
        context = self.service.confirmation_context()
        return self.service.confirm_framework(
            command_id=f"framework-confirm-{uuid.uuid4()}",
            expected_revision=self.kernel.load().revision,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context,
                identity_ref=identity_ref or None,
            ),
        )

    def _authorize(self, framework_ref: str, *, identity_ref: str = ""):
        context = self.service.expansion_authorization_context()
        return self.service.authorize_full_deck_expansion(
            command_id=f"framework-authorize-{uuid.uuid4()}",
            expected_revision=self.kernel.load().revision,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context,
                identity_ref=identity_ref or None,
            ),
        )

    def test_save_draft_keeps_g0_open_and_exposes_no_page_content(self) -> None:
        framework_ref, state = self._save()

        self.assertEqual(state.gate_status["G0"], "open")
        self.assertEqual(
            state.artifact_heads["content/framework-draft"], framework_ref
        )
        payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(framework_ref)
        )["payload"]
        for forbidden in (
            "slides",
            "slide_titles",
            "visible_copy",
            "speaker_notes",
            "materials",
        ):
            self.assertNotIn(forbidden, payload)
        self.assertFalse(
            any(
                slot.startswith("content/")
                and slot
                not in {
                    "content/framework-draft",
                }
                for slot in state.artifact_heads
            )
        )

    def test_draft_must_bind_the_current_mission_confirmation(self) -> None:
        before = self.kernel.load()
        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.save_draft(
                command_id="wrong-mission-binding",
                expected_revision=before.revision,
                payload=valid_framework(
                    "artifact://mission-confirmation/" + "f" * 64
                ),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.kernel.load(), before)

    def test_framework_and_expansion_use_distinct_authoritative_scopes(self) -> None:
        framework_ref, _state = self._save()
        confirmation_context = self.service.confirmation_context()
        self.assertEqual(
            confirmation_context["scope_kind"],
            "content-framework-confirmation",
        )
        self.assertEqual(confirmation_context["scope_id"], framework_ref)
        self.assertEqual(confirmation_context["source_version"], framework_ref)
        self.assertEqual(
            confirmation_context["evidence_refs"],
            [framework_ref, self.mission_confirmation_ref],
        )
        confirmation_ref, _state = self._confirm(framework_ref)

        expansion_context = self.service.expansion_authorization_context()
        self.assertEqual(
            expansion_context["scope_kind"],
            "content-full-deck-expansion-authorization",
        )
        self.assertEqual(expansion_context["scope_id"], confirmation_ref)
        self.assertEqual(expansion_context["source_version"], framework_ref)
        self.assertEqual(
            expansion_context["evidence_refs"],
            [
                framework_ref,
                confirmation_ref,
                self.mission_confirmation_ref,
            ],
        )
        self.assertNotEqual(
            expansion_context["challenge_id"],
            confirmation_context["challenge_id"],
        )

    def test_confirm_current_framework_and_authorize_expansion(self) -> None:
        framework_ref, _state = self._save()
        confirmation_ref, confirmed = self._confirm(framework_ref)
        self.assertEqual(
            confirmed.artifact_heads["content/framework-confirmation"],
            confirmation_ref,
        )
        confirmation = self.kernel.artifacts.resolve(
            ArtifactReference.parse(confirmation_ref)
        )["payload"]
        self.assertEqual(confirmation["framework_ref"], framework_ref)

        authorization_ref, authorized = self._authorize(framework_ref)
        self.assertEqual(
            authorized.artifact_heads[
                "content/full-deck-expansion-authorization"
            ],
            authorization_ref,
        )
        authorization = self.kernel.artifacts.resolve(
            ArtifactReference.parse(authorization_ref)
        )["payload"]
        self.assertEqual(authorization["framework_ref"], framework_ref)
        self.assertEqual(
            authorization["framework_confirmation_ref"], confirmation_ref
        )
        self.assertEqual(authorized.gate_status["G0"], "open")

    def test_stale_framework_and_early_expansion_fail_without_writes(self) -> None:
        framework_ref, _state = self._save()
        before = self.kernel.load()
        context = self.service.confirmation_context()
        stale_ref = "artifact://content-framework-draft/" + "e" * 64
        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="stale-framework",
                expected_revision=before.revision,
                source_version=stale_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )
        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.kernel.load(), before)

        with self.assertRaises(ContentWorkflowError) as early:
            self.service.expansion_authorization_context()
        self.assertEqual(
            early.exception.code,
            "CONTENT_FRAMEWORK_NOT_CONFIRMED",
        )
        self.assertEqual(self.kernel.load(), before)
        self.assertEqual(
            before.artifact_heads["content/framework-draft"], framework_ref
        )

    def test_framework_identity_cannot_be_reused_for_expansion(self) -> None:
        framework_ref, _state = self._save()
        identity = "test-host-action://framework-only"
        self._confirm(framework_ref, identity_ref=identity)
        before = self.kernel.load()
        context = self.service.expansion_authorization_context()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.authorize_full_deck_expansion(
                command_id="cross-scope-reuse",
                expected_revision=before.revision,
                source_version=framework_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    context,
                    identity_ref=identity,
                ),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.kernel.load(), before)
        self.assertNotIn(
            "content/full-deck-expansion-authorization",
            before.artifact_heads,
        )

    def test_existing_mission_confirmation_identity_cannot_be_reused(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="reuse-mission-identity",
                expected_revision=before.revision,
                source_version=framework_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    context,
                    identity_ref="test-user-action://mission-confirmed",
                ),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.kernel.load(), before)
        self.assertNotIn("content/framework-confirmation", before.artifact_heads)

    def test_superseded_mission_confirmation_identity_cannot_be_reused(self) -> None:
        old_identity = "test-user-action://mission-confirmed"
        content = ContentService(self.kernel)
        new_draft_ref = content.save_mission_draft(
            "replacement-mission-draft",
            self.kernel.load().revision,
            {
                "topic": "经营一体化方案 v2",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准二期联合验证",
            },
        )
        self.mission_confirmation_ref = content.confirm_mission(
            "replacement-mission-confirm",
            self.kernel.load().revision,
            mission_draft_ref=new_draft_ref,
            material_mode="no-materials-confirmed",
            material_inventory_ref="",
            user_action_ref="test-user-action://mission-confirmed-v2",
            user_message_ref="",
        )
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError):
            self.service.confirm_framework(
                command_id="reuse-superseded-mission-identity",
                expected_revision=before.revision,
                source_version=framework_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    context,
                    identity_ref=old_identity,
                ),
            )
        self.assertEqual(self.kernel.load(), before)

    def test_current_and_superseded_gate_confirmation_identities_are_rejected(self) -> None:
        old_identity = "chat://message/old-g0"
        current_identity = "chat://message/current-g0"
        self.kernel.commit(
            command_id="old-gate-confirmation",
            expected_revision=self.kernel.load().revision,
            event_type="test.old-gate-confirmation",
            artifact_updates={
                "gate/G0/confirmation": (
                    "g0-confirmation",
                    {"gate": "G0", "user_message_ref": old_identity},
                )
            },
        )
        self.kernel.commit(
            command_id="current-gate-confirmation",
            expected_revision=self.kernel.load().revision,
            event_type="test.current-gate-confirmation",
            artifact_updates={
                "gate/G0/confirmation": (
                    "g0-confirmation",
                    {"gate": "G0", "user_message_ref": current_identity},
                )
            },
        )
        framework_ref, _state = self._save()
        for index, identity in enumerate((old_identity, current_identity)):
            context = self.service.confirmation_context()
            before = self.kernel.load()
            with self.subTest(identity=identity), self.assertRaises(
                ContentWorkflowError
            ):
                self.service.confirm_framework(
                    command_id=f"reuse-gate-identity-{index}",
                    expected_revision=before.revision,
                    source_version=framework_ref,
                    challenge_id=str(context["challenge_id"]),
                    challenge_revision=int(context["challenge_revision"]),
                    host_confirmation_assertion=signed_assertion(
                        context,
                        identity_type="verified-message",
                        identity_ref=identity,
                    ),
                )
            self.assertEqual(self.kernel.load(), before)

    def test_duplicate_confirmation_command_cannot_bypass_identity_consumption(self) -> None:
        framework_ref, _state = self._save()
        identity = "test-host-action://shared-command"
        context = self.service.confirmation_context()
        self.service.confirm_framework(
            command_id="shared-command",
            expected_revision=self.kernel.load().revision,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context,
                identity_ref=identity,
            ),
        )
        expansion_context = self.service.expansion_authorization_context()
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError):
            self.service.authorize_full_deck_expansion(
                command_id="shared-command",
                expected_revision=before.revision,
                source_version=framework_ref,
                challenge_id=str(expansion_context["challenge_id"]),
                challenge_revision=int(
                    expansion_context["challenge_revision"]
                ),
                host_confirmation_assertion=signed_assertion(
                    expansion_context,
                    identity_ref=identity,
                ),
            )
        self.assertEqual(self.kernel.load(), before)

    def test_same_command_and_identity_confirmation_replay_is_rejected(self) -> None:
        framework_ref, _state = self._save()
        identity = "test-host-action://same-command-replay"
        context = self.service.confirmation_context()
        self.service.confirm_framework(
            command_id="same-confirmation-command",
            expected_revision=self.kernel.load().revision,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context,
                identity_ref=identity,
            ),
        )
        before = self.kernel.load()
        replay_context = self.service.confirmation_context()

        with self.assertRaises(ContentWorkflowError):
            self.service.confirm_framework(
                command_id="same-confirmation-command",
                expected_revision=before.revision,
                source_version=framework_ref,
                challenge_id=str(replay_context["challenge_id"]),
                challenge_revision=int(replay_context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(
                    replay_context,
                    identity_ref=identity,
                ),
            )
        self.assertEqual(self.kernel.load(), before)

    def test_forged_framework_confirmation_head_cannot_authorize_expansion(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        forged = {
            "project_id": "wrong-project",
            "scope_kind": "content-review-batch-submission",
            "scope_id": "wrong-scope",
            "source_version": framework_ref,
            "evidence_refs": [framework_ref, self.mission_confirmation_ref],
            "challenge_id": str(context["challenge_id"]),
            "challenge_revision": int(context["challenge_revision"]),
            "user_action_ref": "test-host-action://forged",
            "user_message_ref": "",
            "confirmation_identity_type": "host-action",
            "host_assertion_sha256": "a" * 64,
            "framework_ref": framework_ref,
            "framework_revision": int(context["challenge_revision"]),
            "challenge_identity": str(context["challenge_id"]),
            "confirmed_at": "2026-08-14T00:00:00+00:00",
        }
        self.kernel.commit(
            command_id="forge-framework-confirmation-head",
            expected_revision=self.kernel.load().revision,
            event_type="test.forged-framework-confirmation",
            artifact_updates={
                "content/framework-confirmation": (
                    "content-framework-confirmation",
                    forged,
                )
            },
        )
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.expansion_authorization_context()
        self.assertEqual(
            raised.exception.code,
            "CONTENT_FRAMEWORK_NOT_CONFIRMED",
        )
        self.assertEqual(self.kernel.load(), before)

    def test_confirmation_without_atomic_identity_consumption_is_not_trusted(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        identity = "test-host-action://not-consumed"
        forged = {
            "project_id": "p1",
            "scope_kind": "content-framework-confirmation",
            "scope_id": framework_ref,
            "source_version": framework_ref,
            "evidence_refs": [framework_ref, self.mission_confirmation_ref],
            "challenge_id": str(context["challenge_id"]),
            "challenge_revision": int(context["challenge_revision"]),
            "user_action_ref": identity,
            "user_message_ref": "",
            "confirmation_identity_type": "host-action",
            "host_assertion_sha256": "a" * 64,
            "framework_ref": framework_ref,
            "framework_revision": int(context["challenge_revision"]),
            "challenge_identity": str(context["challenge_id"]),
            "confirmed_at": "2026-08-14T00:00:00+00:00",
        }
        self.kernel.commit(
            command_id="forge-unconsumed-framework-confirmation",
            expected_revision=self.kernel.load().revision,
            event_type="test.forged-unconsumed-framework-confirmation",
            artifact_updates={
                "content/framework-confirmation": (
                    "content-framework-confirmation",
                    forged,
                )
            },
        )
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError):
            self.service.expansion_authorization_context()
        self.assertEqual(self.kernel.load(), before)

    def test_consumed_identity_cannot_authenticate_a_replacement_artifact(self) -> None:
        framework_ref, _state = self._save()
        confirmation_ref, _state = self._confirm(
            framework_ref,
            identity_ref="test-host-action://real-framework-confirmation",
        )
        real_payload = dict(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["payload"]
        )
        replacement_payload = {
            **real_payload,
            "confirmed_at": "2026-08-14T23:59:59+00:00",
            "host_assertion_sha256": "f" * 64,
        }
        replacement_state = self.kernel.commit(
            command_id="replace-confirmation-with-forgery",
            expected_revision=self.kernel.load().revision,
            event_type="test.replace-confirmation-with-forgery",
            artifact_updates={
                "content/framework-confirmation": (
                    "content-framework-confirmation",
                    replacement_payload,
                )
            },
        )
        self.assertNotEqual(
            replacement_state.artifact_heads["content/framework-confirmation"],
            confirmation_ref,
        )
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError):
            self.service.expansion_authorization_context()
        self.assertEqual(self.kernel.load(), before)

    def test_new_framework_reopens_g0_and_removes_formal_page_content_heads(self) -> None:
        state = self.kernel.load()
        content_heads = {
            "content/strategy": ("presales-content-strategy", {"old": True}),
            "content/claim-map": ("claim-evidence-map", {"old": True}),
            "content/argument-map": ("deck-argument-map", {"old": True}),
            "content/draft": ("slide-draft-set", {"slides": [{"old": True}]}),
            "content/review/presales-reviewer": (
                "content-review-record",
                {"old": True},
            ),
            "content/acceptance": ("content-acceptance", {"old": True}),
            "content/blueprint": (
                "content-blueprint",
                {"slides": [{"old": True}]},
            ),
            "content/change-set": ("content-change-set", {"old": True}),
            "content/page-decisions": (
                "content-page-decision-set",
                {"old": True},
            ),
            "content/review-batch": ("content-review-batch", {"old": True}),
            "content/batch-revision-plan": (
                "content-batch-revision-plan",
                {"old": True},
            ),
            "content/batch-plan-confirmation": (
                "content-batch-plan-confirmation",
                {"old": True},
            ),
            "content/review-batch-withdrawal": (
                "content-review-batch-withdrawal",
                {"old": True},
            ),
        }
        old_refs = {
            slot: str(self.kernel.artifacts.put(kind, payload))
            for slot, (kind, payload) in content_heads.items()
        }
        legacy_state = self.kernel.commit(
            command_id="simulate-old-full-deck-state",
            expected_revision=state.revision,
            event_type="test.old-full-deck-state",
            artifact_updates=content_heads,
            gate_mutation=issue_gate_mutation(
                {"G0": "passed", "G1": "open"},
                tuple(old_refs.values()),
            ),
        )

        _framework_ref, framework_state = self.service.save_draft(
            command_id="transition-to-framework-discussion",
            expected_revision=legacy_state.revision,
            payload=valid_framework(self.mission_confirmation_ref),
        )

        self.assertEqual(framework_state.gate_status["G0"], "open")
        self.assertEqual(framework_state.gate_status["G1"], "locked")
        for slot, reference in old_refs.items():
            self.assertNotIn(slot, framework_state.artifact_heads)
            self.assertTrue(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(reference)
                )
            )

    def test_new_framework_removes_future_content_heads_but_keeps_non_content_heads(self) -> None:
        state = self.kernel.commit(
            command_id="simulate-future-content-heads",
            expected_revision=self.kernel.load().revision,
            event_type="test.future-content-heads",
            artifact_updates={
                "content/repair-plan": (
                    "content-repair-plan",
                    {"slides": [{"old": True}]},
                ),
                "content/review/custom-role": (
                    "content-review-record",
                    {"page_level": True},
                ),
                "project/non-content-proof": (
                    "project-proof",
                    {"keep": True},
                ),
            },
        )
        old_repair_ref = state.artifact_heads["content/repair-plan"]
        proof_ref = state.artifact_heads["project/non-content-proof"]

        _framework_ref, framework_state = self.service.save_draft(
            command_id="clear-future-content-heads",
            expected_revision=state.revision,
            payload=valid_framework(self.mission_confirmation_ref),
        )

        self.assertEqual(
            {
                slot
                for slot in framework_state.artifact_heads
                if slot.startswith("content/")
            },
            {"content/framework-draft"},
        )
        self.assertEqual(
            framework_state.artifact_heads["project/non-content-proof"],
            proof_ref,
        )
        self.assertTrue(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(old_repair_ref)
            )
        )

    def test_new_draft_clears_current_confirmation_and_authorization_heads(self) -> None:
        framework_ref, _state = self._save()
        confirmation_ref, _state = self._confirm(framework_ref)
        authorization_ref, _state = self._authorize(framework_ref)

        replacement_ref, state = self._save(version=2)

        self.assertNotEqual(replacement_ref, framework_ref)
        self.assertNotIn("content/framework-confirmation", state.artifact_heads)
        self.assertNotIn(
            "content/full-deck-expansion-authorization",
            state.artifact_heads,
        )
        self.assertEqual(state.gate_status["G0"], "open")
        self.assertEqual(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(confirmation_ref)
            )["kind"],
            "content-framework-confirmation",
        )
        self.assertEqual(
            self.kernel.artifacts.resolve(
                ArtifactReference.parse(authorization_ref)
            )["kind"],
            "full-deck-expansion-authorization",
        )

    def test_context_mismatches_and_invalid_hmac_are_zero_write(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        cases = (
            {
                "source_version": "artifact://content-framework-draft/"
                + "d" * 64
            },
            {"challenge_id": "wrong-challenge"},
            {"challenge_revision": int(context["challenge_revision"]) + 1},
            {
                "host_confirmation_assertion": signed_assertion(
                    context,
                    overrides={"scope_kind": "content-review-batch-submission"},
                )
            },
            {
                "host_confirmation_assertion": signed_assertion(
                    context,
                    overrides={"scope_id": "wrong-scope-id"},
                )
            },
            {"host_confirmation_assertion": "v1.invalid.invalid"},
        )
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                before = self.kernel.load()
                kwargs = {
                    "command_id": f"mismatch-{index}",
                    "expected_revision": before.revision,
                    "source_version": framework_ref,
                    "challenge_id": str(context["challenge_id"]),
                    "challenge_revision": int(context["challenge_revision"]),
                    "host_confirmation_assertion": signed_assertion(context),
                }
                kwargs.update(changes)
                with self.assertRaises(ContentWorkflowError) as raised:
                    self.service.confirm_framework(**kwargs)
                self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
                self.assertEqual(self.kernel.load(), before)

    def test_identity_replay_is_rejected_atomically_across_new_challenge(self) -> None:
        identity = "verified-message://one-time-identity"
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        self.service.confirm_framework(
            command_id="first-identity-use",
            expected_revision=self.kernel.load().revision,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(
                context,
                identity_type="verified-message",
                identity_ref=identity,
            ),
        )
        replacement_ref, _state = self._save(version=2)
        replacement_context = self.service.confirmation_context()
        before = self.kernel.load()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="replayed-identity",
                expected_revision=before.revision,
                source_version=replacement_ref,
                challenge_id=str(replacement_context["challenge_id"]),
                challenge_revision=int(
                    replacement_context["challenge_revision"]
                ),
                host_confirmation_assertion=signed_assertion(
                    replacement_context,
                    identity_type="verified-message",
                    identity_ref=identity,
                ),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self.kernel.load(), before)
        self.assertNotIn("content/framework-confirmation", before.artifact_heads)


if __name__ == "__main__":
    unittest.main()
