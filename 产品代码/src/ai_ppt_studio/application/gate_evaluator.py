"""The only application component that calculates v1.6 Gate transitions."""

from __future__ import annotations

from copy import deepcopy
import json
import subprocess
from typing import Any

from ai_ppt_studio.domains.visual.contracts import (
    assess_visual_contract_set_v23,
    validate_anchor_render_assets,
    validate_anchor_slide_set,
    validate_visual_review,
)
from ai_ppt_studio.domains.visual.compilation import (
    validate_visual_compilation_plan,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    G2_DIAGNOSTIC_CODES,
    GateBlockedError,
)
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
from ai_ppt_studio.application.review_session_service import (
    authoritative_target_publication_revision,
)
from ai_ppt_studio.application.content_review._shared import (
    validate_content_acceptance,
)
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.domains.content.page_decisions import validate_page_decision
from ai_ppt_studio.domains.content.review_batches import (
    validate_content_review_batch,
)
from ai_ppt_studio.domains.content.contracts import (
    validate_content_hard_gate_record,
    validate_reading_deck_blueprint,
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
        confirmation_payload: dict[str, Any] | None = None,
    ) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G0") != "user-reviewable":
            blockers.append("content-not-user-reviewable")
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        review_batch_ref = state.artifact_heads.get("content/review-batch", "")
        decision_refs: tuple[str, ...] = ()
        if not acceptance_ref or not blueprint_ref or not review_batch_ref:
            blockers.append("content-evidence-missing")
        else:
            decision_refs = self._validate_g0_review_evidence(
                acceptance_ref,
                blueprint_ref,
                review_batch_ref,
                required_gate_status="user-reviewable",
            )
        if confirmation_payload is None:
            confirmation_payload = self._resolve(
                confirmation_ref, "g0-confirmation"
            )["payload"]
        else:
            expected_confirmation_ref = str(
                self.kernel.artifacts.reference_for(
                    "g0-confirmation", confirmation_payload
                )
            )
            if confirmation_ref != expected_confirmation_ref:
                blockers.append("confirmation-reference-mismatch")
        source_version = ""
        if blueprint_ref:
            source_version = str(
                self._resolve(blueprint_ref, "reading-deck-blueprint")[
                    "payload"
                ].get("source_version")
                or ""
            )
        expected_evidence = [
            acceptance_ref,
            blueprint_ref,
            review_batch_ref,
            *decision_refs,
        ]
        if (
            confirmation_payload.get("gate") != "G0"
            or confirmation_payload.get("project_id") != state.project_id
            or confirmation_payload.get("scope_kind") != "gate"
            or confirmation_payload.get("scope_id") != "G0"
            or confirmation_payload.get("source_version") != source_version
            or confirmation_payload.get("evidence_refs") != expected_evidence
            or confirmation_payload.get("challenge_revision") != state.revision
            or confirmation_payload.get("content_acceptance_ref") != acceptance_ref
            or confirmation_payload.get("reading_blueprint_ref") != blueprint_ref
            or confirmation_payload.get("content_review_batch_ref")
            != review_batch_ref
            or not self._trusted_confirmation_identity(confirmation_payload)
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G0": "passed", "G1": "open"},
            (
                acceptance_ref,
                blueprint_ref,
                review_batch_ref,
                *decision_refs,
                confirmation_ref,
            ),
        )

    def current_g0_confirmation_evidence(
        self,
    ) -> tuple[str, tuple[str, ...]]:
        state = self.kernel.load()
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        review_batch_ref = state.artifact_heads.get("content/review-batch", "")
        if not acceptance_ref or not blueprint_ref or not review_batch_ref:
            raise GateBlockedError("G0", ("content-evidence-missing",))
        decision_refs = self._validate_g0_review_evidence(
            acceptance_ref,
            blueprint_ref,
            review_batch_ref,
            required_gate_status="user-reviewable",
        )
        source_version = str(
            self._resolve(blueprint_ref, "reading-deck-blueprint")[
                "payload"
            ].get("source_version")
            or ""
        )
        if not source_version:
            raise GateBlockedError("G0", ("content-source-version-missing",))
        return source_version, (
            acceptance_ref,
            blueprint_ref,
            review_batch_ref,
            *decision_refs,
        )

    @staticmethod
    def _trusted_confirmation_identity(payload: dict[str, Any]) -> bool:
        identity_type = str(payload.get("confirmation_identity_type") or "")
        action_ref = str(payload.get("user_action_ref") or "").strip()
        message_ref = str(payload.get("user_message_ref") or "").strip()
        assertion_digest = str(payload.get("host_assertion_sha256") or "")
        challenge_id = str(payload.get("challenge_id") or "")
        if identity_type == "host-action":
            identity_valid = bool(action_ref) and not message_ref
        elif identity_type == "verified-message":
            identity_valid = bool(message_ref) and not action_ref
        else:
            identity_valid = False
        return (
            identity_valid
            and len(assertion_digest) == 64
            and all(character in "0123456789abcdef" for character in assertion_digest)
            and len(challenge_id) == 64
            and all(character in "0123456789abcdef" for character in challenge_id)
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
        try:
            acceptance = validate_content_acceptance(
                self._resolve(acceptance_ref, "content-acceptance")["payload"]
            )
            blueprint = validate_reading_deck_blueprint(
                self._resolve(blueprint_ref, "reading-deck-blueprint")[
                    "payload"
                ]
            )
            batch = validate_content_review_batch(
                self._resolve(review_batch_ref, "content-review-batch")[
                    "payload"
                ]
            )
        except ContractValidationError as error:
            raise GateBlockedError(
                "G0", ("content-review-evidence-malformed",)
            ) from error
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
            acceptance.get("reading_blueprint_ref") != blueprint_ref
            or acceptance.get("source_version") != blueprint.get("source_version")
            or acceptance.get("evidence_gate_ref")
            != state.artifact_heads.get("content/gate/evidence")
            or acceptance.get("presales_reading_gate_ref")
            != state.artifact_heads.get("content/gate/presales-reading")
        ):
            blockers.append("content-acceptance-lineage-mismatch")
        blueprint_hash = ArtifactReference.parse(blueprint_ref).sha256
        gate_specs = (
            (
                "evidence",
                state.artifact_heads.get("content/gate/evidence", ""),
            ),
            (
                "presales-reading",
                state.artifact_heads.get(
                    "content/gate/presales-reading", ""
                ),
            ),
        )
        for gate_type, gate_ref in gate_specs:
            try:
                gate = validate_content_hard_gate_record(
                    self._resolve(
                        gate_ref, "content-hard-gate-record"
                    )["payload"]
                )
            except (ContractValidationError, GateBlockedError):
                blockers.append(f"content-{gate_type}-gate-not-current")
                continue
            if (
                gate["gate_type"] != gate_type
                or gate["overall_result"] != "passed"
                or gate["input_source_version"]
                != blueprint["source_version"]
                or gate["input_hash"] != blueprint_hash
            ):
                blockers.append(f"content-{gate_type}-gate-not-current")
        if (
            batch.get("project_id") != state.project_id
            or batch.get("status") != "submitted"
            or not batch.get("immutable_after_submit")
            or batch.get("reading_blueprint_ref") != blueprint_ref
            or batch.get("source_version") != blueprint.get("source_version")
        ):
            blockers.append("content-review-batch-not-current")
        session_ref = state.review_session_ref("content-full-deck")
        if not session_ref:
            blockers.append("content-review-session-not-current")
            session = {}
        else:
            session = validate_review_session(
                self._resolve(session_ref, "review-session")["payload"],
                trusted_receipts=True,
            )
            authoritative_revision = authoritative_target_publication_revision(
                self.kernel, state, "content-full-deck", blueprint_ref
            )
            if (
                session.get("project_id") != state.project_id
                or session.get("review_type") != "content-full-deck"
                or session.get("review_session_id")
                != batch.get("review_session_id")
                or session.get("target_artifact_ref") != blueprint_ref
                or session.get("source_version")
                != blueprint.get("source_version")
                or session.get("revision") != authoritative_revision
                or session.get("status") != "submitted"
            ):
                blockers.append("content-review-session-not-current")
        slide_ids = [
            slide.get("slide_id")
            for slide in blueprint.get("slides") or []
        ]
        decision_refs = batch.get("decision_refs") or []
        expected_counts = {
            "approved": len(slide_ids),
            "modify": 0,
            "evidence": 0,
            "merge-or-delete": 0,
        }
        if (
            batch.get("slide_ids") != slide_ids
            or len(decision_refs) != len(slide_ids)
            or batch.get("counts") != expected_counts
        ):
            blockers.append("content-review-decisions-incomplete")
        else:
            for slide, decision_ref in zip(
                blueprint.get("slides") or [], decision_refs, strict=True
            ):
                slide_id = slide.get("slide_id")
                if (
                    state.artifact_heads.get(
                        f"content/review/decision/{slide_id}"
                    )
                    != decision_ref
                ):
                    blockers.append(
                        f"content-page-decision-not-current:{slide_id}"
                    )
                decision = validate_page_decision(
                    self._resolve(decision_ref, "content-page-decision")[
                        "payload"
                    ]
                )
                if (
                    decision.get("project_id") != state.project_id
                    or decision.get("review_session_id")
                    != session.get("review_session_id")
                    or decision.get("slide_id") != slide_id
                    or decision.get("slide_order") != slide.get("order")
                    or decision.get("slide_title_snapshot")
                    != slide.get("neutral_title")
                    or decision.get("decision") != "approved"
                    or decision.get("reading_blueprint_ref") != blueprint_ref
                    or decision.get("source_version") != blueprint.get("source_version")
                    or decision.get("status") != "completed"
                ):
                    blockers.append(f"content-page-not-approved:{slide_id}")
                lineage_identity = {
                    "project_id": state.project_id,
                    "review_session_id": session.get("review_session_id"),
                    "source_version": blueprint.get("source_version"),
                    "reading_blueprint_ref": blueprint_ref,
                    "slide_id": slide_id,
                    "slide_order": slide.get("order"),
                    "slide_title_snapshot": slide.get("neutral_title"),
                    "status": "completed",
                }
                if not self._content_decision_lineage_matches(
                    decision_ref, lineage_identity
                ):
                    blockers.append(
                        f"content-page-decision-lineage-stale:{slide_id}"
                    )
        if blockers:
            raise GateBlockedError("G0", tuple(sorted(set(blockers))))
        return tuple(decision_refs)

    def _content_decision_lineage_matches(
        self,
        decision_ref: str,
        expected_identity: dict[str, Any],
    ) -> bool:
        seen: set[str] = set()
        while decision_ref:
            if decision_ref in seen:
                return False
            seen.add(decision_ref)
            try:
                decision = validate_page_decision(
                    self._resolve(
                        decision_ref, "content-page-decision"
                    )["payload"]
                )
            except (ContractValidationError, KeyError, TypeError, ValueError):
                return False
            if any(
                decision.get(field) != value
                for field, value in expected_identity.items()
            ):
                return False
            decision_ref = decision["supersedes_decision_ref"]
        return bool(seen)

    def image_led_upstream_replaced(self) -> GateMutation:
        """Replacing a design dependency reopens engineering gates, never G0."""
        state = self.kernel.load()
        refs = tuple(value for slot, value in state.artifact_heads.items()
                     if slot in {'gate/G0/confirmation', 'visual/image-led/selection'})
        return issue_gate_mutation({'G1': 'open' if state.gate_status.get('G0') == 'passed' else 'locked',
                                    'G2': 'locked', 'G3': 'locked', 'G4': 'locked'}, refs)

    def _visual_plan_publication_is_atomic(
        self,
        *,
        source_revision: int,
        contract_ref: str,
        plan_ref: str,
    ) -> bool:
        if source_revision <= 0:
            return False
        event_path = self.kernel.events_root / f"r{source_revision:08d}.json"
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        heads = event.get("artifact_heads")
        return bool(
            event.get("event_type") == "visual.contract-set-registered"
            and event.get("revision") == source_revision
            and isinstance(heads, dict)
            and heads.get("visual/contracts") == contract_ref
            and heads.get("visual/compilation-plan") == plan_ref
        )

    def _current_visual_compilation_plan(
        self, blockers: list[str]
    ) -> tuple[str, dict[str, Any] | None]:
        """Resolve and verify the exact current v2.3 plan lineage."""

        state = self.kernel.load()
        plan_ref = state.artifact_heads.get("visual/compilation-plan", "")
        if not plan_ref:
            blockers.append("visual-compilation-plan-missing-or-stale")
            return "", None
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            try:
                from ai_ppt_studio.application.image_led_native import ImageLedNativeService
                _contract, plan = ImageLedNativeService(self.kernel).current_contract_plan()
                return plan_ref, plan
            except Exception:
                blockers.append('image-led-compilation-plan-missing-or-stale')
                return '', None
        before = len(blockers)
        try:
            blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
            brief_ref = state.artifact_heads.get("visual/brief", "")
            design_ref = state.artifact_heads.get("visual/design-system", "")
            contracts_ref = state.artifact_heads.get("visual/contracts", "")
            policy_ref, _policy = ReleaseTargetPolicyService(self.kernel).current()
            if not all((blueprint_ref, brief_ref, design_ref, contracts_ref)):
                raise ValueError("visual upstream head is missing")
            plan_payload = self._resolve(
                plan_ref, "visual-compilation-plan"
            )["payload"]
            contracts = self._resolve(
                contracts_ref, "visual-contract-set"
            )["payload"]
            if assess_visual_contract_set_v23(contracts) != "v23-assessed":
                blockers.append("visual-contract-set-legacy-unassessed-by-v23")
            plan = validate_visual_compilation_plan(
                deepcopy(plan_payload), contract_set=deepcopy(contracts)
            )
            brief = self._resolve(brief_ref, "visual-brief")["payload"]
            design = self._resolve(design_ref, "deck-design-system")["payload"]
            blueprint = self._resolve(
                blueprint_ref, "reading-deck-blueprint"
            )["payload"]
            expected = {
                "reading_blueprint_ref": blueprint_ref,
                "visual_brief_ref": brief_ref,
                "deck_design_system_ref": design_ref,
                "visual_contract_set_ref": contracts_ref,
                "release_target_policy_ref": policy_ref,
            }
            if any(plan.get(field) != value for field, value in expected.items()):
                raise ValueError("visual compilation plan upstream refs are stale")
            expected_source_version = str(
                contracts.get("source_version")
                or brief.get("source_version")
                or design.get("source_version")
                or blueprint.get("source_version")
                or ""
            )
            if plan.get("source_version") != expected_source_version:
                raise ValueError("visual compilation plan source version is stale")
            if not self._visual_plan_publication_is_atomic(
                source_revision=int(plan["source_revision"]),
                contract_ref=contracts_ref,
                plan_ref=plan_ref,
            ):
                raise ValueError("visual compilation plan publication is not atomic")
        except Exception:
            if len(blockers) == before:
                blockers.append("visual-compilation-plan-missing-or-stale")
            return "", None
        if len(blockers) != before:
            return "", None
        return plan_ref, plan

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
        compilation_plan_ref, _plan = self._current_visual_compilation_plan(blockers)
        refs["compilation-plan"] = compilation_plan_ref
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
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            from ai_ppt_studio.application.image_led_native import ImageLedNativeService
            ImageLedNativeService(self.kernel).validate_formal_review(refs['review'])
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
        state = self.kernel.load()
        return issue_gate_mutation(
            {"G2": "passed"},
            (
                state.artifact_heads.get("content/reading-blueprint", ""),
                state.artifact_heads.get("visual/brief", ""),
                state.artifact_heads.get("visual/convergence", ""),
                state.artifact_heads.get("visual/review/G1/aesthetic", ""),
                refs["design-system"],
                refs["contracts"],
                refs["compilation-plan"],
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
        diagnostics: list[dict[str, str]] = []

        def diagnostic(stage: str, slot: str, error: Exception) -> dict[str, str]:
            explicit = getattr(error, "cause_code", None)
            defaults = {
                "resolve": "reference-resolution-failed",
                "canonicalize": "canonical-anchor-derivation-failed",
                "legacy-render-assets-fallback": "legacy-render-assets-fallback-failed",
            }
            if explicit in G2_DIAGNOSTIC_CODES:
                cause_code = explicit
            elif isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
                cause_code = "deadline-exceeded"
            else:
                cause_code = defaults.get(stage, "contract-validation")
            return {
                "stage": stage,
                "slot": slot,
                "cause_class": type(error).__name__,
                "cause_code": cause_code,
            }
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
        compilation_plan_ref, _plan = self._current_visual_compilation_plan(blockers)
        refs["compilation-plan"] = compilation_plan_ref
        target_refs = {
            target_id: state.artifact_heads.get(
                f"visual/target-evidence/G2/{target_id}", ""
            )
            for target_id in policy.required_target_ids
        }
        lineage_stale = False
        if state.gate_status.get("G2") == "passed":
            current_lineage = (
                state.artifact_heads.get("content/reading-blueprint", ""),
                state.artifact_heads.get("visual/brief", ""),
                state.artifact_heads.get("visual/convergence", ""),
                state.artifact_heads.get("visual/review/G1/aesthetic", ""),
                refs["design-system"],
                refs["contracts"],
                refs["compilation-plan"],
                refs["anchors"],
                refs["aesthetic-review"],
                refs["engineering-review"],
                policy_ref,
                *(target_refs[target_id] for target_id in policy.required_target_ids),
            )
            lineage_stale = current_lineage != self._latest_passed_gate_evidence(
                "G2", state.revision
            )
        blockers.extend(
            f"missing:{name}"
            for name, value in refs.items()
            if not value and name != "compilation-plan"
        )
        blockers.extend(
            f"missing-target:{target_id}"
            for target_id, value in target_refs.items()
            if not value
        )
        required_ref_missing = any(
            not value for name, value in refs.items() if name != "compilation-plan"
        ) or any(not value for value in target_refs.values())
        if required_ref_missing:
            if lineage_stale:
                blockers.append("G2-reviewed-visual-lineage-stale")
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
            except (
                ArtifactReferenceError,
                ContractValidationError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ) as error:
                blockers.append(blocker)
                diagnostics.append(
                    diagnostic("resolve", blocker, error)
                )
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
            raise GateBlockedError(
                "G2",
                tuple(sorted(set(blockers))),
                tuple(diagnostics),
            )

        if design_system.get("production_route") != "strict-B":
            blockers.append("design-system-route-not-strict-B")
        if contracts.get("deck_design_system_ref") != refs["design-system"]:
            blockers.append("contract-design-system-mismatch")
        if anchors.get("visual_contract_set_ref") != refs["contracts"]:
            blockers.append("anchor-contract-mismatch")
        if anchors.get("visual_compilation_plan_ref") != refs["compilation-plan"]:
            blockers.append("anchor-compilation-plan-mismatch")
        try:
            from ai_ppt_studio.application.image_led_service import is_image_led
            if is_image_led(self.kernel):
                from ai_ppt_studio.application.image_led_native import ImageLedNativeService
                canonical_anchors = ImageLedNativeService(self.kernel).current_anchors()
            else:
                canonical_anchors = validate_anchor_slide_set(deepcopy(anchors), deepcopy(contracts))
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
        ) as error:
            diagnostics.append(
                diagnostic("canonicalize", "visual/anchors", error)
            )
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
            except ContractValidationError as fallback_error:
                blockers.append("anchor-render-assets-invalid")
                diagnostics.append(
                    diagnostic(
                        "legacy-render-assets-fallback",
                        "visual/anchors",
                        fallback_error,
                    )
                )
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
                if is_image_led(self.kernel):
                    ImageLedNativeService(self.kernel).validate_formal_review(refs[f'{reviewer_kind}-review'])
            except (
                ArtifactReferenceError,
                ContractValidationError,
                KeyError,
                OSError,
                TimeoutError,
                TypeError,
                ValueError,
            ) as error:
                diagnostics.append(
                    diagnostic(
                        "review",
                        f"visual/review/G2/{reviewer_kind}",
                        error,
                    )
                )
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
        if lineage_stale:
            blockers.append("G2-reviewed-visual-lineage-stale")
        if blockers:
            raise GateBlockedError(
                "G2",
                tuple(sorted(set(blockers))),
                tuple(diagnostics),
            )
        matrix = validate_required_targets(evidence, policy.required_target_ids)
        if matrix.pptx_sha256 != anchors.get("pptx_sha256"):
            raise GateBlockedError("G2", ("anchor-pptx-hash-mismatch",))
        return {
            "policy_ref": policy_ref,
            "compilation_plan_ref": compilation_plan_ref,
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

    def _latest_passed_gate_evidence(
        self, gate: str, current_revision: int
    ) -> tuple[str, ...]:
        for revision in range(current_revision, 0, -1):
            event_path = self.kernel.events_root / f"r{revision:08d}.json"
            try:
                event = json.loads(event_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise GateBlockedError(
                    gate,
                    ("gate-evidence-history-unavailable",),
                ) from error
            if dict(event.get("gate_updates") or {}).get(gate) == "passed":
                values = event.get("gate_evidence_refs")
                if not isinstance(values, list) or any(
                    not isinstance(value, str) or not value for value in values
                ):
                    raise GateBlockedError(
                        gate,
                        ("gate-evidence-history-invalid",),
                    )
                return tuple(values)
        raise GateBlockedError(gate, ("gate-evidence-history-missing",))

    def visual_user_reviewable(self, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G2") != "passed":
            blockers.append("G2-not-passed")
        if state.gate_status.get("G3") != "locked":
            blockers.append("G3-not-locked")
        contract = self._resolve(visual_contract_ref, "visual-contract")["payload"]
        compilation_plan_ref, _plan = self._current_visual_compilation_plan(blockers)
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
            "visual_compilation_plan_ref": compilation_plan_ref,
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

    def current_g3_confirmation_evidence(
        self,
    ) -> tuple[str, tuple[str, ...]]:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        try:
            self.validate_current_g2_evidence()
        except GateBlockedError as error:
            blockers.extend(error.missing_evidence)
        if state.gate_status.get("G3") != "user-reviewable":
            blockers.append("visual-contract-not-user-reviewable")
        visual_contract_ref = state.artifact_heads.get("visual/contract", "")
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
            "visual_compilation_plan_ref": state.artifact_heads.get(
                "visual/compilation-plan", ""
            ),
            "anchor_slide_set_ref": state.artifact_heads.get(
                "visual/anchors", ""
            ),
        }
        if not visual_contract_ref:
            blockers.append("visual-contract-missing")
        else:
            contract = self._resolve(visual_contract_ref, "visual-contract")[
                "payload"
            ]
            if contract.get("status") != "user-reviewable":
                blockers.append("visual-contract-status-invalid")
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
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return (
            visual_contract_ref,
            (visual_contract_ref, policy_ref, *expected.values()),
        )

    def confirm_g3(
        self,
        *,
        confirmation_ref: str,
        confirmation_payload: dict[str, Any] | None = None,
    ) -> GateMutation:
        state = self.kernel.load()
        visual_contract_ref, evidence_refs = (
            self.current_g3_confirmation_evidence()
        )
        policy_ref = evidence_refs[1]
        blockers: list[str] = []
        if confirmation_payload is None:
            confirmation_payload = self._resolve(
                confirmation_ref, "g3-confirmation"
            )["payload"]
        else:
            expected_confirmation_ref = str(
                self.kernel.artifacts.reference_for(
                    "g3-confirmation", confirmation_payload
                )
            )
            if confirmation_ref != expected_confirmation_ref:
                blockers.append("confirmation-reference-mismatch")
        if (
            confirmation_payload.get("gate") != "G3"
            or confirmation_payload.get("project_id") != state.project_id
            or confirmation_payload.get("scope_kind") != "gate"
            or confirmation_payload.get("scope_id") != "G3"
            or confirmation_payload.get("source_version")
            != visual_contract_ref
            or confirmation_payload.get("evidence_refs")
            != list(evidence_refs)
            or confirmation_payload.get("challenge_revision") != state.revision
            or confirmation_payload.get("visual_contract_ref")
            != visual_contract_ref
            or confirmation_payload.get("release_target_policy_ref")
            != policy_ref
            or not self._trusted_confirmation_identity(confirmation_payload)
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G3": "passed", "G4": "open"},
            (*evidence_refs, confirmation_ref),
        )

    def reopen_g3(self, visual_contract_ref: str) -> GateMutation:
        state = self.kernel.load()
        blockers: list[str] = []
        if state.gate_status.get("G3") not in {"user-reviewable", "passed"}:
            blockers.append("G3-not-reviewable-or-passed")
        if state.artifact_heads.get("visual/contract") != visual_contract_ref:
            blockers.append("current-visual-contract-missing-or-stale")
        else:
            self._resolve(visual_contract_ref, "visual-contract")
        if blockers:
            raise GateBlockedError("G3", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G1": "open", "G2": "locked", "G3": "locked", "G4": "locked"},
            (visual_contract_ref,),
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

    def current_g4_confirmation_evidence(
        self,
    ) -> tuple[str, tuple[str, ...]]:
        state = self.kernel.load()
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        blockers: list[str] = []
        if state.gate_status.get("G4") != "user-reviewable":
            blockers.append("delivery-not-user-reviewable")
        build_ref = state.artifact_heads.get("delivery/build", "")
        package_ref = state.artifact_heads.get("delivery/package", "")
        receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
        target_refs = tuple(
            state.artifact_heads.get(
                f"delivery/target-evidence/G4/{target_id}", ""
            )
            for target_id in policy.required_target_ids
        )
        if not build_ref or not package_ref or not receipt_ref:
            blockers.append("current-delivery-evidence-missing")
        if not target_refs or "" in target_refs:
            blockers.append("current-delivery-target-evidence-missing")
        if (
            build_ref
            and package_ref
            and receipt_ref
            and target_refs
            and "" not in target_refs
        ):
            build = self._resolve(build_ref, "presentation-build")["payload"]
            package = self._resolve(package_ref, "delivery-package")["payload"]
            receipt = self._resolve(receipt_ref, "chat-delivery-receipt")["payload"]
            if (
                package.get("build_ref") != build_ref
                or package.get("pptx_ref") != build.get("source_pptx_ref")
                or package.get("pptx_sha256") != build.get("pptx_sha256")
                or package.get("release_target_policy_ref") != policy_ref
                or package.get("target_evidence_refs") != list(target_refs)
                or receipt.get("send_status") != "sent"
                or receipt.get("build_ref") != build_ref
                or receipt.get("package_ref") != package_ref
                or receipt.get("pptx_ref") != build.get("source_pptx_ref")
                or receipt.get("pptx_sha256") != build.get("pptx_sha256")
            ):
                blockers.append("delivery-evidence-stale")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return (
            package_ref,
            (build_ref, package_ref, receipt_ref, policy_ref, *target_refs),
        )

    def confirm_g4(
        self,
        *,
        confirmation_ref: str,
        confirmation_payload: dict[str, Any] | None = None,
    ) -> GateMutation:
        state = self.kernel.load()
        package_ref, evidence_refs = self.current_g4_confirmation_evidence()
        build_ref, _package_ref, receipt_ref, policy_ref, *_targets = evidence_refs
        receipt = self._resolve(receipt_ref, "chat-delivery-receipt")["payload"]
        blockers: list[str] = []
        if confirmation_payload is None:
            confirmation_payload = self._resolve(
                confirmation_ref, "g4-confirmation"
            )["payload"]
        else:
            expected_confirmation_ref = str(
                self.kernel.artifacts.reference_for(
                    "g4-confirmation", confirmation_payload
                )
            )
            if confirmation_ref != expected_confirmation_ref:
                blockers.append("confirmation-reference-mismatch")
        identity_ref = str(
            confirmation_payload.get("user_action_ref")
            or confirmation_payload.get("user_message_ref")
            or ""
        )
        if receipt.get("message_ref") == identity_ref:
            blockers.append("acceptance-message-must-differ-from-send-message")
        if (
            confirmation_payload.get("gate") != "G4"
            or confirmation_payload.get("project_id") != state.project_id
            or confirmation_payload.get("scope_kind") != "gate"
            or confirmation_payload.get("scope_id") != "G4"
            or confirmation_payload.get("source_version") != package_ref
            or confirmation_payload.get("evidence_refs")
            != list(evidence_refs)
            or confirmation_payload.get("challenge_revision") != state.revision
            or confirmation_payload.get("build_ref") != build_ref
            or confirmation_payload.get("package_ref") != package_ref
            or confirmation_payload.get("receipt_ref") != receipt_ref
            or confirmation_payload.get("release_target_policy_ref")
            != policy_ref
            or not self._trusted_confirmation_identity(confirmation_payload)
        ):
            blockers.append("confirmation-evidence-mismatch")
        if blockers:
            raise GateBlockedError("G4", tuple(sorted(set(blockers))))
        return issue_gate_mutation(
            {"G4": "passed"},
            (*evidence_refs, confirmation_ref),
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
