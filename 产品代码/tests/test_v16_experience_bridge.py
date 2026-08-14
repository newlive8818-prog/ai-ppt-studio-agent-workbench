from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.test_v16_experience_evolution import prepared_personal_candidate
from tests.v16_experience_fixtures import (
    prepared_experience,
    valid_intake_payload,
    valid_mechanism_payload,
    valid_preference_payload,
)


class V16ExperienceBridgeTests(unittest.TestCase):
    def test_task_bound_evolution_decision_atomically_updates_both_heads_and_replays(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            experience, revision, refs = prepared_personal_candidate(project)
            requested = dispatch_v16({
                "operation": "request-agent-action",
                "project_root": str(project),
                "expected_revision": revision,
                "command_id": "atomic-evolution-task",
                "action_type": "evaluate-experience",
                "target_refs": [refs["candidate"], refs["policy"]],
                "instructions": "依据当前评估证据作出经验进化决定。",
            })["result"]
            task_id = requested["task"]["task_id"]
            payload = {
                "artifact_type": "experience-evolution-decision",
                "decision_id": "atomic-disable-reading-path",
                "action": "disable",
                "candidate_ref": refs["candidate"],
                "policy_ref": refs["policy"],
                "evaluation_refs": refs["promotion_evaluations"],
                "reason": "治理复核要求暂停推荐并保留历史。",
                "decided_by": "经验进化治理智能体",
            }
            event_count = len(tuple(experience.kernel.events_root.iterdir()))
            committed = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "atomic-evolution-result",
                "kind": "experience",
                "task_id": task_id,
                "payload": payload,
            })["result"]
            self.assertEqual(committed["snapshot"]["revision"], revision + 2)
            self.assertEqual(
                len(tuple(experience.kernel.events_root.iterdir())), event_count + 1
            )
            state = experience.kernel.load()
            self.assertEqual(
                state.artifact_heads["experience/candidate/candidate-reading-path"],
                committed["artifact_ref"],
            )
            self.assertIn(
                "experience/evolution-decision/atomic-disable-reading-path",
                state.artifact_heads,
            )
            task = experience.kernel.artifacts.resolve(ArtifactReference.parse(
                state.artifact_heads[f"agent/task/{task_id}"]
            ))["payload"]
            self.assertEqual(task["status"], "completed")
            self.assertEqual(task["result_refs"], [committed["artifact_ref"]])
            events = tuple(experience.kernel.events_root.iterdir())

            replayed = dispatch_v16({
                "operation": "commit-artifact",
                "project_root": str(project),
                "expected_revision": revision + 1,
                "command_id": "atomic-evolution-result",
                "kind": "experience",
                "task_id": task_id,
                "payload": payload,
            })["result"]
            self.assertEqual(replayed, committed)
            self.assertEqual(tuple(experience.kernel.events_root.iterdir()), events)

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
