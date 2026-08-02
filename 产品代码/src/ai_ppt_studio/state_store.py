"""Sequential, resumable G0-G4 workflow state."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import InvalidTransitionError, ProjectNotFoundError
from .event_store import EventStore, utc_now
from .json_io import atomic_write_json
from .models import Gate, GateStatus, ProjectState
from .paths import PathPolicy

GATE_ORDER = tuple(Gate)


class StateStore:
    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.events = EventStore(self.project_root, policy)

    @property
    def state_path(self) -> Path:
        return self.policy.assert_write_allowed(
            self.project_root / "state" / "state.json"
        )

    def initialize(self) -> ProjectState:
        if self.state_path.exists():
            return self.load()
        gates = {
            gate.value: (
                GateStatus.OPEN.value
                if gate is Gate.G0
                else GateStatus.LOCKED.value
            )
            for gate in GATE_ORDER
        }
        state = ProjectState(
            schema_version="1.0",
            revision=0,
            gates=gates,
            current_gate=Gate.G0.value,
            updated_at=utc_now(),
        )
        self._save(state)
        self.events.append(
            "project.state.initialized",
            {"revision": state.revision, "current_gate": state.current_gate},
        )
        return state

    def load(self) -> ProjectState:
        if not self.state_path.is_file():
            raise ProjectNotFoundError(
                f"Project state is not initialized: {self.state_path}"
            )
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = ProjectState.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProjectNotFoundError(
                f"Project state is invalid: {self.state_path}"
            ) from exc
        self._validate(state)
        return state

    def pass_gate(
        self, gate: Gate, evidence_refs: tuple[str, ...]
    ) -> ProjectState:
        state = self.load()
        if state.gates.get(gate.value) != GateStatus.OPEN.value:
            raise InvalidTransitionError(f"Gate is not open: {gate.value}")
        evidence = tuple(item.strip() for item in evidence_refs if item.strip())
        if not evidence:
            raise InvalidTransitionError(
                f"Passing {gate.value} requires at least one evidence reference"
            )
        gates = dict(state.gates)
        gates[gate.value] = GateStatus.PASSED.value
        index = GATE_ORDER.index(gate)
        if index + 1 < len(GATE_ORDER):
            next_gate = GATE_ORDER[index + 1]
            gates[next_gate.value] = GateStatus.OPEN.value
            current_gate = next_gate.value
        else:
            current_gate = gate.value
        updated = ProjectState(
            schema_version=state.schema_version,
            revision=state.revision + 1,
            gates=gates,
            current_gate=current_gate,
            updated_at=utc_now(),
        )
        self._save(updated)
        self.events.append(
            "project.gate.passed",
            {
                "gate": gate.value,
                "evidence_refs": list(evidence),
                "revision": updated.revision,
            },
        )
        return updated

    def reopen_from(self, gate: Gate, reason: str) -> ProjectState:
        state = self.load()
        explanation = reason.strip()
        if not explanation:
            raise InvalidTransitionError("Reopening a gate requires a reason")
        selected_index = GATE_ORDER.index(gate)
        gates = dict(state.gates)
        for index, candidate in enumerate(GATE_ORDER):
            if index == selected_index:
                gates[candidate.value] = GateStatus.OPEN.value
            elif index > selected_index:
                gates[candidate.value] = GateStatus.LOCKED.value
        updated = ProjectState(
            schema_version=state.schema_version,
            revision=state.revision + 1,
            gates=gates,
            current_gate=gate.value,
            updated_at=utc_now(),
        )
        self._save(updated)
        self.events.append(
            "project.gate.reopened",
            {
                "gate": gate.value,
                "reason": explanation,
                "revision": updated.revision,
            },
        )
        return updated

    def _save(self, state: ProjectState) -> None:
        atomic_write_json(self.state_path, state.as_dict())

    def _validate(self, state: ProjectState) -> None:
        expected = {gate.value for gate in GATE_ORDER}
        if set(state.gates) != expected:
            raise ProjectNotFoundError("Project state has an invalid gate set")
        statuses = {status.value for status in GateStatus}
        if any(value not in statuses for value in state.gates.values()):
            raise ProjectNotFoundError("Project state has an invalid gate status")
