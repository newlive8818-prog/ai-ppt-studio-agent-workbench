from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ExperienceValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_experience_fixtures import (
    prepared_experience,
    valid_anti_pattern_payload,
    valid_intake_payload,
    valid_mechanism_payload,
    valid_preference_payload,
)


class V16ExperienceIntakeTests(unittest.TestCase):
    def test_intake_separates_project_execution_from_learning_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_experience(Path(temp))
            valid = valid_intake_payload(refs)
            invalid_payloads = []
            for changes in (
                {"source_type": "chat-summary"},
                {"source_version": ""},
                {"privacy_boundary": ""},
                {"learning_status": "personal"},
                {"learning_status": "stable"},
                {"source_project_id": "another-project"},
            ):
                invalid_payloads.append({**copy.deepcopy(valid), **changes})
            missing_source = copy.deepcopy(valid)
            missing_source["source_refs"] = [
                "artifact://preferred-example/" + "a" * 64
            ]
            invalid_payloads.append(missing_source)
            for index, payload in enumerate(invalid_payloads):
                with self.subTest(index=index), self.assertRaises(
                    (ExperienceValidationError, ArtifactReferenceError)
                ):
                    experience.register_intake(
                        f"invalid-intake-{index}", revision, payload
                    )
                self.assertEqual(experience.kernel.load().revision, revision)

            intake_ref = experience.register_intake(
                "valid-intake", revision, valid
            )
            self.assertTrue(intake_ref.startswith("artifact://experience-intake/"))
            state = experience.kernel.load()
            self.assertEqual(
                state.artifact_heads["experience/intake/intake-preferred-example"],
                intake_ref,
            )
            intake = experience.kernel.artifacts.resolve(
                ArtifactReference.parse(intake_ref)
            )["payload"]
            self.assertEqual(intake["execution_status"], "source-registered")
            self.assertEqual(intake["learning_status"], "intake-only")
            self.assertNotIn("candidate_status", intake)

    def test_one_intake_can_create_three_sanitized_result_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_experience(Path(temp))
            intake_ref = experience.register_intake(
                "three-result-intake", revision, valid_intake_payload(refs)
            )
            revision += 1
            result_payloads = [
                valid_preference_payload(intake_ref, refs),
                valid_mechanism_payload(intake_ref, refs),
                valid_anti_pattern_payload(intake_ref, refs),
            ]
            result_refs: list[str] = []
            for payload in result_payloads:
                result_refs.append(
                    experience.register_learning_result(
                        f"result-{payload['result_id']}", revision, payload
                    )
                )
                revision += 1
            self.assertEqual(len(set(result_refs)), 3)
            state = experience.kernel.load()
            self.assertEqual(state.gate_status["G0"], "open")
            for payload, result_ref in zip(
                result_payloads, result_refs, strict=True
            ):
                self.assertEqual(
                    state.artifact_heads[
                        f"experience/result/{payload['result_type']}/{payload['result_id']}"
                    ],
                    result_ref,
                )
                result = experience.kernel.artifacts.resolve(
                    ArtifactReference.parse(result_ref)
                )["payload"]
                self.assertEqual(result["status"], "candidate")
                self.assertEqual(result["intake_ref"], intake_ref)

            invalid = valid_mechanism_payload(intake_ref, refs)
            invalid["result_id"] = "whole-case-copy"
            invalid["whole_case_copy"] = True
            with self.assertRaises(ExperienceValidationError):
                experience.register_learning_result(
                    "reject-whole-case-copy", revision, invalid
                )
            scored = valid_preference_payload(intake_ref, refs)
            scored["result_id"] = "scored-preference"
            scored["score"] = 98
            with self.assertRaises(ExperienceValidationError):
                experience.register_learning_result(
                    "reject-scored-preference", revision, scored
                )
            unsanitized = valid_anti_pattern_payload(intake_ref, refs)
            unsanitized["result_id"] = "client-specific-pattern"
            unsanitized["privacy_boundary"] = "contains-client-identifiers"
            with self.assertRaises(ExperienceValidationError):
                experience.register_learning_result(
                    "reject-client-specific-pattern", revision, unsanitized
                )

    def test_raw_feedback_cannot_bypass_intake_and_governance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_experience(Path(temp))
            raw_ref = str(
                experience.kernel.artifacts.put(
                    "raw-feedback", {"raw_feedback": "以后都做成三栏"}
                )
            )
            payload = valid_preference_payload(raw_ref, refs)
            with self.assertRaises(ArtifactReferenceError):
                experience.register_learning_result(
                    "raw-feedback-bypass", revision, payload
                )
            self.assertEqual(experience.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
