"""Versioned shared storage for v2.2 same-type and global experience."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator
import uuid

from .config import RuntimeConfig
from .domains.experience.contracts import (
    validate_experience_application,
    validate_experience_item,
    validate_experience_outcome,
)
from .errors import ExperienceValidationError
from .experience_models import (
    StoredApplication,
    StoredEvaluation,
    StoredExperience,
)
from .json_io import append_jsonl, atomic_write_json
from .kernel.artifacts import canonical_json
from .paths import PathPolicy


class ExperienceStore:
    """Persist reusable mechanisms outside any single customer project."""

    def __init__(self, config: RuntimeConfig, policy: PathPolicy) -> None:
        self.config = config
        self.policy = policy
        self.personal_root = self._path(config.runtime_root / "personal-memory")
        self.same_type_root = self._path(self.personal_root / "same-type")
        self.global_root = self._path(self.personal_root / "global")
        self.index_path = self._path(
            self.personal_root / "experience-index.json"
        )
        self.evaluation_root = self._path(config.runtime_root / "evaluation")
        self.applications_path = self._path(
            self.evaluation_root / "applications.jsonl"
        )
        self.evaluations_path = self._path(
            self.evaluation_root / "evaluations.jsonl"
        )
        self.promotions_path = self._path(
            self.evaluation_root / "promotions.jsonl"
        )
        self.lock_path = self._path(self.personal_root / "write.lock")

    def initialize(self) -> None:
        self.same_type_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.global_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.evaluation_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.index_path.exists():
            atomic_write_json(
                self.index_path,
                {
                    "schema_version": "2.2",
                    "items": [],
                },
            )
        for path in (
            self.applications_path,
            self.evaluations_path,
            self.promotions_path,
        ):
            if not path.exists():
                descriptor = os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                os.close(descriptor)

    def capability_status(self) -> dict[str, object]:
        self.initialize()
        operations = [
            "absorb_same_type",
            "recommend",
            "record_application",
            "evaluate",
            "promote_global",
            "rollback",
        ]
        return {
            "ready": all(
                callable(getattr(self, name, None)) for name in operations
            )
            and all(
                path.is_file()
                for path in (
                    self.index_path,
                    self.applications_path,
                    self.evaluations_path,
                    self.promotions_path,
                )
            ),
            "schema_version": "2.2",
            "personal_memory_root": str(self.personal_root),
            "same_type_root": str(self.same_type_root),
            "global_root": str(self.global_root),
            "evaluation_root": str(self.evaluation_root),
            "index_path": str(self.index_path),
            "application_log": str(self.applications_path),
            "evaluation_log": str(self.evaluations_path),
            "promotion_log": str(self.promotions_path),
            "operations": operations,
            "legacy_write_model": "retired",
            "stable_kernel_auto_mutation": False,
        }

    def absorb_same_type(self, payload: dict[str, Any]) -> StoredExperience:
        self.initialize()
        normalized = validate_experience_item(payload)
        if normalized["layer"] != "same-type":
            raise ExperienceValidationError(
                "Realtime absorption can only write same-type experience"
            )
        with self._locked():
            existing = self._optional_current(
                normalized["domain"],
                normalized["layer"],
                normalized["experience_id"],
            )
            if existing:
                current = existing.item
                normalized = validate_experience_item(
                    {
                        **normalized,
                        "version": current["version"] + 1,
                        "previous_version": current["version"],
                        "previous_version_ref": existing.experience_ref,
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
            return self._write(normalized)

    def recommend(
        self,
        *,
        domain: str,
        type_signature: str,
        applicability: dict[str, Any],
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        if domain not in {"content", "visual"}:
            raise ExperienceValidationError(
                "Experience domain must be content or visual"
            )
        if not isinstance(type_signature, str) or not type_signature.strip():
            raise ExperienceValidationError("type_signature is required")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ExperienceValidationError("limit must be a positive integer")
        conditions = (
            applicability.get("conditions")
            if isinstance(applicability, dict)
            else None
        )
        if not isinstance(conditions, list) or any(
            not isinstance(value, str) or not value for value in conditions
        ):
            raise ExperienceValidationError(
                "applicability.conditions must be a text array"
            )
        candidates: list[tuple[int, StoredExperience, str]] = []
        for stored in self.list_current(domain=domain):
            item = stored.item
            if (
                item["status"] != "active"
                or type_signature in item["excluded_type_signatures"]
                or not set(item["applicability"]["conditions"]).issubset(
                    set(conditions)
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
            candidates.append((rank, stored, reason))
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rank, stored, reason in sorted(
            candidates,
            key=lambda value: (
                value[0],
                -int(value[1].item["version"]),
                str(value[1].item["experience_id"]),
            ),
        ):
            item = stored.item
            identity = item["experience_id"]
            if identity in seen:
                continue
            seen.add(identity)
            results.append(
                {
                    "experience_ref": stored.experience_ref,
                    "experience_id": identity,
                    "experience_version": item["version"],
                    "layer": item["layer"],
                    "domain": item["domain"],
                    "result_type": item["result_type"],
                    "mechanism": item["mechanism"],
                    "match_reason": reason,
                    "applicability": deepcopy(item["applicability"]),
                }
            )
            if len(results) == limit:
                break
        return results

    def record_application(
        self,
        *,
        experience_ref: str,
        target_project_id: str,
        target_type_signature: str,
        context: dict[str, Any],
        evidence_refs: list[str],
        applied_at: str,
        explicit_validation: bool = False,
    ) -> StoredApplication:
        self.initialize()
        with self._locked():
            stored = self.get(experience_ref)
            current = self.get_current(
                stored.item["domain"],
                stored.item["layer"],
                stored.item["experience_id"],
            )
            if current.experience_ref != experience_ref:
                raise ExperienceValidationError(
                    "Application requires the current experience version"
                )
            item = stored.item
            if item["status"] != "active":
                raise ExperienceValidationError(
                    "Only active experience can be applied"
                )
            if item["layer"] == "same-type" and (
                item["type_signature"] != target_type_signature
                and not explicit_validation
            ):
                raise ExperienceValidationError(
                    "Same-type experience requires an exact type signature"
                )
            if target_type_signature in item["excluded_type_signatures"]:
                raise ExperienceValidationError(
                    "Experience is excluded for the target type signature"
                )
            application_id = f"experience-application-{uuid.uuid4().hex[:20]}"
            payload = validate_experience_application(
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
            append_jsonl(self.applications_path, payload)
            self._write(
                self._next_item(
                    stored,
                    updated_at=applied_at,
                    application_count=item["application_count"] + 1,
                )
            )
            return StoredApplication(
                application_id=application_id,
                experience_ref=experience_ref,
                payload=payload,
            )

    def evaluate(
        self,
        *,
        application_id: str,
        outcome: str,
        user_outcome_ref: str,
        hard_gate_refs: list[str],
        evidence_refs: list[str],
        evaluated_at: str,
    ) -> StoredEvaluation:
        self.initialize()
        with self._locked():
            if any(
                record["application_id"] == application_id
                for record in self._read_jsonl(self.evaluations_path)
            ):
                raise ExperienceValidationError(
                    "An application can only have one evaluation"
                )
            application = self._find_application(application_id)
            current = self.get_current(
                application["domain"],
                application["experience_layer"],
                application["experience_id"],
            )
            target = application["target_type_signature"]
            item = current.item
            successes = set(item["success_type_signatures"])
            failures = set(item["failure_type_signatures"])
            excluded = set(item["excluded_type_signatures"])
            counterexamples = list(item["counterexamples"])
            if outcome == "success":
                successes.add(target)
                failures.discard(target)
                user_result = "accepted"
            elif outcome == "failure":
                failures.add(target)
                excluded.add(target)
                marker = f"type-signature:{target}"
                if marker not in counterexamples:
                    counterexamples.append(marker)
                user_result = "rejected"
            else:
                user_result = "continued-feedback"
            evaluation_id = f"experience-outcome-{uuid.uuid4().hex[:20]}"
            payload = validate_experience_outcome(
                {
                    "outcome_id": evaluation_id,
                    "application_ref": self._record_ref(
                        "experience-application", application
                    ),
                    "application_id": application_id,
                    "experience_ref": application["experience_ref"],
                    "experience_id": application["experience_id"],
                    "experience_version": application["experience_version"],
                    "domain": application["domain"],
                    "experience_layer": application["experience_layer"],
                    "target_project_id": application["target_project_id"],
                    "target_type_signature": target,
                    "outcome": outcome,
                    "user_outcome_ref": user_outcome_ref,
                    "hard_gate_refs": hard_gate_refs,
                    "evidence_refs": evidence_refs,
                    "evaluated_at": evaluated_at,
                }
            )
            append_jsonl(self.evaluations_path, payload)
            self._write(
                self._next_item(
                    current,
                    updated_at=evaluated_at,
                    success_type_signatures=sorted(successes),
                    failure_type_signatures=sorted(failures),
                    excluded_type_signatures=sorted(excluded),
                    counterexamples=counterexamples,
                    user_outcomes=[
                        *item["user_outcomes"],
                        {
                            "project_id": application["target_project_id"],
                            "type_signature": target,
                            "outcome": user_result,
                            "evidence_ref": user_outcome_ref,
                        },
                    ],
                )
            )
            return StoredEvaluation(
                evaluation_id=evaluation_id,
                application_id=application_id,
                experience_ref=application["experience_ref"],
                payload=payload,
            )

    def promote_global(
        self,
        *,
        same_type_ref: str,
        promoted_at: str,
        user_global_directive_ref: str | None = None,
    ) -> StoredExperience:
        self.initialize()
        with self._locked():
            same_type = self.get(same_type_ref)
            current = self.get_current(
                same_type.item["domain"],
                same_type.item["layer"],
                same_type.item["experience_id"],
            )
            if (
                current.experience_ref != same_type_ref
                or same_type.item["layer"] != "same-type"
            ):
                raise ExperienceValidationError(
                    "Global promotion requires current same-type experience"
                )
            directive = (
                user_global_directive_ref.strip()
                if isinstance(user_global_directive_ref, str)
                else ""
            )
            if (
                not directive
                and len(set(same_type.item["success_type_signatures"])) < 2
            ):
                raise ExperienceValidationError(
                    "Global experience requires a user directive or two distinct successful types"
                )
            existing = self._optional_current(
                same_type.item["domain"],
                "global",
                same_type.item["experience_id"],
            )
            item = validate_experience_item(
                {
                    **deepcopy(same_type.item),
                    "version": existing.item["version"] + 1 if existing else 1,
                    "layer": "global",
                    "source_refs": list(
                        dict.fromkeys(
                            [*same_type.item["source_refs"], same_type_ref]
                        )
                    ),
                    "previous_version": (
                        existing.item["version"] if existing else None
                    ),
                    "previous_version_ref": (
                        existing.experience_ref if existing else None
                    ),
                    "rollback_from_version": None,
                    "user_global_directive_ref": directive or None,
                    "updated_at": promoted_at,
                }
            )
            promoted = self._write(item)
            append_jsonl(
                self.promotions_path,
                {
                    "action": "promote-global",
                    "same_type_ref": same_type_ref,
                    "global_ref": promoted.experience_ref,
                    "user_global_directive_ref": directive or None,
                    "success_type_signatures": item[
                        "success_type_signatures"
                    ],
                    "promoted_at": promoted_at,
                },
            )
            return promoted

    def rollback(
        self,
        *,
        experience_ref: str,
        target_version_ref: str,
        reason: str,
        rolled_back_at: str,
    ) -> StoredExperience:
        self.initialize()
        with self._locked():
            current = self.get(experience_ref)
            latest = self.get_current(
                current.item["domain"],
                current.item["layer"],
                current.item["experience_id"],
            )
            target = self.get(target_version_ref)
            if (
                latest.experience_ref != experience_ref
                or target.item["experience_id"]
                != current.item["experience_id"]
                or target.item["domain"] != current.item["domain"]
                or target.item["layer"] != current.item["layer"]
                or target.item["version"] >= current.item["version"]
            ):
                raise ExperienceValidationError(
                    "Rollback target must be an older version of the current item"
                )
            clean_reason = reason.strip() if isinstance(reason, str) else ""
            if not clean_reason:
                raise ExperienceValidationError("Rollback requires a reason")
            rolled_back = self._write(
                validate_experience_item(
                    {
                        **deepcopy(target.item),
                        "version": current.item["version"] + 1,
                        "application_count": current.item[
                            "application_count"
                        ],
                        "previous_version": current.item["version"],
                        "previous_version_ref": experience_ref,
                        "rollback_from_version": target.item["version"],
                        "updated_at": rolled_back_at,
                    }
                )
            )
            append_jsonl(
                self.promotions_path,
                {
                    "action": "rollback",
                    "from_ref": experience_ref,
                    "target_ref": target_version_ref,
                    "result_ref": rolled_back.experience_ref,
                    "reason": clean_reason,
                    "rolled_back_at": rolled_back_at,
                },
            )
            return rolled_back

    def get(self, experience_ref: str) -> StoredExperience:
        self.initialize()
        for entry in self._load_index()["items"]:
            for version in entry.get("versions", []):
                if version.get("experience_ref") == experience_ref:
                    return self._read_stored(Path(str(version["path"])))
        raise ExperienceValidationError(
            f"Experience reference not found: {experience_ref}"
        )

    def get_current(
        self, domain: str, layer: str, experience_id: str
    ) -> StoredExperience:
        value = self._optional_current(domain, layer, experience_id)
        if value is None:
            raise ExperienceValidationError(
                f"Current experience item not found: {domain}/{layer}/{experience_id}"
            )
        return value

    def list_current(
        self, *, domain: str | None = None, layer: str | None = None
    ) -> tuple[StoredExperience, ...]:
        self.initialize()
        values: list[StoredExperience] = []
        for entry in self._load_index()["items"]:
            if domain and entry.get("domain") != domain:
                continue
            if layer and entry.get("layer") != layer:
                continue
            values.append(self.get(str(entry["current_ref"])))
        return tuple(values)

    def _optional_current(
        self, domain: str, layer: str, experience_id: str
    ) -> StoredExperience | None:
        for entry in self._load_index()["items"]:
            if (
                entry.get("domain") == domain
                and entry.get("layer") == layer
                and entry.get("experience_id") == experience_id
            ):
                return self.get(str(entry["current_ref"]))
        return None

    def _write(self, item: dict[str, Any]) -> StoredExperience:
        normalized = validate_experience_item(item)
        root = (
            self.same_type_root
            if normalized["layer"] == "same-type"
            else self.global_root
        )
        path = self._path(
            root
            / normalized["domain"]
            / normalized["experience_id"]
            / f"v{normalized['version']:04d}.json"
        )
        if path.exists():
            raise ExperienceValidationError(
                f"Experience version already exists: {path}"
            )
        reference = self._record_ref("experience-item", normalized)
        atomic_write_json(
            path,
            {
                "schema_version": "2.2",
                "experience_ref": reference,
                "item": normalized,
            },
        )
        self._update_index(reference, path, normalized)
        return StoredExperience(reference, str(path), normalized)

    def _update_index(
        self, reference: str, path: Path, item: dict[str, Any]
    ) -> None:
        index = self._load_index()
        identity = (
            item["domain"],
            item["layer"],
            item["experience_id"],
        )
        entries = [
            entry
            for entry in index["items"]
            if (
                entry.get("domain"),
                entry.get("layer"),
                entry.get("experience_id"),
            )
            != identity
        ]
        previous = next(
            (
                entry
                for entry in index["items"]
                if (
                    entry.get("domain"),
                    entry.get("layer"),
                    entry.get("experience_id"),
                )
                == identity
            ),
            {},
        )
        versions = list(previous.get("versions") or [])
        versions.append(
            {
                "version": item["version"],
                "experience_ref": reference,
                "path": str(path),
            }
        )
        entries.append(
            {
                "domain": item["domain"],
                "layer": item["layer"],
                "experience_id": item["experience_id"],
                "current_ref": reference,
                "current_version": item["version"],
                "status": item["status"],
                "type_signature": item["type_signature"],
                "versions": versions,
            }
        )
        entries.sort(
            key=lambda entry: (
                str(entry["domain"]),
                str(entry["layer"]),
                str(entry["experience_id"]),
            )
        )
        atomic_write_json(
            self.index_path,
            {"schema_version": "2.2", "items": entries},
        )

    def _read_stored(self, path: Path) -> StoredExperience:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            reference = str(payload["experience_ref"])
            item = validate_experience_item(dict(payload["item"]))
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ExperienceValidationError(
                f"Stored experience is invalid: {path}"
            ) from error
        if reference != self._record_ref("experience-item", item):
            raise ExperienceValidationError(
                f"Stored experience reference mismatch: {path}"
            )
        return StoredExperience(reference, str(path), item)

    def _load_index(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExperienceValidationError(
                f"Experience index is invalid: {self.index_path}"
            ) from error
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "2.2"
            or not isinstance(payload.get("items"), list)
        ):
            raise ExperienceValidationError(
                f"Experience index is invalid: {self.index_path}"
            )
        return payload

    def _find_application(self, application_id: str) -> dict[str, Any]:
        matches = [
            value
            for value in self._read_jsonl(self.applications_path)
            if value.get("application_id") == application_id
        ]
        if len(matches) != 1:
            raise ExperienceValidationError(
                f"Application not found or duplicated: {application_id}"
            )
        return validate_experience_application(matches[0])

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as error:
            raise ExperienceValidationError(
                f"Experience log is invalid: {path}"
            ) from error
        if any(not isinstance(record, dict) for record in records):
            raise ExperienceValidationError(
                f"Experience log is invalid: {path}"
            )
        return records

    @staticmethod
    def _next_item(
        stored: StoredExperience, *, updated_at: str, **changes: Any
    ) -> dict[str, Any]:
        item = stored.item
        return validate_experience_item(
            {
                **deepcopy(item),
                **changes,
                "version": item["version"] + 1,
                "previous_version": item["version"],
                "previous_version_ref": stored.experience_ref,
                "rollback_from_version": None,
                "updated_at": updated_at,
            }
        )

    @staticmethod
    def _record_ref(kind: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(
            canonical_json({"kind": kind, "payload": payload})
        ).hexdigest()
        return f"artifact://{kind}/{digest}"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _path(self, path: Path) -> Path:
        return self.policy.assert_write_allowed(path)


__all__ = ["ExperienceStore"]
