from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_delivery_fixtures import (
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)
from tests.v16_visual_fixtures import prepared_g2, prepared_visual_contracts


class V22ReleasePolicyIntegrationTests(unittest.TestCase):
    def test_visual_brief_and_g2_use_only_current_required_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, _revision, refs = prepared_visual_contracts(Path(temp))
            policy_ref, policy = ReleaseTargetPolicyService(visual.kernel).current()
            brief = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(refs["brief"])
            )["payload"]
            self.assertEqual(brief["target_ids"], list(policy.required_target_ids))
            self.assertEqual(policy.required_target_ids, ("macos-powerpoint",))

        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=3)
            state = visual.kernel.load()
            policy_ref, _policy = ReleaseTargetPolicyService(visual.kernel).current()
            target_slots = sorted(
                slot for slot in state.artifact_heads if slot.startswith("visual/target-evidence/G2/")
            )
            self.assertEqual(target_slots, ["visual/target-evidence/G2/macos-powerpoint"])
            published = visual.publish_visual_review("publish-policy-bound", revision)
            contract = visual.kernel.artifacts.resolve(
                ArtifactReference.parse(published.artifact_heads["visual/contract"])
            )["payload"]
            self.assertEqual(contract["release_target_policy_ref"], policy_ref)
            self.assertEqual(
                [item["target_id"] for item in contract["target_evidence_identities"]],
                ["macos-powerpoint"],
            )

    def test_g4_package_and_status_distinguish_required_from_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_delivery_ready(Path(temp), slide_count=3)
            policy_ref, _policy = ReleaseTargetPolicyService(delivery.kernel).current()
            target_slots = sorted(
                slot for slot in delivery.kernel.load().artifact_heads
                if slot.startswith("delivery/target-evidence/G4/")
            )
            self.assertEqual(target_slots, ["delivery/target-evidence/G4/macos-powerpoint"])
            package_ref = delivery.register_delivery_package(
                "policy-bound-package",
                revision,
                valid_package_payload(refs, package_artifacts(delivery, refs)),
            )
            package = delivery.kernel.artifacts.resolve(
                ArtifactReference.parse(package_ref)
            )["payload"]
            self.assertEqual(package["release_target_policy_ref"], policy_ref)
            rows = delivery.delivery_status_projection()["targets"]
            self.assertEqual(
                {row["target_id"]: row["status"] for row in rows},
                {
                    "macos-powerpoint": "passed",
                    "macos-wps": "deferred",
                    "windows-powerpoint": "deferred",
                    "windows-wps": "deferred",
                },
            )


if __name__ == "__main__":
    unittest.main()
