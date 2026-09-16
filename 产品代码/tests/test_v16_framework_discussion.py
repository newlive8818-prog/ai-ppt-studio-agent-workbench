from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_hard_gate_service import (
    ContentHardGateService,
)
from ai_ppt_studio.application.content_review.batch_service import (
    ContentReviewBatchService,
)
from ai_ppt_studio.application.content_review.decision_service import (
    ContentDecisionService,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.scoped_confirmation import (
    ConfirmationConsumption,
    ContentFrameworkResetMutation,
    issue_content_framework_reset,
)
from ai_ppt_studio.errors import (
    ConfirmationTransactionError,
    ContractValidationError,
    GateBlockedError,
    MissionNotConfirmedError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.confirmation_history import (
    CONFIRMATION_LEDGER_KIND,
    CONFIRMATION_LEDGER_SLOT,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_repair_loop import build_content as build_v22_content
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.v22_hard_gate_fixtures import semantic_checks
from tests.material_finding_fixtures import source_inventory


MISSION = {
    "topic": "经营一体化方案",
    "primary_audience": "客户决策者",
    "desired_judgment_or_action": "批准一期联合验证",
}
MATERIALS = {
    "sources": [
        {
            "source_id": "s1",
            "origin": "user-provided",
            "kind": "text",
            "locator": "inline://user-provided/s1",
            "sha256": "a" * 64,
        }
    ]
}
NOW = "2026-08-15T09:30:00+08:00"


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
    """Preserve legacy test identities while proving only current v2.2 behavior."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kernel = ProjectKernel.initialize(Path(self.temp.name), project_id="p1")
        self.mission = MissionMaterialService(self.kernel)
        self.mission_draft_ref = self.mission.save_mission_draft(
            "mission-draft", 0, MISSION
        )
        self.materials_ref = self.mission.register_materials(
            "materials", 1, source_inventory(self.kernel)
        )
        self.mission_confirmation_ref = self.mission.confirm_mission(
            "mission-confirm", 2,
            mission_draft_ref=self.mission_draft_ref,
            material_mode="materials-provided",
            material_inventory_ref=self.materials_ref,
            user_action_ref="test-user-action://mission-confirmed",
            user_message_ref="",
        )

    def _snapshot(self):
        return (
            self.kernel.load(),
            tuple(
                sorted(
                    (path.relative_to(self.kernel.project_root), path.read_bytes())
                    for root in (
                        self.kernel.artifacts.objects_root,
                        self.kernel.events_root,
                        self.kernel.state_path.parent,
                    )
                    if root.exists()
                    for path in (root.rglob("*.json") if root.is_dir() else (root,))
                )
            ),
        )

    def _review(self, source_version: str = "content-v1", slide_count: int = 1):
        blueprint_ref = build_v22_content(
            self.kernel, source_version=source_version, slide_count=slide_count
        )
        blueprint_publication_revision = self.kernel.load().revision
        gates = ContentHardGateService(self.kernel)
        gates.run_evidence_gate(
            command_id=f"evidence-pass-{source_version}",
            expected_revision=self.kernel.load().revision,
            semantic_check_results=semantic_checks("evidence", blueprint_ref),
            reviewer_mode="isolated-review-task",
        )
        gates.run_presales_reading_gate(
            command_id=f"reading-pass-{source_version}",
            expected_revision=self.kernel.load().revision,
            semantic_check_results=semantic_checks("presales-reading", blueprint_ref),
            reviewer_mode="isolated-review-task",
        )
        state = self.kernel.load()
        session_ref, session, state = ReviewSessionService(self.kernel).open_or_resume(
            command_id=f"open-review-{source_version}",
            expected_revision=state.revision,
            review_type="content-full-deck",
            target_artifact_ref=blueprint_ref,
            source_version=source_version,
            source_revision=blueprint_publication_revision,
            open_policy="foreground-if-waiting",
        )
        return blueprint_ref, session_ref, session, state

    def _submit_review(
        self, source_version: str = "content-v1", slide_count: int = 1
    ):
        blueprint_ref, session_ref, session, _state = self._review(
            source_version, slide_count
        )
        for order in range(1, slide_count + 1):
            ContentDecisionService(self.kernel).save(
                command_id=f"approve-{source_version}-{order}",
                expected_revision=self.kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version=source_version,
                slide_id=f"S{order:02d}",
                decision="approved",
                comment="",
            )
        batch_ref, batch, state = ContentReviewBatchService(self.kernel).submit(
            command_id=f"submit-{source_version}",
            expected_revision=self.kernel.load().revision,
            review_session_id=session["review_session_id"],
            source_version=source_version,
        )
        return blueprint_ref, session_ref, session, batch_ref, batch, state

    def _confirm_g0(self):
        review = self._submit_review()
        service = PresalesContentService(self.kernel)
        opened = service.open_g0_review(
            command_id="open-g0", expected_revision=self.kernel.load().revision
        )
        context = service.gate_confirmation_context()
        confirmation_kwargs = gate_confirmation_kwargs(
            context,
            identity_type="verified-message",
            identity_ref="chat://message/verified-g0-confirmed",
        )
        self._last_g0_confirmation_context = context
        self._last_g0_confirmation_kwargs = confirmation_kwargs
        confirmed = service.confirm_g0(
            command_id="confirm-g0",
            expected_revision=opened.revision,
            **confirmation_kwargs,
        )
        return review, service, opened, confirmed

    def _receipt(
        self, *, command_id: str, kind: str, session_id: str, status: str
    ) -> str:
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=self.kernel.load().revision,
            event_type="test.review-receipt-recorded",
            artifact_updates={
                f"test/receipt/{command_id}": (
                    kind,
                    {
                        "review_session_id": session_id,
                        "status": status,
                        "recorded_at": NOW,
                    },
                )
            },
        )
        return state.artifact_heads[f"test/receipt/{command_id}"]

    def _rewrite_heads(self, updates: dict[str, str]) -> None:
        state = self.kernel.load()
        heads = {**state.artifact_heads, **updates}
        atomic_write_json(
            self.kernel.state_path, replace(state, artifact_heads=heads).as_dict()
        )
        event_path = self.kernel.events_root / f"r{state.revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["artifact_heads"] = heads
        atomic_write_json(event_path, event)

    def _install_malformed_ledger(self, payload: dict) -> str:
        reference = str(self.kernel.artifacts.put(CONFIRMATION_LEDGER_KIND, payload))
        self._rewrite_heads({CONFIRMATION_LEDGER_SLOT: reference})
        return reference

    def _legacy_reset_attempt(
        self,
        *,
        payload: dict,
        claim_framework_ref: str | None = None,
        claim_mission_ref: str | None = None,
        raw_claim: object | None = None,
    ):
        state = self.kernel.load()
        candidate = str(
            self.kernel.artifacts.reference_for("content-framework-draft", payload)
        )
        claim = raw_claim or issue_content_framework_reset(
            revision=state.revision,
            framework_ref=claim_framework_ref or candidate,
            mission_confirmation_ref=claim_mission_ref or self.mission_confirmation_ref,
        )
        return self.kernel.commit(
            command_id=f"legacy-reset-{state.revision}",
            expected_revision=state.revision,
            event_type="content.framework-draft-saved",
            artifact_updates={
                "content/framework-draft": ("content-framework-draft", payload)
            },
            artifact_removals=tuple(
                slot
                for slot in state.artifact_heads
                if slot.startswith("content/") and slot != "content/framework-draft"
            ),
            content_framework_reset=claim,
        )


    def test_save_draft_keeps_g0_open_and_exposes_no_page_content(self) -> None:
        state = self.kernel.load()
        self.assertEqual(state.gate_status["G0"], "open")
        self.assertEqual(state.artifact_heads["mission/draft"], self.mission_draft_ref)
        self.assertFalse(any(slot.startswith("content/") for slot in state.artifact_heads))

    def test_framework_reset_epoch_survives_confirmation_and_identical_reset(self) -> None:
        blueprint_ref, session_ref, session, opened = self._review()
        repeated_ref, repeated, repeated_state = ReviewSessionService(
            self.kernel
        ).open_or_resume(
            command_id="repeat-open-current-review",
            expected_revision=opened.revision,
            review_type="content-full-deck",
            target_artifact_ref=blueprint_ref,
            source_version="content-v1",
            source_revision=session["revision"],
            open_policy="foreground-if-waiting",
        )
        self.assertEqual((repeated_ref, repeated), (session_ref, session))
        self.assertEqual(repeated_state.revision, opened.revision)

    def test_legacy_framework_without_ledger_migrates_on_save_draft(self) -> None:
        state = self.kernel.commit(
            command_id="ordinary-current-write",
            expected_revision=self.kernel.load().revision,
            event_type="test.ordinary-current-write",
            artifact_updates={"test/current": ("test-artifact", {"value": 1})},
        )
        self.assertNotIn(CONFIRMATION_LEDGER_SLOT, state.artifact_heads)
        self.assertNotIn("content/framework-draft", state.artifact_heads)

    def test_legacy_authorized_chain_without_ledger_migrates_trust_history(self) -> None:
        ready = MissionReadinessPolicy(self.kernel).require_ready()
        self.assertEqual(ready.mission_confirmation_ref, self.mission_confirmation_ref)
        self.assertNotIn(CONFIRMATION_LEDGER_SLOT, self.kernel.load().artifact_heads)

    def test_legacy_ledger_without_epoch_migrates_on_ordinary_commit(self) -> None:
        before = self.kernel.load()
        committed = self.kernel.commit(
            command_id="ordinary-no-framework-history",
            expected_revision=before.revision,
            event_type="test.no-framework-history",
            artifact_updates={},
        )
        self.assertEqual(committed.revision, before.revision + 1)
        self.assertEqual(self.kernel.current_framework_reset_revision(), 0)

    def test_legacy_ledger_missing_consumed_identity_rejects_zero_write(self) -> None:
        self._install_malformed_ledger(
            {"consumed": [], "artifact_bindings": {}, "framework_reset_revision": 0}
        )
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="reject-malformed-ledger",
                expected_revision=self.kernel.load().revision,
                event_type="test.rejected",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_legacy_epoch_inference_rejects_ambiguous_history_zero_write(self) -> None:
        state = self.kernel.load()
        event_path = self.kernel.events_root / f"r{state.revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["revision"] = state.revision - 1
        atomic_write_json(event_path, event)
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            self.kernel.commit(
                command_id="reject-ambiguous-history",
                expected_revision=state.revision,
                event_type="test.rejected",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_legacy_epoch_inference_rejects_tampered_reset_event_type(self) -> None:
        state = self.kernel.load()
        event_path = self.kernel.events_root / f"r{state.revision:08d}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["transaction_id"] = "tampered-transaction"
        atomic_write_json(event_path, event)
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            self.kernel.commit(
                command_id="reject-tampered-receipt",
                expected_revision=state.revision,
                event_type="test.rejected",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_business_commit_cannot_update_or_remove_confirmation_ledger(self) -> None:
        for index, kwargs in enumerate((
            {
                "artifact_updates": {
                    CONFIRMATION_LEDGER_SLOT: (CONFIRMATION_LEDGER_KIND, {})
                }
            },
            {"artifact_removals": (CONFIRMATION_LEDGER_SLOT,)},
        )):
            with self.subTest(kwargs=kwargs):
                before = self._snapshot()
                with self.assertRaises(ValueError):
                    self.kernel.commit(
                        command_id=f"forged-ledger-{index}",
                        expected_revision=self.kernel.load().revision,
                        event_type="test.forged-ledger",
                        artifact_updates=kwargs.get("artifact_updates", {}),
                        artifact_removals=kwargs.get("artifact_removals", ()),
                    )
                self.assertEqual(self._snapshot(), before)

    def test_missing_or_malformed_framework_epoch_fails_closed(self) -> None:
        self._install_malformed_ledger(
            {
                "consumed": {},
                "artifact_bindings": {},
                "framework_reset_revision": True,
            }
        )
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="malformed-epoch",
                expected_revision=self.kernel.load().revision,
                event_type="test.rejected",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_draft_must_bind_the_current_mission_confirmation(self) -> None:
        self.mission.save_mission_draft(
            "new-mission",
            self.kernel.load().revision,
            {**MISSION, "primary_audience": "客户经营与数字化决策团队"},
        )
        with self.assertRaises(MissionNotConfirmedError):
            MissionReadinessPolicy(self.kernel).require_ready()

    def test_framework_and_expansion_use_distinct_authoritative_scopes(self) -> None:
        _blueprint, _session_ref, session, _state = self._review()
        notification_ref = self._receipt(
            command_id="notification-receipt",
            kind="review-host-notification-receipt",
            session_id=session["review_session_id"],
            status="sent",
        )
        _ref, updated, _state = ReviewSessionService(
            self.kernel
        ).record_host_notification_receipt(
            command_id="apply-notification",
            expected_revision=self.kernel.load().revision,
            review_type="content-full-deck",
            receipt_ref=notification_ref,
        )
        self.assertEqual(updated["host_notification_status"], "sent")
        self.assertEqual(updated["ai_receipt_status"], "pending")

    def test_confirm_current_framework_and_authorize_expansion(self) -> None:
        _review, _service, _opened, confirmed = self._confirm_g0()
        self.assertEqual(confirmed.gate_status["G0"], "passed")
        self.assertEqual(confirmed.gate_status["G1"], "open")
        self.assertIn("gate/G0/confirmation", confirmed.artifact_heads)

    def test_stale_framework_and_early_expansion_fail_without_writes(self) -> None:
        _blueprint, _session_ref, session, _state = self._review()
        before = self._snapshot()
        with self.assertRaises(GateBlockedError):
            PresalesContentService(self.kernel).open_g0_review(
                command_id="g0-too-early",
                expected_revision=self.kernel.load().revision,
            )
        self.assertEqual(self._snapshot(), before)
        self._review("content-v2")
        before = self._snapshot()
        with self.assertRaises(ReviewSourceStaleError):
            ContentDecisionService(self.kernel).save(
                command_id="stale-page-decision",
                expected_revision=self.kernel.load().revision,
                review_session_id=session["review_session_id"],
                source_version="content-v1",
                slide_id="S01",
                decision="approved",
                comment="",
            )
        self.assertEqual(self._snapshot(), before)

    def test_framework_identity_cannot_be_reused_for_expansion(self) -> None:
        first = self.kernel.commit(
            command_id="semantic-command",
            expected_revision=self.kernel.load().revision,
            event_type="test.semantic",
            artifact_updates={"test/semantic": ("test-artifact", {"value": 1})},
            command_fingerprint="a" * 64,
        )
        with self.assertRaises(ContractValidationError):
            self.kernel.commit(
                command_id="semantic-command",
                expected_revision=first.revision,
                event_type="test.semantic",
                artifact_updates={
                    "test/semantic": ("test-artifact", {"value": 2})
                },
                command_fingerprint="b" * 64,
            )

    def test_existing_mission_confirmation_identity_cannot_be_reused(self) -> None:
        _blueprint, _session_ref, session, _state = self._review()
        wrong_ref = self._receipt(
            command_id="wrong-receipt-kind",
            kind="review-host-open-receipt",
            session_id=session["review_session_id"],
            status="opened",
        )
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            ReviewSessionService(self.kernel).record_ai_receipt(
                command_id="apply-wrong-kind",
                expected_revision=self.kernel.load().revision,
                review_type="content-full-deck",
                receipt_ref=wrong_ref,
            )
        self.assertEqual(self._snapshot(), before)

    def test_superseded_mission_confirmation_identity_cannot_be_reused(self) -> None:
        old_confirmation = self.mission_confirmation_ref
        self.mission.save_mission_draft(
            "superseding-mission",
            self.kernel.load().revision,
            {**MISSION, "topic": "经营协同一期方案"},
        )
        state = self.kernel.load()
        self.assertNotEqual(
            state.artifact_heads.get("mission/confirmation", ""), old_confirmation
        )
        with self.assertRaises(MissionNotConfirmedError):
            MissionReadinessPolicy(self.kernel).require_ready()

    def test_current_and_superseded_gate_confirmation_identities_are_rejected(self) -> None:
        _review, _service, _opened, confirmed = self._confirm_g0()
        old_confirmation = confirmed.artifact_heads["gate/G0/confirmation"]
        self._review("content-v2")
        state = self.kernel.load()
        self.assertNotEqual(
            state.artifact_heads.get("gate/G0/confirmation", ""), old_confirmation
        )
        self.assertNotEqual(state.gate_status["G0"], "passed")

    def test_duplicate_confirmation_command_cannot_bypass_identity_consumption(self) -> None:
        _review, service, _opened, confirmed = self._confirm_g0()
        repeated = service.confirm_g0(
            command_id="confirm-g0",
            expected_revision=confirmed.revision,
            **self._last_g0_confirmation_kwargs,
        )
        self.assertEqual(repeated, confirmed)

    def test_same_command_with_different_confirmation_scope_is_rejected(self) -> None:
        _review, service, _opened, confirmed = self._confirm_g0()
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            service.confirm_g0(
                command_id="confirm-g0",
                expected_revision=confirmed.revision,
                **{
                    **self._last_g0_confirmation_kwargs,
                    "challenge_id": "different-confirmation-scope",
                },
            )
        self.assertEqual(self._snapshot(), before)

    def test_old_challenge_after_unrelated_commit_is_rejected_zero_write(self) -> None:
        stale = self.kernel.load().revision
        self.kernel.commit(
            command_id="unrelated",
            expected_revision=stale,
            event_type="test.unrelated",
            artifact_updates={},
        )
        before = self._snapshot()
        with self.assertRaises(RevisionConflictError):
            self.kernel.commit(
                command_id="stale-command",
                expected_revision=stale,
                event_type="test.stale",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_forged_framework_confirmation_head_cannot_authorize_expansion(self) -> None:
        blueprint, _session_ref, _session, batch_ref, _batch, _state = (
            self._submit_review()
        )
        service = PresalesContentService(self.kernel)
        opened = service.open_g0_review(
            command_id="open-g0-forged",
            expected_revision=self.kernel.load().revision,
        )
        fake_ref = str(
            self.kernel.artifacts.put(
                "g0-confirmation",
                {
                    "gate": "G0",
                    "user_message_ref": "chat://message/forged",
                    "content_acceptance_ref": "",
                    "reading_blueprint_ref": blueprint,
                    "content_review_batch_ref": batch_ref,
                    "confirmed_at": NOW,
                },
            )
        )
        before = self._snapshot()
        with self.assertRaises(GateBlockedError):
            GateEvaluator(self.kernel).confirm_g0(
                confirmation_ref=fake_ref,
            )
        self.assertEqual(self.kernel.load(), opened)
        self.assertEqual(self._snapshot(), before)

    def test_confirmation_without_atomic_identity_consumption_is_not_trusted(self) -> None:
        fake_ref = self.kernel.artifacts.put(
            "g0-confirmation",
            {"gate": "G0", "user_message_ref": "chat://message/raw"},
        )
        before = self.kernel.load()
        self.assertTrue(ArtifactReference.parse(str(fake_ref)))
        self.assertEqual(self.kernel.load(), before)
        self.assertEqual(before.gate_status["G0"], "open")

    def test_mismatched_confirmation_binding_is_zero_write(self) -> None:
        self._submit_review()
        PresalesContentService(self.kernel).open_g0_review(
            command_id="open-g0-mismatch",
            expected_revision=self.kernel.load().revision,
        )
        fake_ref = str(
            self.kernel.artifacts.put(
                "g0-confirmation",
                {
                    "gate": "G0",
                    "user_message_ref": "chat://message/mismatch",
                    "content_acceptance_ref": "",
                    "reading_blueprint_ref": "",
                    "content_review_batch_ref": "",
                    "confirmed_at": NOW,
                },
            )
        )
        before = self._snapshot()
        with self.assertRaises(GateBlockedError):
            GateEvaluator(self.kernel).confirm_g0(
                confirmation_ref=fake_ref,
            )
        self.assertEqual(self._snapshot(), before)

    def test_raw_fake_confirmation_consumption_is_rejected_zero_write(self) -> None:
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError) as caught:
            self.kernel.commit(
                command_id="raw-consumption",
                expected_revision=self.kernel.load().revision,
                event_type="test.raw-consumption",
                artifact_updates={},
                confirmation_consumptions=(object(),),
            )
        self.assertEqual(caught.exception.code, "CONFIRMATION_AUTHORITY_INVALID")
        self.assertEqual(self._snapshot(), before)

    def test_valid_confirmation_capability_cannot_be_cloned_or_mutated(self) -> None:
        with self.assertRaises(TypeError):
            ConfirmationConsumption()
        with self.assertRaises(TypeError):
            ContentFrameworkResetMutation()

    def test_valid_capability_cannot_bind_a_tampered_scoped_payload(self) -> None:
        _blueprint, _session_ref, session, _state = self._review()
        receipt_ref = self._receipt(
            command_id="other-session-receipt",
            kind="review-ai-receipt",
            session_id="different-session",
            status="received",
        )
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            ReviewSessionService(self.kernel).record_ai_receipt(
                command_id="apply-tampered-receipt",
                expected_revision=self.kernel.load().revision,
                review_type="content-full-deck",
                receipt_ref=receipt_ref,
            )
        self.assertEqual(session["ai_receipt_status"], "pending")
        self.assertEqual(self._snapshot(), before)

    def test_direct_policy_cannot_mint_framework_reset(self) -> None:
        with self.assertRaises(TypeError):
            ContentFrameworkResetMutation()

    def test_reset_capability_is_bound_to_exact_framework_payload(self) -> None:
        payload = valid_framework(self.mission_confirmation_ref)
        original_ref = str(
            self.kernel.artifacts.reference_for("content-framework-draft", payload)
        )
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self._legacy_reset_attempt(
                payload={**payload, "framework_id": "tampered"},
                claim_framework_ref=original_ref,
            )
        self.assertEqual(self._snapshot(), before)

    def test_direct_issuer_cannot_reset_with_invalid_framework_payload(self) -> None:
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self._legacy_reset_attempt(
                payload={
                    "framework_id": "invalid",
                    "mission_confirmation_ref": self.mission_confirmation_ref,
                }
            )
        self.assertEqual(self._snapshot(), before)

    def test_direct_issuer_cannot_reset_with_stale_mission(self) -> None:
        payload = valid_framework(self.mission_confirmation_ref)
        stale_ref = "artifact://mission-confirmation/" + "f" * 64
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self._legacy_reset_attempt(payload=payload, claim_mission_ref=stale_ref)
        self.assertEqual(self._snapshot(), before)

    def test_forged_current_mission_confirmation_cannot_authorize_reset(self) -> None:
        current = self.kernel.artifacts.resolve(
            ArtifactReference.parse(self.mission_confirmation_ref)
        )["payload"]
        forged_ref = str(
            self.kernel.artifacts.put(
                "mission-confirmation",
                {
                    **current,
                    "mission_draft_ref": "artifact://mission-draft/" + "e" * 64,
                },
            )
        )
        self._rewrite_heads({"mission/confirmation": forged_ref})
        payload = valid_framework(forged_ref)
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self._legacy_reset_attempt(payload=payload, claim_mission_ref=forged_ref)
        self.assertEqual(self._snapshot(), before)

    def test_bare_framework_reset_is_rejected_zero_write(self) -> None:
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self._legacy_reset_attempt(
                payload=valid_framework(self.mission_confirmation_ref),
                raw_claim=object(),
            )
        self.assertEqual(self._snapshot(), before)

    def test_corrupt_confirmation_history_fails_closed_zero_write(self) -> None:
        self._install_malformed_ledger(
            {
                "consumed": {"identity": 7},
                "artifact_bindings": {},
                "framework_reset_revision": 0,
            }
        )
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError):
            self.kernel.commit(
                command_id="corrupt-history",
                expected_revision=self.kernel.load().revision,
                event_type="test.corrupt-history",
                artifact_updates={},
            )
        self.assertEqual(self._snapshot(), before)

    def test_typed_kernel_confirmation_failure_maps_without_message_matching(self) -> None:
        before = self._snapshot()
        with self.assertRaises(ConfirmationTransactionError) as caught:
            self._legacy_reset_attempt(
                payload=valid_framework(self.mission_confirmation_ref),
                raw_claim=object(),
            )
        self.assertEqual(caught.exception.code, "CONFIRMATION_AUTHORITY_INVALID")
        self.assertEqual(self._snapshot(), before)

    def test_consumed_identity_cannot_authenticate_a_replacement_artifact(self) -> None:
        _review, _service, _opened, confirmed = self._confirm_g0()
        old_ref = confirmed.artifact_heads["gate/G0/confirmation"]
        self._review("content-v2")
        current = self.kernel.load()
        self.assertNotEqual(
            current.artifact_heads.get("gate/G0/confirmation", ""), old_ref
        )
        self.assertNotEqual(current.gate_status["G0"], "passed")

    def test_new_framework_reopens_g0_and_removes_formal_page_content_heads(self) -> None:
        _review, _service, _opened, confirmed = self._confirm_g0()
        self.assertEqual(confirmed.gate_status["G0"], "passed")
        self._review("content-v2")
        state = self.kernel.load()
        self.assertEqual(state.gate_status["G0"], "locked")
        self.assertNotIn("gate/G0/confirmation", state.artifact_heads)
        self.assertNotIn("content/review-batch", state.artifact_heads)
        self.assertFalse(
            any(
                slot.startswith("content/review/decision/")
                for slot in state.artifact_heads
            )
        )

    def test_new_framework_removes_future_content_heads_but_keeps_non_content_heads(self) -> None:
        self._submit_review()
        seeded = self.kernel.commit(
            command_id="seed-derived-heads",
            expected_revision=self.kernel.load().revision,
            event_type="test.derived-heads",
            artifact_updates={
                "visual/contract": (
                    "visual-contract",
                    {"source_version": "content-v1"},
                ),
                "delivery/build": ("presentation-build", {"value": 1}),
                "experience/current": ("experience-item", {"value": 1}),
            },
        )
        experience_ref = seeded.artifact_heads["experience/current"]
        self._review("content-v2")
        state = self.kernel.load()
        for slot in (
            "visual/contract",
            "delivery/build",
        ):
            self.assertNotIn(slot, state.artifact_heads)
        self.assertEqual(state.artifact_heads["experience/current"], experience_ref)

    def test_new_draft_clears_current_confirmation_and_authorization_heads(self) -> None:
        self._confirm_g0()
        self.kernel.commit(
            command_id="seed-downstream",
            expected_revision=self.kernel.load().revision,
            event_type="test.downstream",
            artifact_updates={
                "visual/contract": (
                    "visual-contract",
                    {"source_version": "content-v1"},
                ),
                "delivery/build": ("presentation-build", {"value": 1}),
                "experience/current": ("experience-item", {"value": 1}),
            },
        )
        experience_ref = self.kernel.load().artifact_heads["experience/current"]
        self.mission.save_mission_draft(
            "mission-v2",
            self.kernel.load().revision,
            {**MISSION, "topic": "经营协同二期方案"},
        )
        state = self.kernel.load()
        self.assertNotIn("mission/confirmation", state.artifact_heads)
        self.assertFalse(any(slot.startswith("content/") for slot in state.artifact_heads))
        self.assertFalse(any(slot.startswith("visual/") for slot in state.artifact_heads))
        self.assertFalse(any(slot.startswith("delivery/") for slot in state.artifact_heads))
        self.assertFalse(
            any(slot.startswith("review/session/") for slot in state.artifact_heads)
        )
        self.assertNotIn("gate/G0/confirmation", state.artifact_heads)
        self.assertEqual(state.artifact_heads["experience/current"], experience_ref)
        self.assertEqual(
            state.gate_status,
            {
                "G0": "open",
                "G1": "locked",
                "G2": "locked",
                "G3": "locked",
                "G4": "locked",
            },
        )

    def test_new_material_inventory_clears_current_confirmation_and_downstream_heads(self) -> None:
        self._confirm_g0()
        replacement = {
            "sources": [
                {
                    **MATERIALS["sources"][0],
                    "source_id": "s2",
                    "locator": "inline://user-provided/s2",
                    "sha256": "b" * 64,
                }
            ]
        }
        self.mission.register_materials(
            "materials-v2", self.kernel.load().revision, replacement
        )
        state = self.kernel.load()
        self.assertNotIn("mission/confirmation", state.artifact_heads)
        self.assertFalse(any(slot.startswith("content/") for slot in state.artifact_heads))
        self.assertFalse(any(slot.startswith("review/session/") for slot in state.artifact_heads))
        self.assertEqual(state.gate_status["G0"], "open")

    def test_context_mismatches_and_invalid_hmac_are_zero_write(self) -> None:
        blueprint_ref, _session_ref, session, _state = self._review()
        before = self._snapshot()
        with self.assertRaises(ReviewSourceStaleError):
            ReviewSessionService(self.kernel).open_or_resume(
                command_id="mismatched-review-context",
                expected_revision=self.kernel.load().revision,
                review_type="content-full-deck",
                target_artifact_ref=blueprint_ref,
                source_version="content-v99",
                source_revision=session["revision"],
                open_policy="notify-only",
            )
        self.assertEqual(session["source_version"], "content-v1")
        self.assertEqual(self._snapshot(), before)

    def test_identity_replay_is_rejected_atomically_across_new_challenge(self) -> None:
        first = self.kernel.commit(
            command_id="cross-revision-command",
            expected_revision=self.kernel.load().revision,
            event_type="test.cross-revision",
            artifact_updates={"test/value": ("test-artifact", {"value": 1})},
            command_fingerprint="1" * 64,
        )
        self.kernel.commit(
            command_id="advance-after-command",
            expected_revision=first.revision,
            event_type="test.advance",
            artifact_updates={},
        )
        before = self._snapshot()
        with self.assertRaises(ContractValidationError):
            self.kernel.commit(
                command_id="cross-revision-command",
                expected_revision=self.kernel.load().revision,
                event_type="test.cross-revision",
                artifact_updates={
                    "test/value": ("test-artifact", {"value": 2})
                },
                command_fingerprint="2" * 64,
            )
        self.assertEqual(self._snapshot(), before)
if __name__ == "__main__":
    unittest.main()
