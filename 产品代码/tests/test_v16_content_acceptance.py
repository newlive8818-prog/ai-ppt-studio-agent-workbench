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
from ai_ppt_studio.application.framework_discussion_service import FrameworkDiscussionService
from ai_ppt_studio.application.scoped_confirmation import HOST_CONFIRMATION_SECRET_ENV
from ai_ppt_studio.domains.content.contracts import REQUIRED_CONTENT_REVIEW_ROLES
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContentWorkflowError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_content_fixtures import complete_slide_draft_payload


TEST_SECRET = "test-only-content-acceptance-secret-32-bytes-long"


def signed_assertion(context: dict[str, object]) -> str:
    now = int(time.time())
    body = {key: context[key] for key in (
        "project_id", "project_root", "scope_kind", "scope_id",
        "source_version", "evidence_refs", "challenge_id", "challenge_revision",
    )}
    body.update({
        "identity_type": "host-action",
        "identity_ref": f"test-host-action://{uuid.uuid4()}",
        "nonce": str(uuid.uuid4()), "issued_at": now, "expires_at": now + 120,
    })
    segment = base64.urlsafe_b64encode(json.dumps(
        body, ensure_ascii=False, separators=(",", ":")
    ).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(
        TEST_SECRET.encode(), segment.encode("ascii"), hashlib.sha256
    ).digest()).decode().rstrip("=")
    return f"v1.{segment}.{signature}"


def framework_payload(mission_confirmation_ref: str, version: int = 1) -> dict:
    return {
        "framework_id": f"framework-{version}",
        "mission_confirmation_ref": mission_confirmation_ref,
        "core_proposition": "先证明经营断点，再确认一期路径。",
        "persuasion_path": ["问题共识", "方案可信", "一期行动"],
        "chapters": [{
            "chapter_id": "C01", "title": "为何改变", "task": "建立问题共识",
            "expected_judgment": "需要跨系统治理", "transition": "进入建设原则",
        }],
        "structural_risks": ["定量收益证据不足"],
        "highest_impact_question": "是否以一期行动收束？", "status": "discussion",
    }


def authorize_current_framework(service: ContentService, mission_confirmation_ref: str, version: int = 1):
    workflow = FrameworkDiscussionService(service.kernel)
    framework_ref, _ = workflow.save_draft(
        f"framework-{version}", service.kernel.load().revision,
        framework_payload(mission_confirmation_ref, version),
    )
    context = workflow.confirmation_context()
    confirmation_ref, _ = workflow.confirm_framework(
        f"confirm-framework-{version}", service.kernel.load().revision,
        framework_ref, str(context["challenge_id"]), int(context["challenge_revision"]),
        signed_assertion(context),
    )
    context = workflow.expansion_authorization_context()
    authorization_ref, _ = workflow.authorize_full_deck_expansion(
        f"authorize-framework-{version}", service.kernel.load().revision,
        framework_ref, str(context["challenge_id"]), int(context["challenge_revision"]),
        signed_assertion(context),
    )
    return framework_ref, confirmation_ref, authorization_ref


def build_authorized_draft(service: ContentService):
    mission = service.save_mission_draft("c1", 0, {
        "topic": "经营一体化方案", "primary_audience": "客户决策者",
        "desired_judgment_or_action": "批准一期立项",
    })
    materials = service.register_materials("c2", 1, {"sources": [{
        "source_id": "s1", "origin": "user-provided", "kind": "text",
        "locator": "chat://message/material-1", "sha256": "a" * 64,
    }]})
    mission_confirmation = service.confirm_mission(
        "c3", 2, mission_draft_ref=mission, material_mode="materials-provided",
        material_inventory_ref=materials,
        user_action_ref="test-user-action://mission", user_message_ref="",
    )
    lineage = authorize_current_framework(service, mission_confirmation)
    revision = service.kernel.load().revision
    strategy = service.register_content_stage("c4", revision, "strategy", {
        "mission_ref": mission, "material_inventory_ref": materials,
        "content_identity_mode": "material-backed", "decision_stage": "立项",
        "core_tension": "系统割裂",
    })
    claim_map = service.register_content_stage("c5", revision + 1, "claim-map", {
        "strategy_ref": strategy,
        "claims": [{"claim_id": "c1", "status": "supported", "evidence_refs": [materials]}],
    })
    argument = service.register_content_stage("c6", revision + 2, "argument-map", {
        "strategy_ref": strategy, "claim_evidence_map_ref": claim_map,
        "chapters": [{"chapter_id": "ch1", "task": "建立问题共识"}],
    })
    draft = service.register_content_stage(
        "c7", revision + 3, "slide-draft-set",
        complete_slide_draft_payload(argument_map_ref=argument, material_ref=materials),
    )
    return revision + 4, draft, lineage


