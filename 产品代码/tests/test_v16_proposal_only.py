from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.errors import ProposalOnlyIdentityViolationError
from ai_ppt_studio.kernel.references import ArtifactReference


MISSION = {
    "topic": "经营一体化方案",
    "primary_audience": "客户经营与数字化决策团队",
    "desired_judgment_or_action": "确认一期建设范围并进入联合方案验证",
}

IDENTITY_LABELS = [
    "diagnostic-hypothesis",
    "solution-recommendation",
    "joint-validation-required",
]


def confirmed_no_materials(service: ContentService) -> tuple[int, str, str]:
    draft_ref = service.save_mission_draft("draft", 0, MISSION)
    confirmation_ref = service.confirm_mission(
        "confirm-no-materials",
        1,
        mission_draft_ref=draft_ref,
        material_mode="no-materials-confirmed",
        material_inventory_ref="",
        user_action_ref="test-user-action://confirmed-proposal-only-fixture",
        user_message_ref="",
    )
    return 2, draft_ref, confirmation_ref


class ProposalOnlyContentTests(unittest.TestCase):
    def test_no_materials_can_complete_the_formal_content_draft_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, confirmation_ref = confirmed_no_materials(service)
            strategy_ref = service.register_content_stage(
                "strategy",
                revision,
                "strategy",
                {
                    "mission_ref": draft_ref,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": IDENTITY_LABELS,
                    "decision_stage": "方案建议",
                    "core_tension": "诊断假设：经营流程可能存在跨系统断点",
                },
            )
            claim_ref = service.register_content_stage(
                "claim-map",
                revision + 1,
                "claim-map",
                {
                    "strategy_ref": strategy_ref,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": IDENTITY_LABELS,
                    "claims": [
                        {
                            "claim_id": "claim-1",
                            "status": "hypothesis",
                            "identity_class": "diagnostic-hypothesis",
                            "claim": "诊断假设：跨系统协同可能存在流程断点",
                            "evidence_refs": [],
                        },
                        {
                            "claim_id": "claim-2",
                            "status": "recommended",
                            "identity_class": "solution-recommendation",
                            "claim": "方案建议：以经营主线统一范围与实施路径",
                            "evidence_refs": [],
                        },
                    ],
                },
            )
            argument_ref = service.register_content_stage(
                "argument-map",
                revision + 2,
                "argument-map",
                {
                    "strategy_ref": strategy_ref,
                    "claim_evidence_map_ref": claim_ref,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": IDENTITY_LABELS,
                    "chapters": [
                        {
                            "chapter_id": "ch1",
                            "task": "以诊断假设建立联合澄清议程",
                        }
                    ],
                },
            )
            slide_ref = service.register_content_stage(
                "slide-draft-set",
                revision + 3,
                "slide-draft-set",
                {
                    "argument_map_ref": argument_ref,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": IDENTITY_LABELS,
                    "slides": [
                        {
                            "slide_id": "s1",
                            "title": "联合验证的起点",
                            "communication_goal": "明确当前内容身份",
                            "core_claim": "诊断假设：跨系统协同可能存在断点",
                            "identity_class": "diagnostic-hypothesis",
                            "visible_copy": [
                                "诊断假设：流程断点需与客户联合澄清",
                                "当前内容不代表客户已确认事实",
                            ],
                            "speaker_notes": "方案建议：先共同验证现状，再冻结建设范围。",
                            "source_refs": [],
                        }
                    ],
                },
            )

            self.assertTrue(slide_ref.startswith("artifact://slide-draft-set/"))
            payload = service.kernel.artifacts.resolve(
                ArtifactReference.parse(slide_ref)
            )["payload"]
            self.assertEqual(payload["content_identity_mode"], "proposal-only")
            self.assertEqual(
                payload["mission_confirmation_ref"], confirmation_ref
            )

    def test_proposal_only_rejects_customer_facts_numbers_cases_and_promises(self) -> None:
        prohibited = (
            "客户现有 5 套系统彼此割裂",
            "成功案例证明该方案可行",
            "客户确认当前存在流程断点",
            "保证上线后效率提升",
        )
        for index, statement in enumerate(prohibited):
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as temp:
                service = ContentService.initialize(Path(temp), project_id=f"p{index}")
                revision, draft_ref, _confirmation_ref = confirmed_no_materials(
                    service
                )
                with self.assertRaises(ProposalOnlyIdentityViolationError):
                    service.register_content_stage(
                        f"invalid-{index}",
                        revision,
                        "strategy",
                        {
                            "mission_ref": draft_ref,
                            "content_identity_mode": "proposal-only",
                            "identity_labels": IDENTITY_LABELS,
                            "decision_stage": "方案建议",
                            "core_tension": statement,
                        },
                    )

    def test_proposal_only_claim_cannot_masquerade_as_supported_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft_ref, _confirmation_ref = confirmed_no_materials(service)
            strategy_ref = service.register_content_stage(
                "strategy",
                revision,
                "strategy",
                {
                    "mission_ref": draft_ref,
                    "content_identity_mode": "proposal-only",
                    "identity_labels": IDENTITY_LABELS,
                    "decision_stage": "方案建议",
                    "core_tension": "诊断假设：流程可能存在断点",
                },
            )
            with self.assertRaises(ProposalOnlyIdentityViolationError):
                service.register_content_stage(
                    "invalid-claim",
                    revision + 1,
                    "claim-map",
                    {
                        "strategy_ref": strategy_ref,
                        "content_identity_mode": "proposal-only",
                        "identity_labels": IDENTITY_LABELS,
                        "claims": [
                            {
                                "claim_id": "claim-1",
                                "status": "supported",
                                "identity_class": "diagnostic-hypothesis",
                                "claim": "诊断假设：流程可能存在断点",
                                "evidence_refs": [],
                            }
                        ],
                    },
                )


if __name__ == "__main__":
    unittest.main()
