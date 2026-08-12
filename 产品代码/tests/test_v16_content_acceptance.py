from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.domains.content.contracts import REQUIRED_CONTENT_REVIEW_ROLES
from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_content_chain import build_ready_draft


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
    def test_acceptance_requires_five_roles_and_chat_only_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, _refs = build_ready_draft(service)
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

    def test_missing_or_failed_review_blocks_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, _refs = build_ready_draft(service)
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

        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p2")
            revision, draft_ref, _refs = build_ready_draft(service)
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