def review_payload(draft_ref: str, role: str, *, passed: bool = True) -> dict:
    result = "passed" if passed else "failed"
    return {
        "target_ref": draft_ref,
        "reviewer_role": role,
        "input_version": draft_ref,
        "checks": [
            {
                "criterion_id": f"{role}-hard",
                "level": "must-follow",
                "applicability": "applicable",
                "result": result,
                "evidence_refs": [draft_ref],
                "failure_reason": "" if passed else "关键条件未满足",
                "repair_instruction": "" if passed else "定向修复",
            }
        ],
        "overall_result": result,
    }


def register_reviews(
    service: ContentService,
    start_revision: int,
    draft_ref: str,
    roles: tuple[str, ...] = REQUIRED_CONTENT_REVIEW_ROLES,
    *,
    failed_role: str = "",
) -> int:
    revision = start_revision
    for index, role in enumerate(roles):
        service.register_review(
            f"review-{index}",
            revision,
            review_payload(draft_ref, role, passed=role != failed_role),
        )
        revision += 1
    return revision


class V16ContentAcceptanceTests(unittest.TestCase):
    def test_acceptance_revalidates_every_current_content_chain_head_zero_write(self) -> None:
        stages = {
            "content/strategy": "presales-content-strategy",
            "content/claim-map": "claim-evidence-map",
            "content/argument-map": "deck-argument-map",
            "content/draft": "slide-draft-set",
        }
        for slot, kind in stages.items():
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
            ):
                service = ContentService.initialize(Path(temp), project_id="adversarial")
                revision, draft_ref, _lineage = build_authorized_draft(service)
                revision = register_reviews(service, revision, draft_ref)
                current_ref = service.kernel.load().artifact_heads[slot]
                forged = dict(service.kernel.artifacts.resolve(
                    ArtifactReference.parse(current_ref)
                )["payload"])
                forged["framework_ref"] = (
                    "artifact://content-framework-draft/" + "f" * 64
                )
                service.kernel.commit(
                    command_id=f"forge:{slot}", expected_revision=revision,
                    event_type="test.forge-content-chain-head",
                    artifact_updates={slot: (kind, forged)},
                )
                before = service.kernel.load()
                objects_before = tuple(
                    path.relative_to(service.kernel.artifacts.objects_root)
                    for path in service.kernel.artifacts.objects_root.rglob("*")
                    if path.is_file()
                )
                with self.assertRaises(ContentWorkflowError):
                    service.accept_content("reject-forged-chain", before.revision)
                self.assertEqual(service.kernel.load(), before)
                objects_after = tuple(
                    path.relative_to(service.kernel.artifacts.objects_root)
                    for path in service.kernel.artifacts.objects_root.rglob("*")
                    if path.is_file()
                )
                self.assertEqual(objects_after, objects_before)
                self.assertNotIn("content/acceptance", before.artifact_heads)
                self.assertNotIn("content/blueprint", before.artifact_heads)

    def test_acceptance_rejects_wrong_kind_review_heads_zero_write(self) -> None:
        for role in REQUIRED_CONTENT_REVIEW_ROLES:
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temp, patch.dict(
                os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
            ):
                service = ContentService.initialize(Path(temp), project_id="review-kind")
                revision, draft_ref, _lineage = build_authorized_draft(service)
                revision = register_reviews(service, revision, draft_ref)
                slot = f"content/review/{role}"
                current = service.kernel.load().artifact_heads[slot]
                payload = service.kernel.artifacts.resolve(
                    ArtifactReference.parse(current)
                )["payload"]
                service.kernel.commit(
                    command_id=f"wrong-review-kind:{role}",
                    expected_revision=revision,
                    event_type="test.wrong-review-kind",
                    artifact_updates={slot: ("not-a-content-review-record", payload)},
                )
                before = service.kernel.load()
                objects_before = tuple(
                    path.relative_to(service.kernel.artifacts.objects_root)
                    for path in service.kernel.artifacts.objects_root.rglob("*")
                    if path.is_file()
                )
                with self.assertRaises(ArtifactReferenceError):
                    service.accept_content("reject-wrong-review-kind", before.revision)
                self.assertEqual(service.kernel.load(), before)
                objects_after = tuple(
                    path.relative_to(service.kernel.artifacts.objects_root)
                    for path in service.kernel.artifacts.objects_root.rglob("*")
                    if path.is_file()
                )
                self.assertEqual(objects_after, objects_before)
                self.assertNotIn("content/acceptance", before.artifact_heads)
                self.assertNotIn("content/blueprint", before.artifact_heads)

    def test_formal_content_cannot_start_from_mission_readiness_alone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="mission-only")
            mission = service.save_mission_draft("mission", 0, {
                "topic": "经营一体化", "primary_audience": "决策者",
                "desired_judgment_or_action": "批准一期",
            })
            service.confirm_mission(
                "confirm", 1, mission_draft_ref=mission,
                material_mode="no-materials-confirmed", material_inventory_ref="",
                user_action_ref="test-user-action://mission-only", user_message_ref="",
            )
            before = service.kernel.load()
            with self.assertRaises(ContentWorkflowError) as caught:
                service.register_content_stage("too-early", before.revision, "strategy", {
                    "mission_ref": mission, "content_identity_mode": "proposal-only",
                    "decision_stage": "立项", "core_tension": "诊断假设",
                    "identity_labels": ["diagnostic-hypothesis", "solution-recommendation", "joint-validation-required"],
                })
            self.assertEqual(caught.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED")
            self.assertEqual(service.kernel.load(), before)
            self.assertNotIn("content/blueprint", before.artifact_heads)

    def test_acceptance_requires_five_roles_and_chat_only_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, lineage = build_authorized_draft(service)
            revision = register_reviews(service, revision, draft_ref)
            accepted = service.accept_content("accept", revision)
            self.assertTrue(
                accepted.acceptance_ref.startswith(
                    "artifact://content-acceptance/"
                )
            )
            self.assertTrue(
                accepted.blueprint_ref.startswith("artifact://content-blueprint/")
            )
            acceptance = service.kernel.artifacts.resolve(
                ArtifactReference.parse(accepted.acceptance_ref)
            )["payload"]
            self.assertIn("passed_at", acceptance)
            self.assertEqual(
                [acceptance[key] for key in (
                    "framework_ref", "framework_confirmation_ref",
                    "full_deck_expansion_authorization_ref",
                )], list(lineage)
            )
            draft = service.kernel.artifacts.resolve(
                ArtifactReference.parse(draft_ref)
            )["payload"]
            self.assertEqual(
                [draft[key] for key in (
                    "framework_ref", "framework_confirmation_ref",
                    "full_deck_expansion_authorization_ref",
                )], list(lineage)
            )
            blueprint = service.kernel.artifacts.resolve(
                ArtifactReference.parse(accepted.blueprint_ref)
            )["payload"]
            self.assertEqual(
                [blueprint[key] for key in (
                    "framework_ref", "framework_confirmation_ref",
                    "full_deck_expansion_authorization_ref",
                )], list(lineage)
            )
            self.assertTrue(acceptance["passed_at"].endswith("+00:00"))
            self.assertEqual(
                accepted.state.gate_status["G0"], "user-reviewable"
            )
            self.assertEqual(accepted.state.gate_status["G1"], "locked")

            confirmed = service.confirm_g0(
                "confirm-g0",
                accepted.state.revision,
                user_message_ref="chat://message/g0-accepted",
            )
            self.assertEqual(confirmed.gate_status["G0"], "passed")
            self.assertEqual(confirmed.gate_status["G1"], "open")

    def test_new_framework_invalidates_acceptance_without_additional_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            service = ContentService.initialize(Path(temp), project_id="stale")
            revision, draft_ref, lineage = build_authorized_draft(service)
            revision = register_reviews(service, revision, draft_ref)
            mission_confirmation_ref = service.kernel.load().artifact_heads[
                "mission/confirmation"
            ]
            FrameworkDiscussionService(service.kernel).save_draft(
                "replacement", revision,
                framework_payload(mission_confirmation_ref, 2),
            )
            before = service.kernel.load()
            self.assertNotIn("content/draft", before.artifact_heads)
            self.assertNotIn(
                "content/full-deck-expansion-authorization", before.artifact_heads
            )
            with self.assertRaises(ContentWorkflowError) as caught:
                service.accept_content("stale-acceptance", before.revision)
            self.assertEqual(
                caught.exception.code, "FULL_DECK_EXPANSION_NOT_AUTHORIZED"
            )
            self.assertEqual(service.kernel.load(), before)
            self.assertNotIn("content/acceptance", before.artifact_heads)
            self.assertNotIn("content/blueprint", before.artifact_heads)
            self.assertTrue(all(lineage))

    def test_missing_or_failed_review_blocks_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, _refs = build_authorized_draft(service)
            revision = register_reviews(
                service,
                revision,
                draft_ref,
                REQUIRED_CONTENT_REVIEW_ROLES[:-1],
            )
            with self.assertRaises(GateBlockedError):
                service.accept_content("missing-review", revision)
            self.assertEqual(service.kernel.load().revision, revision)
            with self.assertRaises(GateBlockedError):
                service.confirm_g0("early-g0", revision, user_message_ref="")

        with tempfile.TemporaryDirectory() as temp, patch.dict(
            os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
        ):
            service = ContentService.initialize(Path(temp), project_id="p2")
            revision, draft_ref, _refs = build_authorized_draft(service)
            revision = register_reviews(
                service,
                revision,
                draft_ref,
                failed_role="evidence-reviewer",
            )
            with self.assertRaises(GateBlockedError):
                service.accept_content("failed-review", revision)
            self.assertEqual(service.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
