"""Read legacy candidate/personal experience without reviving its write model."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ai_ppt_studio.errors import ExperienceValidationError


class LegacyExperienceV16Adapter:
    """Convert a historical record into a disabled same-type migration draft."""

    def convert_record(
        self, payload: dict[str, Any], *, legacy_ref: str
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ExperienceValidationError(
                "Legacy experience record must be an object"
            )
        if not isinstance(legacy_ref, str) or not legacy_ref.strip():
            raise ExperienceValidationError("legacy_ref is required")
        if (
            payload.get("artifact_type")
            == "stable-capability-release-candidate"
            or payload.get("status") == "release-candidate"
        ):
            return {
                "legacy_ref": legacy_ref,
                "migration_status": "legacy-only",
                "item": None,
                "eligible_for_automatic_global": False,
            }
        if payload.get("level") not in {"candidate", "personal"}:
            return {
                "legacy_ref": legacy_ref,
                "migration_status": "unsupported-legacy-record",
                "item": None,
                "eligible_for_automatic_global": False,
            }

        experience_type = str(payload.get("experience_type") or "")
        domain = "visual" if experience_type.startswith("visual") else "content"
        result_type = (
            "anti-pattern"
            if "anti-pattern" in experience_type
            else "preference"
            if "preference" in experience_type
            else "mechanism"
        )
        scope = payload.get("scope")
        scope = dict(scope) if isinstance(scope, dict) else {}
        before_after: list[dict[str, str]] = []
        for value in payload.get("before_after_refs") or []:
            if not isinstance(value, dict):
                continue
            before = str(value.get("before_ref") or value.get("before") or "")
            after = str(value.get("after_ref") or value.get("after") or "")
            if before and after:
                before_after.append(
                    {"before_ref": before, "after_ref": after}
                )
        experience_id = str(payload.get("experience_id") or "").lower()
        if not experience_id:
            raise ExperienceValidationError(
                "Legacy experience_id is required"
            )
        item = {
            "experience_id": experience_id,
            "version": 1,
            "layer": "same-type",
            "domain": domain,
            "result_type": result_type,
            "mechanism": str(payload.get("mechanism") or "").strip(),
            "type_signature": f"legacy:{domain}:{experience_id}",
            "applicability": {
                key: list(scope.get(key) or ["legacy-unspecified"])
                for key in ("scenes", "audiences", "slide_tasks", "conditions")
            },
            "counterexamples": list(payload.get("counterexamples") or []),
            "failure_boundaries": ["Requires explicit v2.2 validation before use"],
            "source_project_ids": list(payload.get("source_project_ids") or []),
            "source_refs": list(payload.get("source_refs") or []),
            "before_after_refs": before_after,
            "hard_gate_refs": list(
                payload.get("validation_evidence_refs") or []
            ),
            "user_outcomes": [],
            "application_count": 0,
            "success_type_signatures": [],
            "failure_type_signatures": [],
            "excluded_type_signatures": [],
            "sanitized_for_reuse": payload.get("sanitized_for_reuse") is True,
            "privacy": {
                "contains_client_identifiers": False,
                "contains_client_facts": False,
                "contains_client_assets": False,
                "reuse_scope": "mechanism-only",
            },
            "status": "disabled",
            "previous_version": None,
            "previous_version_ref": None,
            "rollback_from_version": None,
            "updated_at": str(payload.get("updated_at") or ""),
            "legacy_source": {
                "legacy_ref": legacy_ref,
                "legacy_level": payload.get("level"),
                "legacy_version": payload.get("version"),
            },
        }
        return {
            "legacy_ref": legacy_ref,
            "migration_status": "same-type-draft",
            "item": deepcopy(item),
            "eligible_for_automatic_global": False,
        }


__all__ = ["LegacyExperienceV16Adapter"]
