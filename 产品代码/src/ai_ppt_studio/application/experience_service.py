"""Revision-safe schema 3 experience application service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.domains.experience.contracts import (
    validate_experience_intake,
    validate_experience_application,
    validate_experience_candidate,
    validate_experience_evaluation,
    validate_evolution_decision,
    validate_evolution_policy,
    validate_learning_result,
    validate_qualified_selection,
    validate_role_specific_slice,
    validate_stable_release_candidate,
)
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    ExperienceValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.role_registry import RoleRegistry


class ExperienceService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def register_intake(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_experience_intake(payload)
        if normalized["source_project_id"] != self.kernel.project_id:
            raise ExperienceValidationError(
                "ExperienceIntake source_project_id must match the current project"
            )
        for field in ("source_refs", "target_refs", "evidence_refs"):
            for value in normalized[field]:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        slot = f"experience/intake/{normalized['intake_id']}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.intake-registered",
            artifact_updates={slot: ("experience-intake", normalized)},
        )
        return committed.artifact_heads[slot]

    def register_learning_result(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_learning_result(payload)
        intake_ref = normalized["intake_ref"]
        intake_record = self._resolve_kind(intake_ref, "experience-intake")
        intake = intake_record["payload"]
        intake_slot = f"experience/intake/{intake.get('intake_id', '')}"
        if self.kernel.load().artifact_heads.get(intake_slot) != intake_ref:
            raise ArtifactReferenceError(
                "Learning result requires the current ExperienceIntake head"
            )
        if not set(normalized["source_refs"]).issubset(
            set(intake.get("source_refs") or [])
        ):
            raise ExperienceValidationError(
                "Learning result source_refs must come from its ExperienceIntake"
            )
        for value in normalized["source_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        for field in (
            "confidence_inputs",
            "evidence_refs",
            "negative_evidence_refs",
        ):
            for value in normalized.get(field, []):
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        slot = (
            f"experience/result/{normalized['result_type']}/"
            f"{normalized['result_id']}"
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.learning-result-registered",
            artifact_updates={
                slot: (normalized["result_type"], normalized)
            },
        )
        return committed.artifact_heads[slot]

    def register_qualified_selection(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_qualified_selection(payload)
        for value in normalized["option_refs"]:
            self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        for value in normalized["preference_signal_refs"]:
            record = self._resolve_kind(value, "preference-signal")["payload"]
            slot = (
                f"experience/result/preference-signal/{record.get('result_id', '')}"
            )
            if self.kernel.load().artifact_heads.get(slot) != value:
                raise ArtifactReferenceError(
                    "Preference selection requires current preference signal heads"
                )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.qualified-selection-registered",
            artifact_updates={
                "experience/qualified-selection": (
                    "qualified-experience-selection",
                    normalized,
                )
            },
        )
        return committed.artifact_heads["experience/qualified-selection"]

    def register_candidate(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        learning_ref = str(payload.get("learning_result_ref") or "")
        reference = ArtifactReference.parse(learning_ref)
        if reference.kind not in {
            "professional-mechanism-candidate",
            "anti-pattern-candidate",
        }:
            raise ArtifactReferenceError(
                "Experience candidates require a mechanism or anti-pattern result"
            )
        learning = self.kernel.artifacts.resolve(reference)["payload"]
        result_slot = (
            f"experience/result/{reference.kind}/{learning.get('result_id', '')}"
        )
        if self.kernel.load().artifact_heads.get(result_slot) != learning_ref:
            raise ArtifactReferenceError(
                "Experience candidates require a current learning result"
            )
        normalized = validate_experience_candidate(payload, learning)
        normalized["source_project_id"] = self.kernel.project_id
        slot = f"experience/candidate/{normalized['candidate_id']}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.candidate-registered",
            artifact_updates={slot: ("experience-candidate", normalized)},
        )
        return committed.artifact_heads[slot]

    def record_application(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        candidate_ref = str(payload.get("candidate_ref") or "")
        candidate = self._require_current_candidate(candidate_ref)
        if not candidate.get("enabled") or candidate.get("level") == "disabled":
            raise ExperienceValidationError(
                "Disabled experience cannot be applied"
            )
        normalized = validate_experience_application(payload, candidate)
        evidence = self._resolve_kind(
            normalized["runtime_evidence_ref"],
            "experience-application-evidence",
        )["payload"]
        if (
            evidence.get("project_id") != normalized["application_project_id"]
            or evidence.get("target_context") != normalized["target_context"]
            or evidence.get("evidence_identity")
            not in {"real-project-runtime", "simulated-contract-only"}
            or not isinstance(evidence.get("simulation"), bool)
        ):
            raise ExperienceValidationError(
                "Application runtime evidence does not match the application context"
            )
        normalized["simulation_evidence"] = bool(evidence["simulation"])
        slot = f"experience/application/{normalized['application_id']}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.application-recorded",
            artifact_updates={slot: ("experience-application", normalized)},
        )
        return committed.artifact_heads[slot]

    def evaluate_application(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        application_ref = str(payload.get("application_ref") or "")
        application_record = self._resolve_kind(
            application_ref, "experience-application"
        )
        application = application_record["payload"]
        slot = f"experience/application/{application.get('application_id', '')}"
        if self.kernel.load().artifact_heads.get(slot) != application_ref:
            raise ArtifactReferenceError(
                "Evaluation requires the current matched application"
            )
        normalized = validate_experience_evaluation(payload, application)
        for field in ("professional_review_refs", "evidence_refs"):
            for value in normalized[field]:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        eligible = (
            normalized["professional_result"] == "passed"
            and normalized["user_outcome"] == "accepted"
            and normalized["application_result"] == "success"
            and application.get("match_result") == "matched"
            and application.get("simulation_evidence") is False
        )
        normalized["promotion_eligibility"] = (
            "eligible" if eligible else "ineligible"
        )
        evaluation_slot = (
            f"experience/evaluation/{application['application_id']}"
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.application-evaluated",
            artifact_updates={
                evaluation_slot: (
                    "experience-application-evaluation",
                    normalized,
                )
            },
        )
        return committed.artifact_heads[evaluation_slot]

    def register_evolution_policy(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_evolution_policy(payload)
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.evolution-policy-registered",
            artifact_updates={
                "experience/evolution-policy": (
                    "experience-evolution-policy",
                    normalized,
                )
            },
        )
        return committed.artifact_heads["experience/evolution-policy"]

    def evolve_candidate(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        decision = validate_evolution_decision(payload)
        candidate_ref = decision["candidate_ref"]
        candidate = self._require_current_candidate(candidate_ref)
        policy = self._require_exact_head(
            decision["policy_ref"],
            "experience/evolution-policy",
            "experience-evolution-policy",
        )["payload"]
        evaluations = [
            self._require_current_evaluation(value)
            for value in decision["evaluation_refs"]
        ]
        action = decision["action"]
        if action == "promote":
            if candidate.get("level") != "candidate":
                raise ExperienceValidationError(
                    "Only a candidate experience can be promoted"
                )
            eligible = [
                item
                for item in evaluations
                if item.get("promotion_eligibility") == "eligible"
                and item.get("candidate_ref") == candidate_ref
            ]
            project_ids = {item["application_project_id"] for item in eligible}
            if len(project_ids) < policy["minimum_distinct_accepted_projects"]:
                raise ExperienceValidationError(
                    "Promotion lacks policy-required distinct accepted projects"
                )
            next_level = "personal"
        elif action == "demote":
            if candidate.get("level") != "personal":
                raise ExperienceValidationError(
                    "Only personal experience can be demoted"
                )
            failures = [
                item
                for item in evaluations
                if item.get("application_result") == "failure"
                and item.get("candidate_ref") == candidate_ref
            ]
            project_ids = {item["application_project_id"] for item in failures}
            if len(project_ids) < policy["minimum_failure_projects_for_demotion"]:
                raise ExperienceValidationError(
                    "Demotion lacks policy-required distinct failure projects"
                )
            next_level = "candidate"
        else:
            next_level = "disabled"
        evolved = {
            **candidate,
            "version": int(candidate["version"]) + 1,
            "level": next_level,
            "enabled": next_level != "disabled",
            "previous_version_ref": candidate_ref,
            "last_evolution_action": action,
            "evolution_policy_ref": decision["policy_ref"],
            "evolution_evaluation_refs": list(decision["evaluation_refs"]),
            "evolution_reason": decision["reason"],
        }
        decision_payload = {
            **decision,
            "from_level": candidate["level"],
            "to_level": next_level,
            "resulting_version": evolved["version"],
        }
        candidate_slot = f"experience/candidate/{candidate['candidate_id']}"
        decision_slot = (
            f"experience/evolution-decision/{decision['decision_id']}"
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=f"experience.candidate-{action}d",
            artifact_updates={
                candidate_slot: ("experience-candidate", evolved),
                decision_slot: (
                    "experience-evolution-decision",
                    decision_payload,
                ),
            },
        )
        return committed.artifact_heads[candidate_slot]

    def rollback_candidate(
        self,
        command_id: str,
        expected_revision: int,
        *,
        candidate_id: str,
        target_version_ref: str,
        reason: str,
    ) -> str:
        clean_reason = reason.strip()
        if not clean_reason:
            raise ExperienceValidationError("Rollback requires a reason")
        current_ref = self.kernel.load().artifact_heads.get(
            f"experience/candidate/{candidate_id}", ""
        )
        if not current_ref:
            raise ArtifactReferenceError("Current experience candidate is missing")
        current = self._resolve_kind(current_ref, "experience-candidate")["payload"]
        target = self._resolve_kind(
            target_version_ref, "experience-candidate"
        )["payload"]
        if (
            current.get("candidate_id") != candidate_id
            or target.get("candidate_id") != candidate_id
        ):
            raise ExperienceValidationError(
                "Rollback target must belong to the same candidate"
            )
        restored = {
            **target,
            "version": int(current["version"]) + 1,
            "previous_version_ref": current_ref,
            "restored_from": target_version_ref,
            "last_evolution_action": "rollback",
            "evolution_reason": clean_reason,
            "enabled": target.get("level") != "disabled",
        }
        slot = f"experience/candidate/{candidate_id}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.candidate-rolled-back",
            artifact_updates={slot: ("experience-candidate", restored)},
        )
        return committed.artifact_heads[slot]

    def propose_stable_release_candidate(
        self,
        command_id: str,
        expected_revision: int,
        payload: dict[str, Any],
    ) -> str:
        normalized = validate_stable_release_candidate(payload)
        for value in normalized["source_experience_refs"]:
            candidate = self._require_current_candidate(value)
            if candidate.get("level") != "personal" or not candidate.get("enabled"):
                raise ExperienceValidationError(
                    "Stable release candidates require current personal experience"
                )
        for field in (
            "positive_regression_refs",
            "negative_regression_refs",
            "cross_role_review_refs",
        ):
            for value in normalized[field]:
                self.kernel.artifacts.resolve(ArtifactReference.parse(value))
        slot = (
            "experience/stable-release-candidate/"
            + normalized["release_candidate_id"]
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.stable-release-candidate-proposed",
            artifact_updates={
                slot: ("stable-capability-release-candidate", normalized)
            },
        )
        return committed.artifact_heads[slot]

    def commit_public_artifact(
        self,
        command_id: str,
        expected_revision: int,
        *,
        payload: dict[str, Any],
    ) -> str:
        artifact_type = str(payload.get("artifact_type") or "")
        if artifact_type == "experience-intake":
            return self.register_intake(command_id, expected_revision, payload)
        if artifact_type in {
            "preference-signal",
            "professional-mechanism-candidate",
            "anti-pattern-candidate",
        }:
            return self.register_learning_result(
                command_id, expected_revision, payload
            )
        if artifact_type == "qualified-experience-selection":
            return self.register_qualified_selection(
                command_id, expected_revision, payload
            )
        if artifact_type == "experience-candidate":
            return self.register_candidate(command_id, expected_revision, payload)
        if artifact_type == "experience-application":
            return self.record_application(command_id, expected_revision, payload)
        if artifact_type == "experience-application-evaluation":
            return self.evaluate_application(command_id, expected_revision, payload)
        if artifact_type == "experience-evolution-policy":
            return self.register_evolution_policy(
                command_id, expected_revision, payload
            )
        if artifact_type == "experience-evolution-decision":
            return self.evolve_candidate(command_id, expected_revision, payload)
        if artifact_type == "stable-capability-release-candidate":
            return self.propose_stable_release_candidate(
                command_id, expected_revision, payload
            )
        if artifact_type == "role-specific-experience-slice":
            return self.compile_role_slice(
                command_id,
                expected_revision,
                role_id=str(payload.get("role_id") or ""),
                task_type=str(payload.get("task_type") or ""),
                target_context=dict(payload.get("target_context") or {}),
                experience_version_refs=list(
                    payload.get("experience_version_refs") or []
                ),
            )
        if artifact_type == "experience-rollback":
            return self.rollback_candidate(
                command_id,
                expected_revision,
                candidate_id=str(payload.get("candidate_id") or ""),
                target_version_ref=str(payload.get("target_version_ref") or ""),
                reason=str(payload.get("reason") or ""),
            )
        raise ContractValidationError(
            "experience payload needs a recognized schema 3 artifact_type"
        )

    def experience_projection(self) -> dict[str, Any]:
        state = self.kernel.load()
        intake_by_source: dict[str, int] = {}
        intake_by_status: dict[str, int] = {}
        result_by_type: dict[str, int] = {}
        result_by_status: dict[str, int] = {}
        candidates: list[dict[str, Any]] = []
        role_slices: list[dict[str, str]] = []
        outcomes: list[dict[str, str]] = []
        release_candidates: list[dict[str, str]] = []
        intake_total = 0
        result_total = 0
        for slot, value in sorted(state.artifact_heads.items()):
            if slot.startswith("experience/intake/"):
                payload = self._resolve_kind(value, "experience-intake")["payload"]
                intake_total += 1
                source_type = str(payload.get("source_type") or "unknown")
                learning_status = str(
                    payload.get("learning_status") or "unknown"
                )
                intake_by_source[source_type] = intake_by_source.get(source_type, 0) + 1
                intake_by_status[learning_status] = (
                    intake_by_status.get(learning_status, 0) + 1
                )
            elif slot.startswith("experience/result/"):
                reference = ArtifactReference.parse(value)
                payload = self.kernel.artifacts.resolve(reference)["payload"]
                result_total += 1
                result_type = str(payload.get("result_type") or reference.kind)
                status = str(payload.get("status") or "unknown")
                result_by_type[result_type] = result_by_type.get(result_type, 0) + 1
                result_by_status[status] = result_by_status.get(status, 0) + 1
            elif slot.startswith("experience/candidate/"):
                payload = self._resolve_kind(value, "experience-candidate")["payload"]
                candidates.append(
                    {
                        "candidate_id": str(payload.get("candidate_id") or ""),
                        "version": int(payload.get("version") or 0),
                        "level": str(payload.get("level") or ""),
                        "enabled": bool(payload.get("enabled")),
                        "experience_ref": value,
                    }
                )
            elif slot.startswith("experience/slice/"):
                payload = self._resolve_kind(
                    value, "role-specific-experience-slice"
                )["payload"]
                role_slices.append(
                    {
                        "target_role_id": str(payload.get("target_role_id") or ""),
                        "task_type": str(payload.get("task_type") or ""),
                        "slice_ref": value,
                    }
                )
            elif slot.startswith("experience/evaluation/"):
                payload = self._resolve_kind(
                    value, "experience-application-evaluation"
                )["payload"]
                outcomes.append(
                    {
                        "application_id": str(payload.get("application_id") or ""),
                        "application_project_id": str(
                            payload.get("application_project_id") or ""
                        ),
                        "application_result": str(
                            payload.get("application_result") or ""
                        ),
                        "user_outcome": str(payload.get("user_outcome") or ""),
                        "promotion_eligibility": str(
                            payload.get("promotion_eligibility") or ""
                        ),
                    }
                )
            elif slot.startswith("experience/stable-release-candidate/"):
                payload = self._resolve_kind(
                    value, "stable-capability-release-candidate"
                )["payload"]
                release_candidates.append(
                    {
                        "release_candidate_id": str(
                            payload.get("release_candidate_id") or ""
                        ),
                        "status": str(payload.get("status") or ""),
                        "release_candidate_ref": value,
                    }
                )
        return {
            "intake_counts": {
                "total": intake_total,
                "by_source_type": intake_by_source,
                "by_learning_status": intake_by_status,
            },
            "result_counts": {
                "total": result_total,
                "by_result_type": result_by_type,
                "by_status": result_by_status,
            },
            "candidates": candidates,
            "role_slices": role_slices,
            "application_outcomes": outcomes,
            "stable_release_candidates": release_candidates,
        }

    def compile_role_slice(
        self,
        command_id: str,
        expected_revision: int,
        *,
        role_id: str,
        task_type: str,
        target_context: dict[str, Any],
        experience_version_refs: list[str],
    ) -> str:
        role = RoleRegistry.default().get(role_id)
        if (
            not isinstance(experience_version_refs, list)
            or not experience_version_refs
            or any(
                not isinstance(value, str) or not value
                for value in experience_version_refs
            )
            or len(set(experience_version_refs)) != len(experience_version_refs)
        ):
            raise ExperienceValidationError(
                "experience_version_refs must be unique artifact references"
            )
        if not isinstance(target_context, dict):
            raise ExperienceValidationError("target_context must be an object")
        scene = str(target_context.get("scene") or "").strip()
        audience = str(target_context.get("audience") or "").strip()
        slide_task = str(target_context.get("slide_task") or "").strip()
        conditions = target_context.get("conditions")
        if (
            not scene
            or not audience
            or not slide_task
            or not isinstance(conditions, list)
            or not conditions
            or any(not isinstance(value, str) or not value for value in conditions)
        ):
            raise ExperienceValidationError(
                "target_context requires scene, audience, slide_task, and conditions"
            )
        access_by_type = {
            "preference-signal": "preferences",
            "professional-mechanism-candidate": "mechanisms",
            "anti-pattern-candidate": "anti-patterns",
        }
        entries: list[dict[str, Any]] = []
        excluded: list[str] = []
        state = self.kernel.load()
        for value in experience_version_refs:
            reference = ArtifactReference.parse(value)
            access = access_by_type.get(reference.kind)
            if access is None:
                raise ArtifactReferenceError(
                    f"Unsupported role-slice artifact kind: {reference.kind}"
                )
            payload = self.kernel.artifacts.resolve(reference)["payload"]
            current_slot = (
                f"experience/result/{reference.kind}/{payload.get('result_id', '')}"
            )
            if state.artifact_heads.get(current_slot) != value:
                raise ArtifactReferenceError(
                    "Role slices require current learning result heads"
                )
            if access not in role.experience_access or not self._matches_context(
                payload, scene, audience, slide_task, list(conditions)
            ):
                excluded.append(value)
                continue
            entries.append(
                {
                    "experience_ref": value,
                    "result_type": reference.kind,
                    "source_refs": list(payload.get("source_refs") or []),
                    "version": int(payload.get("version") or 1),
                    "scope": self._experience_scope(payload),
                    "match_reasons": self._match_reasons(payload),
                    "application_outcomes": [],
                }
            )
        compiled = validate_role_specific_slice(
            {
                "target_role_id": role.role_id,
                "target_role_display_name": role.display_name,
                "task_type": task_type,
                "target_context": {
                    "scene": scene,
                    "audience": audience,
                    "slide_task": slide_task,
                    "conditions": list(conditions),
                },
                "experience_entries": entries,
                "excluded_experience_refs": excluded,
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "revision": expected_revision,
            }
        )
        slot = f"experience/slice/{role.role_id}/{task_type}"
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.role-slice-compiled",
            artifact_updates={
                slot: ("role-specific-experience-slice", compiled)
            },
        )
        return committed.artifact_heads[slot]

    @staticmethod
    def _matches_context(
        payload: dict[str, Any],
        scene: str,
        audience: str,
        slide_task: str,
        conditions: list[str],
    ) -> bool:
        if payload.get("result_type") == "professional-mechanism-candidate":
            return (
                scene in payload.get("scenes", [])
                and audience in payload.get("audiences", [])
                and slide_task in payload.get("slide_tasks", [])
                and set(payload.get("conditions", [])).issubset(set(conditions))
            )
        if payload.get("result_type") == "preference-signal":
            return set(payload.get("conditions", [])).issubset(set(conditions))
        return True

    @staticmethod
    def _experience_scope(payload: dict[str, Any]) -> str:
        if payload.get("scope"):
            return str(payload["scope"])
        if payload.get("scopes"):
            return "|".join(payload["scopes"])
        return "scene=" + "|".join(payload.get("scenes", []))

    @staticmethod
    def _match_reasons(payload: dict[str, Any]) -> list[str]:
        if payload.get("result_type") == "professional-mechanism-candidate":
            return ["scene", "audience", "slide-task", "conditions"]
        if payload.get("result_type") == "preference-signal":
            return ["conditions", "preference-scope"]
        return ["role-access", "failure-scope"]

    def _resolve_kind(self, value: str, kind: str) -> dict:
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(
                f"Expected artifact kind {kind}, got {reference.kind}"
            )
        return self.kernel.artifacts.resolve(reference)

    def _require_current_candidate(self, value: str) -> dict[str, Any]:
        record = self._resolve_kind(value, "experience-candidate")
        candidate = record["payload"]
        slot = f"experience/candidate/{candidate.get('candidate_id', '')}"
        if self.kernel.load().artifact_heads.get(slot) != value:
            raise ArtifactReferenceError(
                "Experience operation requires the current candidate version"
            )
        return candidate

    def _require_current_evaluation(self, value: str) -> dict[str, Any]:
        record = self._resolve_kind(
            value, "experience-application-evaluation"
        )
        evaluation = record["payload"]
        slot = f"experience/evaluation/{evaluation.get('application_id', '')}"
        if self.kernel.load().artifact_heads.get(slot) != value:
            raise ArtifactReferenceError(
                "Evolution requires current application evaluations"
            )
        return evaluation

    def _require_exact_head(self, value: str, slot: str, kind: str) -> dict:
        record = self._resolve_kind(value, kind)
        if self.kernel.load().artifact_heads.get(slot) != value:
            raise ArtifactReferenceError(
                f"Artifact reference is not the current {slot} head"
            )
        return record
