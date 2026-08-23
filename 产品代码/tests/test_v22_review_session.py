from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.review.contracts import (
    review_session_identity,
    validate_review_session,
)
from ai_ppt_studio.errors import ContractValidationError


def valid_session() -> dict[str, object]:
    return {
        "review_session_id": "content-session-01",
        "review_type": "content-full-deck",
        "project_id": "project-01",
        "target_artifact_ref": "artifact://reading-deck-blueprint/" + "a" * 64,
        "source_version": "content-v3",
        "revision": 17,
        "status": "ready",
        "open_policy": "notify-only",
        "host_open_status": "not-requested",
        "persistence_status": "saved",
        "host_notification_status": "pending",
        "ai_receipt_status": "pending",
        "created_at": "2026-08-23T00:00:00+00:00",
        "last_opened_at": None,
        "submitted_at": None,
    }


class ReviewSessionContractTests(unittest.TestCase):
    def test_valid_session_round_trips_and_identity_is_stable(self) -> None:
        payload = valid_session()
        self.assertEqual(validate_review_session(payload), payload)
        self.assertEqual(
            review_session_identity(payload),
            (
                "project-01",
                "content-full-deck",
                payload["target_artifact_ref"],
                "content-v3",
                17,
            ),
        )

    def test_rejects_invalid_review_type_status_and_future_revision(self) -> None:
        for field, value in (
            ("review_type", "content-evidence"),
            ("status", "approved"),
            ("open_policy", "auto-open"),
            ("host_open_status", "assumed-open"),
            ("persistence_status", "received"),
            ("host_notification_status", "assumed-sent"),
            ("ai_receipt_status", "assumed-received"),
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = value
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)
        with self.assertRaises(ContractValidationError):
            validate_review_session(valid_session(), current_revision=16)

    def test_requires_target_source_and_timestamp_fields(self) -> None:
        for field in (
            "review_session_id",
            "target_artifact_ref",
            "source_version",
            "created_at",
        ):
            with self.subTest(field=field):
                payload = valid_session()
                payload[field] = ""
                with self.assertRaises(ContractValidationError):
                    validate_review_session(payload, current_revision=17)


if __name__ == "__main__":
    unittest.main()
