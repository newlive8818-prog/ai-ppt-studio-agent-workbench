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
    ConfirmationTransactionError,
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
        confirmation_consumptions: tuple[object, ...] = (),
        content_framework_reset: object | None = None,
        gate_mutation: object | None = None,
    ) -> KernelState:
        with self._locked():
            state = self.load()
            if command_id in state.processed_commands:
                if confirmation_consumptions:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_COMMAND_REPLAYED",
                        "Confirmation identity cannot replay a processed command"
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
            try:
                from ai_ppt_studio.application.scoped_confirmation import (
                    validate_confirmation_consumption,
                    validate_content_framework_reset,
                )

                trusted_consumptions = tuple(
                    validate_confirmation_consumption(value)
                    for value in confirmation_consumptions
                )
                reset_mutation = (
                    validate_content_framework_reset(content_framework_reset)
                    if content_framework_reset is not None
                    else None
                )
            except ValueError as error:
                raise ConfirmationTransactionError(
                    "CONFIRMATION_AUTHORITY_INVALID", str(error)
                ) from None
            for consumption in trusted_consumptions:
                if consumption.challenge_revision != state.revision:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_CHALLENGE_STALE",
                        "Confirmation challenge revision is stale",
                    )
            if reset_mutation is not None:
                self._validate_framework_reset_contract(
                    state=state,
                    artifact_updates=artifact_updates,
                    artifact_removals=artifact_removals,
                    confirmation_consumptions=trusted_consumptions,
                    reset_revision=reset_mutation.revision,
                )
            authorized_gate = (
                validate_gate_mutation(gate_mutation)
                if gate_mutation is not None
                else None
            )
            if reset_mutation is not None and authorized_gate is not None:
                raise ValueError(
                    "Content framework reset cannot include a gate mutation"
                )

            consumed, artifact_bindings = self._confirmation_ledger(state, heads)
            consumption_updates: dict[str, str] = {}
            for consumption in trusted_consumptions:
                identity = consumption.identity.strip()
                owner = consumption.owner.strip()
                if not identity or not owner:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_IDENTITY_INVALID",
                        "Confirmation consumption identity and owner are required"
                    )
                identity_key = hashlib.sha256(
                    identity.encode("utf-8")
                ).hexdigest()
                previous = consumed.get(identity_key)
                if previous is not None:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_IDENTITY_REPLAYED",
                        "Confirmation identity was already consumed by "
                        f"{previous}"
                    )
                historical_owner = self._historical_confirmation_owner(
                    identity,
                    heads,
                    max_revision=state.revision,
                )
                if historical_owner:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_IDENTITY_REPLAYED",
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
            candidate_references = {
                slot: self.artifacts.reference_for(kind, payload)
                for slot, (kind, payload) in artifact_updates.items()
            }
            for slot, reference in candidate_references.items():
                heads[slot] = str(reference)
            binding_updates = self._confirmation_artifact_bindings(
                artifact_updates=artifact_updates,
                heads=heads,
                confirmation_consumptions=trusted_consumptions,
            )
            artifact_bindings.update(binding_updates)
            ledger_payload = (
                {
                    "consumed": consumed,
                    "artifact_bindings": artifact_bindings,
                }
                if consumption_updates
                else None
            )
            ledger_reference = (
                self.artifacts.reference_for(
                    CONFIRMATION_LEDGER_KIND,
                    ledger_payload,
                )
                if ledger_payload is not None
                else None
            )
            if ledger_reference is not None:
                heads[CONFIRMATION_LEDGER_SLOT] = str(ledger_reference)

            next_revision = state.revision + 1
            gate_updates = (
                {
                    "G0": "open",
                    "G1": "locked",
                    "G2": "locked",
                    "G3": "locked",
                    "G4": "locked",
                }
                if reset_mutation is not None
                else (
                    dict(authorized_gate.updates) if authorized_gate else {}
                )
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

            for slot, (kind, payload) in artifact_updates.items():
                persisted = self.artifacts.put(kind, payload)
                if persisted != candidate_references[slot]:
                    raise RuntimeError(
                        "Persisted artifact reference differs from candidate"
                    )
            if ledger_payload is not None:
                persisted_ledger = self.artifacts.put(
                    CONFIRMATION_LEDGER_KIND,
                    ledger_payload,
                )
                if persisted_ledger != ledger_reference:
                    raise RuntimeError(
                        "Persisted confirmation ledger reference differs "
                        "from candidate"
                    )
            event = {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "event_type": event_type,
                "revision": next_revision,
                "artifact_heads": heads,
                "artifact_head_removals": removed_heads,
                "confirmation_consumptions": consumption_updates,
                "confirmation_artifact_bindings": binding_updates,
                "gate_updates": gate_updates,
                "gate_evidence_refs": (
                    list(authorized_gate.evidence_refs) if authorized_gate else []
                ),
            }
            atomic_write_json(
                self.events_root / f"r{next_revision:08d}.json", event
            )
            atomic_write_json(self.state_path, committed.as_dict())
            return committed

    def _confirmation_consumptions(
        self, state: KernelState, heads: dict[str, str]
    ) -> dict[str, str]:
        return self._confirmation_ledger(state, heads)[0]

    def _confirmation_ledger(
        self, state: KernelState, heads: dict[str, str]
    ) -> tuple[dict[str, str], dict[str, str]]:
        consumed = dict(
            getattr(state, "consumed_user_confirmations", {})
        )
        artifact_bindings: dict[str, str] = {}
        ledger_ref = heads.get(CONFIRMATION_LEDGER_SLOT, "")
        if not ledger_ref:
            return consumed, artifact_bindings
        from ai_ppt_studio.kernel.references import ArtifactReference

        try:
            reference = ArtifactReference.parse(ledger_ref)
            if reference.kind != CONFIRMATION_LEDGER_KIND:
                raise ValueError("Confirmation ledger artifact kind is invalid")
            payload = self.artifacts.resolve(reference)["payload"]
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Confirmation ledger is unreadable",
            ) from error
        ledger_consumed = payload.get("consumed")
        ledger_bindings = payload.get("artifact_bindings", {})
        if not isinstance(ledger_consumed, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in ledger_consumed.items()
        ):
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Confirmation ledger payload is invalid",
            )
        if not isinstance(ledger_bindings, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in ledger_bindings.items()
        ):
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Confirmation artifact binding ledger is invalid",
            )
        for key, value in ledger_consumed.items():
            previous = consumed.get(key)
            if previous is not None and previous != value:
                raise ConfirmationTransactionError(
                    "CONFIRMATION_LEDGER_CORRUPT",
                    "Confirmation consumption history conflicts",
                )
            consumed[key] = value
        artifact_bindings.update(ledger_bindings)
        return consumed, artifact_bindings

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

    def confirmation_artifact_binding(self, identity: str) -> str:
        """Return the exact artifact atomically written with an identity."""

        state = self.load()
        _consumed, bindings = self._confirmation_ledger(
            state,
            dict(state.artifact_heads),
        )
        return bindings.get(
            hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "",
        )

    def _confirmation_artifact_bindings(
        self,
        *,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        heads: dict[str, str],
        confirmation_consumptions: tuple[object, ...],
    ) -> dict[str, str]:
        bindings: dict[str, str] = {}
        for consumption in confirmation_consumptions:
            identity = str(getattr(consumption, "identity", "")).strip()
            owner = str(getattr(consumption, "owner", "")).strip()
            candidates = [
                heads[slot]
                for slot, (_kind, payload) in artifact_updates.items()
                if payload.get("scope_kind")
                and owner
                == f"{payload.get('scope_kind')}:{payload.get('scope_id')}"
                and identity
                in {
                    str(payload.get("user_action_ref") or ""),
                    str(payload.get("user_message_ref") or ""),
                }
            ]
            if len(candidates) != 1:
                raise ConfirmationTransactionError(
                    "CONFIRMATION_ARTIFACT_BINDING_INVALID",
                    "Confirmation consumption must bind one exact artifact"
                )
            bindings[
                hashlib.sha256(identity.encode("utf-8")).hexdigest()
            ] = candidates[0]
        return bindings

    @staticmethod
    def _validate_framework_reset_contract(
        *,
        state: KernelState,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        artifact_removals: tuple[str, ...],
        confirmation_consumptions: tuple[object, ...],
        reset_revision: int,
    ) -> None:
        current_content = {
            slot for slot in state.artifact_heads if slot.startswith("content/")
        }
        expected_removals = current_content - {"content/framework-draft"}
        valid = (
            reset_revision == state.revision
            and set(artifact_updates) == {"content/framework-draft"}
            and artifact_updates["content/framework-draft"][0]
            == "content-framework-draft"
            and set(artifact_removals) == expected_removals
            and not confirmation_consumptions
        )
        if not valid:
            raise ConfirmationTransactionError(
                "CONTENT_FRAMEWORK_RESET_INVALID",
                "Content framework reset transaction contract is invalid",
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
                    if revision > max_revision:
                        continue
                    if not isinstance(event_heads, dict):
                        raise ValueError("event artifact_heads is invalid")
                except (
                    OSError,
                    json.JSONDecodeError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as error:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_HISTORY_CORRUPT",
                        f"Confirmation history is unreadable: {event_path.name}",
                    ) from error
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
                ) as error:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_HISTORY_CORRUPT",
                        "Historical confirmation artifact is unreadable",
                    ) from error
                if identity in {
                    str(payload.get("user_action_ref") or ""),
                    str(payload.get("user_message_ref") or ""),
                }:
                    return slot
        return ""
