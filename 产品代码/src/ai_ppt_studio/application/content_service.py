"""Revision-safe schema 3.0 application service for content production."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_ppt_studio.domains.content.contracts import (
    CONTENT_STAGES,
    REQUIRED_CONTENT_REVIEW_ROLES,
    aggregate_content_reviews,
    validate_content_stage,
    validate_content_review,
)
from ai_ppt_studio.domains.materials.contracts import (
    validate_material_inventory,
)
from ai_ppt_studio.domains.mission.contracts import (
    validate_mission_confirmation,
    validate_mission_draft,
)
from ai_ppt_studio.domains.feedback.contracts import (
    decide_feedback as apply_feedback_decision,
    validate_feedback_governance,
    validate_raw_feedback,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    FeedbackGovernanceError,
    GateBlockedError,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
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
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.draft-saved",
            artifact_updates={
                "mission/draft": (
                    "mission-draft",
                    validate_mission_draft(payload),
                )
            },
        )
        return state.artifact_heads["mission/draft"]

    def register_mission(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        """Compatibility entry point with MissionDraft-only semantics."""

        return self.save_mission_draft(command_id, expected_revision, payload)

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
        draft_ref = self._require_exact_ref(
            mission_draft_ref, "mission/draft", "mission-draft"
        )
        draft = self.kernel.artifacts.resolve(
            ArtifactReference.parse(draft_ref)
        )["payload"]
        from ai_ppt_studio.errors import (
            MaterialModeUnconfirmedError,
            MissionNotConfirmedError,
        )

        if draft.get("status") != "confirmable":
            raise MissionNotConfirmedError(
                "MISSION_NOT_CONFIRMED: MissionDraft is not confirmable"
            )
        mode = material_mode.strip()
        policy = MissionReadinessPolicy(self.kernel)
        payload: dict[str, Any] = {
            "mission_draft_ref": draft_ref,
            "material_mode": mode,
            "user_action_ref": user_action_ref.strip(),
            "user_message_ref": user_message_ref.strip(),
            "revision": expected_revision,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        if mode == "materials-provided":
            current = self.kernel.load().artifact_heads.get("materials", "")
            if not current or material_inventory_ref != current:
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: current material inventory is required"
                )
            self._require_exact_ref(
                current, "materials", "material-inventory"
            )
            payload["material_inventory_ref"] = current
        elif mode == "no-materials-confirmed":
            if self.kernel.load().artifact_heads.get("materials"):
                raise MaterialModeUnconfirmedError(
                    "MATERIAL_MODE_UNCONFIRMED: materials already exist"
                )
            payload["empty_material_identity"] = policy.empty_material_identity(
                draft_ref
            )
        else:
            raise MaterialModeUnconfirmedError(
                "MATERIAL_MODE_UNCONFIRMED: choose materials-provided or no-materials-confirmed"
            )
        normalized = validate_mission_confirmation(payload)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="mission.confirmed",
            artifact_updates={
                "mission/confirmation": (
                    "mission-confirmation",
                    normalized,
                )
            },
        )
        return state.artifact_heads["mission/confirmation"]

    def register_materials(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="materials.registered",
            artifact_updates={
                "materials": (
                    "material-inventory",
                    validate_material_inventory(payload),
                )
            },
        )
        return state.artifact_heads["materials"]

    def register_content_stage(
        self,
        command_id: str,
        expected_revision: int,
        stage: str,
        payload: dict[str, Any],
    ) -> str:
        readiness = MissionReadinessPolicy(self.kernel).require_ready()
        governed_payload = self._govern_content_identity(payload, readiness)
        normalized = validate_content_stage(stage, governed_payload)
        self._validate_lineage(stage, normalized, readiness)
        slot, kind = CONTENT_STAGES[stage]
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=f"content.{stage}.registered",
            artifact_updates={slot: (kind, normalized)},
        )
        return state.artifact_heads[slot]

    def register_review(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        MissionReadinessPolicy(self.kernel).require_ready()
        normalized = validate_content_review(payload)
        draft_ref = self._require_head("content/draft", "slide-draft-set")
        if (
            normalized["target_ref"] != draft_ref
            or normalized["input_version"] != draft_ref
        ):
            raise ArtifactReferenceError(
                "Content review must target the current slide draft"
            )
        for check in normalized["checks"]:
            for value in check.get("evidence_refs") or []:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        role = normalized["reviewer_role"]
        slot = f"content/review/{role}"
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.review.registered",
            artifact_updates={slot: ("content-review-record", normalized)},
        )
        return state.artifact_heads[slot]

    def accept_content(
        self, command_id: str, expected_revision: int
    ) -> ContentAcceptanceResult:
        MissionReadinessPolicy(self.kernel).require_ready()
        state = self.kernel.load()
        draft_ref = self._require_head("content/draft", "slide-draft-set")
        records: list[tuple[str, dict[str, Any]]] = []
        for role in REQUIRED_CONTENT_REVIEW_ROLES:
            value = state.artifact_heads.get(f"content/review/{role}")
            if not value:
                continue
            envelope = self.kernel.artifacts.resolve(ArtifactReference.parse(value))
            records.append((value, envelope["payload"]))
        acceptance = aggregate_content_reviews(draft_ref, records)
        acceptance["passed_at"] = datetime.now(timezone.utc).isoformat()
        acceptance_ref = str(
            self.kernel.artifacts.put("content-acceptance", acceptance)
        )
        blueprint = self._build_blueprint(acceptance_ref)
        blueprint_ref = str(
            self.kernel.artifacts.put("content-blueprint", blueprint)
        )
        mutation = GateEvaluator(self.kernel).content_user_reviewable(
            acceptance_ref, blueprint_ref
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.accepted-internally",
            artifact_updates={
                "content/acceptance": ("content-acceptance", acceptance),
                "content/blueprint": ("content-blueprint", blueprint),
            },
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
        user_message_ref: str,
    ) -> KernelState:
        state = self.kernel.load()
        if state.gate_status.get("G0") != "user-reviewable" or not user_message_ref.startswith(
            "chat://message/"
        ):
            raise GateBlockedError(
                "G0", ("explicit-chat-confirmation-and-accepted-content-required",)
            )
        confirmation = {
            "gate": "G0",
            "user_message_ref": user_message_ref,
            "content_acceptance_ref": state.artifact_heads["content/acceptance"],
            "content_blueprint_ref": state.artifact_heads["content/blueprint"],
        }
        confirmation_ref = str(
            self.kernel.artifacts.put("g0-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g0(
            confirmation_ref=confirmation_ref,
            user_message_ref=user_message_ref,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.confirmed",
            artifact_updates={
                "gate/G0/confirmation": ("g0-confirmation", confirmation)
            },
            gate_mutation=mutation,
        )

    def capture_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_raw_feedback(payload)
        for value in normalized["target_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.captured",
            artifact_updates={"feedback/raw": ("raw-feedback", normalized)},
        )
        return state.artifact_heads["feedback/raw"]

    def govern_feedback(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_feedback_governance(payload)
        raw_ref = normalized["raw_feedback_ref"]
        self._require_exact_ref(raw_ref, "feedback/raw", "raw-feedback")
        for value in normalized["preserve_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.governed",
            artifact_updates={
                "feedback/governance": (
                    "feedback-governance-record",
                    normalized,
                )
            },
        )
        return state.artifact_heads["feedback/governance"]

    def decide_feedback(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
        choice: str,
    ) -> str:
        self._require_exact_ref(
            governance_ref,
            "feedback/governance",
            "feedback-governance-record",
        )
        current = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        decided = apply_feedback_decision(current, choice)
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="feedback.decision-recorded",
            artifact_updates={
                "feedback/governance": (
                    "feedback-governance-record",
                    decided,
                )
            },
        )
        return state.artifact_heads["feedback/governance"]

    def create_content_change_set(
        self,
        command_id: str,
        expected_revision: int,
        governance_ref: str,
    ) -> str:
        try:
            self._require_exact_ref(
                governance_ref,
                "feedback/governance",
                "feedback-governance-record",
            )
        except ArtifactReferenceError as exc:
            raise FeedbackGovernanceError(
                "ContentChangeSet requires the current governed feedback record"
            ) from exc
        governance = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance_ref)
        )["payload"]
        if governance.get("status") != "executable":
            raise FeedbackGovernanceError(
                "Feedback requires governance and any mandatory user decision"
            )
        raw = self.kernel.artifacts.resolve(
            ArtifactReference.parse(governance["raw_feedback_ref"])
        )["payload"]
        choice = governance.get("user_decision")
        governed_intent = (
            raw["raw_feedback"]
            if choice == "follow-user-instruction"
            else governance["ai_recommendation"]
        )
        change = {
            "feedback_governance_record_ref": governance_ref,
            "governed_intent": governed_intent,
            "target_refs": raw["target_refs"],
            "preserve_refs": governance["preserve_refs"],
            "scope": governance["scope"],
            "required_role_runs": ["content-repair-specialist"],
            "review_route": (
                list(REQUIRED_CONTENT_REVIEW_ROLES)
                if governance["feedback_level"] in {"F2", "F3"}
                else ["editorial-reviewer"]
            ),
            "status": "ready",
        }
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.change-set-created",
            artifact_updates={
                "content/change-set": ("content-change-set", change)
            },
        )
        return state.artifact_heads["content/change-set"]

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

    def _build_blueprint(self, acceptance_ref: str) -> dict[str, Any]:
        state = self.kernel.load()
        required = {
            "strategy": "content/strategy",
            "claim_evidence_map": "content/claim-map",
            "argument_map": "content/argument-map",
            "draft": "content/draft",
        }
        payloads: dict[str, Any] = {}
        refs: dict[str, str] = {}
        for label, slot in required.items():
            value = state.artifact_heads.get(slot)
            if not value:
                raise GateBlockedError("G0", (f"missing:{slot}",))
            refs[f"{label}_ref"] = value
            payloads[label] = self.kernel.artifacts.resolve(
                ArtifactReference.parse(value)
            )["payload"]
        return {
            **refs,
            "acceptance_ref": acceptance_ref,
            "strategy": payloads["strategy"],
            "claim_evidence_map": payloads["claim_evidence_map"],
            "argument_map": payloads["argument_map"],
            "slides": payloads["draft"]["slides"],
            "status": "user-reviewable",
        }

    def _validate_lineage(
        self,
        stage: str,
        payload: dict[str, Any],
        readiness: MissionReadiness,
    ) -> None:
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
