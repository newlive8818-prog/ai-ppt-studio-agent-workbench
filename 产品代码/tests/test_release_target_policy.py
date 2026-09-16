from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    SUPPORTED_TARGET_IDS,
    ReleaseTargetPolicy,
)


class ReleaseTargetPolicyTests(unittest.TestCase):
    def test_current_policy_requires_only_macos_powerpoint(self) -> None:
        policy = ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY)

        self.assertEqual(policy.policy_id, "v1.6-macos-powerpoint")
        self.assertEqual(policy.required_target_ids, ("macos-powerpoint",))
        self.assertEqual(
            policy.deferred_target_ids,
            ("macos-wps", "windows-powerpoint", "windows-wps"),
        )
        self.assertEqual(
            policy.compatibility_claim_scope,
            policy.required_target_ids,
        )
        self.assertEqual(policy.as_payload(), CURRENT_RELEASE_TARGET_POLICY)

    def test_policy_partitions_every_supported_profile(self) -> None:
        policy = ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY)

        self.assertTrue(
            set(policy.required_target_ids).isdisjoint(policy.deferred_target_ids)
        )
        self.assertEqual(
            set(policy.required_target_ids + policy.deferred_target_ids),
            set(SUPPORTED_TARGET_IDS),
        )

    def test_policy_rejects_invalid_target_partitions_and_claim_scope(self) -> None:
        cases = {
            "empty-required": {"required_target_ids": []},
            "duplicate-required": {
                "required_target_ids": ["macos-powerpoint", "macos-powerpoint"]
            },
            "duplicate-deferred": {
                "deferred_target_ids": [
                    "macos-wps",
                    "windows-powerpoint",
                    "windows-wps",
                    "windows-wps",
                ]
            },
            "overlap": {
                "deferred_target_ids": [
                    "macos-powerpoint",
                    "macos-wps",
                    "windows-powerpoint",
                    "windows-wps",
                ]
            },
            "incomplete": {
                "deferred_target_ids": ["macos-wps", "windows-powerpoint"]
            },
            "unsupported": {
                "deferred_target_ids": [
                    "macos-wps",
                    "windows-powerpoint",
                    "linux-libreoffice",
                ]
            },
            "claim-scope": {
                "compatibility_claim_scope": [
                    "macos-powerpoint",
                    "windows-powerpoint",
                ]
            },
        }
        for name, update in cases.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY)
                payload.update(update)
                with self.assertRaises(ValueError):
                    ReleaseTargetPolicy.from_payload(payload)

    def test_policy_rejects_inactive_missing_identity_or_naive_time(self) -> None:
        cases = {
            "inactive": {"status": "inactive"},
            "missing-id": {"policy_id": ""},
            "missing-version": {"policy_version": ""},
            "missing-decision-source": {"decision_source": ""},
            "missing-rationale": {"rationale": ""},
            "invalid-time": {"effective_at": "not-a-time"},
            "naive-time": {"effective_at": "2026-08-13T00:00:00"},
        }
        for name, update in cases.items():
            with self.subTest(name=name):
                payload = copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY)
                payload.update(update)
                with self.assertRaises(ValueError):
                    ReleaseTargetPolicy.from_payload(payload)

    def test_policy_rejects_non_object_payload(self) -> None:
        with self.assertRaises(ValueError):
            ReleaseTargetPolicy.from_payload([])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
