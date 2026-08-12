"""Validated v1.6 inventory of user-provided project materials."""

from __future__ import annotations

import re
from typing import Any

from ai_ppt_studio.errors import ContractValidationError

SOURCE_KINDS = frozenset({"file", "directory", "url", "text", "image"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_material_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject external-search sources and normalize a material inventory."""

    if not isinstance(payload, dict) or not isinstance(
        payload.get("sources"), list
    ):
        raise ContractValidationError("MaterialInventory requires a sources array")
    sources = payload["sources"]
    if not sources:
        raise ContractValidationError("MaterialInventory requires at least one source")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sources:
        if not isinstance(item, dict):
            raise ContractValidationError("Every material source must be an object")
        source_id = str(item.get("source_id") or "").strip()
        origin = str(item.get("origin") or "").strip()
        kind = str(item.get("kind") or "").strip()
        locator = str(item.get("locator") or "").strip()
        sha256 = str(item.get("sha256") or "").strip()
        if not source_id or source_id in seen:
            raise ContractValidationError(
                "Material source IDs must be non-empty and unique"
            )
        if origin != "user-provided":
            raise ContractValidationError(
                "Project materials must be explicitly user-provided"
            )
        if kind not in SOURCE_KINDS or not locator or not SHA256.fullmatch(sha256):
            raise ContractValidationError(
                "Material source requires kind, locator, and lowercase SHA-256"
            )
        seen.add(source_id)
        normalized.append(
            {
                **item,
                "source_id": source_id,
                "origin": origin,
                "kind": kind,
                "locator": locator,
                "sha256": sha256,
            }
        )
    return {**payload, "sources": normalized, "status": "verified"}
