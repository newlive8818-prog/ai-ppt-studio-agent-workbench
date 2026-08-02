"""Stable JSON models for the Agent-native workbench projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectSnapshot:
    """A compact, model-safe and Widget-safe projection of one project."""

    schema_version: str
    revision: int
    updated_at: str
    active_space: str
    project: dict[str, Any]
    gate_state: dict[str, Any]
    cognition_map: dict[str, Any]
    artifacts: dict[str, Any]
    space_projections: dict[str, Any]
    current_decision: dict[str, Any]
    last_human_decision_id: str | None
    allowed_next_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["allowed_next_actions"] = list(self.allowed_next_actions)
        return payload


@dataclass(frozen=True)
class DecisionResult:
    """The accepted decision plus the refreshed project projection."""

    decision: dict[str, Any]
    snapshot: ProjectSnapshot
    follow_up_message: str
    model_context: dict[str, Any]
    affected_artifacts: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "decision": dict(self.decision),
            "snapshot": self.snapshot.as_dict(),
            "follow_up_message": self.follow_up_message,
            "model_context": dict(self.model_context),
            "affected_artifacts": list(self.affected_artifacts),
        }
