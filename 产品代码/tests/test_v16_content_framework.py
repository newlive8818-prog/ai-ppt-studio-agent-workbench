from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.content.framework import (
    validate_framework_draft,
    validate_framework_confirmation,
    validate_full_deck_expansion_authorization,
)
from ai_ppt_studio.domains.content.contracts import validate_content_stage
from ai_ppt_studio.errors import ContractValidationError
from tests.v16_content_fixtures import (
    complete_planned_gap_evidence,
    complete_reading_first_slide,
    complete_slide_draft_payload,
)


def valid_framework() -> dict[str, object]:
    return {
        "framework_id": "framework-v1",
        "mission_confirmation_ref": "artifact://mission-confirmation/" + "1" * 64,
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


class FrameworkDraftContractTests(unittest.TestCase):
    def test_accepts_chapter_only_framework_without_slide_content(self) -> None:
        self.assertEqual(validate_framework_draft(valid_framework()), valid_framework())

    def test_rejects_every_slide_level_field(self) -> None:
        for field in (
            "slides",
            "slide_titles",
            "visible_copy",
            "speaker_notes",
            "materials",
        ):
            with self.subTest(field=field):
                payload = valid_framework()
                payload[field] = []
                with self.assertRaisesRegex(
                    ContractValidationError,
                    "FrameworkDraft cannot contain slide-level content",
                ):
                    validate_framework_draft(payload)

    def test_requires_every_top_level_field(self) -> None:
        for field in valid_framework():
            with self.subTest(field=field):
                payload = valid_framework()
                del payload[field]
                with self.assertRaises(ContractValidationError):
                    validate_framework_draft(payload)

    def test_requires_every_chapter_field(self) -> None:
        chapter = valid_framework()["chapters"][0]
        assert isinstance(chapter, dict)
        for field in chapter:
            with self.subTest(field=field):
                payload = valid_framework()
                del payload["chapters"][0][field]
                with self.assertRaises(ContractValidationError):
                    validate_framework_draft(payload)

    def test_rejects_empty_values_and_wrong_collection_types(self) -> None:
        cases = (
            ("framework_id", ""),
            ("persuasion_path", "not-a-list"),
            ("persuasion_path", []),
            ("chapters", "not-a-list"),
            ("chapters", []),
            ("structural_risks", "not-a-list"),
            ("status", "confirmed"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                payload = valid_framework()
                payload[field] = value
                with self.assertRaises(ContractValidationError):
                    validate_framework_draft(payload)


class FrameworkBindingContractTests(unittest.TestCase):
    def test_confirmation_preserves_exact_framework_binding(self) -> None:
        payload = {
            "project_id": "project-1",
            "framework_ref": "artifact://content-framework-draft/" + "2" * 64,
            "framework_revision": 7,
            "challenge_identity": "challenge-framework-7",
            "confirmed_at": "2026-08-14T22:10:00+08:00",
        }
        self.assertEqual(validate_framework_confirmation(payload), payload)

    def test_authorization_preserves_framework_and_confirmation_bindings(self) -> None:
        payload = {
            "project_id": "project-1",
            "framework_ref": "artifact://content-framework-draft/" + "2" * 64,
            "framework_confirmation_ref": (
                "artifact://content-framework-confirmation/" + "3" * 64
            ),
            "framework_revision": 7,
            "challenge_identity": "challenge-full-deck-7",
            "confirmed_at": "2026-08-14T22:12:00+08:00",
        }
        self.assertEqual(validate_full_deck_expansion_authorization(payload), payload)

    def test_confirmation_and_authorization_reject_missing_empty_or_wrong_types(self) -> None:
        confirmation = {
            "project_id": "project-1",
            "framework_ref": "artifact://content-framework-draft/" + "2" * 64,
            "framework_revision": 7,
            "challenge_identity": "challenge-framework-7",
            "confirmed_at": "2026-08-14T22:10:00+08:00",
        }
        authorization = {
            **confirmation,
            "framework_confirmation_ref": (
                "artifact://content-framework-confirmation/" + "3" * 64
            ),
        }
        for validator, valid in (
            (validate_framework_confirmation, confirmation),
            (validate_full_deck_expansion_authorization, authorization),
        ):
            for field in valid:
                with self.subTest(validator=validator.__name__, field=field):
                    missing = copy.deepcopy(valid)
                    del missing[field]
                    with self.assertRaises(ContractValidationError):
                        validator(missing)
            for field, invalid in (
                ("project_id", " "),
                ("framework_ref", None),
                ("framework_revision", True),
                ("framework_revision", 0),
                ("challenge_identity", []),
                ("confirmed_at", ""),
            ):
                with self.subTest(validator=validator.__name__, field=field):
                    malformed = copy.deepcopy(valid)
                    malformed[field] = invalid
                    with self.assertRaises(ContractValidationError):
                        validator(malformed)


class ReadingFirstSlideContractTests(unittest.TestCase):
    def test_accepts_and_normalizes_complete_reading_first_slide(self) -> None:
        payload = complete_slide_draft_payload()
        self.assertEqual(validate_content_stage("slide-draft-set", payload), payload)

    def test_requires_every_complete_slide_field(self) -> None:
        required = (
            "slide_id",
            "chapter_id",
            "order",
            "title",
            "page_purpose",
            "customer_judgment",
            "communication_goal",
            "core_claim",
            "visible_copy",
            "evidence_items",
            "speaker_notes",
            "reading_quality",
            "sequence",
            "user_judgment_prompt",
            "source_refs",
        )
        for field in required:
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                del payload["slides"][0][field]
                with self.assertRaisesRegex(ContractValidationError, field):
                    validate_content_stage("slide-draft-set", payload)

    def test_requires_structured_visible_copy_with_all_fields(self) -> None:
        payload = complete_slide_draft_payload()
        payload["slides"][0]["visible_copy"] = ["legacy string copy"]
        with self.assertRaises(ContractValidationError):
            validate_content_stage("slide-draft-set", payload)
        for field in ("copy_id", "role", "text"):
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                del payload["slides"][0]["visible_copy"][0][field]
                with self.assertRaisesRegex(ContractValidationError, field):
                    validate_content_stage("slide-draft-set", payload)

    def test_requires_complete_material_evidence_metadata(self) -> None:
        fields = tuple(complete_slide_draft_payload()["slides"][0]["evidence_items"][0])
        for field in fields:
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                del payload["slides"][0]["evidence_items"][0][field]
                with self.assertRaisesRegex(ContractValidationError, field):
                    validate_content_stage("slide-draft-set", payload)

    def test_accepts_explicit_planned_gap_and_rejects_other_evidence_kinds(self) -> None:
        slide = complete_reading_first_slide(
            evidence_items=[complete_planned_gap_evidence()], source_refs=[]
        )
        payload = {
            "argument_map_ref": "artifact://deck-argument-map/" + "b" * 64,
            "content_identity_mode": "proposal-only",
            "identity_labels": [
                "diagnostic-hypothesis",
                "solution-recommendation",
                "joint-validation-required",
            ],
            "slides": [
                {
                    **slide,
                    "identity_class": "diagnostic-hypothesis",
                    "core_claim": "诊断假设：流程可能存在重复录入",
                    "speaker_notes": "待联合验证：补充现状材料或降级主张。",
                    "visible_copy": [
                        {
                            "copy_id": "COPY-GAP-01",
                            "role": "body",
                            "text": "诊断假设：重复录入需与客户联合澄清。",
                        }
                    ],
                }
            ],
        }
        self.assertEqual(validate_content_stage("slide-draft-set", payload), payload)
        payload["slides"][0]["evidence_items"][0]["evidence_kind"] = "internet"
        with self.assertRaises(ContractValidationError):
            validate_content_stage("slide-draft-set", payload)

    def test_requires_readability_quality_invariants(self) -> None:
        quality_fields = (
            "independently_readable",
            "information_density",
            "claim_reason_evidence_boundary_complete",
            "review_note",
        )
        for field in quality_fields:
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                del payload["slides"][0]["reading_quality"][field]
                with self.assertRaisesRegex(ContractValidationError, field):
                    validate_content_stage("slide-draft-set", payload)
        for field, invalid in (
            ("independently_readable", 1),
            ("independently_readable", False),
            ("information_density", "overloaded"),
            ("claim_reason_evidence_boundary_complete", 1),
            ("claim_reason_evidence_boundary_complete", False),
            ("review_note", ""),
        ):
            with self.subTest(field=field, invalid=invalid):
                payload = complete_slide_draft_payload()
                payload["slides"][0]["reading_quality"][field] = invalid
                with self.assertRaises(ContractValidationError):
                    validate_content_stage("slide-draft-set", payload)

    def test_requires_complete_sequence_shape(self) -> None:
        for field in (
            "previous_slide_id",
            "next_slide_id",
            "transition_from_previous",
            "transition_to_next",
        ):
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                del payload["slides"][0]["sequence"][field]
                with self.assertRaisesRegex(ContractValidationError, field):
                    validate_content_stage("slide-draft-set", payload)
        for field in ("transition_from_previous", "transition_to_next"):
            with self.subTest(field=field):
                payload = complete_slide_draft_payload()
                payload["slides"][0]["sequence"][field] = ""
                with self.assertRaises(ContractValidationError):
                    validate_content_stage("slide-draft-set", payload)

    def test_requires_unique_contiguous_positive_integer_order(self) -> None:
        for invalid in (True, 0, -1, 1.5, "1"):
            with self.subTest(invalid=invalid):
                payload = complete_slide_draft_payload()
                payload["slides"][0]["order"] = invalid
                with self.assertRaises(ContractValidationError):
                    validate_content_stage("slide-draft-set", payload)
        duplicate = complete_slide_draft_payload(slide_count=2)
        duplicate["slides"][1]["order"] = 1
        with self.assertRaises(ContractValidationError):
            validate_content_stage("slide-draft-set", duplicate)
        gap = complete_slide_draft_payload(slide_count=2)
        gap["slides"][1]["order"] = 3
        with self.assertRaises(ContractValidationError):
            validate_content_stage("slide-draft-set", gap)


if __name__ == "__main__":
    unittest.main()
