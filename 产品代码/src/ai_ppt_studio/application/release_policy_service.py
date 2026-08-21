"""Project-bound release-target policy resolution and migration."""

from __future__ import annotations

from ai_ppt_studio.application.review_commands import fingerprint, replay_ref
from ai_ppt_studio.domains.presentation.release_policy import (
    CURRENT_RELEASE_TARGET_POLICY,
    ReleaseTargetPolicy,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
)
from ai_ppt_studio.kernel.gates import issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ReleaseTargetPolicyService:
    """Bind one validated product-version policy to a schema 3 project."""

    SLOT = "release/target-policy"

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def current(self) -> tuple[str, ReleaseTargetPolicy]:
        value = self.kernel.load().artifact_heads.get(self.SLOT, "")
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
            policy = ReleaseTargetPolicy.from_payload(
                self.kernel.artifacts.resolve(reference)["payload"]
            )
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ContractValidationError(
                f"RELEASE_TARGET_POLICY_INVALID: {error}"
            ) from error
        return value, policy

    def bind_current_policy(self, command_id: str, expected_revision: int):
        return self.bind_policy(
            command_id, expected_revision, CURRENT_RELEASE_TARGET_POLICY
        )

    def bind_policy(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict,
    ):
        try:
            normalized = ReleaseTargetPolicy.from_payload(payload).as_payload()
        except (TypeError, ValueError) as error:
            raise ContractValidationError(
                f"RELEASE_TARGET_POLICY_INVALID: {error}"
            ) from error
        command_fingerprint = fingerprint(
            "bind-release-target-policy", {"payload": normalized}
        )
        with self.kernel.semantic_command(command_fingerprint):
            replay = replay_ref(
                self.kernel, command_id, command_fingerprint, self.SLOT
            )
            if replay:
                return replay
            state = self.kernel.load()
            new_ref = str(
                self.kernel.artifacts.reference_for(
                    "release-target-policy", normalized
                )
            )
            if state.artifact_heads.get(self.SLOT) == new_ref:
                return new_ref, state
            mutation = (
                issue_gate_mutation(
                    {"G2": "open", "G3": "locked", "G4": "locked"},
                    (new_ref,),
                )
                if state.gate_status.get("G2") == "passed"
                else None
            )
            committed = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="release.target-policy-bound",
                artifact_updates={
                    self.SLOT: ("release-target-policy", normalized)
                },
                gate_mutation=mutation,
            )
            return committed.artifact_heads[self.SLOT], committed


__all__ = ["ReleaseTargetPolicyService"]
