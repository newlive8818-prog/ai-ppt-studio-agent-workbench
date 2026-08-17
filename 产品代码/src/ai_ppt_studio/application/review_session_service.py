"""Revision-safe lifecycle service for authoritative professional review sessions."""

from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.review_commands import (
    fingerprint,
    replay_ref,
    stable_id,
)
from ai_ppt_studio.domains.review.contracts import (
    REVIEW_TYPES,
    validate_review_session,
)
from ai_ppt_studio.errors import (
    ContractValidationError,
    ReviewSourceStaleError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel

REVIEW_SESSION_KIND = "review-session"
SOURCE_SLOTS = {
    "content-full-deck": ("content/reading-blueprint",),
    "visual-professional": ("visual/contract",),
}
TARGET_KINDS = {
    "content-full-deck": {"reading-deck-blueprint"},
    "visual-professional": {"visual-contract"},
}
RECEIPTS = {
    "host-open": ("review-host-open-receipt", "opened"),
    "host-notification": ("review-host-notification-receipt", "sent"),
    "ai": ("review-ai-receipt", "received"),
}
BOUND_SAVED_SLOTS = {
    "visual-professional": {
        "visual/anchor-feedback-batch": "visual-anchor-feedback-batch",
        "visual/contract-review-marks": "visual-contract-review-mark-set",
    }
}


class ReviewSessionService:
    """Own all current-session state; adapters may only supply immutable receipts."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def open_or_resume(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
        target_artifact_ref: str,
        source_version: str,
        source_revision: int,
        open_policy: str,
    ) -> tuple[str, dict[str, Any], KernelState]:
        state = self._state(expected_revision)
        self._review_type(review_type)
        if (
            isinstance(source_revision, bool)
            or not isinstance(source_revision, int)
            or source_revision < 0
            or source_revision > state.revision
        ):
            raise ContractValidationError("source_revision is invalid or in the future")
        target_ref, target = self._current_target(
            state, review_type, target_artifact_ref
        )
        actual_source = str(target.get("source_version") or target_ref)
        if source_version != actual_source:
            raise ReviewSourceStaleError(source_version, actual_source)
        current_ref, current = self._current(state, review_type)
        identity = (target_ref, source_version, source_revision)
        if current and (
            current["target_artifact_ref"],
            current["source_version"],
            current["revision"],
        ) == identity:
            return current_ref, current, state

        now = datetime.now(timezone.utc).isoformat()
        session = validate_review_session(
            {
                "review_session_id": self._session_id(
                    state.project_id, review_type, *identity
                ),
                "review_type": review_type,
                "project_id": state.project_id,
                "target_artifact_ref": target_ref,
                "source_version": source_version,
                "revision": source_revision,
                "status": "ready",
                "open_policy": open_policy,
                "host_open_status": "not-requested",
                "persistence_status": "saved",
                "host_notification_status": "not-requested",
                "ai_receipt_status": "pending",
                "created_at": now,
                "last_opened_at": None,
                "submitted_at": None,
            }
        )
        detached = ()
        if current:
            detached = (
                (
                    REVIEW_SESSION_KIND,
                    validate_review_session(
                        {**current, "status": "superseded", "superseded_at": now},
                        trusted_receipts=True,
                    ),
                ),
            )
        committed = self.kernel.commit(
            command_id=self._text(command_id, "command_id"),
            expected_revision=expected_revision,
            event_type="review.session-opened",
            artifact_updates={self._slot(review_type): (REVIEW_SESSION_KIND, session)},
            detached_artifacts=detached,
        )
        return self._current_result(committed, review_type)

    def record_host_open_receipt(self, **kwargs: Any):
        return self._record_receipt("host-open", **kwargs)

    def record_bridge_host_open(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
        review_session_id: str,
        bridge_session_id: str,
        recorded_at: str,
    ) -> tuple[str, dict[str, Any], KernelState]:
        review_type = self._review_type(review_type)
        review_session_id = self._text(review_session_id, "review_session_id")
        bridge_session_id = self._text(bridge_session_id, "bridge_session_id")
        recorded_at = self._timestamp(recorded_at)
        values = {
            "review_type": review_type,
            "review_session_id": review_session_id,
            "bridge_session_id": bridge_session_id,
            "recorded_at": recorded_at,
        }
        command_fingerprint = fingerprint("record-review-bridge-host-open", values)
        slot = self._slot(review_type)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            session_ref, state = replay
            payload = self.kernel.artifacts.resolve(
                ArtifactReference.parse(session_ref)
            )["payload"]
            return session_ref, validate_review_session(
                payload, trusted_receipts=True
            ), state

        state = self._state(expected_revision)
        _, current = self._require_current(state, review_type)
        if current["review_session_id"] != review_session_id:
            raise ContractValidationError(
                "review_session_id does not match the current session"
            )
        receipt = {
            "receipt_id": stable_id(
                "review-host-open", review_session_id, bridge_session_id
            ),
            "review_session_id": review_session_id,
            "bridge_session_id": bridge_session_id,
            "status": "opened",
            "recorded_at": recorded_at,
        }
        receipt_ref = str(
            self.kernel.artifacts.reference_for("review-host-open-receipt", receipt)
        )
        updated = validate_review_session(
            {
                **current,
                "status": (
                    "opened" if current["status"] == "ready" else current["status"]
                ),
                "host_open_status": "opened",
                "last_opened_at": recorded_at,
                "host_open_receipt_ref": receipt_ref,
            },
            trusted_receipts=True,
        )
        committed = self.kernel.commit(
            command_id=self._text(command_id, "command_id"),
            expected_revision=expected_revision,
            event_type="review.bridge-host-open-recorded",
            artifact_updates={slot: (REVIEW_SESSION_KIND, updated)},
            detached_artifacts=(("review-host-open-receipt", receipt),),
            command_fingerprint=command_fingerprint,
        )
        return self._current_result(committed, review_type)

    def record_host_notification_receipt(self, **kwargs: Any):
        return self._record_receipt("host-notification", **kwargs)

    def record_ai_receipt(self, **kwargs: Any):
        return self._record_receipt("ai", **kwargs)

    def mark_submitted(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
        submitted_at: str,
    ) -> tuple[str, dict[str, Any], KernelState]:
        state = self._state(expected_revision)
        _, current = self._require_current(state, review_type)
        if current["status"] == "submitted":
            return self._current_result(state, review_type)
        updated = validate_review_session(
            {**current, "status": "submitted", "submitted_at": submitted_at},
            trusted_receipts=True,
        )
        committed = self.kernel.commit(
            command_id=self._text(command_id, "command_id"),
            expected_revision=expected_revision,
            event_type="review.session-submitted",
            artifact_updates={self._slot(review_type): (REVIEW_SESSION_KIND, updated)},
        )
        return self._current_result(committed, review_type)

    def supersede_current(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
    ) -> KernelState:
        state = self._state(expected_revision)
        _, current = self._require_current(state, review_type)
        superseded = validate_review_session(
            {
                **current,
                "status": "superseded",
                "superseded_at": datetime.now(timezone.utc).isoformat(),
            },
            trusted_receipts=True,
        )
        return self.kernel.commit(
            command_id=self._text(command_id, "command_id"),
            expected_revision=expected_revision,
            event_type="review.session-superseded",
            artifact_updates={},
            detached_artifacts=((REVIEW_SESSION_KIND, superseded),),
            artifact_removals=(self._slot(review_type),),
        )

    def _record_receipt(
        self,
        receipt_type: str,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
        receipt_ref: str,
        review_session_id: str = "",
        source_version: str = "",
        saved_artifact_ref: str = "",
    ) -> tuple[str, dict[str, Any], KernelState]:
        review_type = self._review_type(review_type)
        bound_receipt = (
            receipt_type in {"host-notification", "ai"}
            and review_type in BOUND_SAVED_SLOTS
        )
        values = {
            "receipt_type": receipt_type,
            "review_type": review_type,
            "receipt_ref": receipt_ref,
        }
        if bound_receipt:
            review_session_id = self._text(
                review_session_id, "review_session_id"
            )
            source_version = self._text(source_version, "source_version")
            saved_artifact_ref = self._text(
                saved_artifact_ref, "saved_artifact_ref"
            )
            values.update(
                {
                    "review_session_id": review_session_id,
                    "source_version": source_version,
                    "saved_artifact_ref": saved_artifact_ref,
                }
            )
        command_fingerprint = fingerprint(
            f"record-review-{receipt_type}-receipt", values
        )
        slot = self._slot(review_type)
        replay = replay_ref(self.kernel, command_id, command_fingerprint, slot)
        if replay:
            session_ref, replay_state = replay
            payload = self.kernel.artifacts.resolve(
                ArtifactReference.parse(session_ref)
            )["payload"]
            return session_ref, validate_review_session(
                payload, trusted_receipts=True
            ), replay_state

        state = self._state(expected_revision)
        _, current = self._require_current(state, review_type)
        kind, status = RECEIPTS[receipt_type]
        reference = ArtifactReference.parse(receipt_ref)
        if reference.kind != kind:
            raise ContractValidationError(f"receipt_ref must reference {kind}")
        receipt = self.kernel.artifacts.resolve(reference)["payload"]
        if (
            receipt.get("review_session_id") != current["review_session_id"]
            or receipt.get("status") != status
        ):
            raise ContractValidationError("Receipt does not match the current session")
        if bound_receipt:
            if (
                current["review_session_id"] != review_session_id
                or current["source_version"] != source_version
            ):
                raise ContractValidationError(
                    "Receipt binding does not match the current review source"
                )
            saved_reference = ArtifactReference.parse(saved_artifact_ref)
            matching_slot = next(
                (
                    saved_slot
                    for saved_slot, saved_kind in BOUND_SAVED_SLOTS[
                        review_type
                    ].items()
                    if saved_reference.kind == saved_kind
                    and state.artifact_heads.get(saved_slot) == saved_artifact_ref
                ),
                "",
            )
            if not matching_slot:
                raise ContractValidationError(
                    "saved_artifact_ref is not a current review artifact"
                )
            if (
                receipt.get("project_id") != state.project_id
                or receipt.get("review_type") != review_type
                or receipt.get("review_session_id") != review_session_id
                or receipt.get("source_version") != source_version
                or receipt.get("saved_artifact_ref") != saved_artifact_ref
            ):
                raise ContractValidationError(
                    "Receipt does not match the saved review artifact"
                )
        recorded_at = self._timestamp(receipt.get("recorded_at"))
        changes = {
            "host-open": {
                "status": "opened" if current["status"] == "ready" else current["status"],
                "host_open_status": "opened",
                "last_opened_at": recorded_at,
                "host_open_receipt_ref": receipt_ref,
            },
            "host-notification": {
                "host_notification_status": "sent",
                "host_notification_receipt_ref": receipt_ref,
                **(
                    {
                        "host_notification_receipts": {
                            **current.get("host_notification_receipts", {}),
                            saved_artifact_ref: receipt_ref,
                        }
                    }
                    if bound_receipt
                    else {}
                ),
            },
            "ai": {
                "ai_receipt_status": "received",
                "ai_receipt_ref": receipt_ref,
                **(
                    {
                        "ai_receipts": {
                            **current.get("ai_receipts", {}),
                            saved_artifact_ref: receipt_ref,
                        }
                    }
                    if bound_receipt
                    else {}
                ),
            },
        }[receipt_type]
        updated = validate_review_session(
            {**current, **changes}, trusted_receipts=True
        )
        committed = self.kernel.commit(
            command_id=self._text(command_id, "command_id"),
            expected_revision=expected_revision,
            event_type=f"review.{receipt_type}-receipt-recorded",
            artifact_updates={slot: (REVIEW_SESSION_KIND, updated)},
            command_fingerprint=command_fingerprint,
        )
        return self._current_result(committed, review_type)

    def _current_target(
        self, state: KernelState, review_type: str, supplied_ref: str
    ) -> tuple[str, dict[str, Any]]:
        current_ref = next(
            (
                state.artifact_heads[slot]
                for slot in SOURCE_SLOTS[review_type]
                if state.artifact_heads.get(slot)
            ),
            "",
        )
        if supplied_ref != current_ref:
            raise ReviewSourceStaleError(supplied_ref, current_ref)
        try:
            reference = ArtifactReference.parse(supplied_ref)
            envelope = self.kernel.artifacts.resolve(reference)
        except Exception as error:
            raise ContractValidationError("target_artifact_ref cannot be resolved") from error
        if reference.kind not in TARGET_KINDS[review_type]:
            raise ContractValidationError("target_artifact_ref has the wrong kind")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise ContractValidationError("Review target payload must be an object")
        return supplied_ref, copy.deepcopy(payload)

    def _current(
        self, state: KernelState, review_type: str
    ) -> tuple[str, dict[str, Any] | None]:
        ref = state.review_session_ref(review_type)
        if not ref:
            return "", None
        reference = ArtifactReference.parse(ref)
        if reference.kind != REVIEW_SESSION_KIND:
            raise ContractValidationError("Current review session has the wrong kind")
        payload = self.kernel.artifacts.resolve(reference).get("payload")
        return ref, validate_review_session(payload, trusted_receipts=True)

    def _require_current(
        self, state: KernelState, review_type: str
    ) -> tuple[str, dict[str, Any]]:
        self._review_type(review_type)
        ref, session = self._current(state, review_type)
        if session is None:
            raise ContractValidationError("No current ReviewSession")
        return ref, session

    def _current_result(
        self, state: KernelState, review_type: str
    ) -> tuple[str, dict[str, Any], KernelState]:
        ref, session = self._require_current(state, review_type)
        return ref, session, state

    def _state(self, expected_revision: int) -> KernelState:
        state = self.kernel.load()
        if state.revision != expected_revision:
            raise RevisionConflictError(expected_revision, state.revision)
        return state

    @staticmethod
    def _review_type(review_type: str) -> str:
        if review_type not in REVIEW_TYPES:
            raise ContractValidationError("review_type is not a professional review type")
        return review_type

    @staticmethod
    def _slot(review_type: str) -> str:
        return f"review/session/{review_type}"

    @staticmethod
    def _session_id(project_id: str, review_type: str, *identity: object) -> str:
        digest = hashlib.sha256(
            "\0".join(map(str, (project_id, review_type, *identity))).encode()
        ).hexdigest()[:20]
        return f"{review_type}-{digest}"

    @staticmethod
    def _text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ContractValidationError(f"{field} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _timestamp(value: object) -> str:
        if not isinstance(value, str):
            raise ContractValidationError("Receipt recorded_at is invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ContractValidationError("Receipt recorded_at is invalid") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ContractValidationError("Receipt recorded_at requires a timezone")
        return value
