"""Versioned cross-project personal experience store and evaluation loop."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .config import RuntimeConfig
from .errors import ExperienceValidationError
from .experience_models import (
    CandidateExperience,
    EvaluationOutcome,
    ExperienceApplication,
    ExperienceEvaluation,
    ExperienceLevel,
)
from .json_io import append_jsonl, atomic_write_json
from .models import ProjectManifest
from .paths import PathPolicy


SCOPE_KEYS = ("scenes", "audiences", "slide_tasks", "conditions")
CONTEXT_TO_SCOPE = {
    "scene": "scenes",
    "audience": "audiences",
    "slide_task": "slide_tasks",
    "conditions": "conditions",
}
MATCH_WEIGHTS = {"scene": 4, "audience": 3, "slide_task": 3, "conditions": 1}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _unique_strings(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class ExperienceStore:
    """Persist personal experience separately from any single presentation project."""

    def __init__(self, config: RuntimeConfig, policy: PathPolicy) -> None:
        self.config = config
        self.policy = policy
        self.personal_root = self.policy.assert_write_allowed(
            config.runtime_root / "personal-memory"
        )
        self.experiences_root = self.policy.assert_write_allowed(
            self.personal_root / "experiences"
        )
        self.index_path = self.policy.assert_write_allowed(
            self.personal_root / "experience-index.json"
        )
        self.evaluation_root = self.policy.assert_write_allowed(
            config.runtime_root / "evaluation"
        )
        self.applications_path = self.policy.assert_write_allowed(
            self.evaluation_root / "applications.jsonl"
        )
        self.evaluations_path = self.policy.assert_write_allowed(
            self.evaluation_root / "evaluations.jsonl"
        )
        self.decisions_path = self.policy.assert_write_allowed(
            self.evaluation_root / "promotion-decisions.jsonl"
        )

    def initialize(self) -> None:
        self.experiences_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.evaluation_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.index_path.exists():
            atomic_write_json(
                self.index_path,
                {"schema_version": "1.0", "updated_at": _now(), "experiences": []},
            )

    def capability_status(self) -> dict[str, object]:
        """Return evidence that the local experience subsystem is operational."""

        self.initialize()
        required = (
            "create_candidate",
            "recommend",
            "record_application",
            "evaluate",
            "set_level",
            "rollback",
        )
        operations = [name for name in required if callable(getattr(self, name, None))]
        ready = len(operations) == len(required) and self.index_path.is_file()
        return {
            "ready": ready,
            "schema_version": "1.0",
            "personal_memory_root": str(self.personal_root),
            "evaluation_root": str(self.evaluation_root),
            "index_path": str(self.index_path),
            "operations": operations,
            "stable_kernel_auto_mutation": False,
        }

    def create_candidate(
        self, project: ProjectManifest, payload: dict[str, object]
    ) -> CandidateExperience:
        self.initialize()
        validated = self._validate_candidate_payload(payload)
        now = _now()
        experience_id = f"EXP-{uuid.uuid4().hex[:12]}"
        state: dict[str, object] = {
            "schema_version": "1.0",
            "experience_id": experience_id,
            "name": validated["name"],
            "experience_type": validated["experience_type"],
            "mechanism": validated["mechanism"],
            "model_interpretation": validated["model_interpretation"],
            "source_project_ids": [project.project_id],
            "source_refs": validated["source_refs"],
            "scope": validated["scope"],
            "evidence_refs": validated["evidence_refs"],
            "before_after_refs": validated["before_after_refs"],
            "counterexamples": validated["counterexamples"],
            "privacy_level": validated["privacy_level"],
            "portable_scope": validated["portable_scope"],
            "sanitized_for_reuse": True,
            "level": ExperienceLevel.CANDIDATE.value,
            "enabled": True,
            "usage_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "accepted_success_project_ids": [],
            "failure_project_ids": [],
            "failures_since_promotion": 0,
            "validation_evidence_refs": [],
            "latest_validation_time": None,
            "confidence": self._confidence((), 0, bool(validated["evidence_refs"])),
            "created_at": now,
            "previous_version": None,
            "rollback_from_version": None,
        }
        return self._write_new_version(state, explicit_version=1)

    def list(
        self, level: ExperienceLevel | None = None
    ) -> tuple[CandidateExperience, ...]:
        self.initialize()
        index = self._load_index()
        experiences = tuple(
            self.get(str(item["experience_id"]))
            for item in index.get("experiences", [])
            if level is None or str(item.get("level")) == level.value
        )
        return tuple(sorted(experiences, key=lambda item: (item.name, item.experience_id)))

    def get(self, experience_id: str) -> CandidateExperience:
        self.initialize()
        latest_path = self._latest_path(experience_id)
        if not latest_path.is_file():
            raise ExperienceValidationError(f"Experience not found: {experience_id}")
        try:
            pointer = json.loads(latest_path.read_text(encoding="utf-8"))
            version_path = Path(str(pointer["path"]))
            if not version_path.is_relative_to(self.experiences_root):
                raise ExperienceValidationError(
                    f"Experience version is outside personal memory: {version_path}"
                )
            payload = json.loads(version_path.read_text(encoding="utf-8"))
            return CandidateExperience.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ExperienceValidationError):
                raise
            raise ExperienceValidationError(
                f"Experience record is invalid: {experience_id}"
            ) from exc

    def recommend(
        self, context: dict[str, object], limit: int = 5
    ) -> list[dict[str, object]]:
        normalized = self._validate_context(context)
        if limit < 1:
            raise ExperienceValidationError("Recommendation limit must be positive")
        ranked: list[tuple[int, int, float, dict[str, object]]] = []
        for experience in self.list():
            if not experience.enabled or experience.level in {
                ExperienceLevel.DISABLED,
                ExperienceLevel.RETIRED,
            }:
                continue
            score = 0
            reasons: list[str] = []
            applicable = True
            for context_key, scope_key in CONTEXT_TO_SCOPE.items():
                declared = set(experience.scope.get(scope_key, ()))
                provided = set(normalized[context_key])
                if declared and not declared.intersection(provided):
                    applicable = False
                    break
                matches = declared.intersection(provided)
                if matches:
                    score += MATCH_WEIGHTS[context_key] * len(matches)
                    reasons.extend(f"{context_key}:{item}" for item in sorted(matches))
            if not applicable or score == 0:
                continue
            recommendation = {
                "experience_id": experience.experience_id,
                "version": experience.version,
                "name": experience.name,
                "mechanism": experience.mechanism,
                "level": experience.level.value,
                "confidence": experience.confidence,
                "match_score": score,
                "match_reasons": reasons,
                "privacy_level": experience.privacy_level,
                "portable_scope": experience.portable_scope,
            }
            level_rank = 1 if experience.level is ExperienceLevel.PERSONAL else 0
            ranked.append((score, level_rank, experience.confidence, recommendation))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in ranked[:limit]]

    def record_application(
        self,
        project: ProjectManifest,
        experience_id: str,
        context: dict[str, object],
    ) -> ExperienceApplication:
        self.initialize()
        experience = self.get(experience_id)
        if not experience.enabled:
            raise ExperienceValidationError(
                f"Disabled experience cannot be applied: {experience_id}"
            )
        normalized = self._validate_context(context)
        application = ExperienceApplication(
            schema_version="1.0",
            application_id=f"APP-{uuid.uuid4().hex[:12]}",
            experience_id=experience.experience_id,
            experience_version=experience.version,
            project_id=project.project_id,
            project_root=project.project_root,
            context={
                "scene": normalized["scene"][0],
                "audience": normalized["audience"][0],
                "slide_task": normalized["slide_task"][0],
                "conditions": list(normalized["conditions"]),
            },
            applied_at=_now(),
        )
        append_jsonl(self.applications_path, application.as_dict())
        state = experience.as_dict()
        state["usage_count"] = experience.usage_count + 1
        state["previous_version"] = experience.version
        state["rollback_from_version"] = None
        self._write_new_version(state)
        return application

    def evaluate(
        self, application_id: str, payload: dict[str, object]
    ) -> ExperienceEvaluation:
        self.initialize()
        application = self._find_application(application_id)
        if any(item.application_id == application_id for item in self._read_evaluations()):
            raise ExperienceValidationError(
                f"Application already evaluated: {application_id}"
            )
        try:
            outcome = EvaluationOutcome(str(payload["outcome"]))
        except (KeyError, ValueError) as exc:
            raise ExperienceValidationError(
                "Evaluation outcome must be success, mixed, or failure"
            ) from exc
        if not isinstance(payload.get("user_accepted"), bool):
            raise ExperienceValidationError("Evaluation requires boolean user_accepted")
        evidence_refs = self._string_list(payload.get("evidence_refs", []), "evidence_refs")
        metrics = payload.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ExperienceValidationError("Evaluation metrics must be an object")
        evaluation = ExperienceEvaluation(
            schema_version="1.0",
            evaluation_id=f"EVAL-{uuid.uuid4().hex[:12]}",
            application_id=application.application_id,
            experience_id=application.experience_id,
            project_id=application.project_id,
            outcome=outcome,
            user_accepted=bool(payload["user_accepted"]),
            notes=str(payload.get("notes", "")).strip(),
            evidence_refs=tuple(evidence_refs),
            metrics=dict(metrics),
            evaluated_at=_now(),
        )
        append_jsonl(self.evaluations_path, evaluation.as_dict())
        current = self.get(application.experience_id)
        state = current.as_dict()
        accepted_ids = list(current.accepted_success_project_ids)
        failure_ids = list(current.failure_project_ids)
        validation_refs = list(current.validation_evidence_refs)
        validation_refs.extend(item for item in evidence_refs if item not in validation_refs)
        success_count = current.success_count
        failure_count = current.failure_count
        failures_since_promotion = current.failures_since_promotion
        accepted_success = outcome is EvaluationOutcome.SUCCESS and evaluation.user_accepted
        if accepted_success:
            success_count += 1
            if application.project_id not in accepted_ids:
                accepted_ids.append(application.project_id)
        if outcome is EvaluationOutcome.FAILURE:
            failure_count += 1
            if application.project_id not in failure_ids:
                failure_ids.append(application.project_id)
            if current.level is ExperienceLevel.PERSONAL:
                failures_since_promotion += 1
        state.update(
            {
                "success_count": success_count,
                "failure_count": failure_count,
                "accepted_success_project_ids": accepted_ids,
                "failure_project_ids": failure_ids,
                "failures_since_promotion": failures_since_promotion,
                "validation_evidence_refs": validation_refs,
                "latest_validation_time": evaluation.evaluated_at,
                "confidence": self._confidence(
                    accepted_ids,
                    failure_count,
                    bool(current.evidence_refs or validation_refs),
                ),
                "previous_version": current.version,
                "rollback_from_version": None,
            }
        )
        from_level = current.level
        to_level = from_level
        reason: str | None = None
        if from_level is ExperienceLevel.CANDIDATE and len(accepted_ids) >= 2:
            to_level = ExperienceLevel.PERSONAL
            state["level"] = to_level.value
            state["enabled"] = True
            state["failures_since_promotion"] = 0
            reason = "Two accepted successful applications in distinct target projects"
        elif (
            from_level is ExperienceLevel.PERSONAL
            and failures_since_promotion >= 2
        ):
            to_level = ExperienceLevel.CANDIDATE
            state["level"] = to_level.value
            reason = "Two failures recorded after personal promotion"
        updated = self._write_new_version(state)
        if to_level is not from_level:
            self._record_decision(
                experience_id=current.experience_id,
                from_level=from_level,
                to_level=to_level,
                reason=reason or "Automatic evidence rule",
                automatic=True,
                related_id=evaluation.evaluation_id,
                resulting_version=updated.version,
            )
        return evaluation

    def set_level(
        self, experience_id: str, level: ExperienceLevel, reason: str
    ) -> CandidateExperience:
        clean_reason = reason.strip()
        if not clean_reason:
            raise ExperienceValidationError("Manual level change requires a reason")
        current = self.get(experience_id)
        if current.level is level:
            raise ExperienceValidationError(
                f"Experience is already at level: {level.value}"
            )
        state = current.as_dict()
        state.update(
            {
                "level": level.value,
                "enabled": level not in {ExperienceLevel.DISABLED, ExperienceLevel.RETIRED},
                "previous_version": current.version,
                "rollback_from_version": None,
            }
        )
        updated = self._write_new_version(state)
        self._record_decision(
            experience_id=experience_id,
            from_level=current.level,
            to_level=level,
            reason=clean_reason,
            automatic=False,
            related_id=None,
            resulting_version=updated.version,
        )
        return updated

    def rollback(
        self, experience_id: str, version: int, reason: str
    ) -> CandidateExperience:
        clean_reason = reason.strip()
        if not clean_reason:
            raise ExperienceValidationError("Rollback requires a reason")
        current = self.get(experience_id)
        version_path = self._version_path(experience_id, version)
        if not version_path.is_file():
            raise ExperienceValidationError(
                f"Experience version not found: {experience_id} v{version:04d}"
            )
        try:
            state = json.loads(version_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperienceValidationError(
                f"Experience version is invalid: {version_path}"
            ) from exc
        state["previous_version"] = current.version
        state["rollback_from_version"] = version
        updated = self._write_new_version(state)
        self._record_decision(
            experience_id=experience_id,
            from_level=current.level,
            to_level=updated.level,
            reason=f"Rollback to v{version:04d}: {clean_reason}",
            automatic=False,
            related_id=None,
            resulting_version=updated.version,
            action="rollback",
        )
        return updated

    def _write_new_version(
        self, state: dict[str, object], explicit_version: int | None = None
    ) -> CandidateExperience:
        experience_id = str(state["experience_id"])
        directory = self.policy.assert_write_allowed(
            self.experiences_root / experience_id
        )
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if explicit_version is None:
            current = self.get(experience_id)
            version = current.version + 1
        else:
            version = explicit_version
        version_path = self._version_path(experience_id, version)
        if version_path.exists():
            raise ExperienceValidationError(
                f"Experience version already exists: {version_path}"
            )
        payload = dict(state)
        payload["version"] = version
        payload["updated_at"] = _now()
        payload["path"] = str(version_path)
        atomic_write_json(version_path, payload)
        atomic_write_json(
            self._latest_path(experience_id),
            {
                "schema_version": "1.0",
                "experience_id": experience_id,
                "version": version,
                "path": str(version_path),
                "updated_at": payload["updated_at"],
            },
        )
        experience = CandidateExperience.from_dict(payload)
        self._update_index(experience)
        return experience

    def _update_index(self, experience: CandidateExperience) -> None:
        index = self._load_index()
        entries = [
            item
            for item in index.get("experiences", [])
            if str(item.get("experience_id")) != experience.experience_id
        ]
        entries.append(
            {
                "experience_id": experience.experience_id,
                "name": experience.name,
                "level": experience.level.value,
                "enabled": experience.enabled,
                "confidence": experience.confidence,
                "version": experience.version,
                "latest_path": experience.path,
                "updated_at": experience.updated_at,
            }
        )
        entries.sort(key=lambda item: str(item["experience_id"]))
        atomic_write_json(
            self.index_path,
            {"schema_version": "1.0", "updated_at": _now(), "experiences": entries},
        )

    def _load_index(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperienceValidationError(
                f"Experience index is invalid: {self.index_path}"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("experiences"), list):
            raise ExperienceValidationError(
                f"Experience index is invalid: {self.index_path}"
            )
        return payload

    def _record_decision(
        self,
        *,
        experience_id: str,
        from_level: ExperienceLevel,
        to_level: ExperienceLevel,
        reason: str,
        automatic: bool,
        related_id: str | None,
        resulting_version: int,
        action: str = "level-change",
    ) -> None:
        append_jsonl(
            self.decisions_path,
            {
                "schema_version": "1.0",
                "decision_id": f"DEC-{uuid.uuid4().hex[:12]}",
                "action": action,
                "experience_id": experience_id,
                "from_level": from_level.value,
                "to_level": to_level.value,
                "reason": reason,
                "automatic": automatic,
                "related_id": related_id,
                "resulting_version": resulting_version,
                "decided_at": _now(),
            },
        )

    def _find_application(self, application_id: str) -> ExperienceApplication:
        for application in self._read_applications():
            if application.application_id == application_id:
                return application
        raise ExperienceValidationError(f"Application not found: {application_id}")

    def _read_applications(self) -> tuple[ExperienceApplication, ...]:
        return tuple(
            ExperienceApplication.from_dict(payload)
            for payload in self._read_jsonl(self.applications_path)
        )

    def _read_evaluations(self) -> tuple[ExperienceEvaluation, ...]:
        return tuple(
            ExperienceEvaluation.from_dict(payload)
            for payload in self._read_jsonl(self.evaluations_path)
        )

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("JSONL record must be an object")
                    records.append(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ExperienceValidationError(f"Evaluation log is invalid: {path}") from exc
        return records

    def _version_path(self, experience_id: str, version: int) -> Path:
        if version < 1:
            raise ExperienceValidationError("Experience version must be positive")
        return self.policy.assert_write_allowed(
            self.experiences_root / experience_id / f"v{version:04d}.json"
        )

    def _latest_path(self, experience_id: str) -> Path:
        if re.fullmatch(r"EXP-[A-Za-z0-9]{6,64}", experience_id) is None:
            raise ExperienceValidationError(f"Invalid experience id: {experience_id}")
        return self.policy.assert_write_allowed(
            self.experiences_root / experience_id / "latest.json"
        )

    def _validate_candidate_payload(
        self, payload: dict[str, object]
    ) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ExperienceValidationError("Candidate experience must be a JSON object")
        required_text = ("name", "experience_type", "mechanism", "model_interpretation")
        validated: dict[str, object] = {}
        for key in required_text:
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ExperienceValidationError(f"Candidate experience requires {key}")
            validated[key] = value.strip()
        if payload.get("sanitized_for_reuse") is not True:
            raise ExperienceValidationError(
                "Candidate mechanism must be explicitly sanitized_for_reuse"
            )
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            raise ExperienceValidationError("Candidate experience requires scope")
        normalized_scope = {
            key: self._string_list(scope.get(key, []), f"scope.{key}")
            for key in SCOPE_KEYS
        }
        if not any(normalized_scope.values()):
            raise ExperienceValidationError("Candidate scope cannot be empty")
        source_refs = self._string_list(payload.get("source_refs", []), "source_refs")
        if not source_refs:
            raise ExperienceValidationError("Candidate experience requires source_refs")
        before_after = payload.get("before_after_refs", [])
        if not isinstance(before_after, list) or any(
            not isinstance(item, dict) for item in before_after
        ):
            raise ExperienceValidationError("before_after_refs must be a list of objects")
        privacy = str(payload.get("privacy_level", "private"))
        if privacy not in {"private", "internal", "public"}:
            raise ExperienceValidationError("Unsupported privacy_level")
        portable = str(payload.get("portable_scope", "personal-installation"))
        if portable not in {"project-only", "personal-installation"}:
            raise ExperienceValidationError(
                "Runtime experience portable_scope must be project-only or personal-installation"
            )
        validated.update(
            {
                "source_refs": source_refs,
                "scope": normalized_scope,
                "evidence_refs": self._string_list(
                    payload.get("evidence_refs", []), "evidence_refs"
                ),
                "before_after_refs": [dict(item) for item in before_after],
                "counterexamples": self._string_list(
                    payload.get("counterexamples", []), "counterexamples"
                ),
                "privacy_level": privacy,
                "portable_scope": portable,
            }
        )
        return validated

    def _validate_context(self, context: dict[str, object]) -> dict[str, tuple[str, ...]]:
        if not isinstance(context, dict):
            raise ExperienceValidationError("Experience context must be an object")
        normalized: dict[str, tuple[str, ...]] = {}
        for key in ("scene", "audience", "slide_task"):
            value = context.get(key)
            values = [value] if isinstance(value, str) else value
            if not isinstance(values, list):
                raise ExperienceValidationError(f"Experience context requires {key}")
            normalized[key] = tuple(self._string_list(values, key))
            if not normalized[key]:
                raise ExperienceValidationError(f"Experience context requires {key}")
        conditions = context.get("conditions", [])
        if isinstance(conditions, str):
            conditions = [conditions]
        normalized["conditions"] = tuple(self._string_list(conditions, "conditions"))
        return normalized

    @staticmethod
    def _string_list(value: object, label: str) -> list[str]:
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, str) for item in value
        ):
            raise ExperienceValidationError(f"{label} must be a list of strings")
        return list(_unique_strings(value))

    @staticmethod
    def _confidence(
        accepted_project_ids: Iterable[str], failure_count: int, has_evidence: bool
    ) -> float:
        accepted_count = min(2, len(set(accepted_project_ids)))
        penalty_count = min(2, failure_count)
        score = 0.30 + 0.20 * accepted_count - 0.20 * penalty_count
        if has_evidence:
            score += 0.05
        return round(max(0.05, min(0.95, score)), 2)
