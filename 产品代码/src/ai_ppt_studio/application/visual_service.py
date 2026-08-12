"""Revision-safe strict-route-B visual application service."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.visual.contracts import (
    validate_anchor_slide_set,
    validate_deck_design_system,
    validate_image_asset_pack,
    validate_visual_brief,
    validate_visual_contract_set,
    validate_visual_convergence,
    validate_visual_review,
)
from ai_ppt_studio.domains.presentation.targets import (
    REQUIRED_TARGET_IDS,
    TargetRenderEvidence,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.kernel.state import KernelState


class VisualService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def register_visual_brief(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if state.gate_status.get("G0") != "passed":
            raise GateBlockedError("visual-brief", ("G0-not-passed",))
        normalized = validate_visual_brief(payload)
        self._require_exact_ref(
            normalized["content_blueprint_ref"],
            "content/blueprint",
            "content-blueprint",
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.brief-registered",
            artifact_updates={
                "visual/brief": ("visual-brief", normalized)
            },
        )
        return committed.artifact_heads["visual/brief"]

    def register_design_system(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_deck_design_system(payload)
        self._require_exact_ref(
            normalized["visual_brief_ref"], "visual/brief", "visual-brief"
        )
        self._require_exact_ref(
            normalized["content_blueprint_ref"],
            "content/blueprint",
            "content-blueprint",
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.design-system-registered",
            artifact_updates={
                "visual/design-system": ("deck-design-system", normalized)
            },
        )
        return committed.artifact_heads["visual/design-system"]

    def register_visual_contract_set(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        self._require_exact_ref(
            str(payload.get("deck_design_system_ref") or ""),
            "visual/design-system",
            "deck-design-system",
        )
        content = self._require_exact_ref(
            str(payload.get("content_blueprint_ref") or ""),
            "content/blueprint",
            "content-blueprint",
        )["payload"]
        normalized = validate_visual_contract_set(payload, content)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.contract-set-registered",
            artifact_updates={
                "visual/contracts": ("visual-contract-set", normalized)
            },
        )
        return committed.artifact_heads["visual/contracts"]

    def register_convergence(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_visual_convergence(payload)
        self._require_exact_ref(
            normalized["visual_contract_set_ref"],
            "visual/contracts",
            "visual-contract-set",
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.convergence-registered",
            artifact_updates={
                "visual/convergence": ("visual-convergence", normalized)
            },
        )
        return committed.artifact_heads["visual/convergence"]

    def register_visual_review(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_visual_review(payload)
        if normalized["stage"] == "G1":
            if normalized["reviewer_kind"] != "aesthetic":
                raise ContractValidationError("G1 requires an aesthetic reviewer")
            self._require_exact_ref(
                normalized["target_ref"],
                "visual/contracts",
                "visual-contract-set",
            )
        elif normalized["stage"] == "G2":
            state = self.kernel.load()
            if (
                state.gate_status.get("G1") != "passed"
                or state.gate_status.get("G2") != "open"
            ):
                raise GateBlockedError("visual-review-G2", ("G2-not-open",))
            self._require_exact_ref(
                normalized["target_ref"],
                "visual/anchors",
                "anchor-slide-set",
            )
        else:
            raise ContractValidationError(
                "G4 visual reviews are introduced by the delivery slice"
            )
        for check in normalized["checks"]:
            for value in check.get("evidence_refs") or []:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        slot = f"visual/review/{normalized['stage']}/{normalized['reviewer_kind']}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.review-registered",
            artifact_updates={slot: ("visual-review-record", normalized)},
        )
        return committed.artifact_heads[slot]

    def record_g1(
        self, command_id: str, expected_revision: int
    ) -> KernelState:
        mutation = GateEvaluator(self.kernel).pass_g1()
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G1.passed",
            artifact_updates={},
            gate_mutation=mutation,
        )

    def register_anchor_set(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if state.gate_status.get("G1") != "passed":
            raise GateBlockedError("anchor-slide-set", ("G1-not-passed",))
        contract_record = self._require_exact_ref(
            str(payload.get("visual_contract_set_ref") or ""),
            "visual/contracts",
            "visual-contract-set",
        )
        normalized = validate_anchor_slide_set(payload, contract_record["payload"])
        pptx = self._resolve_kind(
            normalized["native_first_pptx_ref"], "native-pptx"
        )["payload"]
        if (
            pptx.get("production_route") != "strict-B"
            or pptx.get("pptx_sha256") != normalized["pptx_sha256"]
        ):
            raise ContractValidationError(
                "Native-first PPTX must be strict-B and match the declared SHA-256"
            )
        for value in normalized["editability_evidence_refs"]:
            evidence = self._resolve_kind(value, "editability-evidence")["payload"]
            if evidence.get("semantic_objects_editable") is not True:
                raise ContractValidationError(
                    "Anchor editability evidence must prove semantic objects editable"
                )
        for value in normalized["preflight_render_refs"]:
            evidence = self._resolve_kind(value, "preflight-render")["payload"]
            if evidence.get("identity") != "preflight-only":
                raise ContractValidationError(
                    "Anchor preflight renders must be identified as preflight-only"
                )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.anchor-slide-set-registered",
            artifact_updates={
                "visual/anchors": ("anchor-slide-set", normalized)
            },
        )
        return committed.artifact_heads["visual/anchors"]

    def register_image_asset_pack(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_image_asset_pack(payload)
        anchor = self._require_exact_ref(
            normalized["anchor_slide_set_ref"],
            "visual/anchors",
            "anchor-slide-set",
        )["payload"]
        if anchor.get("native_first_frozen") is not True:
            raise ContractValidationError(
                "Image 2 assets require the current native-first anchor set to be frozen"
            )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.image-asset-pack-registered",
            artifact_updates={
                "visual/image-assets": ("image-asset-pack", normalized)
            },
        )
        return committed.artifact_heads["visual/image-assets"]

    def register_target_render_evidence(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if (
            state.gate_status.get("G1") != "passed"
            or state.gate_status.get("G2") != "open"
        ):
            raise GateBlockedError("target-render-evidence", ("G2-not-open",))
        if payload.get("stage") != "G2":
            raise ContractValidationError(
                "Anchor target-render evidence must belong to G2"
            )
        anchor_ref = str(payload.get("anchor_slide_set_ref") or "")
        anchor = self._require_exact_ref(
            anchor_ref, "visual/anchors", "anchor-slide-set"
        )["payload"]
        try:
            evidence = TargetRenderEvidence.from_payload(payload)
        except ValueError as error:
            raise ContractValidationError(str(error)) from error
        if (
            evidence.source_pptx_ref != anchor.get("native_first_pptx_ref")
            or evidence.pptx_sha256 != anchor.get("pptx_sha256")
        ):
            raise ContractValidationError(
                "Target evidence must reference the current anchor PPTX and SHA-256"
            )
        if [check["slide_id"] for check in evidence.slide_checks] != anchor.get(
            "slide_ids"
        ):
            raise ContractValidationError(
                "Target evidence must cover every anchor slide in final order"
            )
        self._resolve_kind(evidence.font_inventory_ref, "font-inventory")
        self._resolve_kind(evidence.font_substitution_plan_ref, "font-plan")
        self._resolve_kind(
            evidence.reviewer_attestation_ref, "desktop-review-attestation"
        )
        self._resolve_kind(evidence.source_pptx_ref, "native-pptx")
        self._resolve_kind(evidence.evidence_ref, "target-render-capture")
        for value in evidence.export_refs:
            self._resolve_kind(value, "target-export")
        for value in evidence.page_image_refs:
            self._resolve_kind(value, "target-page-image")
        for check in evidence.slide_checks:
            for value in check["evidence_refs"]:
                self._resolve_kind(value, "slide-check")
        normalized = {
            **evidence.as_payload(),
            "stage": "G2",
            "anchor_slide_set_ref": anchor_ref,
        }
        slot = f"visual/target-evidence/G2/{evidence.target_id}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.target-render-evidence-registered",
            artifact_updates={slot: ("target-render-evidence", normalized)},
        )
        return committed.artifact_heads[slot]

    def record_g2(
        self, command_id: str, expected_revision: int
    ) -> KernelState:
        mutation = GateEvaluator(self.kernel).pass_g2()
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G2.passed",
            artifact_updates={},
            gate_mutation=mutation,
        )

    def publish_visual_review(
        self, command_id: str, expected_revision: int
    ) -> KernelState:
        state = self.kernel.load()
        if state.gate_status.get("G2") != "passed":
            raise GateBlockedError("visual-review", ("G2-not-passed",))
        required = {
            "content_blueprint_ref": ("content/blueprint", "content-blueprint"),
            "deck_design_system_ref": (
                "visual/design-system",
                "deck-design-system",
            ),
            "visual_contract_set_ref": (
                "visual/contracts",
                "visual-contract-set",
            ),
            "anchor_slide_set_ref": ("visual/anchors", "anchor-slide-set"),
        }
        refs: dict[str, str] = {}
        payloads: dict[str, dict[str, Any]] = {}
        for field, (slot, kind) in required.items():
            value = state.artifact_heads.get(slot, "")
            record = self._require_exact_ref(value, slot, kind)
            refs[field] = value
            payloads[field] = record["payload"]
        target_evidence_refs: list[str] = []
        target_evidence_identities: list[dict[str, Any]] = []
        from ai_ppt_studio.domains.presentation.targets import REQUIRED_TARGET_IDS

        for target_id in REQUIRED_TARGET_IDS:
            slot = f"visual/target-evidence/G2/{target_id}"
            value = state.artifact_heads.get(slot, "")
            record = self._require_exact_ref(value, slot, "target-render-evidence")
            target_evidence_refs.append(value)
            evidence = record["payload"]
            target_evidence_identities.append(
                {
                    key: evidence.get(key)
                    for key in (
                        "target_id",
                        "operating_system",
                        "operating_system_version",
                        "application",
                        "application_version",
                        "font_inventory_ref",
                        "font_substitution_plan_ref",
                        "source_pptx_ref",
                        "pptx_sha256",
                        "export_refs",
                        "page_image_refs",
                        "slide_checks",
                        "executor",
                        "exported_at",
                        "tool_version",
                        "evidence_ref",
                        "overall_result",
                    )
                }
            )
        blueprint = payloads["content_blueprint_ref"]
        contracts = payloads["visual_contract_set_ref"]
        visual_contract = {
            **refs,
            "production_route": "strict-B",
            "deck_framework": {
                "strategy": blueprint.get("strategy"),
                "argument_map": blueprint.get("argument_map"),
                "slides": blueprint.get("slides"),
            },
            "deck_design_system": payloads["deck_design_system_ref"],
            "role_runs": contracts.get("role_runs"),
            "slide_contracts": contracts.get("slide_contracts"),
            "anchor_identity": payloads["anchor_slide_set_ref"],
            "target_evidence_refs": target_evidence_refs,
            "target_evidence_identities": target_evidence_identities,
            "internal_review_refs": [
                state.artifact_heads["visual/review/G2/aesthetic"],
                state.artifact_heads["visual/review/G2/engineering"],
            ],
            "status": "user-reviewable",
        }
        visual_contract_ref = str(
            self.kernel.artifacts.put("visual-contract", visual_contract)
        )
        mutation = GateEvaluator(self.kernel).visual_user_reviewable(
            visual_contract_ref
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.review-published",
            artifact_updates={
                "visual/contract": ("visual-contract", visual_contract)
            },
            gate_mutation=mutation,
        )

    def confirm_g3(
        self,
        command_id: str,
        expected_revision: int,
        *,
        user_message_ref: str,
    ) -> KernelState:
        state = self.kernel.load()
        if (
            state.gate_status.get("G3") != "user-reviewable"
            or not user_message_ref.startswith("chat://message/")
        ):
            raise GateBlockedError(
                "G3", ("explicit-chat-confirmation-and-visual-review-required",)
            )
        confirmation = {
            "gate": "G3",
            "user_message_ref": user_message_ref,
            "visual_contract_ref": state.artifact_heads["visual/contract"],
        }
        confirmation_ref = str(
            self.kernel.artifacts.put("g3-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g3(
            confirmation_ref=confirmation_ref,
            user_message_ref=user_message_ref,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G3.confirmed",
            artifact_updates={
                "gate/G3/confirmation": ("g3-confirmation", confirmation)
            },
            gate_mutation=mutation,
        )

    def record_internal_gate(
        self,
        command_id: str,
        expected_revision: int,
        *,
        gate: str,
        reviewer_role: str,
        acceptance_record_refs: list[str],
    ) -> KernelState:
        if not isinstance(acceptance_record_refs, list) or not acceptance_record_refs:
            raise ContractValidationError(
                "Internal Gate requires current acceptance evidence references"
            )
        state = self.kernel.load()
        if gate == "G1":
            if reviewer_role != "独立审美审查智能体":
                raise ContractValidationError(
                    "G1 can only be recorded by the independent aesthetic reviewer"
                )
            expected = {
                state.artifact_heads.get("visual/convergence", ""),
                state.artifact_heads.get("visual/review/G1/aesthetic", ""),
            }
        elif gate == "G2":
            if reviewer_role != "PPT 工程审查智能体":
                raise ContractValidationError(
                    "G2 final recording requires the PPT engineering reviewer"
                )
            expected = {
                state.artifact_heads.get("visual/review/G2/aesthetic", ""),
                state.artifact_heads.get("visual/review/G2/engineering", ""),
                *(
                    state.artifact_heads.get(
                        f"visual/target-evidence/G2/{target_id}", ""
                    )
                    for target_id in REQUIRED_TARGET_IDS
                ),
            }
        else:
            raise ContractValidationError("Internal Gate must be G1 or G2")
        if "" in expected or set(acceptance_record_refs) != expected:
            raise ContractValidationError(
                "Internal Gate evidence must exactly match the current authorized heads"
            )
        for value in acceptance_record_refs:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        if gate == "G1":
            return self.record_g1(command_id, expected_revision)
        return self.record_g2(command_id, expected_revision)

    def commit_public_artifact(
        self,
        command_id: str,
        expected_revision: int,
        *,
        kind: str,
        payload: dict[str, Any],
    ) -> str:
        """Route the existing MCP artifact vocabulary into schema 3 services."""

        if kind == "experience":
            from ai_ppt_studio.application.experience_service import ExperienceService

            return ExperienceService(self.kernel).commit_public_artifact(
                command_id,
                expected_revision,
                payload=payload,
            )
        if kind == "delivery":
            from ai_ppt_studio.application.delivery_service import DeliveryService

            return DeliveryService(self.kernel).commit_public_artifact(
                command_id,
                expected_revision,
                payload=payload,
            )

        if kind == "visual-brief":
            return self.register_visual_brief(
                command_id, expected_revision, payload
            )
        if kind == "concept-set":
            return self.register_convergence(
                command_id, expected_revision, payload
            )
        if kind == "native-anchor-set":
            return self.register_anchor_set(
                command_id, expected_revision, payload
            )
        if kind == "target-render-evidence":
            if payload.get("stage") == "G4":
                from ai_ppt_studio.application.delivery_service import DeliveryService

                return DeliveryService(
                    self.kernel
                ).register_target_render_evidence(
                    command_id, expected_revision, payload
                )
            return self.register_target_render_evidence(
                command_id, expected_revision, payload
            )
        if kind != "visual-contract":
            raise ContractValidationError(
                f"Artifact kind is not a Slice 03 visual artifact: {kind}"
            )
        artifact_type = str(payload.get("artifact_type") or "")
        if artifact_type == "deck-design-system" or (
            "visual_brief_ref" in payload and "rule_definitions" in payload
        ):
            return self.register_design_system(
                command_id, expected_revision, payload
            )
        if artifact_type == "visual-contract-set" or "slide_contracts" in payload:
            return self.register_visual_contract_set(
                command_id, expected_revision, payload
            )
        if artifact_type == "visual-review-record" or (
            "stage" in payload and "checks" in payload
        ):
            return self.register_visual_review(
                command_id, expected_revision, payload
            )
        if artifact_type == "image-asset-pack" or "asset_kind" in payload:
            return self.register_image_asset_pack(
                command_id, expected_revision, payload
            )
        raise ContractValidationError(
            "visual-contract payload needs a recognized schema 3 artifact_type"
        )

    def _require_exact_ref(self, value: str, slot: str, kind: str) -> dict:
        reference = ArtifactReference.parse(value)
        state = self.kernel.load()
        if state.artifact_heads.get(slot) != value or reference.kind != kind:
            raise ArtifactReferenceError(
                f"Artifact reference is not the current {slot} head: {value}"
            )
        return self.kernel.artifacts.resolve(reference)

    def _resolve_kind(self, value: str, kind: str) -> dict:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(
                f"Expected artifact kind {kind}, got {reference.kind}"
            )
        return self.kernel.artifacts.resolve(reference)
