"""Project-bound release-target policy resolution and migration."""

from __future__ import annotations

from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.gates import issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ReleaseTargetPolicyService:
    """Bind one validated product-version policy to a schema 3 project."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def current(self) -> tuple[str, ReleaseTargetPolicy]:
        state = self.kernel.load()
        value = state.artifact_heads.get("release/target-policy", "")
        if not value:
            raise ContractValidationError(
                "RELEASE_TARGET_POLICY_MISSING: project has no release policy"
            )
        try:
            reference = ArtifactReference.parse(value)
            if reference.kind != "release-target-policy":
                raise ArtifactReferenceError(
                    "Release policy head has the wrong artifact kind"
                )
            record = self.kernel.artifacts.resolve(reference)
            policy = ReleaseTargetPolicy.from_payload(record["payload"])
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ContractValidationError(
                f"RELEASE_TARGET_POLICY_INVALID: {error}"
            ) from error
        return value, policy

    def bind_current_policy(
        self, command_id: str, expected_revision: int
    ) -> tuple[str, KernelState]:
        return self.bind_policy(
            command_id,
            expected_revision,
            CURRENT_RELEASE_TARGET_POLICY,
        )

    def bind_policy(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict,
    ) -> tuple[str, KernelState]:
        try:
            policy = ReleaseTargetPolicy.from_payload(payload)
        except (TypeError, ValueError) as error:
            raise ContractValidationError(
                f"RELEASE_TARGET_POLICY_INVALID: {error}"
            ) from error
        normalized = policy.as_payload()
        new_ref = str(
            self.kernel.artifacts.reference_for(
                "release-target-policy", normalized
            )
        )
        state = self.kernel.load()
        if command_id in state.processed_commands:
            return state.artifact_heads.get("release/target-policy", new_ref), state
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        old_ref = state.artifact_heads.get("release/target-policy", "")
        if old_ref == new_ref:
            return old_ref, state

        mutation = None
        if state.gate_status.get("G2") == "passed":
            mutation = issue_gate_mutation(
                {"G2": "open", "G3": "locked", "G4": "locked"},
                (new_ref,),
            )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="release.target-policy-bound",
            artifact_updates={
                "release/target-policy": ("release-target-policy", normalized)
            },
            gate_mutation=mutation,
        )
        return committed.artifact_heads["release/target-policy"], committed
