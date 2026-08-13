"""HMAC-backed, action-scoped, one-time user confirmation policy."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ai_ppt_studio.errors import ContentWorkflowError

if TYPE_CHECKING:
    from ai_ppt_studio.kernel.transactions import ProjectKernel


HOST_CONFIRMATION_SECRET_ENV = "AI_PPT_HOST_CONFIRMATION_SECRET"
HOST_ASSERTION_VERSION = "v1"
HOST_ASSERTION_MAX_LIFETIME_SECONDS = 300
HOST_ASSERTION_CLOCK_SKEW_SECONDS = 30
_CONFIRMATION_AUTHORITY = object()
_FRAMEWORK_RESET_AUTHORITY = object()


@dataclass(frozen=True)
class ConfirmationConsumption:
    identity: str
    owner: str
    challenge_revision: int
    authority: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class ContentFrameworkResetMutation:
    revision: int
    authority: object = field(repr=False, compare=False)


def validate_confirmation_consumption(value: object) -> ConfirmationConsumption:
    if (
        not isinstance(value, ConfirmationConsumption)
        or value.authority is not _CONFIRMATION_AUTHORITY
    ):
        raise ValueError("Confirmation consumption lacks trusted authority")
    return value


def validate_content_framework_reset(
    value: object,
) -> ContentFrameworkResetMutation:
    if (
        not isinstance(value, ContentFrameworkResetMutation)
        or value.authority is not _FRAMEWORK_RESET_AUTHORITY
    ):
        raise ValueError("Content framework reset lacks trusted authority")
    return value


class HostConfirmationAssertionVerifier:
    """Verify a host assertion against one exact scoped context."""

    @classmethod
    def verify(
        cls,
        token: str,
        current: dict[str, Any],
    ) -> tuple[str, str, str]:
        encoded = token.strip()
        secret = os.environ.get(HOST_CONFIRMATION_SECRET_ENV, "")
        try:
            if not encoded or len(secret.encode("utf-8")) < 32:
                raise ValueError("trusted host assertion is unavailable")
            version, payload_segment, signature_segment = encoded.split(".", 2)
            if version != HOST_ASSERTION_VERSION:
                raise ValueError("unsupported assertion version")
            expected_signature = hmac.new(
                secret.encode("utf-8"),
                payload_segment.encode("ascii"),
                hashlib.sha256,
            ).digest()
            supplied_signature = cls._decode_base64url(signature_segment)
            if not hmac.compare_digest(expected_signature, supplied_signature):
                raise ValueError("invalid assertion signature")
            payload = json.loads(
                cls._decode_base64url(payload_segment).decode("utf-8")
            )
            if not isinstance(payload, dict):
                raise ValueError("assertion payload must be an object")
            now = int(time.time())
            issued_at = int(payload["issued_at"])
            expires_at = int(payload["expires_at"])
            if (
                issued_at > now + HOST_ASSERTION_CLOCK_SKEW_SECONDS
                or expires_at <= now
                or expires_at <= issued_at
                or expires_at - issued_at > HOST_ASSERTION_MAX_LIFETIME_SECONDS
            ):
                raise ValueError("assertion is expired or outside its lifetime")
            expected_context = {
                "project_id": current["project_id"],
                "project_root": current["project_root"],
                "scope_kind": current["scope_kind"],
                "scope_id": current["scope_id"],
                "source_version": current["source_version"],
                "evidence_refs": current["evidence_refs"],
                "challenge_id": current["challenge_id"],
                "challenge_revision": current["challenge_revision"],
            }
            for key, value in expected_context.items():
                if payload.get(key) != value:
                    raise ValueError(f"assertion context mismatch: {key}")
            identity_type = str(payload.get("identity_type") or "")
            identity_ref = str(payload.get("identity_ref") or "").strip()
            nonce = str(payload.get("nonce") or "").strip()
            if identity_type not in {"host-action", "verified-message"}:
                raise ValueError("assertion identity type is invalid")
            if not identity_ref or not nonce:
                raise ValueError("assertion identity or nonce is missing")
        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
        ):
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Trusted host confirmation does not match the current action",
                {
                    "scope_kind": current.get("scope_kind", ""),
                    "scope_id": current.get("scope_id", ""),
                    "challenge_revision": current.get(
                        "challenge_revision", -1
                    ),
                },
            ) from None
        return (
            identity_type,
            identity_ref,
            hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _decode_base64url(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class ScopedConfirmationPolicy:
    """Create and validate a confirmation bound to one action and revision."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def context(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        source_version: str,
        evidence_refs: list[str] | tuple[str, ...],
    ) -> dict[str, Any]:
        state = self.kernel.load()
        challenge_body = {
            "project_id": state.project_id,
            "project_root": str(self.kernel.project_root),
            "scope_kind": scope_kind,
            "scope_id": scope_id,
            "source_version": source_version,
            "evidence_refs": list(evidence_refs),
            "challenge_revision": state.revision,
        }
        challenge_id = self.challenge_id(challenge_body)
        return {**challenge_body, "challenge_id": challenge_id}

    @staticmethod
    def challenge_id(challenge_body: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(
                challenge_body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def confirmation_payload(
        self,
        *,
        current: dict[str, Any],
        source_version: str,
        challenge_id: str,
        challenge_revision: int,
        host_confirmation_assertion: str,
    ) -> tuple[dict[str, Any], tuple[ConfirmationConsumption, ...]]:
        mismatches: dict[str, object] = {}
        if source_version != current["source_version"]:
            mismatches["source_version"] = source_version
        if challenge_id != current["challenge_id"]:
            mismatches["challenge_id"] = challenge_id
        if challenge_revision != current["challenge_revision"]:
            mismatches["challenge_revision"] = challenge_revision
        if mismatches:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Confirmation targets a stale content workflow action",
                {
                    "expected_source_version": current["source_version"],
                    "expected_challenge_id": current["challenge_id"],
                    "expected_challenge_revision": current[
                        "challenge_revision"
                    ],
                    "actual": mismatches,
                },
            )
        identity_type, identity_ref, assertion_digest = (
            HostConfirmationAssertionVerifier.verify(
                host_confirmation_assertion,
                current,
            )
        )
        action_ref = identity_ref if identity_type == "host-action" else ""
        message_ref = (
            identity_ref if identity_type == "verified-message" else ""
        )
        identities = tuple(value for value in (action_ref, message_ref) if value)
        if len(identities) != 1:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Exactly one trusted confirmation identity is required",
                {"scope_kind": current["scope_kind"]},
            )
        payload = {
            "project_id": current["project_id"],
            "scope_kind": current["scope_kind"],
            "scope_id": current["scope_id"],
            "source_version": current["source_version"],
            "evidence_refs": list(current["evidence_refs"]),
            "challenge_id": current["challenge_id"],
            "challenge_revision": current["challenge_revision"],
            "user_action_ref": action_ref,
            "user_message_ref": message_ref,
            "confirmation_identity_type": identity_type,
            "host_assertion_sha256": assertion_digest,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        owner = f"{current['scope_kind']}:{current['scope_id']}"
        return payload, tuple(
            ConfirmationConsumption(
                identity=value,
                owner=owner,
                challenge_revision=int(current["challenge_revision"]),
                authority=_CONFIRMATION_AUTHORITY,
            )
            for value in identities
        )

    def content_framework_reset(self) -> ContentFrameworkResetMutation:
        return ContentFrameworkResetMutation(
            revision=self.kernel.load().revision,
            authority=_FRAMEWORK_RESET_AUTHORITY,
        )
