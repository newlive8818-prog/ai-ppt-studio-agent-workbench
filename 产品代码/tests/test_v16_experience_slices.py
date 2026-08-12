from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_experience_fixtures import prepared_learning_results


def target_context() -> dict[str, object]:
    return {
        "scene": "presales",
        "audience": "executive",
        "slide_task": "solution-overview",
        "conditions": ["reading-first", "strict-B", "executive-audience"],
    }


class V16ExperienceSliceTests(unittest.TestCase):
    def test_preference_can_rank_only_fully_qualified_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_learning_results(Path(temp))
            option_refs = [
                str(
                    experience.kernel.artifacts.put(
                        "qualified-option",
                        {"option_id": option_id, "identity": "simulated-option"},
                    )
                )
                for option_id in ("option-a", "option-b")
            ]
            valid = {
                "option_refs": option_refs,
                "qualification_results": [
                    {
                        "option_ref": option_ref,
                        "fact_result": "passed",
                        "content_result": "passed",
                        "aesthetic_result": "passed",
                        "engineering_result": "passed",
                    }
                    for option_ref in option_refs
                ],
                "preference_signal_refs": [refs["preference"]],
                "selected_option_ref": option_refs[1],
                "selection_reason": "两个方案均合格后按已声明偏好择优",
            }
            failed = copy.deepcopy(valid)
            failed["qualification_results"][0]["aesthetic_result"] = "failed"
            with self.assertRaises(ExperienceValidationError):
                experience.register_qualified_selection(
                    "reject-unqualified-option", revision, failed
                )
            scored = copy.deepcopy(valid)
            scored["qualification_results"][0]["score"] = 9
            with self.assertRaises(ExperienceValidationError):
                experience.register_qualified_selection(
                    "reject-score-selection", revision, scored
                )
            self.assertEqual(experience.kernel.load().revision, revision)

            selection_ref = experience.register_qualified_selection(
                "qualified-selection", revision, valid
            )
            selection = experience.kernel.artifacts.resolve(
                ArtifactReference.parse(selection_ref)
            )["payload"]
            self.assertEqual(selection["qualification_status"], "passed")
            self.assertEqual(selection["selected_option_ref"], option_refs[1])
            self.assertEqual(
                selection["preference_signal_refs"], [refs["preference"]]
            )

    def test_role_slices_isolate_producer_and_reviewer_experience(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            experience, revision, refs = prepared_learning_results(
                root / "schema3-project"
            )
            all_refs = [
                refs["mechanism"],
                refs["preference"],
                refs["anti_pattern"],
            ]
            producer_ref = experience.compile_role_slice(
                "producer-slice",
                revision,
                role_id="deck-designer",
                task_type="deliberate-design",
                target_context=target_context(),
                experience_version_refs=all_refs,
            )
            revision += 1
            reviewer_ref = experience.compile_role_slice(
                "reviewer-slice",
                revision,
                role_id="visual-aesthetic-reviewer",
                task_type="review-aesthetic",
                target_context=target_context(),
                experience_version_refs=all_refs,
            )
            producer = experience.kernel.artifacts.resolve(
                ArtifactReference.parse(producer_ref)
            )["payload"]
            reviewer = experience.kernel.artifacts.resolve(
                ArtifactReference.parse(reviewer_ref)
            )["payload"]
            self.assertEqual(producer["target_role_display_name"], "整 deck 设计师")
            self.assertEqual(reviewer["target_role_display_name"], "审美质量审查师")
            self.assertEqual(
                [entry["result_type"] for entry in producer["experience_entries"]],
                ["professional-mechanism-candidate", "preference-signal"],
            )
            self.assertEqual(
                [entry["result_type"] for entry in reviewer["experience_entries"]],
                ["preference-signal", "anti-pattern-candidate"],
            )
            self.assertEqual(
                producer["excluded_experience_refs"], [refs["anti_pattern"]]
            )
            self.assertEqual(
                reviewer["excluded_experience_refs"], [refs["mechanism"]]
            )
            for item in (producer, reviewer):
                self.assertEqual(item["target_context"], target_context())
                self.assertTrue(item["compiled_at"].endswith("+00:00"))
                for entry in item["experience_entries"]:
                    self.assertTrue(entry["source_refs"])
                    self.assertEqual(entry["version"], 1)
                    self.assertTrue(entry["scope"])
                    self.assertTrue(entry["match_reasons"])
                    self.assertEqual(entry["application_outcomes"], [])
                self.assertNotIn("raw_feedback", str(item))
                self.assertNotIn("producer_self_evaluation", str(item))

            pack = ContextCompiler(experience.kernel).compile_role_task(
                role_id="deck-designer",
                task_type="deliberate-design",
                project_revision=experience.kernel.load().revision,
                target_refs=[],
                instructions="执行已治理的视觉设计任务",
                experience_slice_ref=producer_ref,
            )
            self.assertEqual(
                pack["layers"]["experience_slice"]["slice_refs"], [producer_ref]
            )
            self.assertEqual(
                pack["layers"]["output_contract"]["reference_format"],
                "artifact://<kind>/<sha256>",
            )


if __name__ == "__main__":
    unittest.main()
