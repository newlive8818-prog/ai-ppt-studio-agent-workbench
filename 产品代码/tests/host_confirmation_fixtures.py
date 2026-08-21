"""Test-only signer for the protected Node-to-Python Gate assertion contract."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)


TEST_HOST_CONFIRMATION_SECRET = "test-only-host-confirmation-secret-32-bytes-minimum"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def signed_gate_assertion(
    context: dict[str, Any],
    *,
    identity_type: str = "host-action",
    identity_ref: str | None = None,
) -> str:
    os.environ[HOST_CONFIRMATION_SECRET_ENV] = TEST_HOST_CONFIRMATION_SECRET
    issued_at = int(time.time())
    payload = {
        "project_id": context["project_id"],
        "project_root": context["project_root"],
        "scope_kind": context["scope_kind"],
        "scope_id": context["scope_id"],
        "source_version": context["source_version"],
        "evidence_refs": context["evidence_refs"],
        "challenge_id": context["challenge_id"],
        "challenge_revision": context["challenge_revision"],
        "identity_type": identity_type,
        "identity_ref": identity_ref
        or f"test-host-confirmation://{context['scope_id']}/{uuid.uuid4()}",
        "nonce": str(uuid.uuid4()),
        "issued_at": issued_at,
        "expires_at": issued_at + 120,
    }
    payload_segment = _encode(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        TEST_HOST_CONFIRMATION_SECRET.encode("utf-8"),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"v1.{payload_segment}.{_encode(signature)}"


def gate_confirmation_kwargs(
    context: dict[str, Any],
    *,
    identity_type: str = "host-action",
    identity_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "host_confirmation_assertion": signed_gate_assertion(
            context,
            identity_type=identity_type,
            identity_ref=identity_ref,
        ),
        "source_version": context["source_version"],
        "challenge_id": context["challenge_id"],
        "challenge_revision": context["challenge_revision"],
    }
