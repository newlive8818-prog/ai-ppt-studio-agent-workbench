from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    SUPPORTED_TARGET_IDS,
)
from ai_ppt_studio.errors import ContractValidationError, RevisionConflictError
from ai_ppt_studio.kernel.gates import issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def legacy_project(root: Path) -> ProjectKernel:
    kernel = ProjectKernel.initialize(root, project_id="legacy-policy-project")
    kernel.commit(
        command_id="legacy-project-created",
        expected_revision=0,
        event_type="project.created",
        artifact_updates={
            "project/manifest": (
                "project-manifest",
                {"project_id": kernel.project_id, "name": "Legacy project"},
            ),
            "content/blueprint": (
                "content-blueprint",
                {"identity": "preserved-history"},
            ),
        },
    )
    return kernel


def four_target_policy() -> dict:
    payload = copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY)
    payload.update(
        {
            "policy_id": "future-four-target",
            "policy_version": "2.0",
            "required_target_ids": list(SUPPORTED_TARGET_IDS),
            "deferred_target_ids": [],
            "compatibility_claim_scope": list(SUPPORTED_TARGET_IDS),
            "rationale": "Future policy expansion test.",
        }
    )
    return payload


class ReleaseTargetPolicyServiceTests(unittest.TestCase):
    def test_existing_project_binding_is_revision_safe_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = legacy_project(Path(temp))
            service = ReleaseTargetPolicyService(kernel)

            ref, migrated = service.bind_current_policy("bind-policy", 1)
            same_ref, same_state = service.bind_current_policy("bind-policy", 1)
            unchanged_ref, unchanged_state = service.bind_current_policy(
                "bind-policy-again", 2
            )

            self.assertEqual(migrated.revision, 2)
            self.assertEqual(migrated.artifact_heads["release/target-policy"], ref)
            self.assertEqual(same_ref, ref)
            self.assertEqual(same_state.revision, 2)
            self.assertEqual(unchanged_ref, ref)
            self.assertEqual(unchanged_state.revision, 2)
            self.assertIn("content/blueprint", migrated.artifact_heads)
            record = kernel.artifacts.resolve(ArtifactReference.parse(ref))
            self.assertEqual(record["kind"], "release-target-policy")
            self.assertEqual(
                record["payload"]["required_target_ids"], ["macos-powerpoint"]
            )

    def test_binding_rejects_revision_conflict_and_invalid_policy_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = legacy_project(Path(temp))
            service = ReleaseTargetPolicyService(kernel)

            with self.assertRaises(RevisionConflictError):
                service.bind_current_policy("stale-policy", 0)
            invalid = copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY)
            invalid["required_target_ids"] = []
            with self.assertRaises(ContractValidationError) as invalid_error:
                service.bind_policy("invalid-policy", 1, invalid)

            self.assertIn("RELEASE_TARGET_POLICY_INVALID", str(invalid_error.exception))
            self.assertEqual(kernel.load().revision, 1)
            self.assertNotIn("release/target-policy", kernel.load().artifact_heads)

    def test_missing_or_wrong_policy_head_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = legacy_project(Path(temp))
            service = ReleaseTargetPolicyService(kernel)

            with self.assertRaises(ContractValidationError) as missing:
                service.current()
            self.assertIn("RELEASE_TARGET_POLICY_MISSING", str(missing.exception))

            state = kernel.commit(
                command_id="wrong-policy-kind",
                expected_revision=1,
                event_type="test.wrong-policy-kind",
                artifact_updates={
                    "release/target-policy": (
                        "content-blueprint",
                        CURRENT_RELEASE_TARGET_POLICY,
                    )
                },
            )
            with self.assertRaises(ContractValidationError) as invalid:
                service.current()
            self.assertIn("RELEASE_TARGET_POLICY_INVALID", str(invalid.exception))
            self.assertEqual(state.revision, 2)

    def test_policy_change_after_g2_pass_reopens_g2_and_locks_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = legacy_project(Path(temp))
            service = ReleaseTargetPolicyService(kernel)
            _ref, state = service.bind_current_policy("bind-policy", 1)
            evidence_ref = state.artifact_heads["content/blueprint"]
            state = kernel.commit(
                command_id="simulate-late-gates",
                expected_revision=2,
                event_type="test.simulate-late-gates",
                artifact_updates={
                    "delivery/build": (
                        "presentation-build",
                        {"identity": "preserved-immutable-artifact"},
                    )
                },
                gate_mutation=issue_gate_mutation(
                    {"G1": "passed", "G2": "passed", "G3": "passed", "G4": "open"},
                    (evidence_ref,),
                ),
            )

            new_ref, changed = service.bind_policy(
                "expand-policy", state.revision, four_target_policy()
            )

            self.assertEqual(changed.revision, 4)
            self.assertEqual(changed.gate_status["G1"], "passed")
            self.assertEqual(changed.gate_status["G2"], "open")
            self.assertEqual(changed.gate_status["G3"], "locked")
            self.assertEqual(changed.gate_status["G4"], "locked")
            self.assertEqual(changed.artifact_heads["release/target-policy"], new_ref)
            self.assertIn("content/blueprint", changed.artifact_heads)
            self.assertIn("delivery/build", changed.artifact_heads)


if __name__ == "__main__":
    unittest.main()
