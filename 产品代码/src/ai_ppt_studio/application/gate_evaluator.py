"""The only application component that calculates v1.6 Gate transitions."""

from __future__ import annotations

from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.domains.presentation.targets import (
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
            {
                "G0": "user-reviewable",
                "G1": "locked",
                "G2": "locked",
                "G3": "locked",
                "G4": "locked",
            },
            (acceptance_ref, blueprint_ref),
        )

    def confirm_g0(
        self,
        *,
        confirmation_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G0") != "user-reviewable":
            blockers.append("content-not-user-reviewable")
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        if not acceptance_ref or not blueprint_ref:
            blockers.append("content-evidence-missing")
        else:
            self.content_user_reviewable(acceptance_ref, blueprint_ref)
        confirmation = self._resolve(confirmation_ref, "g0-confirmation")
        confirmation_payload = confirmation["payload"]
        if (
            confirmation_payload.get("gate") != "G0"
            or confirmation_payload.get("project_id") != state.project_id
            or confirmation_payload.get("content_acceptance_ref") != acceptance_ref
            or confirmation_payload.get("content_blueprint_ref") != blueprint_ref
            or confirmation_payload.get("source_version") != blueprint_ref
            or not self._trusted_confirmation_identity(confirmation_payload)
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G0": "passed", "G1": "open"},
            (acceptance_ref, blueprint_ref, confirmation_ref),
        )

    def upgrade_legacy_g0_confirmation(
        self,
        *,
        confirmation_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        legacy_ref = state.artifact_heads.get("gate/G0/confirmation", "")
        confirmation = self._resolve(confirmation_ref, "g0-confirmation")["payload"]
        legacy = self._resolve(legacy_ref, "g0-confirmation")["payload"]
        blockers: list[str] = []
        if state.gate_status.get("G0") != "passed":
            blockers.append("G0-not-passed")
        if (
            legacy.get("gate") != "G0"
            or legacy.get("content_acceptance_ref") != acceptance_ref
            or legacy.get("content_blueprint_ref") != blueprint_ref
            or not str(legacy.get("user_message_ref") or "").startswith(
                "chat://message/"
            )
            or legacy.get("source_version")
            or legacy.get("host_assertion_sha256")
            or legacy.get("confirmation_identity_type")
        ):
            blockers.append("legacy-G0-confirmation-not-upgradeable")
        if (
            confirmation.get("gate") != "G0"
            or confirmation.get("project_id") != state.project_id
            or confirmation.get("content_acceptance_ref") != acceptance_ref
            or confirmation.get("content_blueprint_ref") != blueprint_ref
            or confirmation.get("source_version") != blueprint_ref
            or confirmation.get("confirmation_mode")
            != "legacy-credential-upgrade"
            or confirmation.get("supersedes_confirmation_ref") != legacy_ref
            or legacy_ref not in confirmation.get("evidence_refs", [])
            or not self._trusted_confirmation_identity(confirmation)
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G0": "passed"},
            (acceptance_ref, blueprint_ref, legacy_ref, confirmation_ref),
        )

    def reopen_g0(
        self,
        *,
        acceptance_ref: str,
        blueprint_ref: str,
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G0") not in {
            "user-reviewable",
            "passed",
        }:
            blockers.append("G0-not-reopenable")
        target_status = "open"
        if acceptance_ref and blueprint_ref:
            try:
                self.content_user_reviewable(acceptance_ref, blueprint_ref)
                target_status = "user-reviewable"
            except GateBlockedError:
                target_status = "open"
        if blockers:
            raise GateBlockedError("G0", tuple(blockers))
        evidence = tuple(
            value for value in (acceptance_ref, blueprint_ref) if value
        )
        return issue_gate_mutation(
            {
                "G0": target_status,
                "G1": "locked",
                "G2": "locked",
                "G3": "locked",
                "G4": "locked",
            },
            evidence,
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

    def pass_g2(self) -> tuple[GateMutation, dict[str, object]]:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        required_target_ids = policy.required_target_ids
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
            for target_id in required_target_ids
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
        content_blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        visual_brief_ref = state.artifact_heads.get("visual/brief", "")
        convergence_ref = state.artifact_heads.get("visual/convergence", "")
        g1_review_ref = state.artifact_heads.get(
            "visual/review/G1/aesthetic", ""
        )
        if not all(
            (
                content_blueprint_ref,
                visual_brief_ref,
                convergence_ref,
                g1_review_ref,
            )
        ):
            blockers.append("G1-reviewed-lineage-missing")
        else:
            visual_brief = self._resolve(
                visual_brief_ref, "visual-brief"
            )["payload"]
            convergence = self._resolve(
                convergence_ref, "visual-convergence"
            )["payload"]
            g1_review = self._resolve(
                g1_review_ref, "visual-review-record"
            )["payload"]
            if visual_brief.get("content_blueprint_ref") != content_blueprint_ref:
                blockers.append("visual-brief-content-mismatch")
            if (
                design_system.get("visual_brief_ref") != visual_brief_ref
                or design_system.get("content_blueprint_ref")
                != content_blueprint_ref
            ):
                blockers.append("design-system-lineage-mismatch")
            if contracts.get("content_blueprint_ref") != content_blueprint_ref:
                blockers.append("contract-content-mismatch")
            if (
                convergence.get("visual_contract_set_ref") != refs["contracts"]
                or convergence.get("production_route") != "strict-B"
                or convergence.get("convergence_status") != "passed"
            ):
                blockers.append("convergence-contract-mismatch")
            if (
                g1_review.get("stage") != "G1"
                or g1_review.get("reviewer_kind") != "aesthetic"
                or g1_review.get("target_ref") != refs["contracts"]
                or g1_review.get("overall_result") != "passed"
            ):
                blockers.append("independent-G1-aesthetic-review-failed")
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
        matrix = validate_required_targets(evidence, required_target_ids)
        if matrix.pptx_sha256 != anchors.get("pptx_sha256"):
            raise GateBlockedError("G2", ("anchor-pptx-hash-mismatch",))
        lineage = {
            "content_blueprint_ref": state.artifact_heads.get(
                "content/blueprint", ""
            ),
            "visual_brief_ref": state.artifact_heads.get("visual/brief", ""),
            "visual_convergence_ref": state.artifact_heads.get(
                "visual/convergence", ""
            ),
            "deck_design_system_ref": refs["design-system"],
            "visual_contract_set_ref": refs["contracts"],
            "anchor_slide_set_ref": refs["anchors"],
            "release_target_policy_ref": policy_ref,
            "required_target_ids": list(required_target_ids),
            "deferred_target_ids": list(policy.deferred_target_ids),
            "internal_review_refs": [
                state.artifact_heads.get("visual/review/G1/aesthetic", ""),
                refs["aesthetic-review"],
                refs["engineering-review"],
            ],
            "target_evidence_refs": [
                target_refs[target_id] for target_id in required_target_ids
            ],
        }
        lineage_refs = tuple(
            value
            for value in (
                lineage["content_blueprint_ref"],
                lineage["visual_brief_ref"],
                lineage["visual_convergence_ref"],
                lineage["deck_design_system_ref"],
                lineage["visual_contract_set_ref"],
                lineage["anchor_slide_set_ref"],
                lineage["release_target_policy_ref"],
                *lineage["internal_review_refs"],
                *lineage["target_evidence_refs"],
            )
            if isinstance(value, str) and value
        )
        return issue_gate_mutation({"G2": "passed"}, lineage_refs), lineage

    def current_g2_reviewed_lineage(self) -> dict[str, object]:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        lineage_ref = state.artifact_heads.get("gate/G2/lineage", "")
        if not lineage_ref:
            raise GateBlockedError(
                "G3", ("G2-reviewed-visual-lineage-missing",)
            )
        lineage = self._resolve(lineage_ref, "g2-visual-lineage")["payload"]
        expected = {
            "content_blueprint_ref": state.artifact_heads.get(
                "content/blueprint", ""
            ),
            "visual_brief_ref": state.artifact_heads.get("visual/brief", ""),
            "visual_convergence_ref": state.artifact_heads.get(
                "visual/convergence", ""
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
            "release_target_policy_ref": policy_ref,
            "required_target_ids": list(policy.required_target_ids),
            "deferred_target_ids": list(policy.deferred_target_ids),
            "internal_review_refs": [
                state.artifact_heads.get("visual/review/G1/aesthetic", ""),
                state.artifact_heads.get("visual/review/G2/aesthetic", ""),
                state.artifact_heads.get("visual/review/G2/engineering", ""),
            ],
            "target_evidence_refs": [
                state.artifact_heads.get(
                    f"visual/target-evidence/G2/{target_id}", ""
                )
                for target_id in policy.required_target_ids
            ],
        }
        if any(
            not value
            for value in (
                *(
                    expected[field]
                    for field in (
                        "content_blueprint_ref",
                        "visual_brief_ref",
                        "visual_convergence_ref",
                        "deck_design_system_ref",
                        "visual_contract_set_ref",
                        "anchor_slide_set_ref",
                        "release_target_policy_ref",
                    )
                ),
                *expected["internal_review_refs"],
                *expected["target_evidence_refs"],
            )
        ) or lineage != expected:
            raise GateBlockedError(
                "G3", ("G2-reviewed-visual-lineage-stale",)
            )
        return lineage

    def visual_user_reviewable(self, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G2") != "passed":
            blockers.append("G2-not-passed")
        if state.gate_status.get("G3") != "locked":
            blockers.append("G3-not-locked")
        try:
            reviewed_lineage = self.current_g2_reviewed_lineage()
        except GateBlockedError as error:
            blockers.extend(error.missing_evidence)
            reviewed_lineage = None
        contract = self._resolve(visual_contract_ref, "visual-contract")["payload"]
        expected = {
            "content_blueprint_ref": state.artifact_heads.get(
                "content/blueprint", ""
            ),
            "visual_convergence_ref": state.artifact_heads.get(
                "visual/convergence", ""
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
            "g2_reviewed_lineage_ref": state.artifact_heads.get(
                "gate/G2/lineage", ""
            ),
            "release_target_policy_ref": policy_ref,
        }
        for field, value in expected.items():
            if not value or contract.get(field) != value:
                blockers.append(f"visual-review-source-mismatch:{field}")
        if reviewed_lineage is not None:
            for field, value in expected.items():
                if field == "g2_reviewed_lineage_ref":
                    continue
                if reviewed_lineage.get(field) != value:
                    blockers.append("G2-reviewed-visual-lineage-stale")
            if contract.get("visual_brief_ref") != reviewed_lineage.get(
                "visual_brief_ref"
            ):
                blockers.append("G2-reviewed-visual-lineage-stale")
            if contract.get("internal_review_refs") != reviewed_lineage.get(
                "internal_review_refs"
            ):
                blockers.append("G2-reviewed-visual-lineage-stale")
            if contract.get("target_evidence_refs") != reviewed_lineage.get(
                "target_evidence_refs"
            ):
                blockers.append("G2-reviewed-visual-lineage-stale")
            if contract.get("required_target_ids") != reviewed_lineage.get(
                "required_target_ids"
            ) or contract.get("deferred_target_ids") != reviewed_lineage.get(
                "deferred_target_ids"
            ):
                blockers.append("G2-reviewed-visual-lineage-stale")
        target_ids = tuple(
            item.get("target_id")
            for item in contract.get("target_evidence_identities") or []
            if isinstance(item, dict)
        )
        if target_ids != policy.required_target_ids:
            blockers.append("visual-review-target-identities-incomplete")
        if contract.get("status") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "user-reviewable"}, (visual_contract_ref, *expected.values())
        )

    def confirm_g3(
        self, *, confirmation_ref: str
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G3") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
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
        try:
            current_context = GateConfirmationPolicy(self.kernel).context("G3")
        except GateBlockedError as error:
            blockers.extend(error.missing_evidence)
            current_context = None
        if (
            confirmation.get("gate") != "G3"
            or confirmation.get("project_id") != state.project_id
            or confirmation.get("source_version") != visual_contract_ref
            or confirmation.get("visual_contract_ref") != visual_contract_ref
            or not self._trusted_confirmation_identity(confirmation)
            or current_context is None
            or confirmation.get("evidence_refs")
            != current_context.get("evidence_refs")
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "passed", "G4": "open"},
            (visual_contract_ref, confirmation_ref),
        )

    def reopen_g3(self, *, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        if state.gate_status.get("G3") not in {"user-reviewable", "passed"}:
            raise GateBlockedError("G3", ("G3-not-reopenable",))
        evidence = (visual_contract_ref,) if visual_contract_ref else ()
        return issue_gate_mutation(
            {
                "G1": "open",
                "G2": "locked",
                "G3": "locked",
                "G4": "locked",
            },
            evidence,
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
    ) -> GateMutation:
        state = self.kernel.load()
        policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G4") != "user-reviewable":
            blockers.append("delivery-not-user-reviewable")
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
        confirmation = self._resolve(confirmation_ref, "g4-confirmation")["payload"]
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
            if receipt.get("message_ref") == confirmation.get(
                "user_message_ref"
            ):
                blockers.append("acceptance-message-must-differ-from-send-message")
        if (
            confirmation.get("gate") != "G4"
            or confirmation.get("project_id") != state.project_id
            or confirmation.get("source_version") != package_ref
            or confirmation.get("build_ref") != build_ref
            or confirmation.get("package_ref") != package_ref
            or confirmation.get("receipt_ref") != receipt_ref
            or not self._trusted_confirmation_identity(confirmation)
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

    @staticmethod
    def _trusted_confirmation_identity(payload: dict) -> bool:
        action_ref = str(payload.get("user_action_ref") or "")
        message_ref = str(payload.get("user_message_ref") or "")
        identity_type = payload.get("confirmation_identity_type")
        if not payload.get("host_assertion_sha256"):
            return False
        if identity_type == "host-action":
            return bool(action_ref) and not message_ref
        if identity_type == "verified-message":
            return bool(message_ref) and not action_ref
        return False
