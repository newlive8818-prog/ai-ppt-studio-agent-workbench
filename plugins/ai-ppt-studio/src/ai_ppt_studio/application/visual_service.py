"""Revision-safe strict-route-B visual application service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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
from ai_ppt_studio.domains.visual.compilation import derive_visual_compilation_plan
from ai_ppt_studio.domains.presentation.targets import TargetRenderEvidence
from ai_ppt_studio.errors import (
    ContentWorkflowError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.artifact_guards import (
    require_exact_ref,
    require_visual_review_target_evidence,
    resolve_kind,
)
from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.review_commands import (
    fingerprint,
    replay_ref,
    replay_state,
)
from ai_ppt_studio.application.scoped_confirmation import (
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.visual_invalidation import visual_downstream_slots
from ai_ppt_studio.kernel.state import KernelState


class VisualService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def _require_visual_production_mutable(self, *, allow_image_led=False) -> None:
        from ai_ppt_studio.application.image_led_service import reject_legacy_production
        from ai_ppt_studio.application.image_led_service import is_image_led
        if allow_image_led and is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            ImageLedNativeService(self.kernel).current_contract_plan()
        else:
            reject_legacy_production(self.kernel)
        state = self.kernel.load()
        if state.gate_status.get("G2") != "passed":
            return
        if state.gate_status.get("G3") == "locked":
            blocker = "G2-visual-lineage-frozen-until-G3-publication"
        else:
            blocker = "G3-visual-production-frozen-until-formal-reopen"
        raise GateBlockedError("visual-production", (blocker,))

    def _require_visual_review_publishable(self) -> None:
        state = self.kernel.load()
        if (
            state.gate_status.get("G2") == "passed"
            and state.gate_status.get("G3") != "locked"
        ):
            raise GateBlockedError(
                "visual-review",
                ("G3-visual-production-frozen-until-formal-reopen",),
            )

    def register_visual_brief(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            return ImageLedNativeService(self.kernel).register_brief(command_id, expected_revision, payload)
        self._require_visual_production_mutable()
        state = self.kernel.load()
        if state.gate_status.get("G0") != "passed":
            raise GateBlockedError("visual-brief", ("G0-not-passed",))
        _policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        normalized = validate_visual_brief(payload, policy.required_target_ids)
        require_exact_ref(self.kernel,
            normalized["reading_blueprint_ref"],
            "content/reading-blueprint",
            "reading-deck-blueprint",
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.brief-registered",
            artifact_updates={
                "visual/brief": ("visual-brief", normalized)
            },
            artifact_removals=visual_downstream_slots(
                state.artifact_heads,
                keep={"visual/brief"},
            ),
        )
        return committed.artifact_heads["visual/brief"]

    def register_design_system(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            return ImageLedNativeService(self.kernel).register_design(command_id, expected_revision, payload)
        self._require_visual_production_mutable()
        normalized = validate_deck_design_system(payload)
        require_exact_ref(self.kernel,
            normalized["visual_brief_ref"], "visual/brief", "visual-brief"
        )
        require_exact_ref(self.kernel,
            normalized["reading_blueprint_ref"],
            "content/reading-blueprint",
            "reading-deck-blueprint",
        )
        state = self.kernel.load()
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.design-system-registered",
            artifact_updates={
                "visual/design-system": ("deck-design-system", normalized)
            },
            artifact_removals=visual_downstream_slots(
                state.artifact_heads,
                keep={"visual/brief", "visual/design-system"},
            ),
        )
        return committed.artifact_heads["visual/design-system"]

    def register_visual_contract_set(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            return ImageLedNativeService(self.kernel).register_contracts(command_id, expected_revision, payload)
        self._require_visual_production_mutable()
        state = self.kernel.load()
        brief_ref = state.artifact_heads.get("visual/brief", "")
        brief = require_exact_ref(
            self.kernel,
            brief_ref,
            "visual/brief",
            "visual-brief",
        )["payload"]
        design_ref = str(payload.get("deck_design_system_ref") or "")
        design = require_exact_ref(
            self.kernel,
            design_ref,
            "visual/design-system",
            "deck-design-system",
        )["payload"]
        content = require_exact_ref(self.kernel,
            str(payload.get("reading_blueprint_ref") or ""),
            "content/reading-blueprint",
            "reading-deck-blueprint",
        )["payload"]
        normalized = validate_visual_contract_set(payload, content)
        policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
        command_fingerprint = fingerprint(
            "register-visual-contract-set",
            {
                "reading_blueprint_ref": normalized["reading_blueprint_ref"],
                "visual_brief_ref": brief_ref,
                "deck_design_system_ref": design_ref,
                "release_target_policy_ref": policy_ref,
                "payload": normalized,
            },
        )
        with self.kernel.semantic_command(command_fingerprint):
            replay = replay_ref(
                self.kernel,
                command_id,
                command_fingerprint,
                "visual/contracts",
            )
            if replay:
                replay_contract_ref, replay_state_value = replay
                replay_plan_ref = replay_state_value.artifact_heads.get(
                    "visual/compilation-plan", ""
                )
                if (
                    replay_state_value.artifact_heads.get("visual/contracts")
                    != replay_contract_ref
                    or not replay_plan_ref
                ):
                    raise ContractValidationError(
                        "Processed visual contract command no longer has a current compilation plan"
                    )
                return replay_contract_ref

            contracts_ref = str(
                self.kernel.artifacts.reference_for(
                    "visual-contract-set", normalized
                )
            )
            plan = derive_visual_compilation_plan(
                reading_blueprint_ref=normalized["reading_blueprint_ref"],
                visual_brief_ref=brief_ref,
                deck_design_system_ref=design_ref,
                visual_contract_set_ref=contracts_ref,
                release_target_policy_ref=policy_ref,
                source_version=str(
                    normalized.get("source_version")
                    or content.get("source_version")
                    or ""
                ),
                source_revision=expected_revision + 1,
                visual_brief=brief,
                design_system=design,
                contract_set=normalized,
            )
            committed = self.kernel.commit(
                command_id=command_id,
                expected_revision=expected_revision,
                event_type="visual.contract-set-registered",
                artifact_updates={
                    "visual/contracts": ("visual-contract-set", normalized),
                    "visual/compilation-plan": (
                        "visual-compilation-plan",
                        plan,
                    ),
                },
                artifact_removals=visual_downstream_slots(
                    state.artifact_heads,
                    keep={
                        "visual/brief",
                        "visual/design-system",
                        "visual/contracts",
                        "visual/compilation-plan",
                    },
                ),
                command_fingerprint=command_fingerprint,
            )
            committed_contract_ref = committed.artifact_heads["visual/contracts"]
            if committed_contract_ref != contracts_ref:
                raise ContractValidationError(
                    "Committed visual contract reference differs from the precomputed reference"
                )
            return committed_contract_ref

    def register_convergence(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        self._require_visual_production_mutable(allow_image_led=True)
        normalized = validate_visual_convergence(payload)
        require_exact_ref(self.kernel,
            normalized["visual_contract_set_ref"],
            "visual/contracts",
            "visual-contract-set",
        )
        from ai_ppt_studio.application.image_led_service import is_image_led
        invalidation = {}
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import upstream_keep, PREFIX
            heads = self.kernel.load().artifact_heads
            keep = upstream_keep(heads) | {PREFIX + 'regions', 'visual/brief',
                'visual/design-system', 'visual/contracts', 'visual/compilation-plan', 'visual/convergence'}
            keep.update(slot for slot in heads if slot.startswith(PREFIX + 'region-review/'))
            invalidation = {'gate_mutation': GateEvaluator(self.kernel).image_led_upstream_replaced(),
                'artifact_removals': visual_downstream_slots(heads, keep=keep)}
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.convergence-registered",
            artifact_updates={
                "visual/convergence": ("visual-convergence", normalized)
            },
            **invalidation,
        )
        return committed.artifact_heads["visual/convergence"]

    def register_visual_review(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        self._require_visual_production_mutable(allow_image_led=True)
        normalized = validate_visual_review(payload)
        if normalized["stage"] == "G1":
            if normalized["reviewer_kind"] != "aesthetic":
                raise ContractValidationError("G1 requires an aesthetic reviewer")
            target_kind = "visual-contract-set"
            require_exact_ref(self.kernel,
                normalized["target_ref"],
                "visual/contracts",
                target_kind,
            )
        elif normalized["stage"] == "G2":
            state = self.kernel.load()
            if (
                state.gate_status.get("G1") != "passed"
                or state.gate_status.get("G2") != "open"
            ):
                raise GateBlockedError("visual-review-G2", ("G2-not-open",))
            target_kind = "anchor-slide-set"
            require_exact_ref(self.kernel,
                normalized["target_ref"],
                "visual/anchors",
                target_kind,
            )
            from ai_ppt_studio.application.image_led_service import is_image_led
            if is_image_led(self.kernel):
                from ai_ppt_studio.application.image_led_native import ImageLedNativeService
                ImageLedNativeService(self.kernel).current_anchors()
            require_visual_review_target_evidence(
                self.kernel,
                normalized,
                expected_target_ref=normalized["target_ref"],
                expected_target_kind=target_kind,
            )
        else:
            raise ContractValidationError(
                "G4 visual reviews are introduced by the delivery slice"
            )
        if normalized["stage"] == "G1":
            for check in normalized["checks"]:
                for value in check.get("evidence_refs") or []:
                    self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            service = ImageLedNativeService(self.kernel)
            task = service._agent(action='review-visual-' + normalized['reviewer_kind'],
                target_refs=[normalized['target_ref']])
            if task['role_id'] != normalized['reviewer_role']:
                raise ContractValidationError('Image-led formal reviewer identity differs from its task')
            normalized['image_led_review'] = {'reviewer_task_id': task['task_id'],
                'context_pack_ref': task['context_pack_ref'],
                'selection_ref': self.kernel.load().artifact_heads['visual/image-led/selection'],
                'plan_ref': self.kernel.load().artifact_heads['visual/compilation-plan']}
        slot = f"visual/review/{normalized['stage']}/{normalized['reviewer_kind']}"
        invalidation = {}
        if is_image_led(self.kernel) and normalized['stage'] == 'G1':
            from ai_ppt_studio.application.image_led_native import upstream_keep, PREFIX
            keep = upstream_keep(self.kernel.load().artifact_heads) | {
                PREFIX + 'regions', 'visual/brief', 'visual/design-system', 'visual/contracts',
                'visual/compilation-plan', 'visual/convergence', slot}
            keep.update(s for s in self.kernel.load().artifact_heads if s.startswith(PREFIX + 'region-review/'))
            invalidation = {'gate_mutation': GateEvaluator(self.kernel).image_led_upstream_replaced(),
                'artifact_removals': visual_downstream_slots(self.kernel.load().artifact_heads, keep=keep)}
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="visual.review-registered",
            artifact_updates={slot: ("visual-review-record", normalized)},
            **invalidation,
        )
        return committed.artifact_heads[slot]

    def record_g1(
        self, command_id: str, expected_revision: int
    ) -> KernelState:
        self._require_visual_production_mutable(allow_image_led=True)
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
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            return ImageLedNativeService(self.kernel).register_anchors(command_id, expected_revision, payload)
        self._require_visual_production_mutable()
        state = self.kernel.load()
        if state.gate_status.get("G1") != "passed":
            raise GateBlockedError("anchor-slide-set", ("G1-not-passed",))
        contract_record = require_exact_ref(self.kernel,
            str(payload.get("visual_contract_set_ref") or ""),
            "visual/contracts",
            "visual-contract-set",
        )
        normalized = validate_anchor_slide_set(payload, contract_record["payload"])
        plan = require_exact_ref(
            self.kernel,
            normalized["visual_compilation_plan_ref"],
            "visual/compilation-plan",
            "visual-compilation-plan",
        )["payload"]
        if plan.get("visual_contract_set_ref") != normalized["visual_contract_set_ref"]:
            raise ContractValidationError(
                "AnchorSlideSet compilation plan does not bind its visual contract set"
            )
        pptx = resolve_kind(self.kernel,
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
            evidence = resolve_kind(self.kernel, value, "editability-evidence")["payload"]
            if evidence.get("semantic_objects_editable") is not True:
                raise ContractValidationError(
                    "Anchor editability evidence must prove semantic objects editable"
                )
        for value in normalized["preflight_render_refs"]:
            evidence = resolve_kind(self.kernel, value, "preflight-render")["payload"]
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
        self._require_visual_production_mutable()
        normalized = validate_image_asset_pack(payload)
        anchor = require_exact_ref(self.kernel,
            normalized["anchor_slide_set_ref"],
            "visual/anchors",
            "anchor-slide-set",
        )["payload"]
        if anchor.get("native_first_frozen") is not True:
            raise ContractValidationError(
                "Image 2 assets require the current native-first anchor set to be frozen"
            )
        blockers: list[str] = []
        current_plan_ref, _plan = GateEvaluator(
            self.kernel
        )._current_visual_compilation_plan(blockers)
        if (
            not current_plan_ref
            or anchor.get("visual_compilation_plan_ref") != current_plan_ref
        ):
            raise ContractValidationError(
                "Image 2 assets require the current native-first anchor plan"
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
        self._require_visual_production_mutable(allow_image_led=True)
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
        anchor = require_exact_ref(self.kernel,
            anchor_ref, "visual/anchors", "anchor-slide-set"
        )["payload"]
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            anchor = ImageLedNativeService(self.kernel).current_anchors()
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
        resolve_kind(self.kernel, evidence.font_inventory_ref, "font-inventory")
        resolve_kind(self.kernel, evidence.font_substitution_plan_ref, "font-plan")
        resolve_kind(self.kernel,
            evidence.reviewer_attestation_ref, "desktop-review-attestation"
        )
        resolve_kind(self.kernel, evidence.source_pptx_ref, "native-pptx")
        resolve_kind(self.kernel, evidence.evidence_ref, "target-render-capture")
        for value in evidence.export_refs:
            resolve_kind(self.kernel, value, "target-export")
        for value in evidence.page_image_refs:
            resolve_kind(self.kernel, value, "target-page-image")
        for check in evidence.slide_checks:
            for value in check["evidence_refs"]:
                resolve_kind(self.kernel, value, "slide-check")
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
        self._require_visual_production_mutable(allow_image_led=True)
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
        self._require_visual_review_publishable()
        state = self.kernel.load()
        if state.gate_status.get("G2") != "passed":
            raise GateBlockedError("visual-review", ("G2-not-passed",))
        current_g2 = GateEvaluator(self.kernel).validate_current_g2_evidence()
        reading_blueprint_ref = state.artifact_heads.get(
            "content/reading-blueprint", ""
        )
        blueprint = require_exact_ref(
            self.kernel,
            reading_blueprint_ref,
            "content/reading-blueprint",
            "reading-deck-blueprint",
        )["payload"]
        refs = {
            "reading_blueprint_ref": reading_blueprint_ref,
            "deck_design_system_ref": current_g2["refs"]["design-system"],
            "visual_contract_set_ref": current_g2["refs"]["contracts"],
            "visual_compilation_plan_ref": current_g2["compilation_plan_ref"],
            "anchor_slide_set_ref": current_g2["refs"]["anchors"],
        }
        design = current_g2["design_system"]
        contracts = current_g2["visual_contract_set"]
        anchors = current_g2["anchor_slide_set"]
        source_version = str(
            contracts.get("source_version")
            or anchors.get("source_version")
            or design.get("source_version")
            or ""
        )
        visual_contract = {
            **refs,
            "production_route": "strict-B",
            "reading_deck": {
                "source_version": blueprint.get("source_version"),
                "material_mode": blueprint.get("material_mode"),
                "section_flow": blueprint.get("section_flow"),
                "slides": blueprint.get("slides"),
            },
            "deck_design_system": deepcopy(design),
            "role_runs": deepcopy(contracts.get("role_runs")),
            "slide_contracts": deepcopy(contracts.get("slide_contracts")),
            "anchor_identity": deepcopy(anchors),
            "release_target_policy_ref": current_g2["policy_ref"],
            "required_target_ids": list(current_g2["policy"].required_target_ids),
            "deferred_target_ids": list(current_g2["policy"].deferred_target_ids),
            "target_evidence_refs": deepcopy(
                current_g2["target_evidence_refs"]
            ),
            "target_evidence_identities": deepcopy(
                current_g2["target_evidence_identities"]
            ),
            "internal_review_refs": deepcopy(
                current_g2["internal_review_refs"]
            ),
            "status": "user-reviewable",
        }
        if source_version:
            visual_contract["source_version"] = source_version
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
        source_version: str = "",
        challenge_id: str = "",
        challenge_revision: int = -1,
        host_confirmation_assertion: str = "",
        user_action_ref: str = "",
        user_message_ref: str = "",
    ) -> KernelState:
        if user_action_ref.strip() or user_message_ref.strip():
            raise GateBlockedError(
                "G3", ("untrusted-raw-confirmation-identity",)
            )
        command_fingerprint = fingerprint(
            "confirm-g3",
            {
                "source_version": source_version,
                "challenge_id": challenge_id,
                "challenge_revision": challenge_revision,
            },
        )
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            return replay
        context = self.gate_confirmation_context()
        try:
            scoped, consumptions = ScopedConfirmationPolicy(
                self.kernel
            ).confirmation_payload(
                current=context,
                source_version=source_version,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=host_confirmation_assertion,
            )
        except ContentWorkflowError as error:
            raise GateBlockedError(
                "G3", ("trusted-host-assertion-invalid",)
            ) from error
        state = self.kernel.load()
        _source, evidence_refs = GateEvaluator(
            self.kernel
        ).current_g3_confirmation_evidence()
        confirmation = {
            **scoped,
            "gate": "G3",
            "visual_contract_ref": state.artifact_heads["visual/contract"],
            "release_target_policy_ref": evidence_refs[1],
        }
        confirmation_ref = str(
            self.kernel.artifacts.reference_for("g3-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g3(
            confirmation_ref=confirmation_ref,
            confirmation_payload=confirmation,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G3.confirmed",
            artifact_updates={
                "gate/G3/confirmation": ("g3-confirmation", confirmation)
            },
            confirmation_consumptions=consumptions,
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
        )

    def gate_confirmation_context(self) -> dict[str, Any]:
        source_version, evidence_refs = GateEvaluator(
            self.kernel
        ).current_g3_confirmation_evidence()
        return ScopedConfirmationPolicy(self.kernel).context(
            scope_kind="gate",
            scope_id="G3",
            source_version=source_version,
            evidence_refs=evidence_refs,
        )

    def reopen_g3(
        self,
        command_id: str,
        expected_revision: int,
        *,
        reason: str,
    ) -> KernelState:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ContractValidationError("G3 reopen reason must be non-empty")
        command_fingerprint = fingerprint(
            "reopen-g3", {"reason": normalized_reason}
        )
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            return replay
        state = self.kernel.load()
        visual_contract_ref = state.artifact_heads.get("visual/contract", "")
        mutation = GateEvaluator(self.kernel).reopen_g3(visual_contract_ref)
        reopened_at = datetime.now(timezone.utc).isoformat()
        reopen = {
            "gate": "G3",
            "project_id": state.project_id,
            "visual_contract_ref": visual_contract_ref,
            "reason": normalized_reason,
            "status": "reopened",
            "reopened_at": reopened_at,
        }
        removals = tuple(
            sorted(
                slot
                for slot in state.artifact_heads
                if slot.startswith(("visual/", "delivery/", "chat-delivery/"))
                or slot
                in {
                    "gate/G3/confirmation",
                    "gate/G4/confirmation",
                    "project/completion",
                    "experience/retrospective/job",
                }
            )
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G3.reopened",
            artifact_updates={"gate/G3/reopen": ("g3-reopen", reopen)},
            artifact_removals=removals,
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
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
        command_fingerprint = fingerprint(
            "record-internal-gate",
            {
                "gate": gate,
                "reviewer_role": reviewer_role,
                "acceptance_record_refs": acceptance_record_refs,
            },
        )
        with self.kernel.semantic_command(command_fingerprint):
            replay = replay_state(self.kernel, command_id, command_fingerprint)
            if replay is not None:
                return replay
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
                policy_ref, policy = ReleaseTargetPolicyService(
                    self.kernel
                ).current()
                expected = {
                    policy_ref,
                    state.artifact_heads.get("visual/review/G2/aesthetic", ""),
                    state.artifact_heads.get("visual/review/G2/engineering", ""),
                    *(
                        state.artifact_heads.get(
                            f"visual/target-evidence/G2/{target_id}", ""
                        )
                        for target_id in policy.required_target_ids
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
        if artifact_type.startswith("image-led-"):
            from ai_ppt_studio.application.image_led_service import ImageLedService
            return ImageLedService(self.kernel).commit_artifact(command_id, expected_revision, payload)
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
