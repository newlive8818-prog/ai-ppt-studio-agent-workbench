"""Version-bound, one-time confirmation contexts for user Gates."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import base64
import time
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.content_batch_planning_service import (
    ContentBatchPlanningService,
)
from ai_ppt_studio.application.scoped_confirmation import (
    ScopedConfirmationPolicy,
)
from ai_ppt_studio.domains.content.review_contracts import (
    validate_content_review_batch,
    validate_persisted_page_decision,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ContentWorkflowError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)


USER_GATES = frozenset({"G0", "G3", "G4"})
HOST_CONFIRMATION_SECRET_ENV = "AI_PPT_HOST_CONFIRMATION_SECRET"
HOST_ASSERTION_VERSION = "v1"
HOST_ASSERTION_MAX_LIFETIME_SECONDS = 300
HOST_ASSERTION_CLOCK_SKEW_SECONDS = 30


class GateConfirmationPolicy:
    """Create and validate one current user-checkpoint challenge."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.confirmations = ScopedConfirmationPolicy(kernel)

    def context(self, gate: str) -> dict[str, Any]:
        identity = gate.strip()
        if identity not in USER_GATES:
            raise GateBlockedError(identity or "Gate", ("user-gate-invalid",))
        state = self.kernel.load()
        legacy_g0_upgrade = identity == "G0" and self._legacy_g0_upgrade_ref(state)
        if (
            state.gate_status.get(identity) != "user-reviewable"
            and not legacy_g0_upgrade
        ):
            raise GateBlockedError(identity, ("gate-not-user-reviewable",))

        if identity == "G0":
            if legacy_g0_upgrade:
                source_version = state.artifact_heads.get(
                    "content/blueprint", ""
                )
                acceptance_ref = state.artifact_heads.get(
                    "content/acceptance", ""
                )
                evidence_refs = [acceptance_ref, source_version]
                source = self._resolve(
                    source_version, "content-blueprint", identity
                )
                if source.get("acceptance_ref") != acceptance_ref:
                    raise GateBlockedError(
                        identity, ("content-lineage-stale",)
                    )
                evidence_refs.append(legacy_g0_upgrade)
                review_summary = (
                    f"完整内容蓝图，共 {len(source.get('slides') or [])} 页，"
                    "当前内容与原确认版本一致，本次仅升级历史确认凭据。"
                )
            else:
                (
                    source_version,
                    evidence_refs,
                    review_summary,
                ) = self._g0_evidence()
        elif identity == "G3":
            source_version = state.artifact_heads.get("visual/contract", "")
            if not source_version:
                raise GateBlockedError(identity, ("current-visual-contract-missing",))
            source = self._resolve(source_version, "visual-contract", identity)
            evidence_refs = self._current_g3_evidence(state, source_version, source)
            review_summary = (
                f"完整视觉合同，共 {len(source.get('slide_contracts') or [])} 页，"
                "G1/G2 内部质量门已通过。"
            )
        else:
            source_version = state.artifact_heads.get("delivery/package", "")
            build_ref = state.artifact_heads.get("delivery/build", "")
            receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
            policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
            evidence_refs = [build_ref, source_version, receipt_ref, policy_ref]
            package = self._resolve(source_version, "delivery-package", identity)
            build = self._resolve(build_ref, "presentation-build", identity)
            if (
                package.get("build_ref") != build_ref
                or package.get("pptx_sha256") != build.get("pptx_sha256")
                or package.get("release_target_policy_ref") != policy_ref
            ):
                raise GateBlockedError(identity, ("delivery-lineage-stale",))
            review_summary = (
                f"最终 PPTX 已发送，共 {len(build.get('slide_ids') or [])} 页，"
                f"文件哈希 {build.get('pptx_sha256', '')}。"
            )

        if not source_version or any(not value for value in evidence_refs):
            raise GateBlockedError(identity, ("current-gate-evidence-missing",))
        scoped = self.confirmations.context(
            scope_kind="gate",
            scope_id=identity,
            source_version=source_version,
            evidence_refs=evidence_refs,
        )
        return {
            **scoped,
            "gate": identity,
            "review_summary": review_summary,
            "confirmation_mode": (
                "legacy-credential-upgrade" if legacy_g0_upgrade else "confirm-gate"
            ),
            "legacy_confirmation_ref": legacy_g0_upgrade or "",
        }

    def confirmation_payload(
        self,
        *,
        gate: str,
        source_version: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
        user_action_ref: str = "",
        user_message_ref: str = "",
    ) -> tuple[dict[str, Any], tuple[object, ...]]:
        current = self.context(gate)
        if user_action_ref.strip() or user_message_ref.strip():
            raise GateBlockedError(
                gate, ("untrusted-raw-confirmation-identity",)
            )
        try:
            scoped, consumptions = self.confirmations.confirmation_payload(
                current=current,
                source_version=source_version,
                challenge_id=challenge_id,
                challenge_revision=challenge_revision,
                host_confirmation_assertion=host_confirmation_assertion,
            )
        except ContentWorkflowError as error:
            raise GateBlockedError(
                gate, ("trusted-host-assertion-invalid",)
            ) from error
        identity = str(
            scoped.get("user_action_ref")
            or scoped.get("user_message_ref")
            or ""
        )
        if identity and self._was_consumed(identity):
            raise GateBlockedError(
                gate, ("confirmation-identity-already-consumed",)
            )
        payload = {
            **scoped,
            "gate": gate,
            "confirmation_mode": current["confirmation_mode"],
        }
        if current["confirmation_mode"] == "legacy-credential-upgrade":
            payload["supersedes_confirmation_ref"] = current[
                "legacy_confirmation_ref"
            ]
        return payload, consumptions

    def _g0_evidence(self) -> tuple[str, list[str], str]:
        state = self.kernel.load()
        source_ref = state.artifact_heads.get("content/blueprint", "")
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        batch_ref = state.artifact_heads.get("content/review-batch", "")
        plan_ref = state.artifact_heads.get(
            "content/batch-revision-plan", ""
        )
        confirmation_ref = state.artifact_heads.get(
            "content/batch-plan-confirmation", ""
        )
        try:
            blueprint = self._resolve(
                source_ref, "content-blueprint", "G0"
            )
            acceptance = self._resolve(
                acceptance_ref, "content-acceptance", "G0"
            )
            batch = validate_content_review_batch(
                self._resolve(batch_ref, "content-review-batch", "G0")
            )
            plan = self._resolve(
                plan_ref, "content-batch-revision-plan", "G0"
            )
            confirmation = ContentBatchPlanningService(
                self.kernel
            ).require_current_plan_confirmation(confirmation_ref)
            batch_lineage_valid = self._batch_descends_from(
                batch_ref=batch_ref,
                batch=batch,
                submitted_ref=str(plan.get("review_batch_ref") or ""),
            )
            decisions = {
                ref: validate_persisted_page_decision(
                    self._resolve(ref, "content-page-decision", "G0")
                )
                for ref in batch["decision_refs"]
            }
            validate_content_review_batch(
                batch,
                authoritative_slides=blueprint["slides"],
                decisions_by_ref=decisions,
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            ContentWorkflowError,
            GateBlockedError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise GateBlockedError(
                "G0", ("content-review-batch-current-source-incomplete",)
            ) from error
        blockers: list[str] = []
        if blueprint.get("acceptance_ref") != acceptance_ref:
            blockers.append("content-lineage-stale")
        if acceptance.get("overall_result") != "passed":
            blockers.append("content-acceptance-failed")
        revision_fields = (
            "supersedes_blueprint_ref",
            "review_batch_ref",
            "batch_revision_plan_ref",
            "batch_plan_confirmation_ref",
        )
        if any(
            blueprint.get(field) != acceptance.get(field)
            for field in revision_fields
        ):
            blockers.append("content-lineage-stale")
        if (
            batch.get("status") != "applied"
            or batch.get("source_version") != source_ref
            or batch.get("expected_slide_count")
            != len(blueprint["slides"])
            or not batch_lineage_valid
            or plan.get("review_batch_id") != batch.get("review_batch_id")
            or plan.get("source_version") != source_ref
            or confirmation.get("revision_plan_ref") != plan_ref
        ):
            blockers.append("content-review-batch-current-source-incomplete")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        no_change = not bool(plan.get("requires_blueprint_revision"))
        summary = (
            f"完整内容蓝图，共 {len(blueprint['slides'])} 页；"
            "当前版本全篇审核已完成，"
            + ("确认无需修改。" if no_change else "修改方案已完整执行。")
        )
        return (
            source_ref,
            [acceptance_ref, source_ref, batch_ref, plan_ref, confirmation_ref],
            summary,
        )

    def _batch_descends_from(
        self,
        *,
        batch_ref: str,
        batch: dict[str, Any],
        submitted_ref: str,
    ) -> bool:
        statuses = (
            "applied",
            "plan-confirmed",
            "plan-proposed",
            "submitted",
        )
        immutable_fields = (
            "review_batch_id",
            "project_id",
            "review_type",
            "source_version",
            "decision_set_ref",
            "page_snapshot_refs",
            "decision_refs",
            "expected_slide_count",
            "counts",
            "scope_kind",
            "scope_id",
            "evidence_refs",
        )
        current_ref = batch_ref
        current = batch
        terminal = {field: batch.get(field) for field in immutable_fields}
        seen: set[str] = set()
        for status in statuses:
            if (
                current_ref in seen
                or current.get("status") != status
                or any(
                    current.get(field) != terminal[field]
                    for field in immutable_fields
                )
            ):
                return False
            seen.add(current_ref)
            if status == "submitted":
                return current_ref == submitted_ref
            predecessor_ref = str(current.get("supersedes_ref") or "")
            if not predecessor_ref:
                return False
            current_ref = predecessor_ref
            current = validate_content_review_batch(
                self._resolve(current_ref, "content-review-batch", "G0")
            )
        return False

    def _legacy_g0_upgrade_ref(self, state: Any) -> str:
        if state.gate_status.get("G0") != "passed":
            return ""
        confirmation_ref = state.artifact_heads.get("gate/G0/confirmation", "")
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        if not confirmation_ref or not acceptance_ref or not blueprint_ref:
            return ""
        try:
            confirmation = self._resolve(
                confirmation_ref, "g0-confirmation", "G0"
            )
        except GateBlockedError:
            return ""
        if (
            confirmation.get("gate") != "G0"
            or confirmation.get("content_acceptance_ref") != acceptance_ref
            or confirmation.get("content_blueprint_ref") != blueprint_ref
            or not str(confirmation.get("user_message_ref") or "").startswith(
                "chat://message/"
            )
            or confirmation.get("source_version")
            or confirmation.get("host_assertion_sha256")
            or confirmation.get("confirmation_identity_type")
        ):
            return ""
        return confirmation_ref

    def _verify_assertion(
        self, token: str, current: dict[str, Any]
    ) -> tuple[str, str, str]:
        encoded = token.strip()
        secret = os.environ.get(HOST_CONFIRMATION_SECRET_ENV, "")
        if not encoded or len(secret.encode("utf-8")) < 32:
            raise GateBlockedError(
                str(current.get("gate") or "Gate"),
                ("trusted-host-assertion-required",),
            )
        try:
            version, payload_segment, signature_segment = encoded.split(".", 2)
            if version != HOST_ASSERTION_VERSION:
                raise ValueError("unsupported assertion version")
            expected_signature = hmac.new(
                secret.encode("utf-8"),
                payload_segment.encode("ascii"),
                hashlib.sha256,
            ).digest()
            supplied_signature = self._decode_base64url(signature_segment)
            if not hmac.compare_digest(expected_signature, supplied_signature):
                raise ValueError("invalid assertion signature")
            payload = json.loads(
                self._decode_base64url(payload_segment).decode("utf-8")
            )
            if not isinstance(payload, dict):
                raise ValueError("assertion payload must be an object")
            now = int(time.time())
            issued_at = int(payload["issued_at"])
            expires_at = int(payload["expires_at"])
            if (
                issued_at > now + HOST_ASSERTION_CLOCK_SKEW_SECONDS
                or expires_at <= now
                or expires_at <= issued_at
                or expires_at - issued_at > HOST_ASSERTION_MAX_LIFETIME_SECONDS
            ):
                raise ValueError("assertion is expired or outside its lifetime")
            expected_context = {
                "project_id": current["project_id"],
                "project_root": current["project_root"],
                "gate": current["gate"],
                "source_version": current["source_version"],
                "evidence_refs": current["evidence_refs"],
                "challenge_id": current["challenge_id"],
                "challenge_revision": current["challenge_revision"],
            }
            for key, value in expected_context.items():
                if payload.get(key) != value:
                    raise ValueError(f"assertion context mismatch: {key}")
            identity_type = str(payload.get("identity_type") or "")
            identity_ref = str(payload.get("identity_ref") or "").strip()
            nonce = str(payload.get("nonce") or "").strip()
            if identity_type not in {"host-action", "verified-message"}:
                raise ValueError("assertion identity type is invalid")
            if not identity_ref or not nonce:
                raise ValueError("assertion identity or nonce is missing")
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            raise GateBlockedError(
                str(current.get("gate") or "Gate"),
                ("trusted-host-assertion-invalid",),
            ) from None
        return identity_type, identity_ref, hashlib.sha256(encoded.encode()).hexdigest()

    @staticmethod
    def _decode_base64url(value: str) -> bytes:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
        if canonical != value:
            raise ValueError("non-canonical base64url encoding")
        return decoded

    def _current_g3_evidence(
        self,
        state: Any,
        source_version: str,
        source: dict[str, Any],
    ) -> list[str]:
        fixed_fields = (
            ("content_blueprint_ref", "content/blueprint"),
            ("visual_convergence_ref", "visual/convergence"),
            ("deck_design_system_ref", "visual/design-system"),
            ("visual_contract_set_ref", "visual/contracts"),
            ("anchor_slide_set_ref", "visual/anchors"),
            ("g2_reviewed_lineage_ref", "gate/G2/lineage"),
            ("release_target_policy_ref", "release/target-policy"),
        )
        fixed_refs: list[str] = []
        blockers: list[str] = []
        for field, slot in fixed_fields:
            current_ref = state.artifact_heads.get(slot, "")
            frozen_ref = str(source.get(field) or "")
            if not current_ref or frozen_ref != current_ref:
                blockers.append(f"visual-contract-lineage-stale:{field}")
            fixed_refs.append(frozen_ref)
        review_slots = (
            "visual/review/G1/aesthetic",
            "visual/review/G2/aesthetic",
            "visual/review/G2/engineering",
        )
        current_reviews = [state.artifact_heads.get(slot, "") for slot in review_slots]
        frozen_reviews = list(source.get("internal_review_refs") or [])
        if frozen_reviews != current_reviews or any(not value for value in current_reviews):
            blockers.append("visual-contract-lineage-stale:internal_review_refs")
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        if source.get("release_target_policy_ref") != policy_ref:
            blockers.append("TARGET_POLICY_STALE")
        if source.get("required_target_ids") != list(policy.required_target_ids):
            blockers.append("TARGET_POLICY_STALE")
        if source.get("deferred_target_ids") != list(policy.deferred_target_ids):
            blockers.append("TARGET_POLICY_STALE")
        current_targets = [
            state.artifact_heads.get(f"visual/target-evidence/G2/{target_id}", "")
            for target_id in policy.required_target_ids
        ]
        frozen_targets = list(source.get("target_evidence_refs") or [])
        if frozen_targets != current_targets or any(not value for value in current_targets):
            blockers.append("visual-contract-lineage-stale:target_evidence_refs")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return [source_version, *fixed_refs, *frozen_reviews, *frozen_targets]

    def _was_consumed(self, identity: str) -> bool:
        state = self.kernel.load()
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if key in state.consumed_user_confirmations:
            return True
        for slot, reference_value in state.artifact_heads.items():
            if slot != "mission/confirmation" and not (
                slot.startswith("gate/") and slot.endswith("/confirmation")
            ):
                continue
            try:
                payload = self.kernel.artifacts.resolve(
                    ArtifactReference.parse(reference_value)
                )["payload"]
            except (ArtifactReferenceError, KeyError, TypeError, ValueError):
                continue
            if identity in {
                str(payload.get("user_action_ref") or ""),
                str(payload.get("user_message_ref") or ""),
            }:
                return True
        return False

    def _resolve(self, value: str, kind: str, gate: str) -> dict[str, Any]:
        try:
            reference = ArtifactReference.parse(value)
            if reference.kind != kind:
                raise ValueError("wrong kind")
            return self.kernel.artifacts.resolve(reference)["payload"]
        except (ArtifactReferenceError, KeyError, TypeError, ValueError):
            raise GateBlockedError(gate, (f"current-{kind}-missing",)) from None
