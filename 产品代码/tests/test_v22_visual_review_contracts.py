from __future__ import annotations

import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.visual.review_contracts import (
    validate_anchor_feedback_batch,
    validate_anchor_region_feedback,
    validate_visual_contract_review_mark,
)
from ai_ppt_studio.errors import ContractValidationError

REF = "artifact://anchor-slide-set/" + "a" * 64
CONTRACT_REF = "artifact://visual-contract/" + "b" * 64


def region_feedback(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "feedback_id": "feedback-1",
        "anchor_slide_id": "S01",
        "anchor_artifact_ref": REF,
        "normalized_region": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
        "comment": "  标题和正文层级需要拉开  ",
        "order": 1,
        "visual_source_version": "visual-v1",
        "revision": 7,
        "created_at": "2026-08-15T01:00:00+08:00",
        "created_by": "user",
    }
    value.update(updates)
    return value


def anchor_feedback_batch(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "batch_id": "batch-1",
        "project_id": "p1",
        "review_session_id": "visual-review-session-1",
        "visual_contract_ref": CONTRACT_REF,
        "deck_design_system_ref": "artifact://deck-design-system/" + "c" * 64,
        "anchor_slide_set_ref": REF,
        "items": [region_feedback()],
        "source_version": "visual-v1",
        "revision": 7,
        "persistence_status": "saved",
        "host_notification_status": "not-requested",
        "ai_receipt_status": "pending",
        "immutable_after_submit": True,
        "submitted_at": "2026-08-15T02:00:00+08:00",
        "submitted_by": "user",
    }
    value.update(updates)
    return value


