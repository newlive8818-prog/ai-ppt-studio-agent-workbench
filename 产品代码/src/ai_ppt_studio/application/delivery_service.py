"""Revision-safe schema 3 delivery application service."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy
from ai_ppt_studio.domains.presentation.targets import (
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.domains.presentation.release_policy import SUPPORTED_TARGET_IDS
from ai_ppt_studio.domains.delivery.contracts import (
    validate_chat_delivery_receipt,
    validate_deck_qa,
    validate_delivery_package,
    validate_failed_attempt,
    validate_presentation_build,
    validate_repair,
    validate_slide_qa,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


class DeliveryService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def register_build(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if (
            state.gate_status.get("G3") != "passed"
            or state.gate_status.get("G4") != "open"
        ):
            raise GateBlockedError(
                "presentation-build", ("G3-passed-and-G4-open-required",)
            )
        normalized = self._validated_build_payload(payload)
        previous = state.artifact_heads.get("delivery/build")
        if previous:
            normalized["last_valid_build_ref"] = previous
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.build-registered",
            artifact_updates={
                "delivery/build": ("presentation-build", normalized)
            },
        )
        return committed.artifact_heads["delivery/build"]

    def _validated_build_payload(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        visual_contract_record = self._require_exact_ref(
            str(payload.get("visual_contract_ref") or ""),
            "visual/contract",
            "visual-contract",
        )
        normalized = validate_presentation_build(
            payload, visual_contract_record["payload"]
        )
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        g2_evidence: list[TargetRenderEvidence] = []
        for target_id in policy.required_target_ids:
            ref = state.artifact_heads.get(
                f"visual/target-evidence/G2/{target_id}", ""
            )
            if not ref:
                raise ContractValidationError(
                    "Final build requires the complete current required G2 target matrix"
                )
            try:
                g2_evidence.append(
                    TargetRenderEvidence.from_payload(
                        self._resolve_kind(ref, "target-render-evidence")["payload"]
                    )
                )
            except (ValueError, GateBlockedError) as error:
                raise ContractValidationError(
                    "Final build requires valid G2 target evidence"
                ) from error
        try:
            validate_required_targets(g2_evidence, policy.required_target_ids)
        except GateBlockedError as error:
            raise ContractValidationError(
                "Final build requires valid G2 target evidence"
            ) from error
        pptx = self._resolve_kind(normalized["source_pptx_ref"], "final-pptx")[
            "payload"
        ]
        if (
            pptx.get("pptx_sha256") != normalized["pptx_sha256"]
            or pptx.get("production_route") != "strict-B"
            or pptx.get("slide_ids") != normalized["slide_ids"]
            or pptx.get("tool_name") != "Codex Presentations"
        ):
            raise ContractValidationError(
                "Final PPTX identity, hash, route, slides, or tool does not match the build"
            )
        for value in normalized["native_editability_evidence_refs"]:
            evidence = self._resolve_kind(value, "editability-evidence")["payload"]
            if (
                evidence.get("semantic_objects_editable") is not True
                or evidence.get("whole_slide_bitmap") is not False
                or evidence.get("slide_ids") != normalized["slide_ids"]
            ):
                raise ContractValidationError(
                    "Editability evidence must cover every slide and reject whole-slide bitmaps"
                )
        for value in normalized["preflight_render_refs"]:
            preflight = self._resolve_kind(value, "preflight-render")["payload"]
            if (
                preflight.get("identity") != "preflight-only"
                or preflight.get("slide_ids") != normalized["slide_ids"]
            ):
                raise ContractValidationError(
                    "Preflight evidence must be preflight-only and cover the complete deck"
                )
        return normalized

    def restore_build(
        self,
        command_id: str,
        expected_revision: int,
        *,
        source_build_ref: str,
    ) -> str:
        state = self.kernel.load()
        if (
            state.gate_status.get("G3") != "passed"
            or state.gate_status.get("G4") != "open"
        ):
            raise GateBlockedError(
                "presentation-build-restore",
                ("G3-passed-and-G4-open-required",),
            )
        current_build_ref = state.artifact_heads.get("delivery/build", "")
        if not current_build_ref:
            raise ContractValidationError("No current build exists to replace")
        source = self._resolve_kind(
            source_build_ref, "presentation-build"
        )["payload"]
        normalized = self._validated_build_payload(dict(source))
        normalized["restored_from"] = source_build_ref
        normalized["last_valid_build_ref"] = current_build_ref
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.build-restored",
            artifact_updates={
                "delivery/build": ("presentation-build", normalized)
            },
        )
        return committed.artifact_heads["delivery/build"]

    def register_slide_qa(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        build_record = self._require_exact_ref(
            str(payload.get("build_ref") or ""),
            "delivery/build",
            "presentation-build",
        )
        normalized = validate_slide_qa(payload, build_record["payload"])
        for value in normalized["evidence_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        slot = f"delivery/qa/slide/{normalized['slide_id']}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.slide-qa-registered",
            artifact_updates={slot: ("slide-qa", normalized)},
        )
        return committed.artifact_heads[slot]

    def register_deck_qa(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        build_record = self._require_exact_ref(
            str(payload.get("build_ref") or ""),
            "delivery/build",
            "presentation-build",
        )
        build = build_record["payload"]
        state = self.kernel.load()
        current_refs = [
            state.artifact_heads.get(f"delivery/qa/slide/{slide_id}", "")
            for slide_id in build["slide_ids"]
        ]
        if "" in current_refs:
            raise ContractValidationError(
                "DeckQA requires a current QA record for every slide"
            )
        normalized = validate_deck_qa(payload, build, current_refs)
        for value in current_refs:
            record = self._resolve_kind(value, "slide-qa")["payload"]
            if (
                record.get("build_ref") != payload["build_ref"]
                or record.get("pptx_sha256") != build["pptx_sha256"]
                or record.get("overall_result") != "passed"
            ):
                raise ContractValidationError(
                    "DeckQA can only aggregate current passing slide QA records"
                )
        for value in normalized["evidence_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.deck-qa-registered",
            artifact_updates={"delivery/qa/deck": ("deck-qa", normalized)},
        )
        return committed.artifact_heads["delivery/qa/deck"]

    def record_failed_attempt(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        current_build_ref = state.artifact_heads.get("delivery/build", "")
        if not current_build_ref:
            raise ContractValidationError("No last-valid delivery build exists")
        build = self._resolve_kind(current_build_ref, "presentation-build")["payload"]
        normalized = validate_failed_attempt(payload, current_build_ref, build)
        attempt = self._resolve_kind(normalized["attempt_ref"], "build-attempt")[
            "payload"
        ]
        if attempt.get("status") != "failed":
            raise ContractValidationError("Build attempt must be explicitly failed")
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.build-attempt-failed",
            artifact_updates={
                "delivery/failed-attempt": ("failed-build-attempt", normalized)
            },
        )
        return committed.artifact_heads["delivery/failed-attempt"]

    def register_repair(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        failed_attempt_ref = state.artifact_heads.get("delivery/failed-attempt", "")
        current_build_ref = state.artifact_heads.get("delivery/build", "")
        if not failed_attempt_ref or not current_build_ref:
            raise ContractValidationError(
                "Delivery repair requires a failed attempt and last-valid build"
            )
        build = self._resolve_kind(current_build_ref, "presentation-build")["payload"]
        normalized = validate_repair(
            payload, failed_attempt_ref, current_build_ref, build
        )
        for value in normalized["preserve_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.repair-registered",
            artifact_updates={
                "delivery/repair": ("delivery-repair", normalized)
            },
        )
        return committed.artifact_heads["delivery/repair"]

    def register_target_render_evidence(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if (
            state.gate_status.get("G3") != "passed"
            or state.gate_status.get("G4") != "open"
        ):
            raise GateBlockedError("target-render-evidence", ("G4-not-open",))
        if payload.get("stage") != "G4":
            raise ContractValidationError(
                "Full-deck target-render evidence must belong to G4"
            )
        build_ref = str(payload.get("presentation_build_ref") or "")
        build = self._require_exact_ref(
            build_ref, "delivery/build", "presentation-build"
        )["payload"]
        try:
            evidence = TargetRenderEvidence.from_payload(payload)
        except ValueError as error:
            raise ContractValidationError(str(error)) from error
        if (
            evidence.source_pptx_ref != build.get("source_pptx_ref")
            or evidence.pptx_sha256 != build.get("pptx_sha256")
            or [check["slide_id"] for check in evidence.slide_checks]
            != build.get("slide_ids")
        ):
            raise ContractValidationError(
                "G4 target evidence must cover the current full-deck build and hash"
            )
        self._resolve_kind(evidence.font_inventory_ref, "font-inventory")
        self._resolve_kind(evidence.font_substitution_plan_ref, "font-plan")
        self._resolve_kind(
            evidence.reviewer_attestation_ref, "desktop-review-attestation"
        )
        self._resolve_kind(evidence.source_pptx_ref, "final-pptx")
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
            "stage": "G4",
            "presentation_build_ref": build_ref,
        }
        slot = f"delivery/target-evidence/G4/{evidence.target_id}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.target-render-evidence-registered",
            artifact_updates={slot: ("target-render-evidence", normalized)},
        )
        return committed.artifact_heads[slot]

    def finalize_delivery(
        self, command_id: str, expected_revision: int
    ) -> KernelState:
        mutation = GateEvaluator(self.kernel).delivery_ready()
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.ready",
            artifact_updates={},
            gate_mutation=mutation,
        )

    def register_delivery_package(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        state = self.kernel.load()
        if state.gate_status.get("G4") != "delivery-ready":
            raise GateBlockedError("G4", ("delivery-not-ready",))
        build_ref = str(payload.get("build_ref") or "")
        build = self._require_exact_ref(
            build_ref, "delivery/build", "presentation-build"
        )["payload"]
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        target_refs = [
            state.artifact_heads.get(
                f"delivery/target-evidence/G4/{target_id}", ""
            )
            for target_id in policy.required_target_ids
        ]
        if "" in target_refs:
            raise ContractValidationError(
                "DeliveryPackage requires all current required G4 target evidence heads"
            )
        normalized = validate_delivery_package(
            payload, build, target_refs, policy_ref
        )
        self._resolve_kind(normalized["pptx_ref"], "final-pptx")
        for value in normalized["preview_refs"]:
            preview = self._resolve_kind(value, "delivery-preview")["payload"]
            if preview.get("build_ref") != build_ref:
                raise ContractValidationError(
                    "Delivery preview must bind the current build"
                )
        manifest = self._resolve_kind(
            normalized["source_manifest_ref"], "source-manifest"
        )["payload"]
        if manifest.get("visual_contract_ref") != build.get("visual_contract_ref"):
            raise ContractValidationError(
                "Source manifest must bind the build visual contract"
            )
        font_report = self._resolve_kind(
            normalized["font_platform_report_ref"], "font-platform-report"
        )["payload"]
        if (
            font_report.get("build_ref") != build_ref
            or font_report.get("release_target_policy_ref") != policy_ref
            or font_report.get("targets") != list(policy.required_target_ids)
            or font_report.get("deferred_targets")
            != list(policy.deferred_target_ids)
        ):
            raise ContractValidationError(
                "Font/platform report must bind the current build and release policy"
            )
        qa_report = self._resolve_kind(
            normalized["qa_report_ref"], "delivery-qa-report"
        )["payload"]
        if (
            qa_report.get("build_ref") != build_ref
            or qa_report.get("deck_qa_ref")
            != state.artifact_heads.get("delivery/qa/deck")
        ):
            raise ContractValidationError(
                "QA report must bind the current build and deck QA"
            )
        for value in target_refs:
            self._resolve_kind(value, "target-render-evidence")
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="delivery.package-registered",
            artifact_updates={
                "delivery/package": ("delivery-package", normalized)
            },
        )
        return committed.artifact_heads["delivery/package"]

    def record_chat_delivery(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> KernelState:
        state = self.kernel.load()
        if state.gate_status.get("G4") != "delivery-ready":
            raise GateBlockedError("G4", ("delivery-package-not-ready",))
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        if not build_ref or not package_ref:
            raise GateBlockedError("G4", ("delivery-package-missing",))
        build = self._require_exact_ref(
            build_ref, "delivery/build", "presentation-build"
        )["payload"]
        self._require_exact_ref(
            package_ref, "delivery/package", "delivery-package"
        )
        normalized = validate_chat_delivery_receipt(
            payload, build_ref, package_ref, build
        )
        for value in normalized["artifact_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        retry_of = normalized["retry_of"]
        if retry_of:
            self._resolve_kind(retry_of, "chat-delivery-receipt")
        receipt_ref = str(
            self.kernel.artifacts.put("chat-delivery-receipt", normalized)
        )
        mutation = None
        event_type = "delivery.chat-send-failed"
        if normalized["send_status"] == "sent":
            mutation = GateEvaluator(self.kernel).delivery_user_reviewable(
                receipt_ref
            )
            event_type = "delivery.chat-sent"
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=event_type,
            artifact_updates={
                "chat-delivery/pptx": ("chat-delivery-receipt", normalized)
            },
            gate_mutation=mutation,
        )

    def confirm_g4(
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
            gate="G4",
            source_version=source_version,
            challenge_id=challenge_id,
            challenge_revision=challenge_revision,
            host_confirmation_assertion=host_confirmation_assertion,
            user_action_ref=user_action_ref,
            user_message_ref=user_message_ref,
        )
        confirmation["build_ref"] = confirmation["evidence_refs"][0]
        confirmation["package_ref"] = confirmation["source_version"]
        confirmation["receipt_ref"] = confirmation["evidence_refs"][2]
        confirmation_ref = str(
            self.kernel.artifacts.put("g4-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g4(
            confirmation_ref=confirmation_ref,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G4.confirmed",
            artifact_updates={
                "gate/G4/confirmation": ("g4-confirmation", confirmation)
            },
            confirmation_consumptions=consumptions,
            gate_mutation=mutation,
        )

    def reopen_g4(
        self,
        command_id: str,
        expected_revision: int,
        *,
        user_message_ref: str,
        impact_scope: list[str],
    ) -> KernelState:
        state = self.kernel.load()
        if state.gate_status.get("G4") not in {
            "delivery-ready",
            "user-reviewable",
            "passed",
        }:
            raise GateBlockedError("G4", ("delivery-not-reopenable",))
        if not user_message_ref.startswith("chat://message/"):
            raise ContractValidationError(
                "G4 reopen requires an explicit chat message"
            )
        build_ref = state.artifact_heads.get("delivery/build", "")
        if not build_ref:
            raise GateBlockedError("G4", ("current-build-missing",))
        build = self._resolve_kind(build_ref, "presentation-build")["payload"]
        if (
            not isinstance(impact_scope, list)
            or not impact_scope
            or any(
                not isinstance(value, str)
                or not value
                or value not in build.get("slide_ids", [])
                for value in impact_scope
            )
            or len(set(impact_scope)) != len(impact_scope)
        ):
            raise ContractValidationError(
                "G4 impact_scope must contain unique current slide ids"
            )
        reopen = {
            "gate": "G4",
            "user_message_ref": user_message_ref,
            "impact_scope": list(impact_scope),
            "build_ref": build_ref,
            "package_ref": state.artifact_heads.get("delivery/package", ""),
            "receipt_ref": state.artifact_heads.get("chat-delivery/pptx", ""),
            "prior_status": state.gate_status["G4"],
        }
        reopen_ref = str(self.kernel.artifacts.put("scope-reopen", reopen))
        mutation = GateEvaluator(self.kernel).reopen_g4(
            reopen_ref=reopen_ref,
            user_message_ref=user_message_ref,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G4.reopened",
            artifact_updates={
                "gate/G4/reopen": ("scope-reopen", reopen)
            },
            gate_mutation=mutation,
        )

    def commit_public_artifact(
        self,
        command_id: str,
        expected_revision: int,
        *,
        payload: dict[str, Any],
    ) -> str:
        artifact_type = str(payload.get("artifact_type") or "")
        routes = {
            "presentation-build": self.register_build,
            "slide-qa": self.register_slide_qa,
            "deck-qa": self.register_deck_qa,
            "failed-build-attempt": self.record_failed_attempt,
            "delivery-repair": self.register_repair,
            "delivery-package": self.register_delivery_package,
        }
        route = routes.get(artifact_type)
        if route is None:
            raise ContractValidationError(
                "delivery payload needs a recognized schema 3 artifact_type"
            )
        return route(command_id, expected_revision, payload)

    def record_public_chat_delivery(
        self,
        command_id: str,
        expected_revision: int,
        *,
        delivery_type: str,
        artifact_refs: list[str],
        message_ref: str,
        send_status: str,
        retry_of: str,
    ) -> KernelState:
        if delivery_type != "pptx":
            raise ContractValidationError(
                "Schema 3 delivery receipts currently require delivery_type=pptx"
            )
        state = self.kernel.load()
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        if not build_ref or not package_ref:
            raise GateBlockedError("G4", ("current-build-or-package-missing",))
        build = self._resolve_kind(build_ref, "presentation-build")["payload"]
        return self.record_chat_delivery(
            command_id,
            expected_revision,
            {
                "delivery_type": "pptx",
                "build_ref": build_ref,
                "package_ref": package_ref,
                "pptx_ref": build["source_pptx_ref"],
                "pptx_sha256": build["pptx_sha256"],
                "artifact_refs": artifact_refs,
                "message_ref": message_ref,
                "send_status": send_status,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "retry_of": retry_of,
            },
        )

    def reopen_public_scope(
        self,
        command_id: str,
        expected_revision: int,
        *,
        gate: str,
        reason: str,
    ) -> KernelState:
        explanation = reason.strip()
        if gate != "G4":
            raise ContractValidationError(
                "Schema 3 delivery scope routing currently supports G4 only"
            )
        if not explanation:
            raise ContractValidationError("Reopening G4 requires a reason")
        state = self.kernel.load()
        build_ref = state.artifact_heads.get("delivery/build", "")
        if not build_ref:
            raise GateBlockedError("G4", ("current-build-missing",))
        build = self._resolve_kind(build_ref, "presentation-build")["payload"]
        identity = hashlib.sha256(
            f"{command_id}:{explanation}".encode("utf-8")
        ).hexdigest()
        return self.reopen_g4(
            command_id,
            expected_revision,
            user_message_ref=f"chat://message/reopen-scope/{identity}",
            impact_scope=list(build.get("slide_ids") or []),
        )

    def delivery_status_projection(self) -> dict[str, Any]:
        state = self.kernel.load()
        build_ref = state.artifact_heads.get("delivery/build", "")
        build = (
            self._resolve_kind(build_ref, "presentation-build")["payload"]
            if build_ref
            else {}
        )
        slide_ids = list(build.get("slide_ids") or [])
        slide_records: list[dict[str, Any] | None] = []
        for slide_id in slide_ids:
            value = state.artifact_heads.get(f"delivery/qa/slide/{slide_id}", "")
            if not value:
                slide_records.append(None)
                continue
            payload = self._resolve_kind(value, "slide-qa")["payload"]
            slide_records.append(
                payload
                if payload.get("build_ref") == build_ref
                and payload.get("pptx_sha256") == build.get("pptx_sha256")
                and payload.get("slide_id") == slide_id
                else None
            )

        def slide_gate(field: str) -> str:
            values = [record.get(field) for record in slide_records if record]
            if "failed" in values:
                return "failed"
            if slide_ids and len(values) == len(slide_ids) and set(values) == {"passed"}:
                return "passed"
            return "pending"

        completed = sum(
            1
            for record in slide_records
            if record and record.get("overall_result") == "passed"
        )
        target_rows: list[dict[str, str]] = []
        target_statuses: list[str] = []
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        for target_id in SUPPORTED_TARGET_IDS:
            required = target_id in policy.required_target_ids
            value = state.artifact_heads.get(
                f"delivery/target-evidence/G4/{target_id}", ""
            )
            status = "pending" if required else "deferred"
            sha256 = ""
            if value and required:
                payload = self._resolve_kind(value, "target-render-evidence")[
                    "payload"
                ]
                sha256 = str(payload.get("pptx_sha256") or "")
                current = (
                    payload.get("stage") == "G4"
                    and payload.get("presentation_build_ref") == build_ref
                    and sha256 == build.get("pptx_sha256")
                    and payload.get("target_id") == target_id
                )
                if not current:
                    status = "stale"
                elif payload.get("overall_result") == "passed":
                    status = "passed"
                else:
                    status = "failed"
            target_rows.append(
                {"target_id": target_id, "status": status, "pptx_sha256": sha256}
            )
            if required:
                target_statuses.append(status)
        target_gate = (
            "passed"
            if target_statuses and set(target_statuses) == {"passed"}
            else "failed"
            if any(status in {"failed", "stale"} for status in target_statuses)
            else "pending"
        )
        quality_gates = {
            "semantic": slide_gate("semantic_result"),
            "aesthetic": slide_gate("aesthetic_result"),
            "engineering": slide_gate("engineering_result"),
            "target_render": target_gate,
        }
        receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
        chat_send = {"status": "pending", "message_ref": "", "sent_at": ""}
        if receipt_ref:
            receipt = self._resolve_kind(
                receipt_ref, "chat-delivery-receipt"
            )["payload"]
            current_receipt = (
                receipt.get("build_ref") == build_ref
                and receipt.get("package_ref")
                == state.artifact_heads.get("delivery/package", "")
                and receipt.get("pptx_sha256") == build.get("pptx_sha256")
            )
            chat_send = {
                "status": (
                    str(receipt.get("send_status") or "pending")
                    if current_receipt
                    else "stale"
                ),
                "message_ref": str(receipt.get("message_ref") or ""),
                "sent_at": str(receipt.get("sent_at") or ""),
            }
        blocker: str | None = None
        if not build_ref:
            blocker = "presentation-build-missing"
        elif completed != len(slide_ids):
            blocker = "slide-qa-incomplete-or-failed"
        else:
            deck_ref = state.artifact_heads.get("delivery/qa/deck", "")
            deck = (
                self._resolve_kind(deck_ref, "deck-qa")["payload"]
                if deck_ref
                else {}
            )
            if (
                not deck_ref
                or deck.get("build_ref") != build_ref
                or deck.get("pptx_sha256") != build.get("pptx_sha256")
                or deck.get("overall_result") != "passed"
            ):
                blocker = "deck-qa-incomplete-or-failed"
            elif target_gate != "passed":
                blocker = "required-target-evidence-incomplete-or-failed"
            elif state.gate_status.get("G4") == "delivery-ready" and not state.artifact_heads.get(
                "delivery/package"
            ):
                blocker = "delivery-package-missing"
            elif chat_send["status"] == "failed":
                blocker = "chat-send-failed"
        return {
            "phase": state.gate_status.get("G4", "locked"),
            "slides": {"completed": completed, "total": len(slide_ids)},
            "quality_gates": quality_gates,
            "highest_blocker": blocker,
            "targets": target_rows,
            "hash_identity": str(build.get("pptx_sha256") or ""),
            "chat_send": chat_send,
            "release_target_policy": {
                "policy_ref": policy_ref,
                "policy_id": policy.policy_id,
                "required_target_ids": list(policy.required_target_ids),
                "deferred_target_ids": list(policy.deferred_target_ids),
                "compatibility_claim_scope": list(
                    policy.compatibility_claim_scope
                ),
            },
        }

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
