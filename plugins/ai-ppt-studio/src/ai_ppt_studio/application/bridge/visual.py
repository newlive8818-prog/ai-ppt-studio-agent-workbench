"""Visual professional-review and internal-gate bridge handlers."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.bridge import (
    BridgeContext,
    object_array,
    response,
    result,
    string_array,
)
from ai_ppt_studio.application.visual_review_service import VisualReviewService
from ai_ppt_studio.application.visual_service import VisualService


def get_review_projection(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return response(
        ctx,
        review=VisualReviewService(ctx.kernel).project(
            str(request.get("review_session_id") or "")
        ),
        snapshot_revision=ctx.kernel.load().revision,
    )


def submit_anchor_feedback(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    batch_ref, batch, state = VisualReviewService(
        ctx.kernel
    ).submit_anchor_feedback_batch(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        review_session_id=str(request.get("review_session_id") or ""),
        source_version=str(request.get("source_version") or ""),
        feedback=object_array(request, "feedback"),
    )
    return result(ctx, state, batch_ref=batch_ref, batch=batch)


def save_contract_marks(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    mark_set_ref, mark_set, state = VisualReviewService(
        ctx.kernel
    ).save_contract_review_marks(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        review_session_id=str(request.get("review_session_id") or ""),
        source_version=str(request.get("source_version") or ""),
        marks=object_array(request, "marks"),
    )
    return result(ctx, state, mark_set_ref=mark_set_ref, mark_set=mark_set)


def record_internal_gate(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    state = VisualService(ctx.kernel).record_internal_gate(
        ctx.command_id,
        int(request["expected_revision"]),
        gate=str(request.get("gate") or ""),
        reviewer_role=str(request.get("reviewer_role") or ""),
        acceptance_record_refs=string_array(request, "acceptance_record_refs"),
    )
    return result(ctx, state)


HANDLERS = {
    "get-visual-review-projection": get_review_projection,
    "submit-visual-anchor-feedback-batch": submit_anchor_feedback,
    "save-visual-contract-review-marks": save_contract_marks,
    "record-internal-gate": record_internal_gate,
}


__all__ = ["HANDLERS"]
