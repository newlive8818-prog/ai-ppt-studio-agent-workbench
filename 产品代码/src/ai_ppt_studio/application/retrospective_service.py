"""Project-completion queue and evidence-backed experience retrospective."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

from ai_ppt_studio.application.review_commands import fingerprint, stable_id
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ExperienceValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


COMPLETION_KINDS = frozenset({"delivered", "closed", "aborted"})
JOB_STATUSES = frozenset(
    {
        "queued",
        "running",
        "completed",
        "pending-retry",
        "failed-with-evidence",
    }
)
RETROSPECTIVE_FIELDS = (
    "content_findings",
    "visual_findings",
    "accepted_mechanisms",
    "rejected_patterns",
    "before_after_refs",
    "user_outcome_refs",
    "gate_and_render_refs",
    "same_type_changes",
    "global_changes",
    "next_project_recommendations",
)


class RetrospectiveService:
    """Keep project completion durable even when learning later fails."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    @staticmethod
    def prepare_completion(
        *,
        project_id: str,
        completion_kind: str,
        completion_identity: str,
        completion_ref: str,
        completed_at: str,
        completion_details: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if completion_kind not in COMPLETION_KINDS:
            raise ExperienceValidationError("Invalid completion_kind")
        for label, value in (
            ("project_id", project_id),
            ("completion_identity", completion_identity),
            ("completion_ref", completion_ref),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ExperienceValidationError(f"{label} is required")
        RetrospectiveService._timestamp(completed_at, "completed_at")
        completion = {
            "project_id": project_id,
            "completion_identity": completion_identity,
            "completion_kind": completion_kind,
            "completion_ref": completion_ref,
            "completed_at": completed_at,
            "details": deepcopy(completion_details or {}),
        }
        job = {
            "job_id": stable_id(
                "project-experience-retrospective", completion_identity
            ),
            **completion,
            "status": "queued",
            "attempt_count": 0,
            "last_error_ref": None,
            "queued_at": completed_at,
            "started_at": None,
            "finished_at": None,
        }
        return completion, job

    def queue_project_completion(
        self,
        *,
        command_id: str,
        expected_revision: int,
        completion_kind: str,
        completion_identity: str,
        completion_ref: str,
        completed_at: str,
        completion_details: dict[str, Any] | None = None,
    ):
        state = self.kernel.load()
        existing_ref = state.artifact_heads.get("project/completion", "")
        if existing_ref:
            existing = self._payload(existing_ref, "project-completion")
            if existing.get("completion_identity") == completion_identity:
                return state
            raise ExperienceValidationError(
                "Project already has a different current completion identity"
            )
        completion, job = self.prepare_completion(
            project_id=state.project_id,
            completion_kind=completion_kind,
            completion_identity=completion_identity,
            completion_ref=completion_ref,
            completed_at=completed_at,
            completion_details=completion_details,
        )
        command_fingerprint = fingerprint(
            "queue-project-retrospective",
            {"completion": completion},
        )
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.retrospective-queued",
            artifact_updates={
                "project/completion": ("project-completion", completion),
                "experience/retrospective/job": (
                    "experience-retrospective-job",
                    job,
                ),
            },
            command_fingerprint=command_fingerprint,
        )

    def run(
        self,
        *,
        command_id: str,
        expected_revision: int,
        builder: Callable[[dict[str, Any]], dict[str, Any]],
        started_at: str,
        finished_at: str,
        retryable: bool = True,
        capture_failure: bool = True,
    ):
        state = self.kernel.load()
        job_ref, job = self.current_job()
        if job["status"] == "completed":
            return state
        running = self._start(
            command_id=f"{command_id}:start",
            expected_revision=expected_revision,
            job_ref=job_ref,
            job=job,
            started_at=started_at,
        )
        running_ref, running_job = self.current_job()
        try:
            payload = builder(deepcopy(running_job))
            retrospective = self._validate_retrospective(
                payload,
                completion_kind=running_job["completion_kind"],
                completion_identity=running_job["completion_identity"],
                project_id=running_job["project_id"],
                generated_at=finished_at,
            )
        except Exception as error:
            if not capture_failure:
                raise
            return self._fail(
                command_id=f"{command_id}:failure",
                expected_revision=running.revision,
                job_ref=running_ref,
                job=running_job,
                error=error,
                failed_at=finished_at,
                retryable=retryable,
            )
        return self._complete(
            command_id=f"{command_id}:complete",
            expected_revision=running.revision,
            job_ref=running_ref,
            job=running_job,
            retrospective=retrospective,
            finished_at=finished_at,
        )

    def current_job(self) -> tuple[str, dict[str, Any]]:
        reference = self.kernel.load().artifact_heads.get(
            "experience/retrospective/job", ""
        )
        if not reference:
            raise ArtifactReferenceError(
                "Current retrospective job does not exist"
            )
        job = self._payload(reference, "experience-retrospective-job")
        if job.get("status") not in JOB_STATUSES:
            raise ExperienceValidationError(
                "Retrospective job status is invalid"
            )
        return reference, job

    def current_retrospective(self) -> tuple[str, dict[str, Any]]:
        reference = self.kernel.load().artifact_heads.get(
            "experience/project-retrospective", ""
        )
        if not reference:
            raise ArtifactReferenceError(
                "Current project retrospective does not exist"
            )
        return reference, self._payload(
            reference, "project-experience-retrospective"
        )

    def _start(
        self,
        *,
        command_id: str,
        expected_revision: int,
        job_ref: str,
        job: dict[str, Any],
        started_at: str,
    ):
        if job["status"] not in {"queued", "pending-retry"}:
            raise ExperienceValidationError(
                "Only queued or pending-retry retrospective can start"
            )
        self._timestamp(started_at, "started_at")
        running = {
            **job,
            "status": "running",
            "attempt_count": int(job["attempt_count"]) + 1,
            "started_at": started_at,
            "finished_at": None,
        }
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.retrospective-started",
            artifact_updates={
                "experience/retrospective/job": (
                    "experience-retrospective-job",
                    running,
                )
            },
            command_fingerprint=fingerprint(
                "start-project-retrospective",
                {"job_ref": job_ref, "started_at": started_at},
            ),
        )

    def _complete(
        self,
        *,
        command_id: str,
        expected_revision: int,
        job_ref: str,
        job: dict[str, Any],
        retrospective: dict[str, Any],
        finished_at: str,
    ):
        completed = {
            **job,
            "status": "completed",
            "finished_at": finished_at,
            "last_error_ref": None,
        }
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.retrospective-completed",
            artifact_updates={
                "experience/project-retrospective": (
                    "project-experience-retrospective",
                    retrospective,
                ),
                "experience/retrospective/job": (
                    "experience-retrospective-job",
                    completed,
                ),
            },
            command_fingerprint=fingerprint(
                "complete-project-retrospective",
                {
                    "job_ref": job_ref,
                    "retrospective": retrospective,
                },
            ),
        )

    def _fail(
        self,
        *,
        command_id: str,
        expected_revision: int,
        job_ref: str,
        job: dict[str, Any],
        error: Exception,
        failed_at: str,
        retryable: bool,
    ):
        self._timestamp(failed_at, "failed_at")
        evidence = {
            "error_id": stable_id(
                "retrospective-error",
                job["completion_identity"],
                job["attempt_count"],
            ),
            "completion_identity": job["completion_identity"],
            "attempt_count": job["attempt_count"],
            "error_type": type(error).__name__,
            "message": str(error)[:1000] or "retrospective failed",
            "failed_at": failed_at,
            "retryable": retryable,
        }
        error_ref = str(
            self.kernel.artifacts.reference_for(
                "retrospective-error-evidence", evidence
            )
        )
        failed = {
            **job,
            "status": "pending-retry"
            if retryable
            else "failed-with-evidence",
            "finished_at": failed_at,
            "last_error_ref": error_ref,
        }
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="experience.retrospective-failed",
            artifact_updates={
                "experience/retrospective/error": (
                    "retrospective-error-evidence",
                    evidence,
                ),
                "experience/retrospective/job": (
                    "experience-retrospective-job",
                    failed,
                ),
            },
            command_fingerprint=fingerprint(
                "fail-project-retrospective",
                {
                    "job_ref": job_ref,
                    "evidence": evidence,
                },
            ),
        )

    @staticmethod
    def _validate_retrospective(
        payload: dict[str, Any],
        *,
        completion_kind: str,
        completion_identity: str,
        project_id: str,
        generated_at: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ExperienceValidationError(
                "ProjectExperienceRetrospective must be an object"
            )
        signature = payload.get("project_type_signature")
        if not isinstance(signature, str) or not signature.strip():
            raise ExperienceValidationError(
                "project_type_signature is required"
            )
        if payload.get("completion_kind") != completion_kind:
            raise ExperienceValidationError(
                "Retrospective completion_kind does not match the job"
            )
        normalized: dict[str, Any] = {}
        for field in RETROSPECTIVE_FIELDS:
            values = payload.get(field)
            if not isinstance(values, list):
                raise ExperienceValidationError(f"{field} must be an array")
            normalized[field] = deepcopy(values)
        if completion_kind == "aborted" and RetrospectiveService._contains_success(
            [
                normalized["same_type_changes"],
                normalized["global_changes"],
            ]
        ):
            raise ExperienceValidationError(
                "Aborted retrospective cannot create a success evaluation"
            )
        RetrospectiveService._timestamp(generated_at, "generated_at")
        return {
            "retrospective_id": stable_id(
                "project-retrospective", completion_identity
            ),
            "project_id": project_id,
            "completion_identity": completion_identity,
            "project_type_signature": signature.strip(),
            **normalized,
            "completion_kind": completion_kind,
            "generated_at": generated_at,
        }

    @staticmethod
    def _contains_success(value: object) -> bool:
        if isinstance(value, dict):
            if any(
                value.get(key) == "success"
                for key in ("outcome", "application_result", "evaluation")
            ):
                return True
            return any(
                RetrospectiveService._contains_success(item)
                for item in value.values()
            )
        if isinstance(value, list):
            return any(
                RetrospectiveService._contains_success(item) for item in value
            )
        return False

    def _payload(self, reference: str, kind: str) -> dict[str, Any]:
        parsed = ArtifactReference.parse(reference)
        if parsed.kind != kind:
            raise ArtifactReferenceError(
                f"Expected artifact kind {kind}, got {parsed.kind}"
            )
        value = self.kernel.artifacts.resolve(parsed).get("payload")
        if not isinstance(value, dict):
            raise ArtifactReferenceError(f"{kind} payload must be an object")
        return dict(value)

    @staticmethod
    def _timestamp(value: str, field: str) -> str:
        if not isinstance(value, str) or not value:
            raise ExperienceValidationError(f"{field} is required")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ExperienceValidationError(
                f"{field} must be ISO-8601"
            ) from error
        if parsed.tzinfo is None:
            raise ExperienceValidationError(
                f"{field} must include a timezone"
            )
        return value


__all__ = ["RetrospectiveService"]
