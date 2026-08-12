from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_experience_fixtures import (
    application_evidence,
    prepared_candidate,
    valid_application_payload,
    valid_evaluation_payload,
)


def resolve_payload(experience, value: str) -> dict:
    return experience.kernel.artifacts.resolve(
        ArtifactReference.parse(value)
    )["payload"]


def register_evaluated_application(
    experience,
    revision: int,
    refs: dict[str, object],
    *,
    application_id: str,
    project_id: str,
    result: str = "success",
    simulation: bool = False,
) -> tuple[int, str]:
    context = {
        "scene": "presales",
        "audience": "executive",
        "slide_task": "solution-overview",
        "conditions": ["reading-first", "strict-B"],
    }
    runtime_ref = application_evidence(
        experience, project_id, context, simulation=simulation
    )
    application_ref = experience.record_application(
        f"record-{application_id}",
        revision,
        valid_application_payload(
            refs,
            application_id=application_id,
            project_id=project_id,
            runtime_evidence_ref=runtime_ref,
        ),
    )
    revision += 1
    evaluation_ref = experience.evaluate_application(
        f"evaluate-{application_id}",
        revision,
        valid_evaluation_payload(
            experience, application_ref, result=result
        ),
    )
    return revision + 1, evaluation_ref


def register_policy(experience, revision: int) -> tuple[int, str]:
    policy_ref = experience.register_evolution_policy(
        "experience-evolution-policy",
        revision,
        {
            "policy_version": "personal-experience-policy/test-v1",
            "threshold_status": "configurable-pending-real-validation",
            "minimum_distinct_accepted_projects": 2,
            "minimum_failure_projects_for_demotion": 2,
            "requires_professional_review": True,
            "requires_user_acceptance": True,
            "simulation_evidence_forbidden": True,
        },
    )
    return revision + 1, policy_ref


def prepared_personal_candidate(project: Path):
    experience, revision, refs = prepared_candidate(project)
    revision, evaluation_b = register_evaluated_application(
        experience,
        revision,
        refs,
        application_id="application-project-b",
        project_id="real-project-b",
    )
    revision, evaluation_c = register_evaluated_application(
        experience,
        revision,
        refs,
        application_id="application-project-c",
        project_id="real-project-c",
    )
    revision, policy_ref = register_policy(experience, revision)
    personal_ref = experience.evolve_candidate(
        "promote-candidate",
        revision,
        {
            "decision_id": "decision-promote-reading-path",
            "action": "promote",
            "candidate_ref": refs["candidate"],
            "policy_ref": policy_ref,
            "evaluation_refs": [evaluation_b, evaluation_c],
            "reason": "当前策略要求的不同项目证据已经完整",
            "decided_by": "经验进化治理智能体",
        },
    )
    return experience, revision + 1, {
        **refs,
        "candidate": personal_ref,
        "policy": policy_ref,
        "promotion_evaluations": [evaluation_b, evaluation_c],
    }


