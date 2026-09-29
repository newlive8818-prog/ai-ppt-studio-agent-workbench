"""Read-only confirmation ledgers and legacy framework-history validation."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ConfirmationTransactionError,
    ContractValidationError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState


CONFIRMATION_LEDGER_SLOT = "kernel/confirmation-consumptions"
CONFIRMATION_LEDGER_KIND = "confirmation-consumption-ledger"


class ConfirmationHistoryMixin:
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
            if heads.get("content/framework-draft"):
                _epoch, legacy_consumed, legacy_bindings = (
                    self._infer_legacy_framework_history(
                        state, heads, artifact_bindings={}
                    )
                )
                for key, value in legacy_consumed.items():
                    previous = consumed.get(key)
                    if previous is not None and previous != value:
                        raise ConfirmationTransactionError(
                            "CONFIRMATION_HISTORY_CORRUPT",
                            "Legacy confirmation consumption history conflicts",
                        )
                    consumed[key] = value
                artifact_bindings.update(legacy_bindings)
            return consumed, artifact_bindings
        try:
            reference = ArtifactReference.parse(ledger_ref)
            if reference.kind != CONFIRMATION_LEDGER_KIND:
                raise ValueError("Confirmation ledger artifact kind is invalid")
            payload = self.artifacts.resolve(reference)["payload"]
            if not isinstance(payload, dict):
                raise TypeError("Confirmation ledger payload is invalid")
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Confirmation ledger is unreadable",
            ) from error
        ledger_consumed = payload.get("consumed")
        ledger_bindings = payload.get("artifact_bindings", {})
        has_framework_epoch = "framework_reset_revision" in payload
        framework_reset_revision = payload.get("framework_reset_revision", 0)
        if (
            isinstance(framework_reset_revision, bool)
            or not isinstance(framework_reset_revision, int)
            or framework_reset_revision < 0
            or framework_reset_revision > state.revision
            or (
                bool(heads.get("content/framework-draft"))
                and has_framework_epoch
                and framework_reset_revision < 1
            )
        ):
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Framework reset epoch is invalid",
            )
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
        if heads.get("content/framework-draft") and not has_framework_epoch:
            _epoch, historical_consumed, historical_bindings = (
                self._infer_legacy_framework_history(
                state,
                heads,
                artifact_bindings=artifact_bindings,
                )
            )
            if (
                ledger_consumed != historical_consumed
                or ledger_bindings != historical_bindings
            ):
                raise ConfirmationTransactionError(
                    "CONFIRMATION_HISTORY_CORRUPT",
                    "Legacy ledger does not exactly match validated history",
                )
        return consumed, artifact_bindings

    def _framework_reset_revision(
        self, state: KernelState, heads: dict[str, str]
    ) -> int:
        ledger_ref = heads.get(CONFIRMATION_LEDGER_SLOT, "")
        if not ledger_ref:
            if heads.get("content/framework-draft"):
                return self._infer_legacy_framework_reset_revision(
                    state, heads, artifact_bindings={}
                )
            return 0
        try:
            reference = ArtifactReference.parse(ledger_ref)
            if reference.kind != CONFIRMATION_LEDGER_KIND:
                raise ValueError("Confirmation ledger kind is invalid")
            payload = self.artifacts.resolve(reference)["payload"]
            if not isinstance(payload, dict):
                raise TypeError("Confirmation ledger payload is invalid")
            if "framework_reset_revision" not in payload:
                consumed = payload.get("consumed")
                bindings = payload.get("artifact_bindings", {})
                if not isinstance(consumed, dict) or not isinstance(bindings, dict):
                    raise ValueError("Legacy confirmation ledger is invalid")
                return self._infer_legacy_framework_reset_revision(
                    state,
                    heads,
                    artifact_bindings=bindings,
                )
            value = payload["framework_reset_revision"]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > state.revision
            ):
                raise ValueError("Framework reset epoch is invalid")
            if heads.get("content/framework-draft") and value < 1:
                raise ValueError("Framework reset epoch is missing")
            return value
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Framework reset epoch is unreadable",
            ) from error

    def _needs_framework_epoch_migration(
        self, state: KernelState, heads: dict[str, str]
    ) -> bool:
        if not heads.get("content/framework-draft"):
            return False
        ledger_ref = heads.get(CONFIRMATION_LEDGER_SLOT, "")
        if not ledger_ref:
            self._infer_legacy_framework_reset_revision(
                state, heads, artifact_bindings={}
            )
            return True
        try:
            reference = ArtifactReference.parse(ledger_ref)
            if reference.kind != CONFIRMATION_LEDGER_KIND:
                raise ValueError("Confirmation ledger kind is invalid")
            payload = self.artifacts.resolve(reference)["payload"]
            if not isinstance(payload, dict):
                raise TypeError("Confirmation ledger payload is invalid")
        except (ArtifactReferenceError, KeyError, TypeError, ValueError) as error:
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Confirmation ledger is unreadable",
            ) from error
        if "framework_reset_revision" in payload:
            return False
        _epoch, historical_consumed, historical_bindings = (
            self._infer_legacy_framework_history(
            state,
            heads,
            artifact_bindings=payload.get("artifact_bindings", {}),
            )
        )
        if (
            payload.get("consumed") != historical_consumed
            or payload.get("artifact_bindings", {}) != historical_bindings
        ):
            raise ConfirmationTransactionError(
                "CONFIRMATION_HISTORY_CORRUPT",
                "Legacy ledger does not exactly match validated history",
            )
        return True

    def _infer_legacy_framework_reset_revision(
        self,
        state: KernelState,
        heads: dict[str, str],
        *,
        artifact_bindings: object,
    ) -> int:
        return self._infer_legacy_framework_history(
            state,
            heads,
            artifact_bindings=artifact_bindings,
        )[0]

    def _infer_legacy_framework_history(
        self,
        state: KernelState,
        heads: dict[str, str],
        *,
        artifact_bindings: object,
    ) -> tuple[int, dict[str, str], dict[str, str]]:
        """Infer a pre-epoch framework generation from immutable history.

        Legacy schema-3 projects did not persist a framework epoch.  They are
        accepted only when the complete event chain is continuous, internally
        identified, and ends at the exact current state.  Any ambiguity remains
        fail-closed.
        """

        framework_ref = heads.get("content/framework-draft", "")
        if not framework_ref:
            return 0, {}, {}
        if not isinstance(artifact_bindings, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in artifact_bindings.items()
        ):
            raise ConfirmationTransactionError(
                "CONFIRMATION_LEDGER_CORRUPT",
                "Legacy confirmation bindings are invalid",
            )
        try:
            framework_reference = ArtifactReference.parse(framework_ref)
            if framework_reference.kind != "content-framework-draft":
                raise ValueError("Current framework kind is invalid")
            self.artifacts.resolve(framework_reference)
            event_paths = sorted(self.events_root.glob("r*.json"))
            if len(event_paths) != state.revision:
                raise ValueError("Event history is incomplete")
            events: list[dict[str, Any]] = []
            transaction_ids: set[str] = set()
            historical_consumed: dict[str, str] = {}
            historical_bindings: dict[str, str] = {}
            for expected_revision, event_path in enumerate(event_paths, start=1):
                if event_path.name != f"r{expected_revision:08d}.json":
                    raise ValueError("Event filename is not continuous")
                event = json.loads(event_path.read_text(encoding="utf-8"))
                if event.get("revision") != expected_revision:
                    raise ValueError("Event revision is not continuous")
                transaction_id = str(event.get("transaction_id") or "")
                uuid.UUID(transaction_id)
                if transaction_id in transaction_ids:
                    raise ValueError("Event transaction identity is duplicated")
                transaction_ids.add(transaction_id)
                command_id = str(event.get("command_id") or "")
                if (
                    not command_id
                    or state.processed_commands.get(command_id)
                    != expected_revision
                ):
                    raise ValueError("Event command identity is invalid")
                event_heads = event.get("artifact_heads")
                if not isinstance(event_heads, dict) or any(
                    not isinstance(slot, str) or not isinstance(value, str)
                    for slot, value in event_heads.items()
                ):
                    raise ValueError("Event artifact heads are invalid")
                event_consumed = event.get("confirmation_consumptions", {})
                event_bindings = event.get(
                    "confirmation_artifact_bindings", {}
                )
                if (
                    not isinstance(event_consumed, dict)
                    or not isinstance(event_bindings, dict)
                    or any(
                        not isinstance(key, str) or not isinstance(value, str)
                        for mapping in (event_consumed, event_bindings)
                        for key, value in mapping.items()
                    )
                ):
                    raise ValueError("Event confirmation history is invalid")
                for key, value in event_consumed.items():
                    previous = historical_consumed.get(key)
                    if previous is not None and previous != value:
                        raise ValueError("Confirmation consumption history conflicts")
                    historical_consumed[key] = value
                for key, value in event_bindings.items():
                    previous = historical_bindings.get(key)
                    if previous is not None and previous != value:
                        raise ValueError("Confirmation binding history conflicts")
                    historical_bindings[key] = value
                events.append(event)
            if (
                not events
                or events[-1]["transaction_id"] != state.last_transaction_id
                or events[-1]["artifact_heads"] != heads
            ):
                raise ValueError("Event history does not terminate at current state")

            reset_revisions = [
                int(event["revision"])
                for event in events
                if event.get("event_type") == "content.framework-draft-saved"
                and event["artifact_heads"].get("content/framework-draft")
                == framework_ref
            ]
            if not reset_revisions:
                raise ValueError("Current framework installation is not provable")
            reset_revision = reset_revisions[-1]

            if artifact_bindings and artifact_bindings != historical_bindings:
                raise ValueError("Legacy ledger bindings conflict with event history")

            confirmation_ref = heads.get("content/framework-confirmation", "")
            authorization_ref = heads.get(
                "content/full-deck-expansion-authorization", ""
            )
            confirmation_revision = self._legacy_binding_revision(
                events,
                slot="content/framework-confirmation",
                reference=confirmation_ref,
                event_type="content.framework-confirmed",
                artifact_bindings=historical_bindings,
            )
            authorization_revision = self._legacy_binding_revision(
                events,
                slot="content/full-deck-expansion-authorization",
                reference=authorization_ref,
                event_type="content.full-deck-expansion-authorized",
                artifact_bindings=historical_bindings,
            )
            if confirmation_ref and confirmation_revision <= reset_revision:
                raise ValueError("Framework confirmation predates current reset")
            if authorization_ref and (
                not confirmation_ref
                or authorization_revision <= confirmation_revision
            ):
                raise ValueError("Expansion authorization chronology is invalid")
            return reset_revision, historical_consumed, historical_bindings
        except ConfirmationTransactionError:
            raise
        except (
            ArtifactReferenceError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise ConfirmationTransactionError(
                "CONFIRMATION_HISTORY_CORRUPT",
                "Legacy framework history cannot be proven",
            ) from error

    @staticmethod
    def _legacy_binding_revision(
        events: list[dict[str, Any]],
        *,
        slot: str,
        reference: str,
        event_type: str,
        artifact_bindings: dict[str, str],
    ) -> int:
        if not reference:
            return 0
        revisions = [
            int(event["revision"])
            for event in events
            if event.get("event_type") == event_type
            and event["artifact_heads"].get(slot) == reference
            and reference
            in dict(event.get("confirmation_artifact_bindings") or {}).values()
        ]
        if not revisions or reference not in artifact_bindings.values():
            raise ValueError(f"Current {slot} binding is not provable")
        return revisions[-1]

    def current_framework_reset_revision(self) -> int:
        """Return the kernel-owned irreversible framework reset epoch."""

        state = self.load()
        return self._framework_reset_revision(
            state, dict(state.artifact_heads)
        )

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
            identity = str(consumption[0]).strip()
            owner = str(consumption[1]).strip()
            sealed_payload = json.loads(str(consumption[3]))
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
                and all(
                    payload.get(key) == value
                    for key, value in sealed_payload.items()
                )
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

    def _validate_framework_reset_contract(
        self,
        *,
        state: KernelState,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
        artifact_removals: tuple[str, ...],
        confirmation_consumptions: tuple[object, ...],
        reset_revision: int,
        framework_ref: str,
        mission_confirmation_ref: str,
    ) -> None:
        current_content = {
            slot for slot in state.artifact_heads if slot.startswith("content/")
        }
        expected_removals = current_content - {"content/framework-draft"}
        candidate_ref = str(
            self._framework_candidate_reference(
                state.project_id,
                artifact_updates,
            )
        )
        payload = artifact_updates.get(
            "content/framework-draft", ("", {})
        )[1]
        try:
            from ai_ppt_studio.domains.mission.contracts import (
                validate_mission_confirmation,
                validate_mission_draft,
            )
            from ai_ppt_studio.adapters.legacy.framework_v16 import (
                validate_legacy_framework_draft,
            )
            from ai_ppt_studio.kernel.references import ArtifactReference

            normalized = validate_legacy_framework_draft(payload)
            mission_reference = ArtifactReference.parse(
                mission_confirmation_ref
            )
            current_mission_ref = state.artifact_heads.get(
                "mission/confirmation", ""
            )
            mission_envelope = self.artifacts.resolve(mission_reference)
            mission_confirmation = dict(mission_envelope["payload"])
            normalized_confirmation = validate_mission_confirmation(
                mission_confirmation
            )
            mission_draft_ref = state.artifact_heads.get(
                "mission/draft", ""
            )
            draft_reference = ArtifactReference.parse(mission_draft_ref)
            draft_envelope = self.artifacts.resolve(draft_reference)
            mission_draft = dict(draft_envelope["payload"])
            normalized_draft = validate_mission_draft(mission_draft)
            action_ref = str(
                mission_confirmation.get("user_action_ref") or ""
            ).strip()
            message_ref = str(
                mission_confirmation.get("user_message_ref") or ""
            ).strip()
            identities = tuple(
                value for value in (action_ref, message_ref) if value
            )
            material_mode = str(
                mission_confirmation.get("material_mode") or ""
            )
            current_materials = state.artifact_heads.get("materials", "")
            if material_mode == "materials-provided":
                material_reference = ArtifactReference.parse(current_materials)
                material_envelope = self.artifacts.resolve(material_reference)
                material_binding_valid = (
                    bool(current_materials)
                    and material_reference.kind == "material-inventory"
                    and material_envelope.get("project_id") == state.project_id
                    and mission_confirmation.get("material_inventory_ref")
                    == current_materials
                )
            else:
                expected_empty = (
                    "empty-materials:"
                    + hashlib.sha256(
                        f"{state.project_id}\0{mission_draft_ref}".encode(
                            "utf-8"
                        )
                    ).hexdigest()
                )
                material_binding_valid = (
                    material_mode == "no-materials-confirmed"
                    and not current_materials
                    and mission_confirmation.get("empty_material_identity")
                    == expected_empty
                )
            domain_valid = (
                normalized == payload
                and mission_reference.kind == "mission-confirmation"
                and current_mission_ref == mission_confirmation_ref
                and mission_envelope.get("project_id") == state.project_id
                and mission_envelope.get("kind") == "mission-confirmation"
                and normalized_confirmation == mission_confirmation
                and draft_reference.kind == "mission-draft"
                and draft_envelope.get("project_id") == state.project_id
                and draft_envelope.get("kind") == "mission-draft"
                and normalized_draft == mission_draft
                and mission_draft.get("status") == "confirmable"
                and mission_confirmation.get("mission_draft_ref")
                == mission_draft_ref
                and len(identities) == 1
                and material_binding_valid
            )
        except (
            ArtifactReferenceError,
            ContractValidationError,
            KeyError,
            TypeError,
            ValueError,
        ):
            domain_valid = False
        valid = (
            domain_valid
            and reset_revision == state.revision
            and set(artifact_updates) == {"content/framework-draft"}
            and artifact_updates["content/framework-draft"][0]
            == "content-framework-draft"
            and framework_ref == candidate_ref
            and payload.get("mission_confirmation_ref")
            == mission_confirmation_ref
            and state.artifact_heads.get("mission/confirmation")
            == mission_confirmation_ref
            and set(artifact_removals) == expected_removals
            and not confirmation_consumptions
        )
        if not valid:
            raise ConfirmationTransactionError(
                "CONTENT_FRAMEWORK_RESET_INVALID",
                "Content framework reset transaction contract is invalid",
            )

    @staticmethod
    def _framework_candidate_reference(
        project_id: str,
        artifact_updates: dict[str, tuple[str, dict[str, Any]]],
    ) -> object:
        from ai_ppt_studio.kernel.artifacts import canonical_json
        from ai_ppt_studio.kernel.references import ArtifactReference

        kind, payload = artifact_updates.get(
            "content/framework-draft", ("", {})
        )
        envelope = {
            "project_id": project_id,
            "kind": kind,
            "payload": payload,
        }
        return ArtifactReference(
            kind=kind,
            sha256=hashlib.sha256(canonical_json(envelope)).hexdigest(),
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
