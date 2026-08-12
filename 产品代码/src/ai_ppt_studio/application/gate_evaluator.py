"""The only application component that calculates v1.6 Gate transitions."""

from __future__ import annotations

from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.domains.presentation.targets import (
    REQUIRED_TARGET_IDS,
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.kernel.gates import GateMutation, issue_gate_mutation
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class GateEvaluator:
    """Resolve formal evidence before issuing any Gate mutation."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def content_user_reviewable(
        self, acceptance_ref: str, blueprint_ref: str
    ) -> GateMutation:
        acceptance = self._resolve(acceptance_ref, "content-acceptance")
        blueprint = self._resolve(blueprint_ref, "content-blueprint")
        blockers: list[str] = []
        if acceptance["payload"].get("overall_result") != "passed":
            blockers.append("content-acceptance-failed")
        if blueprint["payload"].get("acceptance_ref") != acceptance_ref:
            blockers.append("blueprint-acceptance-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(blockers))
        return issue_gate_mutation(
            {"G0": "user-reviewable"}, (acceptance_ref, blueprint_ref)
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
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        if not acceptance_ref or not blueprint_ref:
            blockers.append("content-evidence-missing")
        else:
            self.content_user_reviewable(acceptance_ref, blueprint_ref)
        confirmation = self._resolve(confirmation_ref, "g0-confirmation")
        if confirmation["payload"].get("user_message_ref") != user_message_ref:
            blockers.append("confirmation-message-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G0": "passed", "G1": "open"},
            (acceptance_ref, blueprint_ref, confirmation_ref),
        )

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
            for target_id in REQUIRED_TARGET_IDS
        }
        blockers.extend(f"missing:{name}" for name, value in refs.items() if not value)
        blockers.extend(
            f"missing-target:{target_id}"
            for target_id, value in target_refs.items()
            if not value
        )
        if blockers:
            raise GateBlockedError("G2", tuple(sorted(blockers)))
        design_system = self._resolve(
            refs["design-system"], "deck-design-system"
        )["payload"]
        contracts = self._resolve(refs["contracts"], "visual-contract-set")[
            "payload"
        ]
        anchors = self._resolve(refs["anchors"], "anchor-slide-set")["payload"]
        if design_system.get("production_route") != "strict-B":
            blockers.append("design-system-route-not-strict-B")
        if contracts.get("deck_design_system_ref") != refs["design-system"]:
            blockers.append("contract-design-system-mismatch")
        if anchors.get("visual_contract_set_ref") != refs["contracts"]:
            blockers.append("anchor-contract-mismatch")
        if not 2 <= len(anchors.get("slide_ids") or []) <= 3:
            blockers.append("anchor-count-invalid")
        for reviewer_kind in ("aesthetic", "engineering"):
            review = self._resolve(
                refs[f"{reviewer_kind}-review"], "visual-review-record"
            )["payload"]
            if (
                review.get("stage") != "G2"
                or review.get("reviewer_kind") != reviewer_kind
                or review.get("target_ref") != refs["anchors"]
                or review.get("overall_result") != "passed"
            ):
                blockers.append(f"independent-{reviewer_kind}-review-failed")
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
                or payload.get("stage") != "G2"
                or payload.get("anchor_slide_set_ref") != refs["anchors"]
            ):
                blockers.append(f"target-anchor-mismatch:{target_id}")
            evidence.append(item)
        if blockers:
            raise GateBlockedError("G2", tuple(sorted(set(blockers))))
        matrix = validate_required_targets(evidence)
        if matrix.pptx_sha256 != anchors.get("pptx_sha256"):
            raise GateBlockedError("G2", ("anchor-pptx-hash-mismatch",))
        return issue_gate_mutation(
            {"G2": "passed"},
            tuple(refs.values()) + tuple(target_refs.values()),
        )

    def visual_user_reviewable(self, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G2") != "passed":
            blockers.append("G2-not-passed")
        if state.gate_status.get("G3") != "locked":
            blockers.append("G3-not-locked")
        contract = self._resolve(visual_contract_ref, "visual-contract")["payload"]
        expected = {
            "content_blueprint_ref": state.artifact_heads.get(
                "content/blueprint", ""
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
        if target_ids != REQUIRED_TARGET_IDS:
            blockers.append("visual-review-target-identities-incomplete")
        if contract.get("status") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "user-reviewable"}, (visual_contract_ref, *expected.values())
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
            for target_id in REQUIRED_TARGET_IDS
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
        matrix = validate_required_targets(evidence)
        if matrix.pptx_sha256 != build.get("pptx_sha256"):
            raise GateBlockedError("G4", ("build-pptx-hash-mismatch",))
        return issue_gate_mutation(
            {"G4": "delivery-ready"},
            (build_ref, deck_qa_ref, *slide_qa_refs, *target_refs.values()),
        )

    def delivery_user_reviewable(self, receipt_ref: str) -> GateMutation:
        state = self.kernel.load()
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
            (build_ref, package_ref, receipt_ref),
        )

    def confirm_g4(
        self,
        *,
        confirmation_ref: str,
        user_message_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
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
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G4": "passed"},
            (build_ref, package_ref, receipt_ref, confirmation_ref),
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
