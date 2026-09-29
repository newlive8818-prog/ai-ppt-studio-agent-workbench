"""Revision-safe logical transactions for the schema 3.0 project kernel."""

from __future__ import annotations

import fcntl
import hashlib
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContractValidationError,
    ProjectIdentityError,
    RevisionConflictError,
)
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.artifacts import ArtifactRepository
from ai_ppt_studio.kernel.confirmation_history import (
    CONFIRMATION_LEDGER_KIND,
    CONFIRMATION_LEDGER_SLOT,
    ConfirmationHistoryMixin,
)
from ai_ppt_studio.kernel.gates import validate_gate_mutation
from ai_ppt_studio.kernel.persistence import PersistenceMixin
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState


_COMMAND_FINGERPRINT: ContextVar[str] = ContextVar(
    "ai_ppt_studio_command_fingerprint", default=""
)


class ProjectKernel(PersistenceMixin, ConfirmationHistoryMixin):
    """Commit artifacts and events before atomically exposing new state."""

    def __init__(self, project_root: Path, *, project_id: str) -> None:
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.state_path = self.project_root / "kernel" / "state.json"
        self.events_root = self.project_root / "kernel" / "events"
        self.lock_path = self.project_root / "kernel" / "write.lock"
        self.result_lock_path = self.project_root / "kernel" / "result.lock"
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

    def _validate_current_authority(self, state: KernelState) -> None:
        """Fail closed when the exposed state, receipt, or heads were corrupted."""

        if state.revision:
            try:
                event = json.loads(
                    (self.events_root / f"r{state.revision:08d}.json").read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, json.JSONDecodeError) as error:
                raise ContractValidationError(
                    "Current transaction receipt is unavailable"
                ) from error
            command_id = event.get("command_id")
            if (
                event.get("revision") != state.revision
                or event.get("transaction_id") != state.last_transaction_id
                or event.get("artifact_heads") != state.artifact_heads
                or not isinstance(command_id, str)
                or state.processed_commands.get(command_id) != state.revision
            ):
                raise ContractValidationError(
                    "Current transaction receipt does not match kernel state"
                )
        try:
            for value in state.artifact_heads.values():
                self.artifacts.resolve(ArtifactReference.parse(value))
        except (ArtifactReferenceError, TypeError, ValueError) as error:
            raise ContractValidationError(
                "Current artifact authority is unavailable or corrupt"
            ) from error

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def semantic_command(self, fingerprint: str) -> Iterator[None]:
        """Bind trusted request semantics to all commits in this call context."""

        if not fingerprint:
            yield
            return
        token = _COMMAND_FINGERPRINT.set(fingerprint)
        self.result_lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.result_lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                _COMMAND_FINGERPRINT.reset(token)

    def commit(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        detached_artifacts: tuple[tuple[str, dict[str, Any]], ...] = (),
        artifact_removals: tuple[str, ...] = (),
        confirmation_consumptions: tuple[object, ...] = (),
        content_framework_reset: object | None = None,
        gate_mutation: object | None = None,
        command_fingerprint: str = "",
    ) -> KernelState:
        command_fingerprint = command_fingerprint or _COMMAND_FINGERPRINT.get()
        with self._locked():
            original_state_existed = self.state_path.exists()
            original_state_bytes = (
                self.state_path.read_bytes() if original_state_existed else b""
            )
            state = self.load()
            self._validate_current_authority(state)
            if command_id in state.processed_commands:
                if confirmation_consumptions:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_COMMAND_REPLAYED",
                        "Confirmation identity cannot replay a processed command"
                    )
                if command_fingerprint:
                    revision = state.processed_commands[command_id]
                    try:
                        event = json.loads(
                            (self.events_root / f"r{revision:08d}.json").read_text(
                                encoding="utf-8"
                            )
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        raise ContractValidationError(
                            "Processed command receipt is unavailable"
                        ) from exc
                    if event.get("command_fingerprint") != command_fingerprint:
                        raise ContractValidationError(
                            "Processed command has different semantics"
                        )
                return state
            if state.revision != expected_revision:
                raise RevisionConflictError(expected_revision, state.revision)
            if state.revision >= (2**53) - 1:
                raise ContractValidationError(
                    "Current revision has no exactly representable successor"
                )

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
                reset_claim = (
                    validate_content_framework_reset(content_framework_reset)
                    if content_framework_reset is not None
                    else None
                )
            except ValueError as error:
                raise ConfirmationTransactionError(
                    "CONFIRMATION_AUTHORITY_INVALID", str(error)
                ) from None
            for (
                _identity,
                _owner,
                challenge_revision,
                _payload_seal,
            ) in trusted_consumptions:
                if challenge_revision != state.revision:
                    raise ConfirmationTransactionError(
                        "CONFIRMATION_CHALLENGE_STALE",
                        "Confirmation challenge revision is stale",
                    )
            if reset_claim is not None:
                reset_revision, framework_ref, mission_confirmation_ref = (
                    reset_claim
                )
                self._validate_framework_reset_contract(
                    state=state,
                    artifact_updates=artifact_updates,
                    artifact_removals=artifact_removals,
                    confirmation_consumptions=trusted_consumptions,
                    reset_revision=reset_revision,
                    framework_ref=framework_ref,
                    mission_confirmation_ref=mission_confirmation_ref,
                )
            authorized_gate = (
                validate_gate_mutation(gate_mutation)
                if gate_mutation is not None
                else None
            )
            if reset_claim is not None and authorized_gate is not None:
                raise ValueError(
                    "Content framework reset cannot include a gate mutation"
                )

            migrate_framework_epoch = self._needs_framework_epoch_migration(
                state, heads
            )
            consumed, artifact_bindings = self._confirmation_ledger(state, heads)
            current_reset_revision = self._framework_reset_revision(
                state, heads
            )
            consumption_updates: dict[str, str] = {}
            for (
                raw_identity,
                raw_owner,
                _challenge_revision,
                _payload_seal,
            ) in trusted_consumptions:
                identity = raw_identity.strip()
                owner = raw_owner.strip()
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
            if not isinstance(detached_artifacts, tuple):
                raise ContractValidationError(
                    "detached_artifacts must be an immutable tuple"
                )
            detached_definitions: list[
                tuple[str, dict[str, Any], ArtifactReference]
            ] = []
            for index, definition in enumerate(detached_artifacts):
                if (
                    not isinstance(definition, tuple)
                    or len(definition) != 2
                    or not isinstance(definition[0], str)
                    or not definition[0]
                    or not isinstance(definition[1], dict)
                ):
                    raise ContractValidationError(
                        "Each detached artifact must be a (kind, payload) tuple"
                    )
                kind, payload = definition
                try:
                    reference = self.artifacts.reference_for(kind, payload)
                except (ArtifactReferenceError, TypeError, ValueError) as error:
                    raise ContractValidationError(
                        f"Detached artifact {index} is invalid"
                    ) from error
                detached_definitions.append((kind, payload, reference))
            for slot, reference in candidate_references.items():
                heads[slot] = str(reference)
            binding_updates = self._confirmation_artifact_bindings(
                artifact_updates=artifact_updates,
                heads=heads,
                confirmation_consumptions=trusted_consumptions,
            )
            artifact_bindings.update(binding_updates)
            next_revision = state.revision + 1
            framework_reset_revision = (
                next_revision
                if reset_claim is not None
                else current_reset_revision
            )
            ledger_payload = (
                {
                    "consumed": consumed,
                    "artifact_bindings": artifact_bindings,
                    "framework_reset_revision": framework_reset_revision,
                }
                if (
                    consumption_updates
                    or reset_claim is not None
                    or migrate_framework_epoch
                )
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

            gate_updates = (
                {
                    "G0": "open",
                    "G1": "locked",
                    "G2": "locked",
                    "G3": "locked",
                    "G4": "locked",
                }
                if reset_claim is not None
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

            detached_reference_values = list(
                dict.fromkeys(str(item[2]) for item in detached_definitions)
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
                "detached_artifact_refs": detached_reference_values,
                **(
                    {"command_fingerprint": command_fingerprint}
                    if command_fingerprint
                    else {}
                ),
            }
            event_path = self.events_root / f"r{next_revision:08d}.json"
            if event_path.exists():
                raise ContractValidationError(
                    "Next revision event already exists"
                )
            persistence_entries: list[
                tuple[str, dict[str, Any], ArtifactReference]
            ] = [
                (kind, payload, candidate_references[slot])
                for slot, (kind, payload) in artifact_updates.items()
            ]
            persistence_entries.extend(detached_definitions)
            if ledger_payload is not None:
                if ledger_reference is None:
                    raise RuntimeError("Confirmation ledger reference is missing")
                persistence_entries.append(
                    (
                        CONFIRMATION_LEDGER_KIND,
                        ledger_payload,
                        ledger_reference,
                    )
                )
            self._persist_transaction(
                committed=committed,
                event=event,
                event_path=event_path,
                persistence_entries=persistence_entries,
                original_state_existed=original_state_existed,
                original_state_bytes=original_state_bytes,
            )
            return committed
