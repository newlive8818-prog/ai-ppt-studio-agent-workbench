"""ReviewSession lifecycle and trusted-receipt bridge handlers."""

from __future__ import annotations

from typing import Any, Callable

from ai_ppt_studio.application.bridge import BridgeContext, result
from ai_ppt_studio.application.review_session_service import ReviewSessionService


def _session_result(ctx: BridgeContext, outcome: tuple[str, dict[str, Any], Any]):
    session_ref, session, state = outcome
    return result(ctx, state, session_ref=session_ref, session=session)


def open_or_resume(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _session_result(
        ctx,
        ReviewSessionService(ctx.kernel).open_or_resume(
            command_id=ctx.command_id,
            expected_revision=int(request["expected_revision"]),
            review_type=str(request.get("review_type") or ""),
            target_artifact_ref=str(request.get("target_artifact_ref") or ""),
            source_version=str(request.get("source_version") or ""),
            source_revision=int(request["source_revision"]),
            open_policy=str(request.get("open_policy") or ""),
        ),
    )


def record_bridge_host_open(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _session_result(
        ctx,
        ReviewSessionService(ctx.kernel).record_bridge_host_open(
            command_id=ctx.command_id,
            expected_revision=int(request["expected_revision"]),
            review_type=str(request.get("review_type") or ""),
            review_session_id=str(request.get("review_session_id") or ""),
            bridge_session_id=str(request.get("bridge_session_id") or ""),
            recorded_at=str(request.get("recorded_at") or ""),
        ),
    )


def expire_review_session(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _session_result(
        ctx,
        ReviewSessionService(ctx.kernel).expire_current(
            command_id=ctx.command_id,
            expected_revision=int(request["expected_revision"]),
            review_type=str(request.get("review_type") or ""),
        ),
    )


def _receipt(
    ctx: BridgeContext,
    request: dict[str, Any],
    method: Callable[..., tuple[str, dict[str, Any], Any]],
) -> dict[str, Any]:
    return _session_result(
        ctx,
        method(
            command_id=ctx.command_id,
            expected_revision=int(request["expected_revision"]),
            review_type=str(request.get("review_type") or ""),
            receipt_ref=str(request.get("receipt_ref") or ""),
            review_session_id=str(request.get("review_session_id") or ""),
            source_version=str(request.get("source_version") or ""),
            saved_artifact_ref=str(request.get("saved_artifact_ref") or ""),
        ),
    )


def record_host_open(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _receipt(
        ctx,
        request,
        ReviewSessionService(ctx.kernel).record_host_open_receipt,
    )


def record_host_notification(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _receipt(
        ctx,
        request,
        ReviewSessionService(ctx.kernel).record_host_notification_receipt,
    )


def record_ai_receipt(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _receipt(
        ctx,
        request,
        ReviewSessionService(ctx.kernel).record_ai_receipt,
    )


HANDLERS = {
    "open-or-resume-review-session": open_or_resume,
    "expire-review-session": expire_review_session,
    "record-review-bridge-host-open": record_bridge_host_open,
    "record-review-host-open": record_host_open,
    "record-review-host-notification": record_host_notification,
    "record-review-ai-receipt": record_ai_receipt,
}


__all__ = ["HANDLERS"]
