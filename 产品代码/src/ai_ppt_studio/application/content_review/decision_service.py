"""Atomic v2.2 PageDecision persistence for an active content review session."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.domains.content.contracts import (
    validate_reading_deck_blueprint,
)
from ai_ppt_studio.domains.content.page_decisions import (
    validate_page_decision,
    validate_page_decision_set,
)
from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContentWorkflowError,
    ContractValidationError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.artifacts import canonical_json
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


DECISION_SET_SLOT = "content/page-decisions"
DECISION_SET_KIND = "content-page-decision-set"
DECISION_KIND = "content-page-decision"
SNAPSHOT_KIND = "content-visible-copy-snapshot"
SESSION_SLOT = "review/session/current/content-full-deck"
SESSION_IDENTITY_SLOT_PREFIX = "review/session/"


def _review_session_id(identity: tuple[str, str, str, str, int]) -> str:
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "review-session-" + hashlib.sha256(encoded).hexdigest()[:24]


class ContentPageDecisionService:
    """Save one v2.2 page decision without changing the reviewed content."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel
        self.projection = ContentReviewProjectionService(kernel)

    def save(
        self,
        *,
        command_id: str,
        expected_revision: int,
        review_session_id: str,
        review_batch_id: str,
        slide_id: str,
        decision: str,
        comment: str,
    ) -> tuple[dict[str, Any], dict[str, Any], Any]:
        command = str(command_id or "").strip()
        if not command:
            raise ContractValidationError("command_id is required")
        fingerprint = hashlib.sha256(
            canonical_json(
                {
                    "operation": "save-v22-page-decision",
                    "expected_revision": expected_revision,
                    "review_session_id": review_session_id,
                    "review_batch_id": review_batch_id,
                    "slide_id": slide_id,
                    "decision": decision,
                    "comment": comment,
                }
            )
        ).hexdigest()
        state = self.kernel.load()
        replay = self._replay(
            command_id=command,
            fingerprint=fingerprint,
            review_session_id=review_session_id,
            slide_id=slide_id,
            review_batch_id=review_batch_id,
            decision=decision,
            comment=comment,
            state=state,
        )
        if replay is not None:
            return replay
        if expected_revision != state.revision:
            raise RevisionConflictError(expected_revision, state.revision)
        view = self.projection.project(review_session_id=review_session_id)
        source_version = str(view["source_version"])
        batch_id = str(review_batch_id or "").strip()
        if not batch_id:
            raise ContractValidationError("review_batch_id is required")
        slide = next(
            (
                item
                for item in view["slides"]
                if item["slide_id"] == str(slide_id or "").strip()
            ),
            None,
        )
        if slide is None:
            raise ContractValidationError("PageDecision slide_id is not in the current deck")
        prior_set = self._current_set(state, source_version, batch_id)
        if prior_set is not None and prior_set[1]["status"] == "frozen":
            raise ContentWorkflowError(
                "CONTENT_REVIEW_BATCH_FROZEN",
                "Submitted ContentReviewBatch decisions cannot be changed",
                {"review_batch_id": batch_id, "source_version": source_version},
            )
        prior_ref = ""
        rows = [] if prior_set is None else list(prior_set[1]["decision_refs"])
        for row in rows:
            if row["slide_id"] == slide["slide_id"]:
                prior_ref = row["decision_ref"]
        snapshot = {
            "project_id": state.project_id,
            "source_version": source_version,
            "slide_id": slide["slide_id"],
            "slide_order": slide["order"],
            "slide_title_snapshot": slide["neutral_title"],
            "visible_copy_blocks": slide["visible_copy_blocks"],
        }
        snapshot_ref = str(
            self.kernel.artifacts.reference_for(SNAPSHOT_KIND, snapshot)
        )
        saved_at = datetime.now(timezone.utc).isoformat()
        page = validate_page_decision(
            {
                "page_decision_id": str(uuid.uuid4()),
                "review_batch_id": batch_id,
                "project_id": state.project_id,
                "source_version": source_version,
                "slide_id": slide["slide_id"],
                "slide_order": slide["order"],
                "slide_title_snapshot": slide["neutral_title"],
                "visible_copy_snapshot_ref": snapshot_ref,
                "decision": decision,
                "comment": comment,
                "saved_at": saved_at,
                "supersedes_decision_ref": prior_ref,
            }
        )
        page_ref = str(self.kernel.artifacts.reference_for(DECISION_KIND, page))
        rows = [row for row in rows if row["slide_id"] != slide["slide_id"]]
        rows.append(
            {
                "slide_id": page["slide_id"],
                "slide_order": page["slide_order"],
                "decision_ref": page_ref,
            }
        )
        rows.sort(key=lambda row: row["slide_order"])
        decision_set = validate_page_decision_set(
            {
                "decision_set_id": (
                    prior_set[1]["decision_set_id"]
                    if prior_set
                    else str(uuid.uuid4())
                ),
                "review_batch_id": batch_id,
                "project_id": state.project_id,
                "source_version": source_version,
                "expected_slide_count": len(view["slides"]),
                "status": "draft",
                "decision_refs": rows,
                "updated_at": saved_at,
            }
        )
        committed = self.kernel.commit(
            command_id=command,
            expected_revision=expected_revision,
            event_type="content.v22-page-decision-saved",
            artifact_updates={DECISION_SET_SLOT: (DECISION_SET_KIND, decision_set)},
            detached_artifacts=((SNAPSHOT_KIND, snapshot), (DECISION_KIND, page)),
            command_fingerprint=fingerprint,
        )
        return self._page(page_ref, page), self._progress(decision_set, view), committed

    def _replay(
        self,
        *,
        command_id: str,
        fingerprint: str,
        review_session_id: str,
        slide_id: str,
        review_batch_id: str,
        decision: str,
        comment: str,
        state: Any,
    ) -> tuple[dict[str, Any], dict[str, Any], Any] | None:
        revision = state.processed_commands.get(command_id)
        if revision is None:
            return None
        try:
            event = json.loads(
                (self.kernel.events_root / f"r{revision:08d}.json").read_text(
                    encoding="utf-8"
                )
            )
            decision_set_ref = str(
                event.get("artifact_heads", {}).get(DECISION_SET_SLOT) or ""
            )
            if (
                event.get("command_id") != command_id
                or event.get("event_type") != "content.v22-page-decision-saved"
                or event.get("command_fingerprint") != fingerprint
            ):
                raise ValueError("receipt mismatch")
            heads = event.get("artifact_heads")
            if not isinstance(heads, dict) or any(
                not isinstance(slot, str) or not isinstance(ref, str)
                for slot, ref in heads.items()
            ):
                raise ValueError("receipt heads are invalid")
            session, blueprint, decision_set, pages = self._replay_lineage(
                heads=heads,
                decision_set_ref=decision_set_ref,
                review_session_id=review_session_id,
            )
            row, page_ref, page = next(
                item
                for item in pages
                if item[0]["slide_id"] == str(slide_id).strip()
            )
            normalized_decision = str(decision).strip()
            normalized_comment = str(comment).strip()
            if (
                decision_set["review_batch_id"] != str(review_batch_id).strip()
                or page["project_id"] != session["project_id"]
                or page["source_version"] != session["target_artifact_ref"]
                or page["review_batch_id"] != str(review_batch_id).strip()
                or page["decision"] != normalized_decision
                or page["comment"] != (
                    "" if normalized_decision == "approved" else normalized_comment
                )
            ):
                raise ValueError("result mismatch")
            view = {"slides": blueprint["slides"]}
            return self._page(page_ref, page), self._progress(decision_set, view), state
        except (
            ArtifactReferenceError,
            OSError,
            json.JSONDecodeError,
            StopIteration,
            TypeError,
            ValueError,
            ContractValidationError,
        ) as exc:
            raise ContractValidationError(
                "Processed page-decision command has different semantics"
            ) from exc

    def _replay_lineage(
        self,
        *,
        heads: dict[str, str],
        decision_set_ref: str,
        review_session_id: str,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        list[tuple[dict[str, Any], str, dict[str, Any]]],
    ]:
        session_ref = self._head_reference(
            heads, SESSION_SLOT, "review-session"
        )
        session = validate_review_session(
            self._resolve_payload(session_ref, "review-session")
        )
        if (
            session["review_session_id"] != str(review_session_id).strip()
            or session["review_type"] != "content-full-deck"
            or session["status"] not in {"ready", "opened", "submitted"}
            or session_ref
            != self._head_reference(
                heads,
                f"{SESSION_IDENTITY_SLOT_PREFIX}{session['review_session_id']}",
                "review-session",
            )
            or session["review_session_id"]
            != _review_session_id(
                (
                    session["project_id"],
                    session["review_type"],
                    session["target_artifact_ref"],
                    session["source_version"],
                    session["revision"],
                )
            )
        ):
            raise ValueError("receipt review session is invalid")
        blueprint_ref = session["target_artifact_ref"]
        blueprint = validate_reading_deck_blueprint(
            self._resolve_payload(blueprint_ref, "reading-deck-blueprint")
        )
        if (
            blueprint["project_id"] != session["project_id"]
            or blueprint["source_version"] != session["source_version"]
        ):
            raise ValueError("receipt reading deck does not match its session")
        decision_set_reference = ArtifactReference.parse(decision_set_ref)
        if decision_set_reference.kind != DECISION_SET_KIND:
            raise ValueError("receipt decision set has the wrong kind")
        decision_set = validate_page_decision_set(
            self.kernel.artifacts.resolve(decision_set_reference)["payload"]
        )
        expected_rows = [
            {"slide_id": slide["slide_id"], "slide_order": slide["order"]}
            for slide in blueprint["slides"]
        ]
        actual_rows = [
            {"slide_id": row["slide_id"], "slide_order": row["slide_order"]}
            for row in decision_set["decision_refs"]
        ]
        expected_subset = [
            row
            for row in expected_rows
            if row["slide_id"] in {item["slide_id"] for item in actual_rows}
        ]
        if (
            decision_set["project_id"] != session["project_id"]
            or decision_set["source_version"] != blueprint_ref
            or decision_set["expected_slide_count"] != len(blueprint["slides"])
            or len(actual_rows) > len(expected_rows)
            or actual_rows != expected_subset
        ):
            raise ValueError("receipt decision set is not bound to its reading deck")
        slides_by_id = {
            str(slide["slide_id"]): slide for slide in blueprint["slides"]
        }
        pages: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
        for row in decision_set["decision_refs"]:
            slide = slides_by_id.get(row["slide_id"])
            if slide is None:
                raise ValueError("receipt decision row is not in its reading deck")
            page_ref = str(row["decision_ref"])
            page = validate_page_decision(
                self._resolve_payload(page_ref, DECISION_KIND)
            )
            snapshot = self._resolve_payload(
                page["visible_copy_snapshot_ref"], SNAPSHOT_KIND
            )
            if (
                page["project_id"] != session["project_id"]
                or page["source_version"] != blueprint_ref
                or page["review_batch_id"] != decision_set["review_batch_id"]
                or page["slide_id"] != row["slide_id"]
                or page["slide_order"] != row["slide_order"]
                or page["slide_order"] != slide["order"]
                or page["slide_title_snapshot"] != slide["neutral_title"]
                or not isinstance(snapshot, dict)
                or snapshot.get("project_id") != session["project_id"]
                or snapshot.get("source_version") != blueprint_ref
                or snapshot.get("slide_id") != slide["slide_id"]
                or snapshot.get("slide_order") != slide["order"]
                or snapshot.get("slide_title_snapshot") != slide["neutral_title"]
                or snapshot.get("visible_copy_blocks")
                != slide["visible_copy_blocks"]
            ):
                raise ValueError("receipt decision or snapshot is not source-bound")
            pages.append((row, page_ref, page))
        return session, blueprint, decision_set, pages

    def _head_reference(
        self, heads: dict[str, str], slot: str, expected_kind: str
    ) -> str:
        value = str(heads.get(slot) or "")
        reference = ArtifactReference.parse(value)
        if reference.kind != expected_kind:
            raise ValueError(f"receipt {slot} has the wrong kind")
        return value

    def _resolve_payload(self, value: str, expected_kind: str) -> dict[str, Any]:
        reference = ArtifactReference.parse(value)
        if reference.kind != expected_kind:
            raise ValueError(f"expected {expected_kind}")
        payload = self.kernel.artifacts.resolve(reference)["payload"]
        if not isinstance(payload, dict):
            raise ValueError(f"{expected_kind} payload is invalid")
        return dict(payload)

    def _current_set(
        self, state: Any, source_version: str, review_batch_id: str
    ) -> tuple[str, dict[str, Any]] | None:
        value = str(state.artifact_heads.get(DECISION_SET_SLOT) or "")
        if not value:
            return None
        reference = ArtifactReference.parse(value)
        if reference.kind != DECISION_SET_KIND:
            raise ContractValidationError("Content page-decision head has the wrong kind")
        payload = validate_page_decision_set(
            self.kernel.artifacts.resolve(reference)["payload"]
        )
        if payload["source_version"] != source_version:
            return None
        if payload["review_batch_id"] != review_batch_id:
            if payload["status"] == "frozen":
                raise ContentWorkflowError(
                    "CONTENT_REVIEW_BATCH_FROZEN",
                    "Submitted ContentReviewBatch decisions cannot be replaced",
                    {
                        "review_batch_id": payload["review_batch_id"],
                        "source_version": source_version,
                    },
                )
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "The current content review requires its returned review_batch_id",
                {
                    "review_batch_id": payload["review_batch_id"],
                    "source_version": source_version,
                },
            )
        return value, payload

    @staticmethod
    def _page(page_ref: str, page: dict[str, Any]) -> dict[str, Any]:
        return {"page_decision_ref": page_ref, **page}

    def _progress(
        self, decision_set: dict[str, Any], view: dict[str, Any]
    ) -> dict[str, Any]:
        counts = {
            "approved": 0,
            "modify": 0,
            "evidence": 0,
            "merge_or_delete": 0,
        }
        saved_comment_count = 0
        for row in decision_set["decision_refs"]:
            decision = validate_page_decision(
                self.kernel.artifacts.resolve(
                    ArtifactReference.parse(row["decision_ref"])
                )["payload"]
            )
            count_key = decision["decision"].replace("-", "_")
            counts[count_key] += 1
            if decision["comment"]:
                saved_comment_count += 1
        completed = len(decision_set["decision_refs"])
        return {
            "total": len(view["slides"]),
            "completed": completed,
            "remaining": len(view["slides"]) - completed,
            "saved_comment_count": saved_comment_count,
            "counts": counts,
        }


__all__ = ["ContentPageDecisionService"]
