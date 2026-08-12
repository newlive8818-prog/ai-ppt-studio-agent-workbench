from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from tests.v16_experience_fixtures import (
    prepared_experience,
    valid_intake_payload,
    valid_mechanism_payload,
    valid_preference_payload,
)


class V16ExperienceBridgeTests(unittest.TestCase):
    def test_existing_commit_operation_and_snapshot_project_experience(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            experience, revision, refs = prepared_experience(project)
            intake = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "kind": "experience",
                    "payload": {
                        **valid_intake_payload(refs),
                        "artifact_type": "experience-intake",
                    },
                }
            )
            intake_ref = intake["result"]["artifact_ref"]
            revision = intake["result"]["snapshot"]["revision"]
            for payload in (
                {
                    **valid_preference_payload(intake_ref, refs),
                    "artifact_type": "preference-signal",
                },
                {
                    **valid_mechanism_payload(intake_ref, refs),
                    "artifact_type": "professional-mechanism-candidate",
                },
            ):
                result = dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision,
                        "kind": "experience",
                        "payload": payload,
                    }
                )
                revision = result["result"]["snapshot"]["revision"]
            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]
            projection = snapshot["experience"]
            self.assertEqual(
                set(projection),
                {
                    "intake_counts",
                    "result_counts",
                    "candidates",
                    "role_slices",
                    "application_outcomes",
                    "stable_release_candidates",
                },
            )
            self.assertEqual(projection["intake_counts"]["total"], 1)
            self.assertEqual(
                projection["intake_counts"]["by_source_type"],
                {"preferred-example": 1},
            )
            self.assertEqual(projection["result_counts"]["total"], 2)
            self.assertEqual(
                projection["result_counts"]["by_result_type"],
                {
                    "preference-signal": 1,
                    "professional-mechanism-candidate": 1,
                },
            )
            self.assertEqual(projection["candidates"], [])
            self.assertNotIn("raw_feedback", str(projection))
            self.assertNotIn("diagnosis", str(projection))
            self.assertNotIn("case_content", str(projection))

    def test_unsupported_experience_artifact_does_not_change_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            experience, revision, _refs = prepared_experience(project)
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "expected_revision": revision,
                        "kind": "experience",
                        "payload": {
                            "artifact_type": "legacy-experience-rule",
                            "status": "stable",
                        },
                    }
                )
            self.assertEqual(experience.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