class V16ExperienceEvolutionTests(unittest.TestCase):
    def test_application_requires_exact_context_and_evaluation_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_candidate(Path(temp))
            context = {
                "scene": "presales",
                "audience": "executive",
                "slide_task": "solution-overview",
                "conditions": ["reading-first", "strict-B"],
            }
            runtime_ref = application_evidence(
                experience, "real-project-b", context
            )
            valid = valid_application_payload(
                refs,
                application_id="application-exact-context",
                project_id="real-project-b",
                runtime_evidence_ref=runtime_ref,
            )
            mismatched = copy.deepcopy(valid)
            mismatched["target_context"]["audience"] = "technical-team"
            with self.assertRaises(ExperienceValidationError):
                experience.record_application(
                    "reject-context-mismatch", revision, mismatched
                )
            application_ref = experience.record_application(
                "matched-application", revision, valid
            )
            revision += 1
            invalid_evaluation = valid_evaluation_payload(
                experience, application_ref
            )
            invalid_evaluation["user_outcome"] = "not-evaluated"
            with self.assertRaises(ExperienceValidationError):
                experience.evaluate_application(
                    "reject-unevaluated", revision, invalid_evaluation
                )
            evaluation_ref = experience.evaluate_application(
                "accepted-evaluation",
                revision,
                valid_evaluation_payload(experience, application_ref),
            )
            evaluation = resolve_payload(experience, evaluation_ref)
            self.assertEqual(evaluation["promotion_eligibility"], "eligible")
            self.assertEqual(evaluation["application_project_id"], "real-project-b")

    def test_simulated_or_wrong_context_application_cannot_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_candidate(Path(temp))
            revision, simulated_eval = register_evaluated_application(
                experience,
                revision,
                refs,
                application_id="simulated-application",
                project_id="simulated-project",
                simulation=True,
            )
            revision, real_eval = register_evaluated_application(
                experience,
                revision,
                refs,
                application_id="real-application",
                project_id="real-project-b",
            )
            revision, policy_ref = register_policy(experience, revision)
            with self.assertRaises(ExperienceValidationError):
                experience.evolve_candidate(
                    "reject-simulated-promotion",
                    revision,
                    {
                        "decision_id": "decision-reject-simulation",
                        "action": "promote",
                        "candidate_ref": refs["candidate"],
                        "policy_ref": policy_ref,
                        "evaluation_refs": [simulated_eval, real_eval],
                        "reason": "模拟证据不得计入真实晋级",
                        "decided_by": "经验进化治理智能体",
                    },
                )
            self.assertEqual(experience.kernel.load().revision, revision)

    def test_policy_governs_promotion_demotion_disable_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_personal_candidate(Path(temp))
            personal_ref = refs["candidate"]
            personal = resolve_payload(experience, personal_ref)
            self.assertEqual(personal["level"], "personal")
            self.assertEqual(personal["version"], 2)

            failure_refs: list[str] = []
            for suffix in ("d", "e"):
                revision, evaluation_ref = register_evaluated_application(
                    experience,
                    revision,
                    refs,
                    application_id=f"failure-project-{suffix}",
                    project_id=f"real-project-{suffix}",
                    result="failure",
                )
                failure_refs.append(evaluation_ref)
            demoted_ref = experience.evolve_candidate(
                "demote-candidate",
                revision,
                {
                    "decision_id": "decision-demote-reading-path",
                    "action": "demote",
                    "candidate_ref": personal_ref,
                    "policy_ref": refs["policy"],
                    "evaluation_refs": failure_refs,
                    "reason": "不同项目出现策略阈值要求的失败证据",
                    "decided_by": "经验进化治理智能体",
                },
            )
            revision += 1
            self.assertEqual(resolve_payload(experience, demoted_ref)["level"], "candidate")
            restored_ref = experience.rollback_candidate(
                "rollback-to-personal",
                revision,
                candidate_id="candidate-reading-path",
                target_version_ref=personal_ref,
                reason="复核确认降级证据适用范围错误，恢复上一有效个人经验",
            )
            revision += 1
            restored = resolve_payload(experience, restored_ref)
            self.assertEqual(restored["level"], "personal")
            self.assertEqual(restored["restored_from"], personal_ref)
            self.assertEqual(restored["previous_version_ref"], demoted_ref)
            disabled_ref = experience.evolve_candidate(
                "disable-candidate",
                revision,
                {
                    "decision_id": "decision-disable-reading-path",
                    "action": "disable",
                    "candidate_ref": restored_ref,
                    "policy_ref": refs["policy"],
                    "evaluation_refs": failure_refs,
                    "reason": "治理审查要求暂停推荐并保留历史",
                    "decided_by": "经验进化治理智能体",
                },
            )
            disabled = resolve_payload(experience, disabled_ref)
            self.assertEqual(disabled["level"], "disabled")
            self.assertFalse(disabled["enabled"])
            self.assertEqual(resolve_payload(experience, personal_ref)["level"], "personal")

    def test_runtime_can_only_propose_a_stable_release_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            experience, revision, refs = prepared_personal_candidate(Path(temp))
            stable_files = [
                ROOT / "skills" / "ai-ppt-studio" / "SKILL.md",
                ROOT / "src" / "ai_ppt_studio" / "role_registry.py",
                ROOT / "src" / "ai_ppt_studio" / "scenario_packs.py",
            ]
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in stable_files
            }
            regression_refs = [
                str(
                    experience.kernel.artifacts.put(
                        "capability-regression",
                        {"kind": kind, "result": "passed"},
                    )
                )
                for kind in ("positive", "negative", "cross-role")
            ]
            valid = {
                "release_candidate_id": "stable-reading-path-v1",
                "source_experience_refs": [refs["candidate"]],
                "positive_regression_refs": [regression_refs[0]],
                "negative_regression_refs": [regression_refs[1]],
                "cross_role_review_refs": [regression_refs[2]],
                "scope": "presales-reading-first",
                "counterexamples": ["证据链不完整时不得应用"],
                "failure_boundaries": ["不得改变事实与质量门"],
                "proposed_versions": {
                    "stable_prompt": "prompt/release-candidate-v1",
                    "role_contract": "roles/release-candidate-v1",
                    "scenario_pack": "scenario/release-candidate-v1",
                },
            }
            forbidden = {**valid, "publish": True}
            with self.assertRaises(ExperienceValidationError):
                experience.propose_stable_release_candidate(
                    "reject-runtime-publish", revision, forbidden
                )
            release_ref = experience.propose_stable_release_candidate(
                "stable-release-candidate", revision, valid
            )
            release = resolve_payload(experience, release_ref)
            self.assertEqual(release["status"], "release-candidate")
            self.assertFalse(release["runtime_publish_allowed"])
            after = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in stable_files
            }
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
