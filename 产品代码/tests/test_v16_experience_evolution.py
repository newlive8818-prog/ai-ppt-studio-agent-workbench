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
from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v16_experience_fixtures import (
    application_evidence,
    prepared_candidate,
    valid_application_payload,
    valid_evaluation_payload,
)
from tests.v22_experience_fixtures import experience_item


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
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            experience = ExperienceService(kernel)
            experience_ref, _item, state = experience.absorb_same_type(
                command_id="absorb",
                expected_revision=0,
                payload=experience_item(),
            )
            before = kernel.load()
            with self.assertRaises(ExperienceValidationError):
                experience.record_application(
                    command_id="reject-context-mismatch",
                    expected_revision=state.revision,
                    experience_ref=experience_ref,
                    target_project_id="real-project-b",
                    target_type_signature="presales:manufacturing:decision",
                    context={"conditions": ["阅读优先"]},
                    evidence_refs=[
                        "artifact://reading-deck-blueprint/" + "e" * 64
                    ],
                    applied_at="2026-08-15T01:00:00+08:00",
                )
            self.assertEqual(kernel.load(), before)
            application_ref, application, state = experience.record_application(
                command_id="matched-application",
                expected_revision=state.revision,
                experience_ref=experience_ref,
                target_project_id="real-project-b",
                target_type_signature="presales:manufacturing:decision",
                context={"conditions": ["阅读优先"]},
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "e" * 64
                ],
                applied_at="2026-08-15T01:00:00+08:00",
                explicit_validation=True,
            )
            self.assertTrue(application["explicit_validation"])
            outcome_ref, outcome, _state = experience.evaluate_application(
                command_id="accepted-evaluation",
                expected_revision=state.revision,
                application_ref=application_ref,
                outcome="success",
                user_outcome_ref="host-message://accepted-real-project-b",
                hard_gate_refs=[
                    "artifact://content-hard-gate-record/" + "f" * 64
                ],
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "1" * 64
                ],
                evaluated_at="2026-08-15T02:00:00+08:00",
            )
            self.assertTrue(outcome_ref)
            self.assertEqual(outcome["outcome"], "success")
            self.assertEqual(outcome["target_project_id"], "real-project-b")

    def test_simulated_or_wrong_context_application_cannot_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            experience = ExperienceService(kernel)
            same_type_ref, _item, state = experience.absorb_same_type(
                command_id="absorb",
                expected_revision=0,
                payload=experience_item(),
            )
            with self.assertRaises(ExperienceValidationError):
                experience.promote_global(
                    command_id="reject-unproven-promotion",
                    expected_revision=state.revision,
                    same_type_ref=same_type_ref,
                )
            self.assertEqual(kernel.load().revision, state.revision)

    def test_policy_governs_promotion_demotion_disable_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            experience = ExperienceService(kernel)
            same_type_ref, _item, state = experience.absorb_same_type(
                command_id="absorb",
                expected_revision=0,
                payload=experience_item(),
            )
            global_ref, global_item, state = experience.promote_global(
                command_id="promote-by-user",
                expected_revision=state.revision,
                same_type_ref=same_type_ref,
                user_global_directive_ref="host-message://use-globally",
            )
            self.assertEqual(global_item["layer"], "global")
            application_ref, _application, state = experience.record_application(
                command_id="apply-counterexample",
                expected_revision=state.revision,
                experience_ref=global_ref,
                target_project_id="finance-project",
                target_type_signature="presales:finance:decision",
                context={"conditions": ["阅读优先"]},
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "2" * 64
                ],
                applied_at="2026-08-15T03:00:00+08:00",
            )
            experience.evaluate_application(
                command_id="evaluate-counterexample",
                expected_revision=state.revision,
                application_ref=application_ref,
                outcome="failure",
                user_outcome_ref="host-message://rejected-finance",
                hard_gate_refs=[
                    "artifact://content-hard-gate-record/" + "3" * 64
                ],
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "4" * 64
                ],
                evaluated_at="2026-08-15T04:00:00+08:00",
            )
            self.assertEqual(
                experience.recommend(
                    domain="content",
                    type_signature="presales:finance:decision",
                    applicability={"conditions": ["阅读优先"]},
                ),
                [],
            )
            current_ref, current = experience.get_current(
                "content", "global", "exp-reading-path"
            )
            rollback_ref, rolled_back, _state = experience.rollback(
                command_id="rollback",
                expected_revision=kernel.load().revision,
                experience_ref=current_ref,
                target_version_ref=global_ref,
                reason="恢复用户明确认可的版本并等待重新限定范围。",
                rolled_back_at="2026-08-15T05:00:00+08:00",
            )
            self.assertNotEqual(rollback_ref, current_ref)
            self.assertEqual(rolled_back["version"], current["version"] + 1)
            self.assertEqual(rolled_back["rollback_from_version"], 1)

    def test_runtime_can_only_propose_a_stable_release_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            experience = ExperienceService(kernel)
            experience.absorb_same_type(
                command_id="absorb",
                expected_revision=0,
                payload=experience_item(),
            )
            stable_files = [
                ROOT / "skills" / "ai-ppt-studio" / "SKILL.md",
                ROOT / "src" / "ai_ppt_studio" / "role_registry.py",
                ROOT / "src" / "ai_ppt_studio" / "scenario_packs.py",
            ]
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in stable_files
            }
            projection = experience.experience_projection()
            self.assertEqual(projection["layers"], ["same-type", "global"])
            self.assertFalse(
                hasattr(experience, "propose_stable_release_candidate")
            )
            after = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in stable_files
            }
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
