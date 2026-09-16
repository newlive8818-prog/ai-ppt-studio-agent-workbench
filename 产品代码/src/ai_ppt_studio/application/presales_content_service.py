"""Authoritative v2.2 evidence-first content object writer."""

from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any

from ai_ppt_studio.application.gate_evaluator import GateEvaluator
from ai_ppt_studio.application.material_finding_service import MaterialFindingService
from ai_ppt_studio.application.review_commands import (
    fingerprint,
    replay_ref,
    replay_state,
)
from ai_ppt_studio.application.scoped_confirmation import ScopedConfirmationPolicy
from ai_ppt_studio.domains.content.contracts import (
    validate_customer_decision_context,
    validate_presales_evidence_book,
    validate_problem_solution_fit_map,
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ContentWorkflowError,
    GateBlockedError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class PresalesContentService:
    """Write the four current content objects in exact upstream order."""

    _CONTENT_OBJECT_SLOTS = {
        "content/evidence-book",
        "content/decision-context",
        "content/problem-solution-fit",
        "content/reading-blueprint",
    }
    _CONTENT_CHAIN_SLOTS = (
        "content/evidence-book",
        "content/decision-context",
        "content/problem-solution-fit",
        "content/reading-blueprint",
    )
    _DOWNSTREAM_PREFIXES = (
        "agent/",
        "visual/",
        "delivery/",
        "review/session/",
        "chat-delivery/",
    )
    _DOWNSTREAM_SLOTS = {
        "gate/G0/confirmation",
        "gate/G3/confirmation",
        "gate/G4/confirmation",
        "project/completion",
        "experience/retrospective/job",
        "experience/project-retrospective",
        "experience/retrospective/error",
    }
    _FIT_NODE_FIELDS = (
        "situations",
        "symptoms",
        "causes_or_hypotheses",
        "impacts",
        "constraints",
        "unknowns",
        "derived_requirements",
        "solution_components",
        "boundaries",
        "alternatives",
        "validation_items",
    )
    _CONTENT_CHAIN_OBJECTS = MappingProxyType(
        {
            "evidence_book": (
                "content/evidence-book",
                "presales-evidence-book",
            ),
            "decision_context": (
                "content/decision-context",
                "customer-decision-context",
            ),
            "problem_solution_fit": (
                "content/problem-solution-fit",
                "problem-solution-fit-map",
            ),
            "reading_blueprint": (
                "content/reading-blueprint",
                "reading-deck-blueprint",
            ),
        }
    )

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def build_evidence_book(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_presales_evidence_book(payload)
        command_fingerprint = fingerprint(
            "build-presales-evidence-book", normalized
        )
        replay = replay_ref(
            self.kernel,
            command_id,
            command_fingerprint,
            "content/evidence-book",
        )
        if replay is not None:
            return replay[0]
        self._require_current(
            "mission/confirmation",
            "mission-confirmation",
            normalized["mission_confirmation_ref"],
        )
        material_ref = normalized["material_inventory_ref"]
        if normalized["material_mode"] == "proposal-led":
            if self.kernel.load().artifact_heads.get("materials"):
                raise ContractValidationError(
                    "proposal-led cannot be used while current materials exist"
                )
        else:
            self._require_current("materials", "material-inventory", material_ref)
        MaterialFindingService(self.kernel).validate_evidence(normalized)
        return self._commit(
            command_id,
            expected_revision,
            "content.evidence-book-built",
            "content/evidence-book",
            "presales-evidence-book",
            normalized,
            command_fingerprint,
        )

    def build_decision_context(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_customer_decision_context(payload)
        command_fingerprint = fingerprint(
            "build-customer-decision-context", normalized
        )
        replay = replay_ref(
            self.kernel,
            command_id,
            command_fingerprint,
            "content/decision-context",
        )
        if replay is not None:
            return replay[0]
        self._require_current(
            "content/evidence-book",
            "presales-evidence-book",
            normalized["evidence_book_ref"],
        )
        MaterialFindingService(self.kernel).validate_evidence(self._payload(normalized["evidence_book_ref"]))
        return self._commit(
            command_id,
            expected_revision,
            "content.decision-context-built",
            "content/decision-context",
            "customer-decision-context",
            normalized,
            command_fingerprint,
        )

    def build_problem_solution_fit(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_problem_solution_fit_map(payload)
        command_fingerprint = fingerprint(
            "build-problem-solution-fit", normalized
        )
        replay = replay_ref(
            self.kernel,
            command_id,
            command_fingerprint,
            "content/problem-solution-fit",
        )
        if replay is not None:
            return replay[0]
        self._require_current(
            "content/evidence-book",
            "presales-evidence-book",
            normalized["evidence_book_ref"],
        )
        self._require_current(
            "content/decision-context",
            "customer-decision-context",
            normalized["decision_context_ref"],
        )
        context = self._payload(normalized["decision_context_ref"])
        if context.get("evidence_book_ref") != normalized["evidence_book_ref"]:
            raise ContractValidationError(
                "Current content chain lineage is inconsistent"
            )
        evidence = self._payload(normalized["evidence_book_ref"])
        self._validate_fit_evidence(normalized, evidence=evidence)
        return self._commit(
            command_id,
            expected_revision,
            "content.problem-solution-fit-built",
            "content/problem-solution-fit",
            "problem-solution-fit-map",
            normalized,
            command_fingerprint,
        )

    def build_reading_deck_blueprint(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        normalized = validate_reading_deck_blueprint(payload)
        command_fingerprint = fingerprint(
            "build-reading-deck-blueprint", normalized
        )
        replay = replay_ref(
            self.kernel,
            command_id,
            command_fingerprint,
            "content/reading-blueprint",
        )
        if replay is not None:
            return replay[0]
        if normalized["project_id"] != self.kernel.project_id:
            raise ContractValidationError("ReadingDeckBlueprint project_id is stale")
        upstream = (
            ("content/evidence-book", "presales-evidence-book", "evidence_book_ref"),
            ("content/decision-context", "customer-decision-context", "decision_context_ref"),
            ("content/problem-solution-fit", "problem-solution-fit-map", "problem_solution_fit_ref"),
        )
        for slot, kind, field in upstream:
            self._require_current(slot, kind, normalized[field])
        evidence = self._payload(normalized["evidence_book_ref"])
        if evidence.get("material_mode") != normalized["material_mode"]:
            raise ContractValidationError("ReadingDeckBlueprint material_mode is stale")
        if evidence.get("source_version") != normalized["source_version"]:
            raise ContractValidationError("ReadingDeckBlueprint source_version is stale")
        context = self._payload(normalized["decision_context_ref"])
        fit = self._payload(normalized["problem_solution_fit_ref"])
        if (
            context.get("evidence_book_ref") != normalized["evidence_book_ref"]
            or fit.get("evidence_book_ref") != normalized["evidence_book_ref"]
            or fit.get("decision_context_ref")
            != normalized["decision_context_ref"]
        ):
            raise ContractValidationError(
                "Current content chain lineage is inconsistent"
            )
        self._validate_blueprint_evidence(
            normalized,
            evidence=evidence,
            fit=fit,
        )
        state = self.kernel.load()
        artifact_updates = {
            "content/reading-blueprint": ("reading-deck-blueprint", normalized)
        }
        change_set_ref = state.artifact_heads.get("content/change-set", "")
        if change_set_ref:
            from ai_ppt_studio.application.content_review.planning_service import (
                PLAN_APPLICATION_KIND,
                PLAN_APPLICATION_SLOT,
                ContentRevisionPlanningService,
            )

            new_blueprint_ref = str(
                self.kernel.artifacts.reference_for(
                    "reading-deck-blueprint", normalized
                )
            )
            application = ContentRevisionPlanningService(
                self.kernel
            ).prepare_application(
                state=state,
                change_set_ref=change_set_ref,
                new_reading_blueprint_ref=new_blueprint_ref,
                new_source_version=normalized["source_version"],
            )
            artifact_updates[PLAN_APPLICATION_SLOT] = (
                PLAN_APPLICATION_KIND,
                application,
            )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="content.reading-blueprint-built",
            artifact_updates=artifact_updates,
            artifact_removals=self._replacement_removals(
                state.artifact_heads,
                preserved_slots=tuple(artifact_updates),
            ),
            gate_mutation=GateEvaluator(self.kernel).content_source_replaced(
                tuple(
                    reference
                    for reference in dict.fromkeys(
                        (
                            *(state.artifact_heads[slot] for slot, _kind, _field in upstream),
                            state.artifact_heads.get("content/reading-blueprint", ""),
                        )
                    )
                    if reference
                )
            ),
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads["content/reading-blueprint"]

    def get_current_content_chain(self) -> dict[str, Any]:
        state = self.kernel.load()
        objects: dict[str, dict[str, Any] | None] = {}
        for key, (slot, kind) in self._CONTENT_CHAIN_OBJECTS.items():
            value = state.artifact_heads.get(slot, "")
            if not value:
                objects[key] = None
                continue
            reference = ArtifactReference.parse(value)
            if reference.kind != kind:
                raise ArtifactReferenceError(f"{slot} must reference {kind}")
            envelope = self.kernel.artifacts.resolve(reference)
            objects[key] = {
                "ref": value,
                "payload": copy.deepcopy(envelope["payload"]),
            }
        self._require_content_chain_lineage(objects)
        return {
            "project_id": self.kernel.project_id,
            "revision": state.revision,
            "objects": objects,
        }

    def repair_reading_deck_blueprint(
        self, command_id: str, expected_revision: int, payload: dict[str, Any]
    ) -> str:
        state = self.kernel.load()
        failed = False
        for slot in ("content/gate/evidence", "content/gate/presales-reading"):
            value = state.artifact_heads.get(slot, "")
            if value and self._payload(value).get("overall_result") == "failed":
                failed = True
        if not failed:
            raise ContractValidationError(
                "ReadingDeckBlueprint repair requires a current failed hard gate"
            )
        if not payload.get("repair_history"):
            raise ContractValidationError("Repair must preserve the applied requirements")
        return self.build_reading_deck_blueprint(
            command_id, expected_revision, payload
        )

    def open_g0_review(
        self, *, command_id: str, expected_revision: int
    ):
        command_fingerprint = fingerprint("open-g0-review", {})
        replay = replay_state(self.kernel, command_id, command_fingerprint)
        if replay is not None:
            return replay
        state = self.kernel.load()
        acceptance_ref = state.artifact_heads.get("content/acceptance", "")
        blueprint_ref = state.artifact_heads.get("content/reading-blueprint", "")
        review_batch_ref = state.artifact_heads.get("content/review-batch", "")
        if not acceptance_ref or not blueprint_ref or not review_batch_ref:
            raise GateBlockedError("G0", ("content-review-evidence-missing",))
        mutation = GateEvaluator(self.kernel).content_user_reviewable(
            acceptance_ref, blueprint_ref, review_batch_ref
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.user-reviewable",
            artifact_updates={},
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
        )

    def confirm_g0(
        self,
        *,
        command_id: str,
        expected_revision: int,
        source_version: str = "",
        challenge_id: str = "",
        challenge_revision: int = -1,
        host_confirmation_assertion: str = "",
        user_action_ref: str = "",
        user_message_ref: str = "",
    ):
        if user_action_ref.strip() or user_message_ref.strip():
            raise GateBlockedError("G0", ("untrusted-raw-confirmation-identity",))
        command_fingerprint = fingerprint(
            "confirm-g0",
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
                "G0", ("trusted-host-assertion-invalid",)
            ) from error
        state = self.kernel.load()
        confirmation = {
            **scoped,
            "gate": "G0",
            "content_acceptance_ref": state.artifact_heads.get(
                "content/acceptance", ""
            ),
            "reading_blueprint_ref": state.artifact_heads.get(
                "content/reading-blueprint", ""
            ),
            "content_review_batch_ref": state.artifact_heads.get(
                "content/review-batch", ""
            ),
        }
        confirmation_ref = str(
            self.kernel.artifacts.reference_for("g0-confirmation", confirmation)
        )
        mutation = GateEvaluator(self.kernel).confirm_g0(
            confirmation_ref=confirmation_ref,
            confirmation_payload=confirmation,
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="gate.G0.confirmed",
            artifact_updates={
                "gate/G0/confirmation": ("g0-confirmation", confirmation)
            },
            confirmation_consumptions=consumptions,
            gate_mutation=mutation,
            command_fingerprint=command_fingerprint,
        )

    def gate_confirmation_context(self) -> dict[str, Any]:
        source_version, evidence_refs = GateEvaluator(
            self.kernel
        ).current_g0_confirmation_evidence()
        return ScopedConfirmationPolicy(self.kernel).context(
            scope_kind="gate",
            scope_id="G0",
            source_version=source_version,
            evidence_refs=evidence_refs,
        )

    def _commit(
        self,
        command_id: str,
        expected_revision: int,
        event_type: str,
        slot: str,
        kind: str,
        payload: dict[str, Any],
        command_fingerprint: str,
    ) -> str:
        current = self.kernel.load()
        chain_index = self._CONTENT_CHAIN_SLOTS.index(slot)
        invalidated_content_slots = self._CONTENT_CHAIN_SLOTS[chain_index + 1 :]
        replacement_plan_active = bool(
            current.artifact_heads.get("content/change-set")
        )
        state = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=event_type,
            artifact_updates={slot: (kind, payload)},
            artifact_removals=tuple(
                downstream_slot
                for downstream_slot in invalidated_content_slots
                if downstream_slot in current.artifact_heads
                and not replacement_plan_active
            ),
            gate_mutation=GateEvaluator(self.kernel).content_source_replaced(
                tuple(
                    current.artifact_heads[current_slot]
                    for current_slot in self._CONTENT_CHAIN_SLOTS
                    if current_slot in current.artifact_heads
                )
            ),
            command_fingerprint=command_fingerprint,
        )
        return state.artifact_heads[slot]

    def _require_current(self, slot: str, kind: str, supplied_ref: str) -> None:
        current = self.kernel.load().artifact_heads.get(slot, "")
        if supplied_ref != current:
            raise ArtifactReferenceError(f"{slot} must bind the current {kind}")
        reference = ArtifactReference.parse(supplied_ref)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"{slot} must reference {kind}")
        self.kernel.artifacts.resolve(reference)

    @staticmethod
    def _declared_evidence(
        evidence: dict[str, Any],
    ) -> tuple[set[str], set[str]]:
        return (
            set(evidence.get("source_refs", [])),
            set(evidence.get("excluded_material_refs", [])),
        )

    @staticmethod
    def _require_declared_refs(
        refs: list[str],
        *,
        declared: set[str],
        excluded: set[str],
        field: str,
    ) -> None:
        invalid = [ref for ref in refs if ref not in declared or ref in excluded]
        if invalid:
            raise ContractValidationError(
                f"{field} must reference declared, non-excluded evidence"
            )

    def _validate_fit_evidence(
        self,
        payload: dict[str, Any],
        *,
        evidence: dict[str, Any],
    ) -> None:
        MaterialFindingService(self.kernel).validate_evidence(evidence)
        declared, excluded = self._declared_evidence(evidence)
        mode = evidence["material_mode"]
        rows = [
            row
            for field in self._FIT_NODE_FIELDS
            for row in payload[field]
        ]
        mappings = payload["mappings"]
        if mode == "proposal-led":
            if any(row["evidence_refs"] for row in rows + mappings):
                raise ContractValidationError(
                    "proposal-led fit cannot cite project evidence"
                )
            factual_identities = {"来源事实", "用户已确认", "材料推断"}
            if any(row["identity"] in factual_identities for row in rows + mappings):
                raise ContractValidationError(
                    "proposal-led fit cannot claim factual identities"
                )
            return
        for row in rows + mappings:
            self._require_declared_refs(
                row["evidence_refs"],
                declared=declared,
                excluded=excluded,
                field="ProblemSolutionFit evidence_refs",
            )
        if any(not mapping["evidence_refs"] for mapping in mappings):
            raise ContractValidationError(
                f"{mode} mappings require declared evidence"
            )

    def _validate_blueprint_evidence(
        self,
        payload: dict[str, Any],
        *,
        evidence: dict[str, Any],
        fit: dict[str, Any],
    ) -> None:
        MaterialFindingService(self.kernel).validate_evidence(evidence)
        declared, excluded = self._declared_evidence(evidence)
        mapping_ids = {mapping["mapping_id"] for mapping in fit["mappings"]}
        for slide in payload["slides"]:
            self._require_declared_refs(
                slide["customer_decision_item"]["evidence_refs"],
                declared=declared,
                excluded=excluded,
                field="ReadingDeckBlueprint customer decision item",
            )
            for binding in slide["evidence_bindings"]:
                self._require_declared_refs(
                    binding["source_refs"],
                    declared=declared,
                    excluded=excluded,
                    field="ReadingDeckBlueprint evidence binding",
                )
            for material_view in slide["material_views"]:
                self._require_declared_refs(
                    [material_view["source_ref"]],
                    declared=declared,
                    excluded=excluded,
                    field="ReadingDeckBlueprint material view",
                )
            if any(
                mapping_ref not in mapping_ids
                for mapping_ref in slide["solution_mapping_refs"]
            ):
                raise ContractValidationError(
                    "ReadingDeckBlueprint solution mapping refs must be current"
                )

    @staticmethod
    def _require_content_chain_lineage(
        objects: dict[str, dict[str, Any] | None],
    ) -> None:
        evidence = objects["evidence_book"]
        context = objects["decision_context"]
        fit = objects["problem_solution_fit"]
        blueprint = objects["reading_blueprint"]
        inconsistent = False
        if context is not None:
            inconsistent = evidence is None or (
                context["payload"].get("evidence_book_ref")
                != evidence["ref"]
            )
        if fit is not None:
            inconsistent = inconsistent or evidence is None or context is None
            if evidence is not None and context is not None:
                inconsistent = inconsistent or (
                    fit["payload"].get("evidence_book_ref") != evidence["ref"]
                    or fit["payload"].get("decision_context_ref")
                    != context["ref"]
                )
        if blueprint is not None:
            inconsistent = (
                inconsistent
                or evidence is None
                or context is None
                or fit is None
            )
            if evidence is not None and context is not None and fit is not None:
                inconsistent = inconsistent or (
                    blueprint["payload"].get("evidence_book_ref")
                    != evidence["ref"]
                    or blueprint["payload"].get("decision_context_ref")
                    != context["ref"]
                    or blueprint["payload"].get("problem_solution_fit_ref")
                    != fit["ref"]
                    or blueprint["payload"].get("source_version")
                    != evidence["payload"].get("source_version")
                    or blueprint["payload"].get("material_mode")
                    != evidence["payload"].get("material_mode")
                )
        if inconsistent:
            raise ContractValidationError(
                "Current content chain lineage is inconsistent"
            )

    @classmethod
    def _replacement_removals(
        cls,
        heads: dict[str, str],
        *,
        preserved_slots: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        preserved = set(preserved_slots)
        return tuple(
            slot
            for slot in heads
            if slot not in preserved
            and (
                (
                    slot.startswith("content/")
                    and slot not in cls._CONTENT_OBJECT_SLOTS
                )
                or slot in cls._DOWNSTREAM_SLOTS
                or slot.startswith(cls._DOWNSTREAM_PREFIXES)
            )
        )

    def _payload(self, reference: str) -> dict[str, Any]:
        return dict(
            self.kernel.artifacts.resolve(ArtifactReference.parse(reference))["payload"]
        )


__all__ = ["PresalesContentService"]
