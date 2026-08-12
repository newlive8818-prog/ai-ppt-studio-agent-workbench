"""Revision-safe logical transactions for the schema 3.0 project kernel."""

from __future__ import annotations

import fcntl
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from ai_ppt_studio.errors import ProjectIdentityError, RevisionConflictError
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.artifacts import ArtifactRepository
from ai_ppt_studio.kernel.gates import validate_gate_mutation
from ai_ppt_studio.kernel.state import KernelState


class ProjectKernel:
    """Commit artifacts and events before atomically exposing new state."""

    def __init__(self, project_root: Path, *, project_id: str) -> None:
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.state_path = self.project_root / "kernel" / "state.json"
        self.events_root = self.project_root / "kernel" / "events"
        self.lock_path = self.project_root / "kernel" / "write.lock"
        self.artifacts = ArtifactRepository(
            self.project_root, project_id=project_id
        )

    @classmethod
    def initialize(cls, project_root: Path, *, project_id: str) -> "ProjectKernel":
        kernel = cls(project_root, project_id=project_id)
        if not kernel.state_path.exists():
            atomic_write_json(
                kernel.state_path, KernelState.initial(project_id).as_dict()
            )
        return kernel

    def load(self) -> KernelState:
        state = KernelState.from_dict(
            json.loads(self.state_path.read_text(encoding="utf-8"))
        )
        if state.project_id != self.project_id:
            raise ProjectIdentityError(
                f"Kernel belongs to {state.project_id}, not {self.project_id}"
            )
        return state

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def commit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        gate_mutation: object | None = None,
    ) -> KernelState:
        with self._locked():
            state = self.load()
            if command_id in state.processed_commands:
                return state
            if state.revision != expected_revision:
                raise RevisionConflictError(expected_revision, state.revision)

            transaction_id = str(uuid.uuid4())
            heads = dict(state.artifact_heads)
            for slot, (kind, payload) in artifact_updates.items():
                heads[slot] = str(self.artifacts.put(kind, payload))

            next_revision = state.revision + 1
            authorized_gate = (
                validate_gate_mutation(gate_mutation)
                if gate_mutation is not None
                else None
            )
            event = {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "event_type": event_type,
                "revision": next_revision,
                "artifact_heads": heads,
                "gate_updates": (
                    dict(authorized_gate.updates) if authorized_gate else {}
                ),
                "gate_evidence_refs": (
                    list(authorized_gate.evidence_refs) if authorized_gate else []
                ),
            }
            atomic_write_json(
                self.events_root / f"r{next_revision:08d}.json", event
            )

            commands = dict(state.processed_commands)
            commands[command_id] = next_revision
            gate_status = dict(state.gate_status)
            if authorized_gate:
                gate_status.update(authorized_gate.updates)
            committed = replace(
                state,
                revision=next_revision,
                artifact_heads=heads,
                gate_status=gate_status,
                processed_commands=commands,
                last_transaction_id=transaction_id,
            )
            atomic_write_json(self.state_path, committed.as_dict())
            return committed
