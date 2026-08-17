from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    SUPPORTED_TARGET_IDS,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.gates import issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


def expanded_policy() -> dict[str, object]:
    payload = copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY)
    payload.update(
        policy_id="future-four-target",
        policy_version="2.0",
        required_target_ids=list(SUPPORTED_TARGET_IDS),
        deferred_target_ids=[],
        compatibility_claim_scope=list(SUPPORTED_TARGET_IDS),
        rationale="未来版本的显式扩展策略。",
    )
    return payload


class V22ReleaseTargetPolicyTests(unittest.TestCase):
    def test_current_policy_requires_only_macos_powerpoint(self) -> None:
        policy = ReleaseTargetPolicy.from_payload(CURRENT_RELEASE_TARGET_POLICY)
        self.assertEqual(policy.required_target_ids, ("macos-powerpoint",))
        self.assertEqual(
            policy.deferred_target_ids,
            ("macos-wps", "windows-powerpoint", "windows-wps"),
        )
        self.assertEqual(policy.compatibility_claim_scope, policy.required_target_ids)
        self.assertEqual(policy.as_payload(), CURRENT_RELEASE_TARGET_POLICY)

    def test_policy_rejects_invalid_partition_and_claim_scope(self) -> None:
        for update in (
            {"required_target_ids": []},
            {"required_target_ids": ["macos-powerpoint", "macos-powerpoint"]},
            {"deferred_target_ids": ["macos-wps", "windows-powerpoint"]},
            {"compatibility_claim_scope": ["macos-powerpoint", "macos-wps"]},
        ):
            with self.subTest(update=update), self.assertRaises(ValueError):
                ReleaseTargetPolicy.from_payload(
                    {**copy.deepcopy(CURRENT_RELEASE_TARGET_POLICY), **update}
                )

    def test_new_project_binds_current_policy_in_first_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime_root = root / "runtime"
            project = ProjectService(
                RuntimeConfig.create(
                    runtime_root,
                    root / "source",
                    root / "install",
                    root / "upstream",
                )
            ).create_project("策略项目", project_id="policy-project")
            state = project.load()
            self.assertEqual(state.revision, 1)
            policy_ref, policy = ReleaseTargetPolicyService(project).current()
            self.assertEqual(state.artifact_heads["release/target-policy"], policy_ref)
            self.assertEqual(policy.required_target_ids, ("macos-powerpoint",))

    def test_policy_command_is_semantic_and_change_reopens_downstream_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="policy-project")
            service = ReleaseTargetPolicyService(kernel)
            policy_ref, bound = service.bind_current_policy("bind-policy", 0)
            replay_ref, replayed = service.bind_current_policy("bind-policy", 0)
            self.assertEqual((replay_ref, replayed), (policy_ref, bound))
            with self.assertRaisesRegex(
                ContractValidationError, "Processed command has different semantics"
            ):
                service.bind_policy("bind-policy", 0, expanded_policy())
            self.assertEqual(kernel.load(), bound)

            evidence_ref = str(
                kernel.artifacts.put("test-evidence", {"identity": "gate-proof"})
            )
            late = kernel.commit(
                command_id="simulate-passed-gates",
                expected_revision=bound.revision,
                event_type="test.gates-passed",
                artifact_updates={},
                gate_mutation=issue_gate_mutation(
                    {"G1": "passed", "G2": "passed", "G3": "passed", "G4": "open"},
                    (evidence_ref,),
                ),
            )
            new_ref, changed = service.bind_policy(
                "expand-policy", late.revision, expanded_policy()
            )
            self.assertNotEqual(new_ref, policy_ref)
            self.assertEqual(
                {gate: changed.gate_status[gate] for gate in ("G1", "G2", "G3", "G4")},
                {"G1": "passed", "G2": "open", "G3": "locked", "G4": "locked"},
            )
            self.assertEqual(
                kernel.artifacts.resolve(ArtifactReference.parse(new_ref))["payload"],
                expanded_policy(),
            )


if __name__ == "__main__":
    unittest.main()
