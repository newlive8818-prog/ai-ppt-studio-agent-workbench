"""The only application component that calculates v1.6 Gate transitions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_ppt_studio.domains.visual.contracts import (
    validate_anchor_render_assets,
    validate_anchor_slide_set,
    validate_visual_review,
)
from ai_ppt_studio.errors import ContractValidationError, GateBlockedError
from ai_ppt_studio.domains.presentation.targets import (
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.artifact_guards import (
    VisualReviewEvidenceError,
    require_visual_review_target_evidence,
)
from ai_ppt_studio.kernel.gates import GateMutation, issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class GateEvaluator:
    """Resolve formal evidence before issuing any Gate mutation."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def content_source_replaced(
        self, evidence_refs: tuple[str, ...] = ()
    ) -> GateMutation:
        """Reopen the full content-dependent chain for a new authoritative source."""

        return issue_gate_mutation(
            {
                "G0": "open",
                "G1": "locked",
                "G2": "locked",
                "G3": "locked",
                "G4": "locked",
            },
            evidence_refs,
        )

    def await_content_review_v22(
        self,
        *,
        blueprint_ref: str,
        evidence_gate_ref: str,
        presales_reading_gate_ref: str,
        acceptance_ref: str,
    ) -> GateMutation:
        """Keep G0 locked until a current applied full-deck review exists."""

        state = self.kernel.load()
        blockers = []
        expected = {
            "blueprint": (blueprint_ref, "reading-deck-blueprint"),
            "evidence": (evidence_gate_ref, "content-hard-gate-record"),
            "reading": (
                presales_reading_gate_ref,
                "content-hard-gate-record",
            ),
            "acceptance": (acceptance_ref, "content-acceptance"),
        }
        if state.artifact_heads.get("content/reading-blueprint") != blueprint_ref:
            blockers.append("reading-blueprint-not-current")
        if state.artifact_heads.get("content/gate/evidence") != evidence_gate_ref:
            blockers.append("evidence-gate-not-current")
        for name, (reference, kind) in expected.items():
            try:
                if ArtifactReference.parse(reference).kind != kind:
                    blockers.append(f"wrong-kind:{name}")
            except Exception:
                blockers.append(f"invalid-ref:{name}")
        if blockers:
            raise GateBlockedError("G0", tuple(blockers))
        return issue_gate_mutation(
            {"G0": "locked"},
            tuple(reference for reference, _kind in expected.values()),
        )

    def content_user_reviewable(
        self,
        acceptance_ref: str,
        blueprint_ref: str,
        review_batch_ref: str,
    ) -> GateMutation:
        decision_refs = self._validate_g0_review_evidence(
            acceptance_ref,
            blueprint_ref,
            review_batch_ref,
            required_gate_status="locked",
        )
        return issue_gate_mutation(
            {"G0": "user-reviewable"},
            (acceptance_ref, blueprint_ref, review_batch_ref, *decision_refs),
        )

    def confirm_g0(
        self,
        *,
        confirmation_ref: str,
        user_message_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G0") != "user-reviewable":
            blockers.append("content-not-user-reviewable")
        if not user_message_ref.startswith("chat://message/"):
            blockers.append("explicit-chat-message-required")
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        review_batch_ref = state.artifact_heads.get("content/review-batch", "")
        if not acceptance_ref or not blueprint_ref or not review_batch_ref:
            blockers.append("content-evidence-missing")
        else:
            self._validate_g0_review_evidence(
                acceptance_ref,
                blueprint_ref,
                review_batch_ref,
                required_gate_status="user-reviewable",
            )
        confirmation = self._resolve(confirmation_ref, "g0-confirmation")
        confirmation_payload = confirmation["payload"]
        if (
            confirmation_payload.get("user_message_ref") != user_message_ref
            or confirmation_payload.get("content_acceptance_ref") != acceptance_ref
            or confirmation_payload.get("reading_blueprint_ref") != blueprint_ref
            or confirmation_payload.get("content_review_batch_ref")
            != review_batch_ref
        ):
            blockers.append("confirmation-message-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G0": "passed", "G1": "open"},
            (acceptance_ref, blueprint_ref, review_batch_ref, confirmation_ref),
        )

    def _validate_g0_review_evidence(
        self,
        acceptance_ref: str,
        blueprint_ref: str,
        review_batch_ref: str,
        *,
        required_gate_status: str,
    ) -> tuple[str, ...]:
        """Validate the exact all-approved content lineage used by G0."""

        state = self.kernel.load()
        acceptance = self._resolve(acceptance_ref, "content-acceptance")["payload"]
        blueprint = self._resolve(blueprint_ref, "reading-deck-blueprint")["payload"]
        batch = self._resolve(review_batch_ref, "content-review-batch")["payload"]
        blockers = []
        if state.gate_status.get("G0") != required_gate_status:
            blockers.append(f"content-review-not-{required_gate_status}")
        if state.artifact_heads.get("content/acceptance") != acceptance_ref:
            blockers.append("content-acceptance-not-current")
        if state.artifact_heads.get("content/reading-blueprint") != blueprint_ref:
            blockers.append("reading-blueprint-not-current")
        if state.artifact_heads.get("content/review-batch") != review_batch_ref:
            blockers.append("content-review-batch-not-current")
        if (
            acceptance.get("overall_result") != "passed"
            or acceptance.get("reading_blueprint_ref") != blueprint_ref
            or acceptance.get("source_version") != blueprint.get("source_version")
            or acceptance.get("evidence_gate_ref")
            != state.artifact_heads.get("content/gate/evidence")
            or acceptance.get("presales_reading_gate_ref")
            != state.artifact_heads.get("content/gate/presales-reading")
        ):
            blockers.append("content-acceptance-lineage-mismatch")
        if (
            batch.get("status") != "submitted"
            or not batch.get("immutable_after_submit")
            or batch.get("reading_blueprint_ref") != blueprint_ref
            or batch.get("source_version") != blueprint.get("source_version")
        ):
            blockers.append("content-review-batch-not-current")
        slide_ids = [slide.get("slide_id") for slide in blueprint.get("slides") or []]
        decision_refs = batch.get("decision_refs") or []
        if batch.get("slide_ids") != slide_ids or len(decision_refs) != len(slide_ids):
            blockers.append("content-review-decisions-incomplete")
        else:
            for slide_id, decision_ref in zip(slide_ids, decision_refs, strict=True):
                decision = self._resolve(decision_ref, "content-page-decision")["payload"]
                if (
                    decision.get("slide_id") != slide_id
                    or decision.get("decision") != "approved"
                    or decision.get("reading_blueprint_ref") != blueprint_ref
                    or decision.get("source_version") != blueprint.get("source_version")
                ):
                    blockers.append(f"content-page-not-approved:{slide_id}")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return tuple(decision_refs)

    def pass_g1(self) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G0") != "passed":
            blockers.append("G0-not-passed")
        if state.gate_status.get("G1") != "open":
            blockers.append("G1-not-open")
        refs = {
            "contracts": state.artifact_heads.get("visual/contracts", ""),
            "convergence": state.artifact_heads.get("visual/convergence", ""),
            "review": state.artifact_heads.get("visual/review/G1/aesthetic", ""),
        }
        blockers.extend(f"missing:{name}" for name, value in refs.items() if not value)
        if blockers:
            raise GateBlockedError("G1", tuple(sorted(blockers)))
        contracts = self._resolve(refs["contracts"], "visual-contract-set")
        convergence = self._resolve(refs["convergence"], "visual-convergence")
        review = self._resolve(refs["review"], "visual-review-record")
        if convergence["payload"].get("visual_contract_set_ref") != refs["contracts"]:
            blockers.append("convergence-contract-mismatch")
        if convergence["payload"].get("production_route") != "strict-B":
            blockers.append("route-not-strict-B")
        review_payload = review["payload"]
        if (
            review_payload.get("stage") != "G1"
            or review_payload.get("reviewer_kind") != "aesthetic"
            or review_payload.get("target_ref") != refs["contracts"]
            or review_payload.get("overall_result") != "passed"
        ):
            blockers.append("independent-aesthetic-review-failed")
        if contracts["payload"].get("production_route") != "strict-B":
            blockers.append("contract-route-not-strict-B")
        if blockers:
            raise GateBlockedError("G1", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G1": "passed", "G2": "open"}, tuple(refs.values())
        )

    def pass_g2(self) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G1") != "passed":
            blockers.append("G1-not-passed")
        if state.gate_status.get("G2") != "open":
            blockers.append("G2-not-open")
        if blockers:
            raise GateBlockedError("G2", tuple(sorted(set(blockers))))
        evidence = self.validate_current_g2_evidence()
        refs = evidence["refs"]
        return issue_gate_mutation(
            {"G2": "passed"},
            (
                refs["design-system"],
                refs["contracts"],
                refs["anchors"],
                refs["aesthetic-review"],
                refs["engineering-review"],
                evidence["policy_ref"],
                *evidence["target_evidence_refs"],
            ),
        )

    def validate_current_g2_evidence(self) -> dict[str, Any]:
        """Revalidate every current G2 artifact independently of Gate status."""

        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        refs = {
            "design-system": state.artifact_heads.get("visual/design-system", ""),
            "contracts": state.artifact_heads.get("visual/contracts", ""),
            "anchors": state.artifact_heads.get("visual/anchors", ""),
            "aesthetic-review": state.artifact_heads.get(
                "visual/review/G2/aesthetic", ""
            ),
            "engineering-review": state.artifact_heads.get(
                "visual/review/G2/engineering", ""
            ),
        }
        target_refs = {
            target_id: state.artifact_heads.get(
                f"visual/target-evidence/G2/{target_id}", ""
            )
            for target_id in policy.required_target_ids
        }
        blockers.extend(f"missing:{name}" for name, value in refs.items() if not value)
        blockers.extend(
            f"missing-target:{target_id}"
            for target_id, value in target_refs.items()
            if not value
        )
        if blockers:
            raise GateBlockedError("G2", tuple(sorted(blockers)))

        def resolve_payload(
            reference: str, kind: str, blocker: str
        ) -> dict[str, Any] | None:
            try:
                parsed = ArtifactReference.parse(reference)
                if parsed.kind != kind:
                    raise ValueError(f"Expected {kind}, got {parsed.kind}")
                payload = self.kernel.artifacts.resolve(parsed).get("payload")
                if not isinstance(payload, dict):
                    raise ValueError(f"{kind} payload must be an object")
                return payload
            except Exception:
                blockers.append(blocker)
                return None

        design_system = resolve_payload(
            refs["design-system"],
            "deck-design-system",
            "design-system-invalid",
        )
        contracts = resolve_payload(
            refs["contracts"], "visual-contract-set", "visual-contract-set-invalid"
        )
        anchors = resolve_payload(
            refs["anchors"], "anchor-slide-set", "anchor-slide-set-invalid"
        )
        if design_system is None or contracts is None or anchors is None:
            raise GateBlockedError("G2", tuple(sorted(set(blockers))))

        if design_system.get("production_route") != "strict-B":
            blockers.append("design-system-route-not-strict-B")
        if contracts.get("deck_design_system_ref") != refs["design-system"]:
            blockers.append("contract-design-system-mismatch")
        if anchors.get("visual_contract_set_ref") != refs["contracts"]:
            blockers.append("anchor-contract-mismatch")
        try:
            canonical_anchors = validate_anchor_slide_set(
                deepcopy(anchors), deepcopy(contracts)
            )
        except ContractValidationError:
            canonical_anchors = None
            contract_slide_ids = {
                item.get("slide_id")
                for item in contracts.get("slide_contracts") or []
                if isinstance(item, dict)
            }
            try:
                validate_anchor_render_assets(
                    anchors, valid_slide_ids=contract_slide_ids
                )
            except ContractValidationError:
                blockers.append("anchor-render-assets-invalid")
            else:
                blockers.append("anchor-slide-set-invalid")

        native_pptx_ref = str(anchors.get("native_first_pptx_ref") or "")
        native_pptx = resolve_payload(
            native_pptx_ref, "native-pptx", "anchor-native-pptx-invalid"
        )
        if native_pptx is not None and (
            native_pptx.get("production_route") != "strict-B"
            or native_pptx.get("pptx_sha256") != anchors.get("pptx_sha256")
        ):
            blockers.append("anchor-native-pptx-mismatch")

        editability_refs = anchors.get("editability_evidence_refs")
        if isinstance(editability_refs, list):
            for index, reference in enumerate(editability_refs):
                editability = resolve_payload(
                    str(reference),
                    "editability-evidence",
                    f"anchor-editability-evidence-invalid:{index}",
                )
                if editability is not None and (
                    editability.get("semantic_objects_editable") is not True
                ):
                    blockers.append(f"anchor-editability-evidence-failed:{index}")

        preflight_refs = anchors.get("preflight_render_refs")
        if isinstance(preflight_refs, list):
            for index, reference in enumerate(preflight_refs):
                preflight = resolve_payload(
                    str(reference),
                    "preflight-render",
                    f"anchor-preflight-render-invalid:{index}",
                )
                if preflight is not None and preflight.get("identity") != "preflight-only":
                    blockers.append(f"anchor-preflight-render-not-preflight:{index}")

        for reviewer_kind in ("aesthetic", "engineering"):
            review_payload = resolve_payload(
                refs[f"{reviewer_kind}-review"],
                "visual-review-record",
                f"independent-{reviewer_kind}-review-invalid",
            )
            if review_payload is None:
                continue
            try:
                review = validate_visual_review(deepcopy(review_payload))
            except ContractValidationError:
                blockers.append(f"independent-{reviewer_kind}-review-invalid")
                continue
            if (
                review["stage"] != "G2"
                or review["reviewer_kind"] != reviewer_kind
                or review["target_ref"] != refs["anchors"]
                or review["overall_result"] != "passed"
            ):
                blockers.append(f"independent-{reviewer_kind}-review-failed")
                continue
            try:
                require_visual_review_target_evidence(
                    self.kernel,
                    review,
                    expected_target_ref=refs["anchors"],
                    expected_target_kind="anchor-slide-set",
                )
            except VisualReviewEvidenceError as error:
                blockers.append(
                    f"independent-{reviewer_kind}-review-evidence-invalid:"
                    f"{error.check_index}:{error.evidence_index}"
                )
        evidence: list[TargetRenderEvidence] = []
        target_payloads: dict[str, dict[str, Any]] = {}
        target_evidence_identities: list[dict[str, Any]] = []
        identity_keys = (
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
        for target_id, value in target_refs.items():
            payload = resolve_payload(
                value,
                "target-render-evidence",
                f"invalid-target-evidence:{target_id}",
            )
            if payload is None:
                continue
            try:
                item = TargetRenderEvidence.from_payload(payload)
            except ValueError:
                blockers.append(f"invalid-target-evidence:{target_id}")
                continue
            if (
                item.target_id != target_id
                or payload.get("stage") != "G2"
                or payload.get("anchor_slide_set_ref") != refs["anchors"]
                or item.source_pptx_ref != native_pptx_ref
                or item.pptx_sha256 != anchors.get("pptx_sha256")
                or [check["slide_id"] for check in item.slide_checks]
                != anchors.get("slide_ids")
            ):
                blockers.append(f"target-anchor-mismatch:{target_id}")
            dependency_refs = (
                (item.font_inventory_ref, "font-inventory"),
                (item.font_substitution_plan_ref, "font-plan"),
                (item.reviewer_attestation_ref, "desktop-review-attestation"),
                (item.source_pptx_ref, "native-pptx"),
                (item.evidence_ref, "target-render-capture"),
                *((reference, "target-export") for reference in item.export_refs),
                *((reference, "target-page-image") for reference in item.page_image_refs),
                *(
                    (reference, "slide-check")
                    for check in item.slide_checks
                    for reference in check["evidence_refs"]
                ),
            )
            for index, (reference, kind) in enumerate(dependency_refs):
                resolve_payload(
                    reference,
                    kind,
                    f"target-evidence-dependency-invalid:{target_id}:{index}",
                )
            evidence.append(item)
            target_payloads[target_id] = deepcopy(payload)
            target_evidence_identities.append(
                {key: deepcopy(payload.get(key)) for key in identity_keys}
            )
        if blockers:
            raise GateBlockedError("G2", tuple(sorted(set(blockers))))
        matrix = validate_required_targets(evidence, policy.required_target_ids)
        if matrix.pptx_sha256 != anchors.get("pptx_sha256"):
            raise GateBlockedError("G2", ("anchor-pptx-hash-mismatch",))
        return {
            "policy_ref": policy_ref,
            "policy": policy,
            "refs": dict(refs),
            "target_evidence_refs": [
                target_refs[target_id] for target_id in policy.required_target_ids
            ],
            "target_evidence_ref_by_id": dict(target_refs),
            "target_evidence_payloads": target_payloads,
            "target_evidence_identities": target_evidence_identities,
            "internal_review_refs": [
                refs["aesthetic-review"], refs["engineering-review"]
            ],
            "design_system": deepcopy(design_system),
            "visual_contract_set": deepcopy(contracts),
            "anchor_slide_set": deepcopy(canonical_anchors or anchors),
        }

    def visual_user_reviewable(self, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G2") != "passed":
            blockers.append("G2-not-passed")
        if state.gate_status.get("G3") != "locked":
            blockers.append("G3-not-locked")
        contract = self._resolve(visual_contract_ref, "visual-contract")["payload"]
        expected = {
            "reading_blueprint_ref": state.artifact_heads.get(
                "content/reading-blueprint", ""
            ),
            "deck_design_system_ref": state.artifact_heads.get(
                "visual/design-system", ""
            ),
            "visual_contract_set_ref": state.artifact_heads.get(
                "visual/contracts", ""
            ),
            "anchor_slide_set_ref": state.artifact_heads.get(
                "visual/anchors", ""
            ),
        }
        for field, value in expected.items():
            if not value or contract.get(field) != value:
                blockers.append(f"visual-review-source-mismatch:{field}")
        target_ids = tuple(
            item.get("target_id")
            for item in contract.get("target_evidence_identities") or []
            if isinstance(item, dict)
        )
        if (
            contract.get("release_target_policy_ref") != policy_ref
            or target_ids != policy.required_target_ids
        ):
            blockers.append("visual-review-target-identities-incomplete")
        if contract.get("status") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "user-reviewable"},
            (visual_contract_ref, policy_ref, *expected.values()),
        )

    def confirm_g3(
        self, *, confirmation_ref: str, user_message_ref: str
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G3") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
        if not user_message_ref.startswith("chat://message/"):
            blockers.append("explicit-chat-message-required")
        visual_contract_ref = state.artifact_heads.get("visual/contract", "")
        if not visual_contract_ref:
            blockers.append("visual-contract-missing")
        else:
            contract = self._resolve(visual_contract_ref, "visual-contract")[
                "payload"
            ]
            if contract.get("status") != "user-reviewable":
                blockers.append("visual-contract-status-invalid")
        confirmation = self._resolve(confirmation_ref, "g3-confirmation")[
            "payload"
        ]
        if (
            confirmation.get("user_message_ref") != user_message_ref
            or confirmation.get("visual_contract_ref") != visual_contract_ref
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "passed", "G4": "open"},
            (visual_contract_ref, confirmation_ref),
        )

    def delivery_ready(self) -> GateMutation:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G3") != "passed":
            blockers.append("G3-not-passed")
        if state.gate_status.get("G4") != "open":
            blockers.append("G4-not-open")
        build_ref = state.artifact_heads.get("delivery/build", "")
        deck_qa_ref = state.artifact_heads.get("delivery/qa/deck", "")
        if not build_ref:
            blockers.append("missing:delivery/build")
        if not deck_qa_ref:
            blockers.append("missing:delivery/qa/deck")
        target_refs = {
            target_id: state.artifact_heads.get(
                f"delivery/target-evidence/G4/{target_id}", ""
            )
            for target_id in policy.required_target_ids
        }
        blockers.extend(
            f"missing-target:{target_id}"
            for target_id, value in target_refs.items()
            if not value
        )
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(blockers)))
        build = self._resolve(build_ref, "presentation-build")["payload"]
        slide_qa_refs = [
            state.artifact_heads.get(f"delivery/qa/slide/{slide_id}", "")
            for slide_id in build.get("slide_ids") or []
        ]
        if not slide_qa_refs or "" in slide_qa_refs:
            blockers.append("slide-qa-incomplete")
        else:
            for slide_id, value in zip(
                build["slide_ids"], slide_qa_refs, strict=True
            ):
                qa = self._resolve(value, "slide-qa")["payload"]
                if (
                    qa.get("slide_id") != slide_id
                    or qa.get("build_ref") != build_ref
                    or qa.get("pptx_sha256") != build.get("pptx_sha256")
                    or qa.get("overall_result") != "passed"
                ):
                    blockers.append(f"slide-qa-failed-or-stale:{slide_id}")
        deck_qa = self._resolve(deck_qa_ref, "deck-qa")["payload"]
        if (
            deck_qa.get("build_ref") != build_ref
            or deck_qa.get("pptx_sha256") != build.get("pptx_sha256")
            or deck_qa.get("slide_qa_refs") != slide_qa_refs
            or deck_qa.get("overall_result") != "passed"
        ):
            blockers.append("deck-qa-failed-or-stale")
        evidence: list[TargetRenderEvidence] = []
        for target_id, value in target_refs.items():
            payload = self._resolve(value, "target-render-evidence")["payload"]
            try:
                item = TargetRenderEvidence.from_payload(payload)
            except ValueError:
                blockers.append(f"invalid-target-evidence:{target_id}")
                continue
            if (
                item.target_id != target_id
                or payload.get("stage") != "G4"
                or payload.get("presentation_build_ref") != build_ref
                or item.source_pptx_ref != build.get("source_pptx_ref")
                or [check["slide_id"] for check in item.slide_checks]
                != build.get("slide_ids")
            ):
                blockers.append(f"target-build-mismatch:{target_id}")
            evidence.append(item)
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        matrix = validate_required_targets(evidence, policy.required_target_ids)
        if matrix.pptx_sha256 != build.get("pptx_sha256"):
            raise GateBlockedError("G4", ("build-pptx-hash-mismatch",))
        return issue_gate_mutation(
            {"G4": "delivery-ready"},
            (
                build_ref,
                deck_qa_ref,
                policy_ref,
                *slide_qa_refs,
                *target_refs.values(),
            ),
        )

    def delivery_user_reviewable(self, receipt_ref: str) -> GateMutation:
        state = self.kernel.load()
        policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G4") != "delivery-ready":
            blockers.append("delivery-not-ready")
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        if not build_ref or not package_ref:
            blockers.append("current-build-or-package-missing")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        build = self._resolve(build_ref, "presentation-build")["payload"]
        package = self._resolve(package_ref, "delivery-package")["payload"]
        receipt = self._resolve(receipt_ref, "chat-delivery-receipt")["payload"]
        if (
            package.get("build_ref") != build_ref
            or package.get("pptx_ref") != build.get("source_pptx_ref")
            or package.get("pptx_sha256") != build.get("pptx_sha256")
            or package.get("release_target_policy_ref") != policy_ref
            or package.get("status") != "delivery-ready"
        ):
            blockers.append("delivery-package-stale")
        if (
            receipt.get("send_status") != "sent"
            or receipt.get("build_ref") != build_ref
            or receipt.get("package_ref") != package_ref
            or receipt.get("pptx_ref") != build.get("source_pptx_ref")
            or receipt.get("pptx_sha256") != build.get("pptx_sha256")
        ):
            blockers.append("chat-delivery-failed-or-stale")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G4": "user-reviewable"},
            (build_ref, package_ref, receipt_ref, policy_ref),
        )

    def confirm_g4(
        self,
        *,
        confirmation_ref: str,
        user_message_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G4") != "user-reviewable":
            blockers.append("delivery-not-user-reviewable")
        if not user_message_ref.startswith("chat://message/"):
            blockers.append("explicit-chat-message-required")
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
        if not build_ref or not package_ref or not receipt_ref:
            blockers.append("current-delivery-evidence-missing")
        else:
            build = self._resolve(build_ref, "presentation-build")["payload"]
            package = self._resolve(package_ref, "delivery-package")["payload"]
            receipt = self._resolve(receipt_ref, "chat-delivery-receipt")["payload"]
            if (
                package.get("build_ref") != build_ref
                or package.get("pptx_ref") != build.get("source_pptx_ref")
                or package.get("pptx_sha256") != build.get("pptx_sha256")
                or package.get("release_target_policy_ref") != policy_ref
                or receipt.get("send_status") != "sent"
                or receipt.get("build_ref") != build_ref
                or receipt.get("package_ref") != package_ref
                or receipt.get("pptx_ref") != build.get("source_pptx_ref")
                or receipt.get("pptx_sha256") != build.get("pptx_sha256")
            ):
                blockers.append("delivery-evidence-stale")
            if receipt.get("message_ref") == user_message_ref:
                blockers.append("acceptance-message-must-differ-from-send-message")
        confirmation = self._resolve(confirmation_ref, "g4-confirmation")["payload"]
        if (
            confirmation.get("user_message_ref") != user_message_ref
            or confirmation.get("build_ref") != build_ref
            or confirmation.get("package_ref") != package_ref
            or confirmation.get("receipt_ref") != receipt_ref
            or confirmation.get("release_target_policy_ref") != policy_ref
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G4": "passed"},
            (build_ref, package_ref, receipt_ref, policy_ref, confirmation_ref),
        )

    def reopen_g4(
        self,
        *,
        reopen_ref: str,
        user_message_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G4") not in {
            "delivery-ready",
            "user-reviewable",
            "passed",
        }:
            blockers.append("delivery-not-reopenable")
        if not user_message_ref.startswith("chat://message/"):
            blockers.append("explicit-chat-message-required")
        build_ref = state.artifact_heads.get("delivery/build", "")
        reopen = self._resolve(reopen_ref, "scope-reopen")["payload"]
        if (
            reopen.get("gate") != "G4"
            or reopen.get("user_message_ref") != user_message_ref
            or reopen.get("build_ref") != build_ref
            or reopen.get("prior_status") != state.gate_status.get("G4")
        ):
            blockers.append("reopen-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return issue_gate_mutation({"G4": "open"}, (build_ref, reopen_ref))

    def _resolve(self, value: str, kind: str) -> dict:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise GateBlockedError("G0", (f"wrong-artifact-kind:{kind}",))
        return self.kernel.artifacts.resolve(reference)