class VisualReviewContractTests(unittest.TestCase):
    def test_region_requires_a_perceptible_bounded_rectangle_and_comment(self) -> None:
        normalized = validate_anchor_region_feedback(region_feedback())
        self.assertEqual(normalized["comment"], "标题和正文层级需要拉开")
        for rectangle in (
            {"x": 0.1, "y": 0.1, "width": 0, "height": 0},
            {"x": 0.99, "y": 0.1, "width": 0.2, "height": 0.2},
            {"x": -0.1, "y": 0.1, "width": 0.2, "height": 0.2},
            {"x": 0.1, "y": 0.1, "width": 0.01, "height": 0.2},
            {"x": float("nan"), "y": 0.1, "width": 0.2, "height": 0.2},
            {"x": 0.1, "y": 0.1, "width": float("nan"), "height": 0.2},
            {"x": float("inf"), "y": 0.1, "width": 0.2, "height": 0.2},
            {"x": 0.1, "y": float("-inf"), "width": 0.2, "height": 0.2},
        ):
            invalid = region_feedback(normalized_region=rectangle)
            with self.subTest(rectangle=rectangle), self.assertRaises(
                ContractValidationError
            ):
                validate_anchor_region_feedback(invalid)
        with self.assertRaises(ContractValidationError):
            validate_anchor_region_feedback(region_feedback(comment="   "))

    def test_region_requires_user_authorship_and_an_offset_timestamp(self) -> None:
        for updates in (
            {"created_by": "agent"},
            {"created_at": "not-a-timestamp"},
            {"created_at": "2026-08-15T01:00:00"},
        ):
            with self.subTest(updates=updates), self.assertRaises(
                ContractValidationError
            ):
                validate_anchor_region_feedback(region_feedback(**updates))

    def test_batch_rejects_noncanonical_authorship_and_timestamp_lineage(self) -> None:
        variants = (
            anchor_feedback_batch(
                items=[region_feedback(created_by="agent")]
            ),
            anchor_feedback_batch(
                items=[region_feedback(created_at="not-a-timestamp")]
            ),
            anchor_feedback_batch(
                items=[region_feedback(created_at="2026-08-15T01:00:00")]
            ),
            anchor_feedback_batch(
                items=[region_feedback(created_at="2026-08-15T03:00:00+08:00")]
            ),
            anchor_feedback_batch(submitted_at="not-a-timestamp"),
            anchor_feedback_batch(submitted_at="2026-08-15T02:00:00"),
            anchor_feedback_batch(submitted_by="agent"),
        )
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(
                ContractValidationError
            ):
                validate_anchor_feedback_batch(payload)

    def test_contract_marks_keep_field_and_text_range_context(self) -> None:
        field = validate_visual_contract_review_mark(
            {
                "mark_id": "mark-field",
                "target_type": "contract-field",
                "slide_id": "S01",
                "deck_section_id": "",
                "target_key": "composition_intent",
                "selected_text": "",
                "context_before": "",
                "context_after": "",
                "comment": "构图需要更明确",
                "visual_contract_ref": CONTRACT_REF,
                "source_version": "visual-v1",
                "revision": 7,
                "created_at": "2026-08-15T01:00:00+08:00",
                "created_by": "user",
            }
        )
        text = copy.deepcopy(field)
        text.update(
            {
                "mark_id": "mark-text",
                "target_type": "text-range",
                "selected_text": "阅读顺序",
                "context_before": "当前",
                "context_after": "需要调整",
            }
        )
        for representation in ("browser-v1", "browser-v2"):
            with self.subTest(representation=representation):
                versioned = validate_visual_contract_review_mark(
                    {**text, "anchor_representation_version": representation}
                )
                self.assertEqual(versioned["selected_text"], "阅读顺序")
                self.assertEqual(
                    versioned["anchor_representation_version"],
                    representation,
                )
        for invalid in (
            {**field, "target_type": "point"},
            {**text, "selected_text": ""},
            {**field, "target_key": ""},
            {**field, "slide_id": "S01", "deck_section_id": "deck-design-system"},
            {**field, "created_by": "agent"},
            {**field, "created_at": "not-a-timestamp"},
            {**field, "created_at": "2026-08-15T01:00:00"},
            {**text, "anchor_representation_version": "browser-v3"},
            {**field, "anchor_representation_version": "browser-v2"},
        ):
            with self.assertRaises(ContractValidationError):
                validate_visual_contract_review_mark(invalid)

        with self.assertRaises(ContractValidationError):
            validate_visual_contract_review_mark(
                {**field, "created_at": "2999-01-01T00:00:00Z"},
                created_not_after=datetime.now(timezone.utc),
            )

    def test_text_range_contract_uses_ecmascript_edge_whitespace(self) -> None:
        base = {
            "mark_id": "mark-text-whitespace",
            "target_type": "text-range",
            "slide_id": "S01",
            "deck_section_id": "",
            "target_key": "composition_intent",
            "selected_text": "beta",
            "context_before": "alpha",
            "context_after": "gamma",
            "comment": "保留浏览器文字表示",
            "visual_contract_ref": CONTRACT_REF,
            "source_version": "visual-v1",
            "revision": 7,
            "created_at": "2026-08-15T01:00:00+08:00",
            "created_by": "user",
            "anchor_representation_version": "browser-v2",
        }
        cases = (
            (
                "NEL-before",
                {"context_before": "alpha\u0085"},
                {"context_before": "alpha\u0085"},
            ),
            (
                "NEL-after",
                {"context_after": "\u0085gamma"},
                {"context_after": "\u0085gamma"},
            ),
            (
                "Python-only-control-whitespace",
                {"context_before": "alpha\u001c\u001d\u001e\u001f"},
                {"context_before": "alpha\u001c\u001d\u001e\u001f"},
            ),
            (
                "ECMAScript-BOM-edge",
                {
                    "selected_text": "\ufeffbeta\ufeff",
                    "context_before": "\ufeffalpha\ufeff",
                    "context_after": "\ufeffgamma\ufeff",
                },
                {
                    "selected_text": "beta",
                    "context_before": "alpha",
                    "context_after": "gamma",
                },
            ),
            (
                "ECMAScript-BOM-only-optional-context",
                {
                    "context_before": "\ufeff",
                    "context_after": "\ufeff",
                },
                {
                    "context_before": "",
                    "context_after": "",
                },
            ),
        )

        for name, updates, expected in cases:
            with self.subTest(name=name):
                mark = validate_visual_contract_review_mark({**base, **updates})
                self.assertEqual(
                    {key: mark[key] for key in expected},
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
