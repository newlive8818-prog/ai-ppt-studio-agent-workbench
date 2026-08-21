"""Shared command identity and replay guards for review-domain writes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.artifacts import canonical_json
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


def fingerprint(operation: str, values: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json({"operation": operation, "values": values})
    ).hexdigest()


def replay_ref(
    kernel: ProjectKernel, command_id: str, command_fingerprint: str, slot: str
) -> tuple[str, KernelState] | None:
    state = replay_state(kernel, command_id, command_fingerprint)
    if state is None:
        return None
    revision = state.processed_commands[command_id]
    event = _command_event(kernel, revision)
    reference = dict(event.get("artifact_heads") or {}).get(slot, "")
    if not reference:
        raise ContractValidationError("Processed command result is unavailable")
    return reference, state


def replay_state(
    kernel: ProjectKernel, command_id: str, command_fingerprint: str
) -> KernelState | None:
    state = kernel.load()
    revision = state.processed_commands.get(command_id)
    if revision is None:
        return None
    event = _command_event(kernel, revision)
    if event.get("command_fingerprint") != command_fingerprint:
        raise ContractValidationError("Processed command has different semantics")
    return state


def _command_event(kernel: ProjectKernel, revision: int) -> dict[str, Any]:
    try:
        return json.loads(
            (kernel.events_root / f"r{revision:08d}.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ContractValidationError("Processed command receipt is unavailable") from error


def stable_id(prefix: str, *values: object) -> str:
    digest = hashlib.sha256("\0".join(map(str, values)).encode()).hexdigest()[:20]
    return f"{prefix}-{digest}"


__all__ = ["fingerprint", "replay_ref", "replay_state", "stable_id"]
