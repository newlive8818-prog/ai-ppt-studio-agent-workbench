"""Delivery, reusable experience, and retrospective bridge handlers."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.bridge import (
    BridgeContext,
    object_value,
    response,
    result,
    string_array,
)
from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.application.retrospective_service import RetrospectiveService
from ai_ppt_studio.errors import ExperienceValidationError


def get_delivery_status(
    ctx: BridgeContext, _request: dict[str, Any]
) -> dict[str, Any]:
    return response(
        ctx,
        delivery=DeliveryService(ctx.kernel).delivery_status_projection(),
        snapshot_revision=ctx.kernel.load().revision,
    )


def record_chat_delivery(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    state = DeliveryService(ctx.kernel).record_public_chat_delivery(
        ctx.command_id,
        int(request["expected_revision"]),
        delivery_type=str(request.get("delivery_type") or ""),
        artifact_refs=string_array(request, "artifact_refs"),
        message_ref=str(request.get("message_ref") or ""),
        send_status=str(request.get("send_status") or ""),
        retry_of=str(request.get("retry_of") or ""),
    )
    return result(ctx, state)


def recommend_experience(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    recommendations = ExperienceService(ctx.kernel).recommend(
        domain=str(request.get("domain") or ""),
        type_signature=str(request.get("type_signature") or ""),
        applicability=object_value(request, "applicability"),
        top_n=int(request.get("top_n") or 8),
    )
    return response(
        ctx,
        recommendations=recommendations,
        snapshot_revision=ctx.kernel.load().revision,
    )


def record_experience_application(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    application_ref, application, state = ExperienceService(
        ctx.kernel
    ).record_application(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        experience_ref=str(request.get("experience_ref") or ""),
        target_project_id=str(request.get("target_project_id") or ""),
        target_type_signature=str(request.get("target_type_signature") or ""),
        context=object_value(request, "context"),
        evidence_refs=string_array(request, "evidence_refs"),
        applied_at=str(request.get("applied_at") or ""),
        explicit_validation=bool(request.get("explicit_validation", False)),
    )
    return result(
        ctx, state, application_ref=application_ref, application=application
    )


def summarize_project_experience(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    service = RetrospectiveService(ctx.kernel)
    _job_ref, job = service.current_job()
    expected_kind = {
        "completed": "delivered",
        "closed": "closed",
        "aborted": "aborted",
    }.get(str(request.get("terminal_status") or ""))
    if expected_kind != job["completion_kind"]:
        raise ExperienceValidationError(
            "terminal_status does not match the current completion trigger"
        )
    retrospective = object_value(request, "payload")
    state = service.run(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        builder=lambda _job: retrospective,
        started_at=str(request.get("started_at") or ""),
        finished_at=str(request.get("finished_at") or ""),
        retryable=bool(request.get("retryable", True)),
    )
    job_ref, job = service.current_job()
    retrospective_ref = state.artifact_heads.get("experience/project-retrospective", "")
    return result(
        ctx,
        state,
        job_ref=job_ref,
        job=job,
        retrospective_ref=retrospective_ref,
    )


HANDLERS = {
    "get-delivery-status-projection": get_delivery_status,
    "record-chat-delivery": record_chat_delivery,
    "recommend-experience": recommend_experience,
    "record-experience-application": record_experience_application,
    "summarize-project-experience": summarize_project_experience,
}


__all__ = ["HANDLERS"]
