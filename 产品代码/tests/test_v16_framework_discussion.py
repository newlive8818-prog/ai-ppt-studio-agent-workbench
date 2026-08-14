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
from dataclasses import replace
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
    issue_content_framework_reset,
)
from ai_ppt_studio.errors import (
    ConfirmationTransactionError,
    ContentWorkflowError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.gates import issue_gate_mutation
from ai_ppt_studio.kernel.transactions import (
    CONFIRMATION_LEDGER_KIND,
    CONFIRMATION_LEDGER_SLOT,
)
from ai_ppt_studio.json_io import atomic_write_json


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

    def _filesystem_snapshot(self) -> dict[Path, bytes]:
        return {
            path.relative_to(self.kernel.project_root): path.read_bytes()
            for root in (
                self.kernel.artifacts.objects_root,
                self.kernel.events_root,
                self.kernel.state_path.parent,
            )
            if root.exists()
            for path in (root.rglob("*.json") if root.is_dir() else (root,))
        }

    def _rewrite_as_legacy_epoch_state(self, *, keep_legacy_ledger: bool) -> None:
        """Rewrite modern fixtures into the exact pre-epoch on-disk shape."""

        state = self.kernel.load()
        rewritten_heads = dict(state.artifact_heads)
        for event_path in sorted(self.kernel.events_root.glob("r*.json")):
            event = json.loads(event_path.read_text(encoding="utf-8"))
            heads = dict(event["artifact_heads"])
            ledger_ref = heads.get(CONFIRMATION_LEDGER_SLOT, "")
            if ledger_ref and keep_legacy_ledger:
                payload = dict(
                    self.kernel.artifacts.resolve(
                        ArtifactReference.parse(ledger_ref)
                    )["payload"]
                )
                payload.pop("framework_reset_revision", None)
                legacy_ref = str(
                    self.kernel.artifacts.put(CONFIRMATION_LEDGER_KIND, payload)
                )
                heads[CONFIRMATION_LEDGER_SLOT] = legacy_ref
                if event["revision"] == state.revision:
                    rewritten_heads[CONFIRMATION_LEDGER_SLOT] = legacy_ref
            else:
                heads.pop(CONFIRMATION_LEDGER_SLOT, None)
                if event["revision"] == state.revision:
                    rewritten_heads.pop(CONFIRMATION_LEDGER_SLOT, None)
            event["artifact_heads"] = heads
            atomic_write_json(event_path, event)
        atomic_write_json(
            self.kernel.state_path,
            replace(state, artifact_heads=rewritten_heads).as_dict(),
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

    def test_framework_reset_epoch_survives_confirmation_and_identical_reset(self) -> None:
        framework_ref, first_reset = self._save()

        self.assertIn(CONFIRMATION_LEDGER_SLOT, first_reset.artifact_heads)
        first_epoch = self.kernel.current_framework_reset_revision()
        self.assertEqual(first_epoch, first_reset.revision)

        self._confirm(framework_ref)
        self.assertEqual(
            self.kernel.current_framework_reset_revision(),
            first_epoch,
        )
        self._authorize(framework_ref)
        self.assertEqual(
            self.kernel.current_framework_reset_revision(),
            first_epoch,
        )

        same_ref, second_reset = self.service.save_draft(
            command_id="identical-framework-reset-epoch",
            expected_revision=self.kernel.load().revision,
            payload=valid_framework(self.mission_confirmation_ref),
        )

        self.assertEqual(same_ref, framework_ref)
        self.assertEqual(
            self.kernel.current_framework_reset_revision(),
            second_reset.revision,
        )
        self.assertGreater(second_reset.revision, first_epoch)

    def test_legacy_framework_without_ledger_migrates_on_save_draft(self) -> None:
        self._save()
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=False)
        legacy = self.kernel.load()
        self.assertNotIn(CONFIRMATION_LEDGER_SLOT, legacy.artifact_heads)

        _ref, migrated = self.service.save_draft(
            command_id="migrate-legacy-framework-without-ledger",
            expected_revision=legacy.revision,
            payload=valid_framework(self.mission_confirmation_ref, version=2),
        )

        self.assertEqual(
            self.kernel.current_framework_reset_revision(), migrated.revision
        )
        ledger = self.kernel.artifacts.resolve(
            ArtifactReference.parse(
                migrated.artifact_heads[CONFIRMATION_LEDGER_SLOT]
            )
        )["payload"]
        self.assertEqual(ledger["framework_reset_revision"], migrated.revision)

    def test_legacy_authorized_chain_without_ledger_migrates_trust_history(self) -> None:
        framework_ref, _state = self._save()
        confirmation_ref, _state = self._confirm(framework_ref)
        authorization_ref, _state = self._authorize(framework_ref)
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=False)
        legacy = self.kernel.load()

        migrated = self.kernel.commit(
            command_id="migrate-authorized-chain-without-ledger",
            expected_revision=legacy.revision,
            event_type="test.authorized-legacy-chain-migrated",
            artifact_updates={
                "test/migration-marker": ("migration-marker", {"ok": True})
            },
        )

        ledger = self.kernel.artifacts.resolve(
            ArtifactReference.parse(
                migrated.artifact_heads[CONFIRMATION_LEDGER_SLOT]
            )
        )["payload"]
        self.assertIn(confirmation_ref, ledger["artifact_bindings"].values())
        self.assertIn(authorization_ref, ledger["artifact_bindings"].values())
        from ai_ppt_studio.application.content_service import (
            require_full_deck_expansion_authorization,
        )
        self.assertEqual(
            require_full_deck_expansion_authorization(self.kernel),
            {
                "framework_ref": framework_ref,
                "framework_confirmation_ref": confirmation_ref,
                "full_deck_expansion_authorization_ref": authorization_ref,
            },
        )

    def test_legacy_ledger_without_epoch_migrates_on_ordinary_commit(self) -> None:
        framework_ref, _state = self._save()
        self._confirm(framework_ref)
        self._authorize(framework_ref)
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=True)
        legacy = self.kernel.load()
        legacy_revision = legacy.revision

        migrated = self.kernel.commit(
            command_id="migrate-legacy-ledger-on-ordinary-commit",
            expected_revision=legacy_revision,
            event_type="test.legacy-ledger-migrated",
            artifact_updates={
                "test/migration-marker": ("migration-marker", {"ok": True})
            },
        )

        self.assertEqual(
            self.kernel.current_framework_reset_revision(),
            3,
        )
        ledger = self.kernel.artifacts.resolve(
            ArtifactReference.parse(
                migrated.artifact_heads[CONFIRMATION_LEDGER_SLOT]
            )
        )["payload"]
        self.assertEqual(ledger["framework_reset_revision"], 3)

    def test_legacy_ledger_missing_consumed_identity_rejects_zero_write(self) -> None:
        framework_ref, _state = self._save()
        self._confirm(framework_ref)
        self._authorize(framework_ref)
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=True)
        state = self.kernel.load()
        ledger_ref = state.artifact_heads[CONFIRMATION_LEDGER_SLOT]
        payload = dict(self.kernel.artifacts.resolve(
            ArtifactReference.parse(ledger_ref)
        )["payload"])
        removed_identity = next(iter(payload["consumed"]))
        del payload["consumed"][removed_identity]
        incomplete_ref = str(
            self.kernel.artifacts.put(CONFIRMATION_LEDGER_KIND, payload)
        )
        rewritten = replace(
            state,
            artifact_heads={
                **state.artifact_heads,
                CONFIRMATION_LEDGER_SLOT: incomplete_ref,
            },
        )
        latest = self.kernel.events_root / f"r{state.revision:08d}.json"
        event = json.loads(latest.read_text(encoding="utf-8"))
        event["artifact_heads"] = dict(rewritten.artifact_heads)
        atomic_write_json(latest, event)
        atomic_write_json(self.kernel.state_path, rewritten.as_dict())
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError) as raised:
            self.kernel.commit(
                command_id="reject-incomplete-legacy-consumed",
                expected_revision=state.revision,
                event_type="test.must-not-migrate",
                artifact_updates={"test/no-write": ("marker", {"x": 1})},
            )

        self.assertEqual(raised.exception.code, "CONFIRMATION_HISTORY_CORRUPT")
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_legacy_epoch_inference_rejects_ambiguous_history_zero_write(self) -> None:
        self._save()
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=False)
        latest = self.kernel.events_root / f"r{self.kernel.load().revision:08d}.json"
        event = json.loads(latest.read_text(encoding="utf-8"))
        event["transaction_id"] = "not-the-state-transaction"
        atomic_write_json(latest, event)
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError) as raised:
            self.kernel.commit(
                command_id="reject-ambiguous-legacy-history",
                expected_revision=self.kernel.load().revision,
                event_type="test.must-not-write",
                artifact_updates={"test/no-write": ("marker", {"x": 1})},
            )

        self.assertEqual(raised.exception.code, "CONFIRMATION_HISTORY_CORRUPT")
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_legacy_epoch_inference_rejects_tampered_reset_event_type(self) -> None:
        self._save()
        self._rewrite_as_legacy_epoch_state(keep_legacy_ledger=False)
        reset_event = self.kernel.events_root / "r00000003.json"
        event = json.loads(reset_event.read_text(encoding="utf-8"))
        event["event_type"] = "test.disguised-framework-reset"
        atomic_write_json(reset_event, event)
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError) as raised:
            self.kernel.commit(
                command_id="reject-tampered-legacy-reset-type",
                expected_revision=self.kernel.load().revision,
                event_type="test.must-not-write",
                artifact_updates={"test/no-write": ("marker", {"x": 1})},
            )

        self.assertEqual(raised.exception.code, "CONFIRMATION_HISTORY_CORRUPT")
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_business_commit_cannot_update_or_remove_confirmation_ledger(self) -> None:
        self._save()
        before = self._filesystem_snapshot()
        state = self.kernel.load()

        attempts = (
            {
                "artifact_updates": {
                    CONFIRMATION_LEDGER_SLOT: (
                        "confirmation-consumption-ledger",
                        {
                            "consumed": {},
                            "artifact_bindings": {},
                            "framework_reset_revision": 0,
                        },
                    )
                }
            },
            {"artifact_updates": {}, "artifact_removals": (CONFIRMATION_LEDGER_SLOT,)},
        )
        for index, changes in enumerate(attempts):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.kernel.commit(
                    command_id=f"tamper-kernel-ledger-{index}",
                    expected_revision=state.revision,
                    event_type="test.tamper-kernel-ledger",
                    **changes,
                )
            self.assertEqual(self._filesystem_snapshot(), before)

    def test_missing_or_malformed_framework_epoch_fails_closed(self) -> None:
        self._save()
        state = self.kernel.load()
        without_ledger = replace(
            state,
            artifact_heads={
                slot: reference
                for slot, reference in state.artifact_heads.items()
                if slot != CONFIRMATION_LEDGER_SLOT
            },
        )
        malformed_ref = str(
            self.kernel.artifacts.put(
                CONFIRMATION_LEDGER_KIND,
                [],  # type: ignore[arg-type]
            )
        )
        malformed_ledger = replace(
            state,
            artifact_heads={
                **state.artifact_heads,
                CONFIRMATION_LEDGER_SLOT: malformed_ref,
            },
        )

        for corrupted, expected_code in (
            (without_ledger, "CONFIRMATION_HISTORY_CORRUPT"),
            (malformed_ledger, "CONFIRMATION_LEDGER_CORRUPT"),
        ):
            with self.subTest(heads=corrupted.artifact_heads), patch.object(
                self.kernel,
                "load",
                return_value=corrupted,
            ), self.assertRaises(ConfirmationTransactionError) as raised:
                self.kernel.current_framework_reset_revision()
            self.assertEqual(
                raised.exception.code,
                expected_code,
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

    def test_old_challenge_after_unrelated_commit_is_rejected_zero_write(self) -> None:
        framework_ref, _state = self._save()
        stale_context = self.service.confirmation_context()
        stale_assertion = signed_assertion(stale_context)
        advanced = self.kernel.commit(
            command_id="unrelated-revision-advance",
            expected_revision=self.kernel.load().revision,
            event_type="test.unrelated-revision-advance",
            artifact_updates={
                "project/unrelated": ("project-unrelated", {"value": 1})
            },
        )
        before = self._filesystem_snapshot()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="stale-challenge-after-unrelated-commit",
                expected_revision=advanced.revision,
                source_version=framework_ref,
                challenge_id=str(stale_context["challenge_id"]),
                challenge_revision=int(stale_context["challenge_revision"]),
                host_confirmation_assertion=stale_assertion,
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self._filesystem_snapshot(), before)

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

    def test_mismatched_confirmation_binding_is_zero_write(self) -> None:
        framework_ref, _state = self._save()
        before = self.kernel.load()
        before_state_bytes = self.kernel.state_path.read_bytes()
        before_artifacts = {
            path.relative_to(self.kernel.project_root): path.read_bytes()
            for path in self.kernel.artifacts.objects_root.rglob("*.json")
        }
        before_events = {
            path.relative_to(self.kernel.project_root): path.read_bytes()
            for path in self.kernel.events_root.rglob("*.json")
        }
        payload_identity = "test-host-action://payload-identity"
        consumed_identity = "test-host-action://different-consumed-identity"
        confirmation_payload = {
            "project_id": "p1",
            "scope_kind": "content-framework-confirmation",
            "scope_id": framework_ref,
            "source_version": framework_ref,
            "evidence_refs": [framework_ref, self.mission_confirmation_ref],
            "challenge_id": "test-challenge",
            "challenge_revision": before.revision,
            "user_action_ref": payload_identity,
            "user_message_ref": "",
            "confirmation_identity_type": "host-action",
            "host_assertion_sha256": "a" * 64,
            "framework_ref": framework_ref,
            "framework_revision": before.revision,
            "challenge_identity": "test-challenge",
            "confirmed_at": "2026-08-14T00:00:00+00:00",
        }

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="mismatched-confirmation-binding",
                expected_revision=before.revision,
                event_type="test.mismatched-confirmation-binding",
                artifact_updates={
                    "content/framework-confirmation": (
                        "content-framework-confirmation",
                        confirmation_payload,
                    )
                },
                confirmation_consumptions=(
                    self.service.confirmations.confirmation_payload(
                        current=self.service.confirmation_context(),
                        source_version=framework_ref,
                        challenge_id=str(
                            self.service.confirmation_context()["challenge_id"]
                        ),
                        challenge_revision=int(
                            self.service.confirmation_context()[
                                "challenge_revision"
                            ]
                        ),
                        host_confirmation_assertion=signed_assertion(
                            self.service.confirmation_context(),
                            identity_ref=consumed_identity,
                        ),
                    )[1][0],
                ),
            )

        self.assertEqual(self.kernel.load(), before)
        self.assertEqual(self.kernel.state_path.read_bytes(), before_state_bytes)
        self.assertEqual(
            {
                path.relative_to(self.kernel.project_root): path.read_bytes()
                for path in self.kernel.artifacts.objects_root.rglob("*.json")
            },
            before_artifacts,
        )
        self.assertEqual(
            {
                path.relative_to(self.kernel.project_root): path.read_bytes()
                for path in self.kernel.events_root.rglob("*.json")
            },
            before_events,
        )

    def test_raw_fake_confirmation_consumption_is_rejected_zero_write(self) -> None:
        framework_ref, _state = self._save()
        before = self._filesystem_snapshot()
        identity = "test-host-action://raw-forgery"
        owner = f"content-framework-confirmation:{framework_ref}"
        forged = {
            "project_id": "p1",
            "scope_kind": "content-framework-confirmation",
            "scope_id": framework_ref,
            "source_version": framework_ref,
            "evidence_refs": [framework_ref, self.mission_confirmation_ref],
            "challenge_id": "forged",
            "challenge_revision": self.kernel.load().revision,
            "user_action_ref": identity,
            "user_message_ref": "",
            "confirmation_identity_type": "host-action",
            "host_assertion_sha256": "f" * 64,
        }

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="raw-fake-confirmation-consumption",
                expected_revision=self.kernel.load().revision,
                event_type="test.raw-fake-confirmation-consumption",
                artifact_updates={
                    "content/framework-confirmation": (
                        "content-framework-confirmation",
                        forged,
                    )
                },
                confirmation_consumptions=((identity, owner),),
            )

        self.assertEqual(self._filesystem_snapshot(), before)

    def test_valid_confirmation_capability_cannot_be_cloned_or_mutated(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        _payload, consumptions = self.service.confirmations.confirmation_payload(
            current=context,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        capability = consumptions[0]
        before = self._filesystem_snapshot()

        with self.assertRaises((TypeError, AttributeError)):
            replace(capability, identity="test-host-action://cloned-forgery")
        with self.assertRaises((TypeError, AttributeError)):
            capability.identity = "test-host-action://mutated-forgery"
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_valid_capability_cannot_bind_a_tampered_scoped_payload(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        payload, consumptions = self.service.confirmations.confirmation_payload(
            current=context,
            source_version=framework_ref,
            challenge_id=str(context["challenge_id"]),
            challenge_revision=int(context["challenge_revision"]),
            host_confirmation_assertion=signed_assertion(context),
        )
        tampered = {**payload, "host_assertion_sha256": "f" * 64}
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="tampered-scoped-payload",
                expected_revision=self.kernel.load().revision,
                event_type="test.tampered-scoped-payload",
                artifact_updates={
                    "content/framework-confirmation": (
                        "content-framework-confirmation",
                        tampered,
                    )
                },
                confirmation_consumptions=consumptions,
            )

        self.assertEqual(self._filesystem_snapshot(), before)

    def test_direct_policy_cannot_mint_framework_reset(self) -> None:
        before = self._filesystem_snapshot()
        with self.assertRaises(AttributeError):
            self.service.confirmations.content_framework_reset()
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_reset_capability_is_bound_to_exact_framework_payload(self) -> None:
        normalized = valid_framework(self.mission_confirmation_ref)
        reset = self.service._framework_reset_mutation(normalized)
        before = self._filesystem_snapshot()
        invalid_payload = {
            **normalized,
            "mission_confirmation_ref": (
                "artifact://mission-confirmation/" + "f" * 64
            ),
        }

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="reset-with-wrong-framework-payload",
                expected_revision=self.kernel.load().revision,
                event_type="test.reset-with-wrong-framework-payload",
                artifact_updates={
                    "content/framework-draft": (
                        "content-framework-draft",
                        invalid_payload,
                    )
                },
                content_framework_reset=reset,
            )

        self.assertEqual(self._filesystem_snapshot(), before)

    def test_direct_issuer_cannot_reset_with_invalid_framework_payload(self) -> None:
        invalid = {
            **valid_framework(self.mission_confirmation_ref),
            "unvalidated_extra": "must not survive normalization",
        }
        framework_ref = str(
            self.kernel.artifacts.reference_for(
                "content-framework-draft", invalid
            )
        )
        reset = issue_content_framework_reset(
            revision=self.kernel.load().revision,
            framework_ref=framework_ref,
            mission_confirmation_ref=self.mission_confirmation_ref,
        )
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="direct-issuer-invalid-framework-reset",
                expected_revision=self.kernel.load().revision,
                event_type="test.direct-issuer-invalid-framework-reset",
                artifact_updates={
                    "content/framework-draft": (
                        "content-framework-draft",
                        invalid,
                    )
                },
                content_framework_reset=reset,
            )

        self.assertEqual(self._filesystem_snapshot(), before)

    def test_direct_issuer_cannot_reset_with_stale_mission(self) -> None:
        stale_mission_ref = self.mission_confirmation_ref
        content = ContentService(self.kernel)
        new_draft_ref = content.save_mission_draft(
            "new-mission-before-stale-reset",
            self.kernel.load().revision,
            {
                "topic": "经营一体化方案 v2",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准新版联合验证",
            },
        )
        self.mission_confirmation_ref = content.confirm_mission(
            "confirm-new-mission-before-stale-reset",
            self.kernel.load().revision,
            mission_draft_ref=new_draft_ref,
            material_mode="no-materials-confirmed",
            material_inventory_ref="",
            user_action_ref="test-user-action://new-mission",
            user_message_ref="",
        )
        stale = valid_framework(stale_mission_ref)
        framework_ref = str(
            self.kernel.artifacts.reference_for(
                "content-framework-draft", stale
            )
        )
        reset = issue_content_framework_reset(
            revision=self.kernel.load().revision,
            framework_ref=framework_ref,
            mission_confirmation_ref=stale_mission_ref,
        )
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="direct-issuer-stale-mission-reset",
                expected_revision=self.kernel.load().revision,
                event_type="test.direct-issuer-stale-mission-reset",
                artifact_updates={
                    "content/framework-draft": (
                        "content-framework-draft",
                        stale,
                    )
                },
                content_framework_reset=reset,
            )

        self.assertEqual(self._filesystem_snapshot(), before)

    def test_forged_current_mission_confirmation_cannot_authorize_reset(self) -> None:
        draft_ref = self.kernel.load().artifact_heads["mission/draft"]
        forged_mission_ref = str(
            self.kernel.artifacts.put(
                "mission-confirmation",
                {"forged": True},
            )
        )
        state = self.kernel.commit(
            command_id="install-forged-mission-confirmation",
            expected_revision=self.kernel.load().revision,
            event_type="test.install-forged-mission-confirmation",
            artifact_updates={
                "mission/confirmation": (
                    "mission-confirmation",
                    {"forged": True},
                )
            },
        )
        self.assertEqual(
            state.artifact_heads["mission/confirmation"], forged_mission_ref
        )
        framework = valid_framework(forged_mission_ref)
        framework_ref = str(
            self.kernel.artifacts.reference_for(
                "content-framework-draft", framework
            )
        )
        reset = issue_content_framework_reset(
            revision=state.revision,
            framework_ref=framework_ref,
            mission_confirmation_ref=forged_mission_ref,
        )
        before = self._filesystem_snapshot()

        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="reset-with-forged-mission-confirmation",
                expected_revision=state.revision,
                event_type="test.reset-with-forged-mission-confirmation",
                artifact_updates={
                    "content/framework-draft": (
                        "content-framework-draft",
                        framework,
                    )
                },
                content_framework_reset=reset,
            )

        self.assertEqual(self._filesystem_snapshot(), before)
        self.assertEqual(
            self.kernel.load().artifact_heads["mission/draft"], draft_ref
        )

    def test_bare_framework_reset_is_rejected_zero_write(self) -> None:
        before = self._filesystem_snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="bare-framework-reset",
                expected_revision=self.kernel.load().revision,
                event_type="test.bare-framework-reset",
                artifact_updates={},
                content_framework_reset=True,
            )
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_corrupt_confirmation_history_fails_closed_zero_write(self) -> None:
        old_ref = self.kernel.load().artifact_heads["mission/confirmation"]
        content = ContentService(self.kernel)
        new_draft_ref = content.save_mission_draft(
            "corrupt-history-replacement-draft",
            self.kernel.load().revision,
            {
                "topic": "经营一体化方案 v2",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准二期联合验证",
            },
        )
        self.mission_confirmation_ref = content.confirm_mission(
            "corrupt-history-replacement-confirmation",
            self.kernel.load().revision,
            mission_draft_ref=new_draft_ref,
            material_mode="no-materials-confirmed",
            material_inventory_ref="",
            user_action_ref="test-user-action://mission-confirmed-v2",
            user_message_ref="",
        )
        framework_ref, _state = self._save()
        old_path = self.kernel.artifacts.path_for(ArtifactReference.parse(old_ref))
        old_path.write_text("{corrupt", encoding="utf-8")
        before = self._filesystem_snapshot()
        context = self.service.confirmation_context()

        with self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="reuse-with-corrupt-history",
                expected_revision=self.kernel.load().revision,
                source_version=framework_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self._filesystem_snapshot(), before)

    def test_typed_kernel_confirmation_failure_maps_without_message_matching(self) -> None:
        framework_ref, _state = self._save()
        context = self.service.confirmation_context()
        before = self._filesystem_snapshot()

        with patch.object(
            self.kernel,
            "commit",
            side_effect=ConfirmationTransactionError(
                "CONFIRMATION_HISTORY_CORRUPT",
                "opaque typed failure",
            ),
        ), self.assertRaises(ContentWorkflowError) as raised:
            self.service.confirm_framework(
                command_id="typed-confirmation-failure",
                expected_revision=self.kernel.load().revision,
                source_version=framework_ref,
                challenge_id=str(context["challenge_id"]),
                challenge_revision=int(context["challenge_revision"]),
                host_confirmation_assertion=signed_assertion(context),
            )

        self.assertEqual(raised.exception.code, "CONTENT_REVIEW_CONFLICT")
        self.assertEqual(self._filesystem_snapshot(), before)

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
