"""Revision-safe schema 3.0 application service for content production."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import re

from ai_ppt_studio.domains.content.contracts import (
    CONTENT_STAGES,
    REQUIRED_CONTENT_REVIEW_ROLES,
    aggregate_content_reviews,
    validate_content_stage,
    validate_content_review,
)
from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_blueprint,
    validate_content_review_batch,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContentWorkflowError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.application.mission_readiness import (
    MissionReadiness,
    MissionReadinessPolicy,
)


@dataclass(frozen=True)
class ContentAcceptanceResult:
    acceptance_ref: str
    blueprint_ref: str
    state: KernelState


CONTENT_WORKFLOW_LINEAGE_FIELDS = (
    "framework_ref",
    "framework_confirmation_ref",
    "full_deck_expansion_authorization_ref",
)


def require_full_deck_expansion_authorization(
    kernel: ProjectKernel,
) -> dict[str, str]:
    """Return the exact trusted framework lineage or reject before any write."""

    from ai_ppt_studio.application.framework_discussion_service import (
        FULL_DECK_EXPANSION_SCOPE,
        FrameworkDiscussionService,
    )

    state = kernel.load()
    try:
        context = FrameworkDiscussionService(
            kernel
        ).expansion_authorization_context()
        framework_ref = str(context["source_version"])
        confirmation_ref = str(context["scope_id"])
        confirmation_reference = ArtifactReference.parse(confirmation_ref)
        if confirmation_reference.kind != "content-framework-confirmation":
            raise ValueError("confirmation kind is invalid")
        confirmation = dict(
            kernel.artifacts.resolve(confirmation_reference)["payload"]
        )
        confirmation_revision = confirmation.get("challenge_revision")
        if (
            isinstance(confirmation_revision, bool)
            or not isinstance(confirmation_revision, int)
        ):
            raise ValueError("confirmation revision is invalid")
        authorization_ref = state.artifact_heads.get(
            "content/full-deck-expansion-authorization", ""
        )
        if not authorization_ref:
            raise ValueError("authorization head is missing")
        reference = ArtifactReference.parse(authorization_ref)
        if reference.kind != "full-deck-expansion-authorization":
            raise ValueError("authorization kind is invalid")
        authorization = dict(kernel.artifacts.resolve(reference)["payload"])
        revision = authorization.get("challenge_revision")
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise ValueError("authorization revision is invalid")
        evidence_refs = list(context["evidence_refs"])
        challenge_body = {
            "project_id": state.project_id,
            "project_root": str(kernel.project_root),
            "scope_kind": FULL_DECK_EXPANSION_SCOPE,
            "scope_id": confirmation_ref,
            "source_version": framework_ref,
            "evidence_refs": evidence_refs,
            "challenge_revision": revision,
        }
        challenge_id = FrameworkDiscussionService(
            kernel
        ).confirmations.challenge_id(challenge_body)
        expected = {
            "project_id": state.project_id,
            "scope_kind": FULL_DECK_EXPANSION_SCOPE,
            "scope_id": confirmation_ref,
            "source_version": framework_ref,
            "evidence_refs": evidence_refs,
            "challenge_id": challenge_id,
            "framework_ref": framework_ref,
            "framework_confirmation_ref": confirmation_ref,
            "framework_revision": revision,
            "challenge_identity": challenge_id,
        }
        if any(
            authorization.get(key) != value
            for key, value in expected.items()
        ):
            raise ValueError("authorization binding is stale")
        action_ref = str(authorization.get("user_action_ref") or "")
        message_ref = str(authorization.get("user_message_ref") or "")
        identities = tuple(value for value in (action_ref, message_ref) if value)
        if (
            revision < 1
            or revision >= state.revision
            or len(identities) != 1
            or authorization.get("confirmation_identity_type")
            not in {"host-action", "verified-message"}
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(authorization.get("host_assertion_sha256") or ""),
            )
            or not str(authorization.get("confirmed_at") or "").strip()
            or kernel.confirmation_owner(identities[0])
            != f"{FULL_DECK_EXPANSION_SCOPE}:{confirmation_ref}"
            or kernel.confirmation_artifact_binding(identities[0])
            != authorization_ref
            or confirmation_revision < kernel.current_framework_reset_revision()
            or revision <= confirmation_revision
        ):
            raise ValueError("authorization trust binding is invalid")
    except (
        ArtifactReferenceError,
        ConfirmationTransactionError,
        ContentWorkflowError,
        KeyError,
        TypeError,
        ValueError,
    ):
        raise ContentWorkflowError(
            "FULL_DECK_EXPANSION_NOT_AUTHORIZED",
            "The exact current framework is not authorized for full-deck expansion",
            {
                "framework_ref": state.artifact_heads.get(
                    "content/framework-draft", ""
                ),
                "framework_confirmation_ref": state.artifact_heads.get(
                    "content/framework-confirmation", ""
                ),
                "full_deck_expansion_authorization_ref": state.artifact_heads.get(
                    "content/full-deck-expansion-authorization", ""
                ),
                "revision": state.revision,
            },
        ) from None
    return {
        "framework_ref": framework_ref,
        "framework_confirmation_ref": confirmation_ref,
        "full_deck_expansion_authorization_ref": authorization_ref,
    }
class ContentService:
    """Persist and validate the formal content artifact chain."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    @classmethod
    def initialize(cls, project_root: Path, *, project_id: str) -> "ContentService":
        return cls(ProjectKernel.initialize(project_root, project_id=project_id))

    def save_mission_draft(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.mission_material_service import (
            MissionMaterialService,
        )

        return MissionMaterialService(
            self.kernel, allow_legacy_modes=True
        ).save_mission_draft(command_id, expected_revision, payload)

    def register_mission(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        """Compatibility entry point with MissionDraft-only semantics."""

        from ai_ppt_studio.application.mission_material_service import (
            MissionMaterialService,
        )

        return MissionMaterialService(
            self.kernel, allow_legacy_modes=True
        ).register_mission(command_id, expected_revision, payload)

    def confirm_mission(
        self,
        command_id: str,
        expected_revision: int,
        *,
        mission_draft_ref: str,
        material_mode: str,
        material_inventory_ref: str,
        user_action_ref: str,
        user_message_ref: str,
    ) -> str:
        from ai_ppt_studio.application.mission_material_service import (
            MissionMaterialService,
        )

        return MissionMaterialService(
            self.kernel, allow_legacy_modes=True
        ).confirm_mission(
            command_id,
            expected_revision,
            mission_draft_ref=mission_draft_ref,
            material_mode=material_mode,
            material_inventory_ref=material_inventory_ref,
            user_action_ref=user_action_ref,
            user_message_ref=user_message_ref,
        )

    def register_materials(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.mission_material_service import (
            MissionMaterialService,
        )

        return MissionMaterialService(
            self.kernel, allow_legacy_modes=True
        ).register_materials(command_id, expected_revision, payload)

    def register_content_stage(
        self,
        command_id: str,
        expected_revision: int,
        stage: str,
        payload: dict[str, Any],
    ) -> str:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "Formal content stages require an exact governed Agent task",
            {"stage": stage},
        )

    def _prepare_content_stage_update(
        self, stage: str, payload: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any]]:
        """Validate one stage completely without exposing a new head."""

        readiness = MissionReadinessPolicy(self.kernel).require_ready()
        lineage = require_full_deck_expansion_authorization(self.kernel)
        if stage == "slide-draft-set" and self.kernel.load().artifact_heads.get(
            "content/blueprint"
        ):
            self._current_revision_plan_lineage(self.kernel.load())
        self._reject_supplied_stale_workflow_lineage(payload, lineage)
        governed_payload = self._govern_content_identity(
            {**payload, **lineage}, readiness
        )
        normalized = validate_content_stage(stage, governed_payload)
        self._validate_lineage(stage, normalized, readiness)
        slot, kind = CONTENT_STAGES[stage]
        return slot, kind, normalized

    def register_review(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "Formal content reviews require an exact governed Agent task",
            {},
        )

    def _prepare_review_update(
        self, payload: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any]]:
        """Validate one independent review completely without writing it."""

        MissionReadinessPolicy(self.kernel).require_ready()
        lineage = require_full_deck_expansion_authorization(self.kernel)
        self._reject_supplied_stale_workflow_lineage(payload, lineage)
        normalized = validate_content_review({**payload, **lineage})
        draft_ref = self._require_head("content/draft", "slide-draft-set")
        if (
            normalized["target_ref"] != draft_ref
            or normalized["input_version"] != draft_ref
        ):
            raise ArtifactReferenceError(
                "Content review must target the current slide draft"
            )
        self._require_exact_workflow_lineage(normalized, lineage)
        draft = self.kernel.artifacts.resolve(
            ArtifactReference.parse(draft_ref)
        )["payload"]
        self._require_exact_workflow_lineage(draft, lineage)
        for check in normalized["checks"]:
            for value in check.get("evidence_refs") or []:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        role = normalized["reviewer_role"]
        slot = f"content/review/{role}"
        return slot, "content-review-record", normalized

    def accept_content(
        self, command_id: str, expected_revision: int
    ) -> ContentAcceptanceResult:
        MissionReadinessPolicy(self.kernel).require_ready()
        lineage = require_full_deck_expansion_authorization(self.kernel)
        state = self.kernel.load()
        revision_lineage = self._current_revision_plan_lineage(
            state, allow_initial=True
        )
        refs, payloads = self._validated_current_content_chain(lineage)
        draft_ref = refs["draft_ref"]
        records: list[tuple[str, dict[str, Any]]] = []
        for role in REQUIRED_CONTENT_REVIEW_ROLES:
            value = state.artifact_heads.get(f"content/review/{role}")
            if not value:
                continue
            reference = ArtifactReference.parse(value)
            if reference.kind != "content-review-record":
                raise ArtifactReferenceError(
                    f"Unexpected artifact kind for content/review/{role}"
                )
            envelope = self.kernel.artifacts.resolve(reference)
            self._require_exact_workflow_lineage(envelope["payload"], lineage)
            records.append((value, envelope["payload"]))
        acceptance = aggregate_content_reviews(draft_ref, records)
        acceptance.update(lineage)
        acceptance.update(revision_lineage)
        acceptance["passed_at"] = datetime.now(timezone.utc).isoformat()
        acceptance_ref = str(
            self.kernel.artifacts.put("content-acceptance", acceptance)
        )
        blueprint = self._build_blueprint(
            acceptance_ref,
            lineage,
            revision_lineage,
            refs,
            payloads,
        )
        blueprint_ref = str(
            self.kernel.artifacts.put("content-blueprint", blueprint)
        )
        mutation = GateEvaluator(self.kernel).content_user_reviewable(
            acceptance_ref, blueprint_ref
        )
        downstream_prefixes = (
            "visual/",
            "delivery/",
            "chat-delivery/",
            "gate/",
            "review-marks/visual",
        )
        removals = tuple(
            sorted(
                slot
                for slot in state.artifact_heads
                if slot.startswith(downstream_prefixes)
            )
        )
        artifact_updates: dict[str, tuple[str, dict[str, Any]]] = {
            "content/acceptance": ("content-acceptance", acceptance),
            "content/blueprint": ("content-blueprint", blueprint),
        }
        if revision_lineage["supersedes_blueprint_ref"]:
            current_batch_ref = state.artifact_heads.get(
                "content/review-batch", ""
            )
            current_batch = self.kernel.artifacts.resolve(
                ArtifactReference.parse(current_batch_ref)
            )["payload"]
            applied_batch = copy.deepcopy(current_batch)
            applied_batch["status"] = "applied"
            applied_batch["supersedes_ref"] = current_batch_ref
            applied_batch["result_blueprint_ref"] = blueprint_ref
            applied_batch = validate_content_review_batch(
                applied_batch, prior_submitted=current_batch
            )
            artifact_updates["content/review-batch"] = (
                "content-review-batch",
                applied_batch,
            )
        removal_set = set(removals)
        active_ref = state.artifact_heads.get("agent/task/active", "")
        if active_ref:
            removal_set.add("agent/task/active")
            task = self.kernel.artifacts.resolve(
                ArtifactReference.parse(active_ref)
            )["payload"]
            if task.get("status") not in {"completed", "invalidated"}:
                invalidated = {
                    **task,
                    "status": "invalidated",
                    "progress": {
                        "stage": "invalidated",
                        "done": task.get("progress", {}).get("done", 0),
                        "total": task.get("progress", {}).get("total", 1),
                    },
                    "invalidated_by_gate": "G0",
                    "invalidation_reason": "content-blueprint-republished",
                }
                artifact_updates[f"agent/task/{task['task_id']}"] = (
                    "agent-task",
                    invalidated,
                )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.accepted-internally",
            artifact_updates=artifact_updates,
            artifact_removals=tuple(sorted(removal_set)),
            gate_mutation=mutation,
        )
        return ContentAcceptanceResult(
            acceptance_ref=committed.artifact_heads["content/acceptance"],
            blueprint_ref=committed.artifact_heads["content/blueprint"],
            state=committed,
        )

    def confirm_g0(
        self,
        command_id: str,
        expected_revision: int,
        *,
        user_action_ref: str = "",
        user_message_ref: str = "",
        host_confirmation_assertion: str = "",
        source_version: str = "",
        challenge_id: str = "",
        challenge_revision: int = -1,
    ) -> KernelState:
        policy = GateConfirmationPolicy(self.kernel)
        confirmation, consumptions = policy.confirmation_payload(
            gate="G0",
            source_version=source_version,
            challenge_id=challenge_id,
            challenge_revision=challenge_revision,
            host_confirmation_assertion=host_confirmation_assertion,
            user_action_ref=user_action_ref,
            user_message_ref=user_message_ref,
        )
        confirmation["content_acceptance_ref"] = confirmation["evidence_refs"][0]
        confirmation["content_blueprint_ref"] = confirmation["source_version"]
        confirmation_ref = str(
            self.kernel.artifacts.put("g0-confirmation", confirmation)
        )
        evaluator = GateEvaluator(self.kernel)
        mutation = (
            evaluator.upgrade_legacy_g0_confirmation(
                confirmation_ref=confirmation_ref
            )
            if confirmation.get("confirmation_mode")
            == "legacy-credential-upgrade"
            else evaluator.confirm_g0(confirmation_ref=confirmation_ref)
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=(
                "gate.G0.confirmation-credential-upgraded"
                if confirmation.get("confirmation_mode")
                == "legacy-credential-upgrade"
                else "gate.G0.confirmed"
            ),
            artifact_updates={
                "gate/G0/confirmation": ("g0-confirmation", confirmation)
            },
            confirmation_consumptions=consumptions,
            gate_mutation=mutation,
        )

    def gate_confirmation_context(self, gate: str = "G0") -> dict[str, Any]:
        return GateConfirmationPolicy(self.kernel).context(gate)

    def reopen_g0(
        self,
        command_id: str,
        expected_revision: int,
        *,
        reason: str,
    ) -> KernelState:
        explanation = reason.strip()
        if not explanation:
            raise ContractValidationError("Reopening G0 requires a reason")
        state = self.kernel.load()
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        mutation = GateEvaluator(self.kernel).reopen_g0(
            acceptance_ref=acceptance_ref,
            blueprint_ref=blueprint_ref,
        )
        downstream_prefixes = (
            "visual/",
            "delivery/",
            "chat-delivery/",
            "gate/",
            "review-marks/visual",
        )
        removals = {
            slot
            for slot in state.artifact_heads
            if slot.startswith(downstream_prefixes)
        }
        removals.discard("gate/G0/reopen")
        artifact_updates: dict[str, tuple[str, dict[str, Any]]] = {
            "gate/G0/reopen": (
                "scope-reopen",
                {
                    "gate": "G0",
                    "reason": explanation,
                    "prior_status": state.gate_status.get("G0", "locked"),
                    "content_acceptance_ref": acceptance_ref,
                    "content_blueprint_ref": blueprint_ref,
                },
            )
        }
        active_ref = state.artifact_heads.get("agent/task/active", "")
        if active_ref:
            removals.add("agent/task/active")
            task = self.kernel.artifacts.resolve(
                ArtifactReference.parse(active_ref)
            )["payload"]
            if task.get("status") not in {"completed", "invalidated"}:
                invalidated = {
                    **task,
                    "status": "invalidated",
                    "progress": {
                        "stage": "invalidated",
                        "done": task.get("progress", {}).get("done", 0),
                        "total": task.get("progress", {}).get("total", 1),
                    },
                    "invalidated_by_gate": "G0",
                    "invalidation_reason": explanation,
                }
                artifact_updates[f"agent/task/{task['task_id']}"] = (
                    "agent-task",
                    invalidated,
                )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.reopened",
            artifact_updates=artifact_updates,
            artifact_removals=tuple(sorted(removals)),
            gate_mutation=mutation,
        )

    def capture_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.feedback_service import FeedbackService

        return FeedbackService(self.kernel).capture_feedback(
            command_id, expected_revision, payload
        )

    def govern_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.feedback_service import FeedbackService

        return FeedbackService(self.kernel).govern_feedback(
            command_id, expected_revision, payload
        )

    def decide_feedback(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        choice: str,
    ) -> str:
        from ai_ppt_studio.application.feedback_service import FeedbackService

        return FeedbackService(self.kernel).decide_feedback(
            command_id, expected_revision, governance_ref, choice
        )

    def create_content_change_set(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        plan_confirmation_ref: str = "",
    ) -> str:
        from ai_ppt_studio.application.feedback_service import FeedbackService

        return FeedbackService(self.kernel).create_content_change_set(
            command_id,
            expected_revision,
            governance_ref,
            plan_confirmation_ref,
        )

    def commit_public_artifact(
        self,
        command_id: str,
        expected_revision: int,
        *,
        kind: str,
        payload: dict[str, Any],
    ) -> str:
        """Route the public MCP content vocabulary into formal services."""

        artifact_type = str(payload.get("artifact_type") or "")
        stages = {
            "presales-content-strategy": "strategy",
            "claim-evidence-map": "claim-map",
            "deck-argument-map": "argument-map",
            "slide-draft-set": "slide-draft-set",
        }
        stage = stages.get(artifact_type)
        if stage is not None:
            return self.register_content_stage(
                command_id, expected_revision, stage, payload
            )
        if artifact_type == "content-review-record":
            return self.register_review(command_id, expected_revision, payload)
        if artifact_type == "content-acceptance-request":
            return self.accept_content(
                command_id, expected_revision
            ).acceptance_ref
        if artifact_type == "raw-feedback":
            return self.capture_feedback(command_id, expected_revision, payload)
        if artifact_type == "feedback-governance-record":
            return self.govern_feedback(command_id, expected_revision, payload)
        if artifact_type == "content-change-set-request":
            return self.create_content_change_set(
                command_id,
                expected_revision,
                str(payload.get("governance_ref") or ""),
                str(payload.get("plan_confirmation_ref") or ""),
            )
        if kind == "material-findings" and (
            artifact_type == "material-inventory" or "sources" in payload
        ):
            return self.register_materials(
                command_id, expected_revision, payload
            )
        raise ContractValidationError(
            "content payload needs a recognized schema 3 artifact_type"
        )

    def _build_blueprint(
        self,
        acceptance_ref: str,
        lineage: dict[str, str],
        revision_lineage: dict[str, str],
        refs: dict[str, str],
        payloads: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return validate_content_blueprint({
            **refs,
            **lineage,
            **revision_lineage,
            "acceptance_ref": acceptance_ref,
            "strategy": payloads["strategy"],
            "claim_evidence_map": payloads["claim_evidence_map"],
            "argument_map": payloads["argument_map"],
            "slides": payloads["draft"]["slides"],
            "status": "user-reviewable",
        })

    def _current_revision_plan_lineage(
        self,
        state: KernelState,
        *,
        allow_initial: bool = False,
    ) -> dict[str, str]:
        prior_blueprint_ref = state.artifact_heads.get(
            "content/blueprint", ""
        )
        if not prior_blueprint_ref:
            if not allow_initial:
                raise ContentWorkflowError(
                    "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                    "A revised draft requires an existing source blueprint",
                    {},
                )
            return {
                "supersedes_blueprint_ref": "",
                "review_batch_ref": "",
                "batch_revision_plan_ref": "",
                "batch_plan_confirmation_ref": "",
            }
        from ai_ppt_studio.application.content_batch_planning_service import (
            ContentBatchPlanningService,
        )

        plan_ref = state.artifact_heads.get(
            "content/batch-revision-plan", ""
        )
        confirmation_ref = state.artifact_heads.get(
            "content/batch-plan-confirmation", ""
        )
        change_set_ref = state.artifact_heads.get("content/change-set", "")
        try:
            confirmation = ContentBatchPlanningService(
                self.kernel
            ).require_current_plan_confirmation(confirmation_ref)
            plan = self.kernel.artifacts.resolve(
                ArtifactReference.parse(plan_ref)
            )["payload"]
            change_set = self.kernel.artifacts.resolve(
                ArtifactReference.parse(change_set_ref)
            )["payload"]
        except (
            ArtifactReferenceError,
            ContentWorkflowError,
            KeyError,
            TypeError,
        ) as error:
            raise ContentWorkflowError(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "Revised content requires the current confirmed batch plan",
                {},
            ) from error
        review_batch_ref = str(plan.get("review_batch_ref") or "")
        if (
            not plan.get("requires_blueprint_revision")
            or plan.get("source_version") != prior_blueprint_ref
            or confirmation.get("revision_plan_ref") != plan_ref
            or change_set.get("review_batch_ref") != review_batch_ref
            or change_set.get("revision_plan_ref") != plan_ref
            or change_set.get("plan_confirmation_ref") != confirmation_ref
            or change_set.get("source_blueprint_ref") != prior_blueprint_ref
        ):
            raise ContentWorkflowError(
                "CONTENT_BATCH_PLAN_NOT_CONFIRMED",
                "Revised content lineage does not match the current source",
                {},
            )
        return {
            "supersedes_blueprint_ref": prior_blueprint_ref,
            "review_batch_ref": review_batch_ref,
            "batch_revision_plan_ref": plan_ref,
            "batch_plan_confirmation_ref": confirmation_ref,
        }

    def _validated_current_content_chain(
        self, lineage: dict[str, str]
    ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        readiness = MissionReadinessPolicy(self.kernel).require_ready()
        required = {
            "strategy": (
                "content/strategy", "presales-content-strategy", "strategy"
            ),
            "claim_evidence_map": (
                "content/claim-map", "claim-evidence-map", "claim-map"
            ),
            "argument_map": (
                "content/argument-map", "deck-argument-map", "argument-map"
            ),
            "draft": (
                "content/draft", "slide-draft-set", "slide-draft-set"
            ),
        }
        refs: dict[str, str] = {}
        payloads: dict[str, dict[str, Any]] = {}
        for label, (slot, kind, stage) in required.items():
            value = self._require_head(slot, kind)
            payload = dict(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(value)
                )["payload"]
            )
            self._require_exact_workflow_lineage(payload, lineage)
            self._validate_lineage(stage, payload, readiness)
            refs[f"{label}_ref"] = value
            payloads[label] = payload
        return refs, payloads

    def _validate_lineage(
        self,
        stage: str,
        payload: dict[str, Any],
        readiness: MissionReadiness,
    ) -> None:
        current_lineage = require_full_deck_expansion_authorization(self.kernel)
        self._require_exact_workflow_lineage(payload, current_lineage)
        if stage == "strategy":
            self._require_exact_ref(
                payload["mission_ref"], "mission/draft", "mission-draft"
            )
            if readiness.content_identity_mode == "material-backed":
                self._require_exact_ref(
                    payload["material_inventory_ref"],
                    "materials",
                    "material-inventory",
                )
            elif (
                payload.get("empty_material_identity")
                != readiness.empty_material_identity
            ):
                from ai_ppt_studio.errors import (
                    ProposalOnlyIdentityViolationError,
                )

                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: empty material identity is missing"
                )
        elif stage == "claim-map":
            self._require_exact_ref(
                payload["strategy_ref"],
                "content/strategy",
                "presales-content-strategy",
            )
            if readiness.content_identity_mode == "material-backed":
                for claim in payload["claims"]:
                    for ref in claim["evidence_refs"]:
                        self._require_exact_ref(
                            ref, "materials", "material-inventory"
                        )
        elif stage == "argument-map":
            self._require_exact_ref(
                payload["strategy_ref"],
                "content/strategy",
                "presales-content-strategy",
            )
            self._require_exact_ref(
                payload["claim_evidence_map_ref"],
                "content/claim-map",
                "claim-evidence-map",
            )
        else:
            self._require_exact_ref(
                payload["argument_map_ref"],
                "content/argument-map",
                "deck-argument-map",
            )
            if readiness.content_identity_mode == "material-backed":
                for slide in payload["slides"]:
                    for ref in slide["source_refs"]:
                        self._require_exact_ref(
                            ref, "materials", "material-inventory"
                        )

    @staticmethod
    def _require_exact_workflow_lineage(
        payload: dict[str, Any], lineage: dict[str, str]
    ) -> None:
        if any(
            payload.get(field) != lineage[field]
            for field in CONTENT_WORKFLOW_LINEAGE_FIELDS
        ):
            raise ContentWorkflowError(
                "FULL_DECK_EXPANSION_NOT_AUTHORIZED",
                "Formal content is not bound to the exact current framework authorization",
                {
                    "expected": dict(lineage),
                    "actual": {
                        field: str(payload.get(field) or "")
                        for field in CONTENT_WORKFLOW_LINEAGE_FIELDS
                    },
                },
            )

    @staticmethod
    def _reject_supplied_stale_workflow_lineage(
        payload: dict[str, Any], lineage: dict[str, str]
    ) -> None:
        mismatches = {
            field: {
                "expected": lineage[field],
                "actual": str(payload.get(field) or ""),
            }
            for field in CONTENT_WORKFLOW_LINEAGE_FIELDS
            if field in payload and payload.get(field) != lineage[field]
        }
        if mismatches:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Caller-supplied content lineage is stale or inconsistent",
                {"mismatches": mismatches},
            )

    @staticmethod
    def _govern_content_identity(
        payload: dict[str, Any], readiness: MissionReadiness
    ) -> dict[str, Any]:
        from ai_ppt_studio.errors import ProposalOnlyIdentityViolationError

        supplied = str(payload.get("content_identity_mode") or "").strip()
        if supplied and supplied != readiness.content_identity_mode:
            raise ProposalOnlyIdentityViolationError(
                "PROPOSAL_ONLY_IDENTITY_VIOLATION: content identity mode does not match MissionConfirmation"
            )
        governed = {
            **payload,
            "content_identity_mode": readiness.content_identity_mode,
            "mission_confirmation_ref": readiness.mission_confirmation_ref,
        }
        if readiness.content_identity_mode == "proposal-only":
            required = {
                "diagnostic-hypothesis",
                "solution-recommendation",
                "joint-validation-required",
            }
            labels = payload.get("identity_labels")
            if not isinstance(labels, list) or not required.issubset(
                {str(value) for value in labels}
            ):
                raise ProposalOnlyIdentityViolationError(
                    "PROPOSAL_ONLY_IDENTITY_VIOLATION: proposal-only content must preserve all three identity labels"
                )
            governed["empty_material_identity"] = (
                readiness.empty_material_identity
            )
        return governed

    def _require_head(self, slot: str, kind: str) -> str:
        current = self.kernel.load().artifact_heads.get(slot)
        if not current:
            raise ArtifactReferenceError(f"Required artifact head is missing: {slot}")
        return self._require_exact_ref(current, slot, kind)

    def _require_exact_ref(self, value: str, slot: str, kind: str) -> str:
        reference = ArtifactReference.parse(value)
        state = self.kernel.load()
        if state.artifact_heads.get(slot) != value or reference.kind != kind:
            raise ArtifactReferenceError(
                f"Artifact reference is not the current {slot} head: {value}"
            )
        self.kernel.artifacts.resolve(reference)
        return value
