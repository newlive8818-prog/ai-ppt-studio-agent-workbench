"""Revision-safe logical transactions for the schema 3.0 project kernel."""

from __future__ import annotations

import fcntl
import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ProjectIdentityError,
    RevisionConflictError,
)
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.artifacts import ArtifactRepository
from ai_ppt_studio.kernel.gates import validate_gate_mutation
from ai_ppt_studio.kernel.state import KernelState


CONFIRMATION_LEDGER_SLOT = "kernel/confirmation-consumptions"
CONFIRMATION_LEDGER_KIND = "confirmation-consumption-ledger"


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
        artifact_removals: tuple[str, ...] = (),
        confirmation_consumptions: tuple[tuple[str, str], ...] = (),
        content_framework_reset: bool = False,
        gate_mutation: object | None = None,
    ) -> KernelState:
        with self._locked():
            state = self.load()
            if command_id in state.processed_commands:
                self._validate_idempotent_confirmation_replay(
                    state,
                    confirmation_consumptions,
                )
                return state
            if state.revision != expected_revision:
                raise RevisionConflictError(expected_revision, state.revision)

            transaction_id = str(uuid.uuid4())
            heads = dict(state.artifact_heads)
            if set(artifact_updates).intersection(artifact_removals):
                raise ValueError(
                    "A transaction cannot update and remove the same artifact head"
                )
            if CONFIRMATION_LEDGER_SLOT in artifact_updates or (
                CONFIRMATION_LEDGER_SLOT in artifact_removals
            ):
                raise ValueError("The confirmation ledger is kernel-owned")

            consumed = self._confirmation_consumptions(state, heads)
            consumption_updates: dict[str, str] = {}
            for raw_identity, raw_owner in confirmation_consumptions:
                identity = raw_identity.strip()
                owner = raw_owner.strip()
                if not identity or not owner:
                    raise ValueError(
                        "Confirmation consumption identity and owner are required"
                    )
                identity_key = hashlib.sha256(
                    identity.encode("utf-8")
                ).hexdigest()
                previous = consumed.get(identity_key)
                if previous is not None:
                    raise ValueError(
                        "Confirmation identity was already consumed by "
                        f"{previous}"
                    )
                historical_owner = self._historical_confirmation_owner(
                    identity,
                    heads,
                    max_revision=state.revision,
                )
                if historical_owner:
                    raise ValueError(
                        "Confirmation identity was already consumed by "
                        f"{historical_owner}"
                    )
                consumed[identity_key] = owner
                consumption_updates[identity_key] = owner

            removed_heads = {
                slot: heads.pop(slot)
                for slot in artifact_removals
                if slot in heads
            }
            for slot, (kind, payload) in artifact_updates.items():
                heads[slot] = str(self.artifacts.put(kind, payload))
            if consumption_updates:
                heads[CONFIRMATION_LEDGER_SLOT] = str(
                    self.artifacts.put(
                        CONFIRMATION_LEDGER_KIND,
                        {"consumed": consumed},
                    )
                )

            next_revision = state.revision + 1
            authorized_gate = (
                validate_gate_mutation(gate_mutation)
                if gate_mutation is not None
                else None
            )
            if content_framework_reset and authorized_gate is not None:
                raise ValueError(
                    "Content framework reset cannot include a gate mutation"
                )
            gate_updates = (
                {
                    "G0": "open",
                    "G1": "locked",
                    "G2": "locked",
                    "G3": "locked",
                    "G4": "locked",
                }
                if content_framework_reset
                else (
                    dict(authorized_gate.updates) if authorized_gate else {}
                )
            )
            event = {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "event_type": event_type,
                "revision": next_revision,
                "artifact_heads": heads,
                "artifact_head_removals": removed_heads,
                "confirmation_consumptions": consumption_updates,
                "gate_updates": gate_updates,
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
            gate_status.update(gate_updates)
            state_updates: dict[str, Any] = {
                "revision": next_revision,
                "artifact_heads": heads,
                "gate_status": gate_status,
                "processed_commands": commands,
                "last_transaction_id": transaction_id,
            }
            if hasattr(state, "consumed_user_confirmations"):
                state_updates["consumed_user_confirmations"] = consumed
            committed = replace(state, **state_updates)
            atomic_write_json(self.state_path, committed.as_dict())
            return committed

    def _confirmation_consumptions(
        self, state: KernelState, heads: dict[str, str]
    ) -> dict[str, str]:
        consumed = dict(
            getattr(state, "consumed_user_confirmations", {})
        )
        ledger_ref = heads.get(CONFIRMATION_LEDGER_SLOT, "")
        if not ledger_ref:
            return consumed
        from ai_ppt_studio.kernel.references import ArtifactReference

        reference = ArtifactReference.parse(ledger_ref)
        if reference.kind != CONFIRMATION_LEDGER_KIND:
            raise ValueError("Confirmation ledger artifact kind is invalid")
        payload = self.artifacts.resolve(reference)["payload"]
        ledger_consumed = payload.get("consumed")
        if not isinstance(ledger_consumed, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in ledger_consumed.items()
        ):
            raise ValueError("Confirmation ledger payload is invalid")
        for key, value in ledger_consumed.items():
            previous = consumed.get(key)
            if previous is not None and previous != value:
                raise ValueError("Confirmation consumption history conflicts")
            consumed[key] = value
        return consumed

    def confirmation_owner(self, identity: str) -> str:
        """Return the atomic owner of a consumed trusted identity, if any."""

        state = self.load()
        consumed = self._confirmation_consumptions(
            state,
            dict(state.artifact_heads),
        )
        return consumed.get(
            hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "",
        )

    def _validate_idempotent_confirmation_replay(
        self,
        state: KernelState,
        confirmation_consumptions: tuple[tuple[str, str], ...],
    ) -> None:
        if not confirmation_consumptions:
            return
        consumed = self._confirmation_consumptions(
            state,
            dict(state.artifact_heads),
        )
        for raw_identity, raw_owner in confirmation_consumptions:
            identity = raw_identity.strip()
            owner = raw_owner.strip()
            if not identity or not owner:
                raise ValueError(
                    "Confirmation consumption identity and owner are required"
                )
            identity_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            previous = consumed.get(identity_key)
            if previous is None:
                raise ValueError(
                    "Confirmation identity cannot be added to a processed command"
                )
            if previous != owner:
                raise ValueError(
                    "Confirmation identity was already consumed by "
                    f"{previous}"
                )

    def _historical_confirmation_owner(
        self,
        identity: str,
        heads: dict[str, str],
        *,
        max_revision: int,
    ) -> str:
        from ai_ppt_studio.kernel.references import ArtifactReference

        historical_heads = [heads]
        if self.events_root.is_dir():
            for event_path in sorted(self.events_root.glob("r*.json")):
                try:
                    event = json.loads(event_path.read_text(encoding="utf-8"))
                    revision = int(event["revision"])
                    event_heads = event["artifact_heads"]
                    if revision > max_revision or not isinstance(
                        event_heads, dict
                    ):
                        continue
                except (
                    OSError,
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue
                historical_heads.append(event_heads)
        seen: set[str] = set()
        for snapshot in historical_heads:
            for slot, reference_value in snapshot.items():
                if slot != "mission/confirmation" and not (
                    slot.startswith("gate/")
                    and slot.endswith("/confirmation")
                ):
                    continue
                if reference_value in seen:
                    continue
                seen.add(reference_value)
                try:
                    payload = self.artifacts.resolve(
                        ArtifactReference.parse(reference_value)
                    )["payload"]
                except (
                    ArtifactReferenceError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue
                if identity in {
                    str(payload.get("user_action_ref") or ""),
                    str(payload.get("user_message_ref") or ""),
                }:
                    return slot
        return ""
