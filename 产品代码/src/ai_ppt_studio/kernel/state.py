"""Schema 3.0 project state and its serialization contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _initial_gate_status() -> dict[str, str]:
    return {
        "G0": "open",
        "G1": "locked",
        "G2": "locked",
        "G3": "locked",
        "G4": "locked",
    }


@dataclass(frozen=True)
class KernelState:
    """The sole visibility boundary for committed project state."""

    schema_version: str
    project_id: str
    revision: int
    artifact_heads: dict[str, str] = field(default_factory=dict)
    gate_status: dict[str, str] = field(default_factory=_initial_gate_status)
    consumed_user_confirmations: dict[str, str] = field(default_factory=dict)
    processed_commands: dict[str, int] = field(default_factory=dict)
    last_transaction_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def initial(cls, project_id: str) -> "KernelState":
        return cls(schema_version="3.0", project_id=project_id, revision=0)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KernelState":
        return cls(
            schema_version=str(payload["schema_version"]),
            project_id=str(payload["project_id"]),
            revision=int(payload["revision"]),
            artifact_heads=dict(payload.get("artifact_heads", {})),
            gate_status=dict(payload.get("gate_status", {})),
            consumed_user_confirmations={
                str(key): str(value)
                for key, value in payload.get(
                    "consumed_user_confirmations", {}
                ).items()
            },
            processed_commands={
                str(key): int(value)
                for key, value in payload.get("processed_commands", {}).items()
            },
            last_transaction_id=str(payload.get("last_transaction_id", "")),
        )
