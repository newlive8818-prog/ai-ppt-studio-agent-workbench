"""Immutable release-target policy for desktop presentation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


SUPPORTED_TARGET_IDS = (
    "macos-powerpoint",
    "macos-wps",
    "windows-powerpoint",
    "windows-wps",
)

CURRENT_RELEASE_TARGET_POLICY = {
    "policy_id": "v1.6-macos-powerpoint",
    "policy_version": "1.0",
    "status": "active",
    "required_target_ids": ["macos-powerpoint"],
    "deferred_target_ids": [
        "macos-wps",
        "windows-powerpoint",
        "windows-wps",
    ],
    "compatibility_claim_scope": ["macos-powerpoint"],
    "effective_at": "2026-08-13T00:00:00+08:00",
    "decision_source": "explicit-user-confirmation",
    "rationale": "v1.6 当前先保证 macOS Microsoft PowerPoint；WPS 和 Windows 延期。",
}


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _target_ids(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    values = payload.get(field)
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value for value in values
    ):
        raise ValueError(f"{field} must be an array of target IDs")
    return tuple(values)


@dataclass(frozen=True)
class ReleaseTargetPolicy:
    policy_id: str
    policy_version: str
    status: str
    required_target_ids: tuple[str, ...]
    deferred_target_ids: tuple[str, ...]
    compatibility_claim_scope: tuple[str, ...]
    effective_at: str
    decision_source: str
    rationale: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ReleaseTargetPolicy":
        if not isinstance(payload, dict):
            raise ValueError("ReleaseTargetPolicy must be an object")
        policy = cls(
            policy_id=_text(payload, "policy_id"),
            policy_version=_text(payload, "policy_version"),
            status=_text(payload, "status"),
            required_target_ids=_target_ids(payload, "required_target_ids"),
            deferred_target_ids=_target_ids(payload, "deferred_target_ids"),
            compatibility_claim_scope=_target_ids(
                payload, "compatibility_claim_scope"
            ),
            effective_at=_text(payload, "effective_at"),
            decision_source=_text(payload, "decision_source"),
            rationale=_text(payload, "rationale"),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.status != "active":
            raise ValueError("ReleaseTargetPolicy status must be active")
        if not self.required_target_ids:
            raise ValueError("required_target_ids cannot be empty")
        for field, values in (
            ("required_target_ids", self.required_target_ids),
            ("deferred_target_ids", self.deferred_target_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{field} cannot contain duplicates")
            unsupported = set(values).difference(SUPPORTED_TARGET_IDS)
            if unsupported:
                raise ValueError(f"{field} contains unsupported target IDs")
        required = set(self.required_target_ids)
        deferred = set(self.deferred_target_ids)
        if required.intersection(deferred):
            raise ValueError("Required and deferred target IDs must be disjoint")
        if required.union(deferred) != set(SUPPORTED_TARGET_IDS):
            raise ValueError("Required and deferred targets must partition supported IDs")
        if self.compatibility_claim_scope != self.required_target_ids:
            raise ValueError(
                "compatibility_claim_scope must equal required_target_ids"
            )
        try:
            effective_at = datetime.fromisoformat(self.effective_at)
        except ValueError as error:
            raise ValueError("effective_at must be an ISO-8601 timestamp") from error
        if effective_at.tzinfo is None:
            raise ValueError("effective_at must include a timezone")

    def as_payload(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "status": self.status,
            "required_target_ids": list(self.required_target_ids),
            "deferred_target_ids": list(self.deferred_target_ids),
            "compatibility_claim_scope": list(self.compatibility_claim_scope),
            "effective_at": self.effective_at,
            "decision_source": self.decision_source,
            "rationale": self.rationale,
        }
