"""Revision-safe same-type/global experience application service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_ppt_studio.application.review_commands import (
    fingerprint,
    replay_ref,
    stable_id,
)
from ai_ppt_studio.domains.experience.contracts import (
    validate_experience_application,
    validate_experience_item,
    validate_experience_outcome,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ExperienceValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ExperienceService:
    """Own the only writable reusable-experience path in v2.2."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def absorb_same_type(
        self,
        *,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ):
        normalized = validate_experience_item(payload)
        if normalized["layer"] != "same-type":
            raise ExperienceValidationError(
                "Realtime absorption can only create same-type experience"
            )
        slot = self._item_slot(
            normalized["domain"], "same-type", normalized["experience_id"]
        )
        values = {"payload": normalized}
        command_fingerprint = fingerprint("absorb-same-type-experience", values)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, self._payload(reference, "experience-item"), state

        state = self.kernel.load()
        current_ref = state.artifact_heads.get(slot, "")
        if current_ref:
            current = self._payload(current_ref, "experience-item")
            if (
                current["domain"] != normalized["domain"]
                or current["layer"] != "same-type"
            ):
                raise ExperienceValidationError(
                    "Experience identity cannot change domain or layer"
                )
            normalized = validate_experience_item(
                {
                    **normalized,
                    "version": current["version"] + 1,
                    "previous_version": current["version"],
                    "previous_version_ref": current_ref,
                    "application_count": current["application_count"],
                }
            )
        elif (
            normalized["version"] != 1
            or normalized["previous_version"] is not None
            or normalized["previous_version_ref"] is not None
        ):
            raise ExperienceValidationError(
                "New same-type experience must start at version 1"
            )

        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.same-type-absorbed",
            artifact_updates={slot: ("experience-item", normalized)},
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], normalized, committed

    def recommend(
        self,
        *,
        domain: str,
        type_signature: str,
        applicability: dict[str, Any],
        top_n: int = 8,
    ) -> list[dict[str, Any]]:
        if domain not in {"content", "visual"}:
            raise ExperienceValidationError("Experience domain must be content or visual")
        if not isinstance(type_signature, str) or not type_signature.strip():
            raise ExperienceValidationError("type_signature is required")
        if not isinstance(applicability, dict):
            raise ExperienceValidationError("applicability must be an object")
        if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
            raise ExperienceValidationError("top_n must be a positive integer")
        requested_conditions = applicability.get("conditions", [])
        if not isinstance(requested_conditions, list) or any(
            not isinstance(value, str) or not value for value in requested_conditions
        ):
            raise ExperienceValidationError(
                "applicability.conditions must be a text array"
            )

        state = self.kernel.load()
        prefix = f"experience/item/{domain}/"
        candidates: list[tuple[int, str, dict[str, Any]]] = []
        for slot, reference in sorted(state.artifact_heads.items()):
            if not slot.startswith(prefix):
                continue
            item = validate_experience_item(
                self._payload(reference, "experience-item")
            )
            if (
                item["status"] != "active"
                or type_signature in item["excluded_type_signatures"]
                or not set(item["applicability"]["conditions"]).issubset(
                    set(requested_conditions)
                )
            ):
                continue
            if item["layer"] == "same-type":
                if item["type_signature"] != type_signature:
                    continue
                rank = 0
                reason = "same-type-exact"
            else:
                rank = 1
                reason = "global-not-excluded"
            candidates.append(
                (
                    rank,
                    reference,
                    {
                        "experience_ref": reference,
                        "experience_id": item["experience_id"],
                        "experience_version": item["version"],
                        "layer": item["layer"],
                        "domain": item["domain"],
                        "result_type": item["result_type"],
                        "mechanism": item["mechanism"],
                        "match_reason": reason,
                        "applicability": deepcopy(item["applicability"]),
                    },
                )
            )

        recommendations: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _rank, _reference, result in sorted(
            candidates,
            key=lambda entry: (
                entry[0],
                -int(entry[2]["experience_version"]),
                str(entry[2]["experience_id"]),
            ),
        ):
            identity = str(result["experience_id"])
            if identity in seen:
                continue
            seen.add(identity)
            recommendations.append(result)
            if len(recommendations) == top_n:
                break
        return recommendations

    def record_application(
        self,
        *,
        command_id: str,
        expected_revision: int,
        experience_ref: str,
        target_project_id: str,
        target_type_signature: str,
        context: dict[str, Any],
        evidence_refs: list[str],
        applied_at: str,
        explicit_validation: bool = False,
    ):
        application_id = stable_id(
            "experience-application",
            command_id,
            experience_ref,
            target_project_id,
            target_type_signature,
        )
        slot = f"experience/application/{application_id}"
        values = {
            "experience_ref": experience_ref,
            "target_project_id": target_project_id,
            "target_type_signature": target_type_signature,
            "context": context,
            "evidence_refs": evidence_refs,
            "applied_at": applied_at,
            "explicit_validation": explicit_validation,
        }
        command_fingerprint = fingerprint("record-experience-application", values)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return (
                reference,
                self._payload(reference, "experience-application"),
                state,
            )

        item = self._require_current_item(experience_ref)
        if item["status"] != "active":
            raise ExperienceValidationError(
                "Only active experience can be applied"
            )
        if item["layer"] == "same-type" and (
            target_type_signature != item["type_signature"]
            and not explicit_validation
        ):
            raise ExperienceValidationError(
                "Same-type experience requires an exact type signature"
            )
        if target_type_signature in item["excluded_type_signatures"]:
            raise ExperienceValidationError(
                "Experience is excluded for the target type signature"
            )

        application = validate_experience_application(
            {
                "application_id": application_id,
                "experience_ref": experience_ref,
                "experience_id": item["experience_id"],
                "experience_version": item["version"],
                "domain": item["domain"],
                "experience_layer": item["layer"],
                "source_type_signature": item["type_signature"],
                "target_project_id": target_project_id,
                "target_type_signature": target_type_signature,
                "context": context,
                "evidence_refs": evidence_refs,
                "explicit_validation": explicit_validation,
                "status": "applied",
                "applied_at": applied_at,
            }
        )
        item_slot = self._item_slot(
            item["domain"], item["layer"], item["experience_id"]
        )
        next_item = self._next_item(
            item,
            experience_ref,
            updated_at=applied_at,
            application_count=item["application_count"] + 1,
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.application-recorded",
            artifact_updates={
                slot: ("experience-application", application),
                item_slot: ("experience-item", next_item),
            },
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], application, committed

    def evaluate_application(
        self,
        *,
        command_id: str,
        expected_revision: int,
        application_ref: str,
        outcome: str,
        user_outcome_ref: str,
        hard_gate_refs: list[str],
        evidence_refs: list[str],
        evaluated_at: str,
    ):
        application = self._require_current_application(application_ref)
        outcome_id = stable_id(
            "experience-outcome", application["application_id"]
        )
        slot = f"experience/outcome/{application['application_id']}"
        values = {
            "application_ref": application_ref,
            "outcome": outcome,
            "user_outcome_ref": user_outcome_ref,
            "hard_gate_refs": hard_gate_refs,
            "evidence_refs": evidence_refs,
            "evaluated_at": evaluated_at,
        }
        command_fingerprint = fingerprint("evaluate-experience-application", values)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, self._payload(reference, "experience-outcome"), state
        if self.kernel.load().artifact_heads.get(slot):
            raise ExperienceValidationError(
                "An experience application can only have one outcome"
            )

        item_ref, item = self.get_current(
            application["domain"],
            application["experience_layer"],
            application["experience_id"],
        )
        target_type = application["target_type_signature"]
        success = set(item["success_type_signatures"])
        failures = set(item["failure_type_signatures"])
        excluded = set(item["excluded_type_signatures"])
        counterexamples = list(item["counterexamples"])
        if outcome == "success":
            success.add(target_type)
            failures.discard(target_type)
        elif outcome == "failure":
            failures.add(target_type)
            excluded.add(target_type)
            counterexample = f"type-signature:{target_type}"
            if counterexample not in counterexamples:
                counterexamples.append(counterexample)

        result = validate_experience_outcome(
            {
                "outcome_id": outcome_id,
                "application_ref": application_ref,
                "application_id": application["application_id"],
                "experience_ref": application["experience_ref"],
                "experience_id": application["experience_id"],
                "experience_version": application["experience_version"],
                "domain": application["domain"],
                "experience_layer": application["experience_layer"],
                "target_project_id": application["target_project_id"],
                "target_type_signature": target_type,
                "outcome": outcome,
                "user_outcome_ref": user_outcome_ref,
                "hard_gate_refs": hard_gate_refs,
                "evidence_refs": evidence_refs,
                "evaluated_at": evaluated_at,
            }
        )
        next_item = self._next_item(
            item,
            item_ref,
            updated_at=evaluated_at,
            success_type_signatures=sorted(success),
            failure_type_signatures=sorted(failures),
            excluded_type_signatures=sorted(excluded),
            counterexamples=counterexamples,
        )
        item_slot = self._item_slot(
            item["domain"], item["layer"], item["experience_id"]
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.application-evaluated",
            artifact_updates={
                slot: ("experience-outcome", result),
                item_slot: ("experience-item", next_item),
            },
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], result, committed

    def promote_global(
        self,
        *,
        command_id: str,
        expected_revision: int,
        same_type_ref: str,
        user_global_directive_ref: str | None = None,
    ):
        item = self._require_current_item(same_type_ref)
        if item["layer"] != "same-type":
            raise ExperienceValidationError(
                "Only current same-type experience can become global"
            )
        directive = (
            user_global_directive_ref.strip()
            if isinstance(user_global_directive_ref, str)
            else ""
        )
        if not directive and len(set(item["success_type_signatures"])) < 2:
            raise ExperienceValidationError(
                "Global experience requires a user directive or two distinct successful types"
            )
        slot = self._item_slot(
            item["domain"], "global", item["experience_id"]
        )
        values = {
            "same_type_ref": same_type_ref,
            "user_global_directive_ref": directive or None,
        }
        command_fingerprint = fingerprint("promote-global-experience", values)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, self._payload(reference, "experience-item"), state

        existing_ref = self.kernel.load().artifact_heads.get(slot, "")
        existing = (
            self._payload(existing_ref, "experience-item")
            if existing_ref
            else None
        )
        version = int(existing["version"]) + 1 if existing else 1
        source_refs = list(dict.fromkeys([*item["source_refs"], same_type_ref]))
        global_item = validate_experience_item(
            {
                **deepcopy(item),
                "version": version,
                "layer": "global",
                "source_refs": source_refs,
                "previous_version": existing["version"] if existing else None,
                "previous_version_ref": existing_ref or None,
                "rollback_from_version": None,
                "user_global_directive_ref": directive or None,
            }
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.global-promoted",
            artifact_updates={slot: ("experience-item", global_item)},
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], global_item, committed

    def rollback(
        self,
        *,
        command_id: str,
        expected_revision: int,
        experience_ref: str,
        target_version_ref: str,
        reason: str,
        rolled_back_at: str,
    ):
        current = self._require_current_item(experience_ref)
        target = validate_experience_item(
            self._payload(target_version_ref, "experience-item")
        )
        if (
            target["experience_id"] != current["experience_id"]
            or target["domain"] != current["domain"]
            or target["layer"] != current["layer"]
            or target["version"] >= current["version"]
        ):
            raise ExperienceValidationError(
                "Rollback target must be an older version of the current item"
            )
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise ExperienceValidationError("Rollback requires a reason")
        slot = self._item_slot(
            current["domain"], current["layer"], current["experience_id"]
        )
        values = {
            "experience_ref": experience_ref,
            "target_version_ref": target_version_ref,
            "reason": clean_reason,
            "rolled_back_at": rolled_back_at,
        }
        command_fingerprint = fingerprint("rollback-experience", values)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            reference, state = replay
            return reference, self._payload(reference, "experience-item"), state
        rolled_back = validate_experience_item(
            {
                **deepcopy(target),
                "version": current["version"] + 1,
                "application_count": current["application_count"],
                "previous_version": current["version"],
                "previous_version_ref": experience_ref,
                "rollback_from_version": target["version"],
                "updated_at": rolled_back_at,
            }
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.version-rolled-back",
            artifact_updates={slot: ("experience-item", rolled_back)},
            command_fingerprint=command_fingerprint,
        )
        return committed.artifact_heads[slot], rolled_back, committed

    def get_current(
        self, domain: str, layer: str, experience_id: str
    ) -> tuple[str, dict[str, Any]]:
        slot = self._item_slot(domain, layer, experience_id)
        reference = self.kernel.load().artifact_heads.get(slot, "")
        if not reference:
            raise ArtifactReferenceError(
                f"Current experience item does not exist: {slot}"
            )
        return reference, validate_experience_item(
            self._payload(reference, "experience-item")
        )

    def experience_projection(self) -> dict[str, Any]:
        state = self.kernel.load()
        items = {"content": {"same-type": [], "global": []}, "visual": {"same-type": [], "global": []}}
        applications: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        for slot, reference in sorted(state.artifact_heads.items()):
            if slot.startswith("experience/item/"):
                item = validate_experience_item(
                    self._payload(reference, "experience-item")
                )
                items[item["domain"]][item["layer"]].append(
                    {
                        "experience_ref": reference,
                        "experience_id": item["experience_id"],
                        "version": item["version"],
                        "result_type": item["result_type"],
                        "type_signature": item["type_signature"],
                        "status": item["status"],
                        "application_count": item["application_count"],
                    }
                )
            elif slot.startswith("experience/application/"):
                application = validate_experience_application(
                    self._payload(reference, "experience-application")
                )
                applications.append(
                    {
                        "application_ref": reference,
                        "application_id": application["application_id"],
                        "experience_ref": application["experience_ref"],
                        "target_project_id": application["target_project_id"],
                        "target_type_signature": application["target_type_signature"],
                    }
                )
            elif slot.startswith("experience/outcome/"):
                result = validate_experience_outcome(
                    self._payload(reference, "experience-outcome")
                )
                outcomes.append(
                    {
                        "outcome_ref": reference,
                        "application_id": result["application_id"],
                        "outcome": result["outcome"],
                        "target_type_signature": result["target_type_signature"],
                    }
                )
        return {
            "layers": ["same-type", "global"],
            "domains": ["content", "visual"],
            "items": items,
            "applications": applications,
            "application_outcomes": outcomes,
        }

    def commit_public_artifact(
        self,
        command_id: str,
        expected_revision: int,
        *,
        payload: dict[str, Any],
    ) -> str:
        """Keep the legacy generic entry read-compatible but not writable."""

        if payload.get("artifact_type") != "experience-item":
            raise ContractValidationError(
                "Generic legacy experience writes are retired in v2.2"
            )
        reference, _item, _state = self.absorb_same_type(
            command_id=command_id,
            expected_revision=expected_revision,
            payload={key: value for key, value in payload.items() if key != "artifact_type"},
        )
        return reference

    def _require_current_item(self, reference: str) -> dict[str, Any]:
        item = validate_experience_item(
            self._payload(reference, "experience-item")
        )
        slot = self._item_slot(
            item["domain"], item["layer"], item["experience_id"]
        )
        if self.kernel.load().artifact_heads.get(slot) != reference:
            raise ArtifactReferenceError(
                "Experience operation requires the current item version"
            )
        return item

    def _require_current_application(self, reference: str) -> dict[str, Any]:
        application = validate_experience_application(
            self._payload(reference, "experience-application")
        )
        slot = f"experience/application/{application['application_id']}"
        if self.kernel.load().artifact_heads.get(slot) != reference:
            raise ArtifactReferenceError(
                "Experience outcome requires the current application"
            )
        return application

    def _payload(self, reference: str, kind: str) -> dict[str, Any]:
        try:
            parsed = ArtifactReference.parse(reference)
            if parsed.kind != kind:
                raise ArtifactReferenceError(
                    f"Expected artifact kind {kind}, got {parsed.kind}"
                )
            payload = self.kernel.artifacts.resolve(parsed).get("payload")
        except Exception as error:
            if isinstance(error, ArtifactReferenceError):
                raise
            raise ArtifactReferenceError(
                f"Cannot resolve {kind}: {reference}"
            ) from error
        if not isinstance(payload, dict):
            raise ArtifactReferenceError(f"{kind} payload must be an object")
        return dict(payload)

    @staticmethod
    def _next_item(
        item: dict[str, Any],
        current_ref: str,
        *,
        updated_at: str,
        **changes: Any,
    ) -> dict[str, Any]:
        return validate_experience_item(
            {
                **deepcopy(item),
                **changes,
                "version": item["version"] + 1,
                "previous_version": item["version"],
                "previous_version_ref": current_ref,
                "rollback_from_version": None,
                "updated_at": updated_at,
            }
        )

    @staticmethod
    def _item_slot(domain: str, layer: str, experience_id: str) -> str:
        if domain not in {"content", "visual"}:
            raise ExperienceValidationError("Experience domain must be content or visual")
        if layer not in {"same-type", "global"}:
            raise ExperienceValidationError(
                "Experience layer must be same-type or global"
            )
        if not isinstance(experience_id, str) or not experience_id:
            raise ExperienceValidationError("experience_id is required")
        return f"experience/item/{domain}/{layer}/{experience_id}"


__all__ = ["ExperienceService"]
