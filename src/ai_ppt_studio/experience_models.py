"""Stable models for cross-project personal experience evolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ExperienceLevel(str, Enum):
    CANDIDATE = "candidate"
    PERSONAL = "personal"
    DISABLED = "disabled"
    RETIRED = "retired"


class EvaluationOutcome(str, Enum):
    SUCCESS = "success"
    MIXED = "mixed"
    FAILURE = "failure"


@dataclass(frozen=True)
class CandidateExperience:
    """One immutable version of a bounded reusable experience."""

    schema_version: str
    experience_id: str
    version: int
    name: str
    experience_type: str
    mechanism: str
    model_interpretation: str
    source_project_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    scope: dict[str, tuple[str, ...]]
    evidence_refs: tuple[str, ...]
    before_after_refs: tuple[dict[str, str], ...]
    counterexamples: tuple[str, ...]
    privacy_level: str
    portable_scope: str
    sanitized_for_reuse: bool
    level: ExperienceLevel
    enabled: bool
    usage_count: int
    success_count: int
    failure_count: int
    accepted_success_project_ids: tuple[str, ...]
    failure_project_ids: tuple[str, ...]
    failures_since_promotion: int
    validation_evidence_refs: tuple[str, ...]
    latest_validation_time: str | None
    confidence: float
    created_at: str
    updated_at: str
    previous_version: int | None
    rollback_from_version: int | None
    path: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["level"] = self.level.value
        payload["scope"] = {
            key: list(values) for key, values in self.scope.items()
        }
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateExperience":
        return cls(
            schema_version=str(payload["schema_version"]),
            experience_id=str(payload["experience_id"]),
            version=int(payload["version"]),
            name=str(payload["name"]),
            experience_type=str(payload["experience_type"]),
            mechanism=str(payload["mechanism"]),
            model_interpretation=str(payload["model_interpretation"]),
            source_project_ids=tuple(str(item) for item in payload["source_project_ids"]),
            source_refs=tuple(str(item) for item in payload["source_refs"]),
            scope={
                str(key): tuple(str(item) for item in values)
                for key, values in payload["scope"].items()
            },
            evidence_refs=tuple(str(item) for item in payload["evidence_refs"]),
            before_after_refs=tuple(
                {str(key): str(value) for key, value in item.items()}
                for item in payload["before_after_refs"]
            ),
            counterexamples=tuple(str(item) for item in payload["counterexamples"]),
            privacy_level=str(payload["privacy_level"]),
            portable_scope=str(payload["portable_scope"]),
            sanitized_for_reuse=bool(payload["sanitized_for_reuse"]),
            level=ExperienceLevel(str(payload["level"])),
            enabled=bool(payload["enabled"]),
            usage_count=int(payload["usage_count"]),
            success_count=int(payload["success_count"]),
            failure_count=int(payload["failure_count"]),
            accepted_success_project_ids=tuple(
                str(item) for item in payload["accepted_success_project_ids"]
            ),
            failure_project_ids=tuple(
                str(item) for item in payload["failure_project_ids"]
            ),
            failures_since_promotion=int(payload["failures_since_promotion"]),
            validation_evidence_refs=tuple(
                str(item) for item in payload["validation_evidence_refs"]
            ),
            latest_validation_time=(
                str(payload["latest_validation_time"])
                if payload.get("latest_validation_time") is not None
                else None
            ),
            confidence=float(payload["confidence"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            previous_version=(
                int(payload["previous_version"])
                if payload.get("previous_version") is not None
                else None
            ),
            rollback_from_version=(
                int(payload["rollback_from_version"])
                if payload.get("rollback_from_version") is not None
                else None
            ),
            path=str(payload["path"]),
        )


@dataclass(frozen=True)
class ExperienceApplication:
    """A record that one exact experience version was used in a target project."""

    schema_version: str
    application_id: str
    experience_id: str
    experience_version: int
    project_id: str
    project_root: str
    context: dict[str, object]
    applied_at: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperienceApplication":
        return cls(
            schema_version=str(payload["schema_version"]),
            application_id=str(payload["application_id"]),
            experience_id=str(payload["experience_id"]),
            experience_version=int(payload["experience_version"]),
            project_id=str(payload["project_id"]),
            project_root=str(payload["project_root"]),
            context=dict(payload["context"]),
            applied_at=str(payload["applied_at"]),
        )


@dataclass(frozen=True)
class ExperienceEvaluation:
    """Outcome evidence for one experience application."""

    schema_version: str
    evaluation_id: str
    application_id: str
    experience_id: str
    project_id: str
    outcome: EvaluationOutcome
    user_accepted: bool
    notes: str
    evidence_refs: tuple[str, ...]
    metrics: dict[str, object]
    evaluated_at: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperienceEvaluation":
        return cls(
            schema_version=str(payload["schema_version"]),
            evaluation_id=str(payload["evaluation_id"]),
            application_id=str(payload["application_id"]),
            experience_id=str(payload["experience_id"]),
            project_id=str(payload["project_id"]),
            outcome=EvaluationOutcome(str(payload["outcome"])),
            user_accepted=bool(payload["user_accepted"]),
            notes=str(payload.get("notes", "")),
            evidence_refs=tuple(str(item) for item in payload.get("evidence_refs", [])),
            metrics=dict(payload.get("metrics", {})),
            evaluated_at=str(payload["evaluated_at"]),
        )
