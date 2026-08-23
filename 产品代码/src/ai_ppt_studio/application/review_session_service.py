"""Authoritative, revision-safe review-session persistence."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from ai_ppt_studio.domains.review.contracts import (
    OPEN_POLICIES,
    REVIEW_TYPES,
    review_session_identity,
    validate_review_session,
)
from ai_ppt_studio.errors import (
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


ARTIFACT_KIND = "review-session"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _current_slot(review_type: str) -> str:
    return f"review/session/current/{review_type}"


def _identity_slot(review_session_id: str) -> str:
    return f"review/session/{review_session_id}"


def _session_id(identity: tuple[str, str, str, str, int]) -> str:
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "review-session-" + hashlib.sha256(encoded).hexdigest()[:24]


class ReviewSessionService:
    """Own the single current business session for each review surface."""

    def __init__(
        self,
        kernel: ProjectKernel,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.kernel = kernel
        self.clock = clock

    def open_or_resume(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
        target_artifact_ref: str,
        source_version: str,
        target_revision: int,
        open_policy: str,
    ) -> tuple[dict[str, Any], KernelState]:
        if review_type not in REVIEW_TYPES:
            raise ContractValidationError("ReviewSession review_type is invalid")
        if open_policy not in OPEN_POLICIES:
            raise ContractValidationError("ReviewSession open_policy is invalid")
        state = self.kernel.load()
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)

        current = self._current(state, review_type)
        requested_identity = (
            state.project_id,
            review_type,
            str(target_artifact_ref).strip(),
            str(source_version).strip(),
            target_revision,
        )
        if current is not None and review_session_identity(
            current
        ) == requested_identity:
            return current, state

        if target_revision != state.revision:
            raise ContractValidationError(
                "A new ReviewSession must bind the current project revision"
            )
        target_ref = str(target_artifact_ref).strip()
        if not target_ref or target_ref not in state.artifact_heads.values():
            raise ContractValidationError(
                "ReviewSession target artifact must be a current head"
            )
        self.kernel.artifacts.resolve(ArtifactReference.parse(target_ref))

        session_id = _session_id(requested_identity)
        session = validate_review_session(
            {
                "review_session_id": session_id,
                "review_type": review_type,
                "project_id": state.project_id,
                "target_artifact_ref": target_ref,
                "source_version": str(source_version).strip(),
                "revision": target_revision,
                "status": "ready",
                "open_policy": open_policy,
                "host_open_status": (
                    "pending"
                    if open_policy == "foreground-if-waiting"
                    else "not-requested"
                ),
                "persistence_status": "saved",
                "host_notification_status": (
                    "pending"
                    if open_policy == "notify-only"
                    else "not-requested"
                ),
                "ai_receipt_status": "pending",
                "created_at": self.clock(),
                "last_opened_at": None,
                "submitted_at": None,
            },
            current_revision=state.revision,
        )
        updates: dict[str, tuple[str, dict[str, Any]]] = {
            _current_slot(review_type): (ARTIFACT_KIND, session),
            _identity_slot(session_id): (ARTIFACT_KIND, session),
        }
        if current is not None:
            superseded = {**current, "status": "superseded"}
            validate_review_session(
                superseded,
                current_revision=state.revision,
            )
            updates[_identity_slot(current["review_session_id"])] = (
                ARTIFACT_KIND,
                superseded,
            )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="review.session-opened",
            artifact_updates=updates,
        )
        return copy.deepcopy(session), committed

    def record_host_open_receipt(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        result: str,
        receipt_ref: str,
    ) -> tuple[dict[str, Any], KernelState]:
        if result not in {"opened", "failed", "unavailable"}:
            raise ContractValidationError("Host open receipt result is invalid")
        if result == "opened" and not receipt_ref.strip():
            raise ContractValidationError(
                "An opened host result requires a real receipt"
            )
        session, state = self._require_current(
            expected_revision,
            review_session_id,
        )
        updated = {
            **session,
            "host_open_status": result,
            "host_open_receipt_ref": receipt_ref.strip(),
        }
        if result == "opened":
            updated["status"] = "opened"
            updated["last_opened_at"] = self.clock()
        return self._commit_current(
            command_id=command_id,
            expected_revision=state.revision,
            event_type="review.host-open-recorded",
            session=updated,
        )

    def record_host_notification_receipt(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        result: str,
        receipt_ref: str,
    ) -> tuple[dict[str, Any], KernelState]:
        if result not in {"sent", "failed", "unavailable"}:
            raise ContractValidationError(
                "Host notification receipt result is invalid"
            )
        if result == "sent" and not receipt_ref.strip():
            raise ContractValidationError(
                "A sent host notification requires a real receipt"
            )
        session, state = self._require_current(
            expected_revision,
            review_session_id,
        )
        updated = {
            **session,
            "host_notification_status": result,
            "host_notification_receipt_ref": receipt_ref.strip(),
        }
        return self._commit_current(
            command_id=command_id,
            expected_revision=state.revision,
            event_type="review.host-notification-recorded",
            session=updated,
        )

    def record_ai_receipt(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        result: str,
        receipt_ref: str,
    ) -> tuple[dict[str, Any], KernelState]:
        if result not in {"received", "rejected", "unverified"}:
            raise ContractValidationError("AI receipt result is invalid")
        if result in {"received", "rejected"} and not receipt_ref.strip():
            raise ContractValidationError(
                "A verified AI receipt result requires a real receipt"
            )
        session, state = self._require_current(
            expected_revision,
            review_session_id,
        )
        updated = {
            **session,
            "ai_receipt_status": result,
            "ai_receipt_ref": receipt_ref.strip(),
        }
        return self._commit_current(
            command_id=command_id,
            expected_revision=state.revision,
            event_type="review.ai-receipt-recorded",
            session=updated,
        )

    def mark_submitted(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
    ) -> tuple[dict[str, Any], KernelState]:
        session, state = self._require_current(
            expected_revision,
            review_session_id,
        )
        updated = {
            **session,
            "status": "submitted",
            "submitted_at": self.clock(),
        }
        return self._commit_current(
            command_id=command_id,
            expected_revision=state.revision,
            event_type="review.session-submitted",
            session=updated,
        )

    def supersede_current(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_type: str,
    ) -> tuple[dict[str, Any] | None, KernelState]:
        if review_type not in REVIEW_TYPES:
            raise ContractValidationError("ReviewSession review_type is invalid")
        state = self.kernel.load()
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        current = self._current(state, review_type)
        if current is None:
            return None, state
        superseded = validate_review_session(
            {**current, "status": "superseded"},
            current_revision=state.revision,
        )
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type="review.session-superseded",
            artifact_updates={
                _identity_slot(superseded["review_session_id"]): (
                    ARTIFACT_KIND,
                    superseded,
                )
            },
            artifact_removals=(_current_slot(review_type),),
        )
        return copy.deepcopy(superseded), committed

    def _require_current(
        self,
        expected_revision: int,
        review_session_id: str,
    ) -> tuple[dict[str, Any], KernelState]:
        state = self.kernel.load()
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        identity = str(review_session_id).strip()
        if not identity:
            raise ContractValidationError("ReviewSession ID is required")
        identity_ref = state.artifact_heads.get(_identity_slot(identity), "")
        if not identity_ref:
            raise ContractValidationError("ReviewSession is unavailable")
        reference = ArtifactReference.parse(identity_ref)
        if reference.kind != ARTIFACT_KIND:
            raise ContractValidationError("ReviewSession has the wrong kind")
        session = validate_review_session(
            self.kernel.artifacts.resolve(reference)["payload"],
            current_revision=state.revision,
        )
        if session["review_session_id"] != identity:
            raise ContractValidationError("ReviewSession identity is invalid")
        if state.artifact_heads.get(
            _current_slot(session["review_type"]),
            "",
        ) != identity_ref or session["status"] in {"superseded", "expired"}:
            raise ContractValidationError("ReviewSession is not current")
        return session, state

    def _commit_current(
        self,
        *,
        command_id: str,
        expected_revision: int,
        event_type: str,
        session: dict[str, Any],
    ) -> tuple[dict[str, Any], KernelState]:
        normalized = validate_review_session(
            session,
            current_revision=expected_revision,
        )
        updates = {
            _current_slot(normalized["review_type"]): (
                ARTIFACT_KIND,
                normalized,
            ),
            _identity_slot(normalized["review_session_id"]): (
                ARTIFACT_KIND,
                normalized,
            ),
        }
        committed = self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=event_type,
            artifact_updates=updates,
        )
        return copy.deepcopy(normalized), committed

    def _current(
        self,
        state: KernelState,
        review_type: str,
    ) -> dict[str, Any] | None:
        current_ref = state.artifact_heads.get(_current_slot(review_type), "")
        if not current_ref:
            return None
        reference = ArtifactReference.parse(current_ref)
        if reference.kind != ARTIFACT_KIND:
            raise ContractValidationError(
                "Current ReviewSession head has the wrong kind"
            )
        payload = self.kernel.artifacts.resolve(reference)["payload"]
        normalized = validate_review_session(
            payload,
            current_revision=state.revision,
        )
        if normalized["review_type"] != review_type:
            raise ContractValidationError(
                "Current ReviewSession type does not match its slot"
            )
        identity_ref = state.artifact_heads.get(
            _identity_slot(normalized["review_session_id"]),
            "",
        )
        if identity_ref != current_ref:
            raise ContractValidationError(
                "Current ReviewSession does not match its identity head"
            )
        return normalized
