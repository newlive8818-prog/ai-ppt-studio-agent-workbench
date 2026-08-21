"""Project, Mission, Agent-task, and user-checkpoint bridge handlers."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.bridge import (
    BridgeContext,
    object_value,
    response,
    result,
    snapshot,
    string_array,
)
from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.application.mission_material_service import MissionMaterialService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.project_status_projection import (
    ProjectStatusProjectionService,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.errors import ContractValidationError


def get_user_status(ctx: BridgeContext, _request: dict[str, Any]) -> dict[str, Any]:
    return response(ctx, status=ProjectStatusProjectionService(ctx.kernel).project())


def get_snapshot(ctx: BridgeContext, _request: dict[str, Any]) -> dict[str, Any]:
    return response(ctx, snapshot=snapshot(ctx))


def get_gate_confirmation_context(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    gate = str(request.get("gate") or "")
    if gate == "G0":
        context = PresalesContentService(ctx.kernel).gate_confirmation_context()
        review_summary = (
            "当前完整内容审核版本已满足 G0 用户确认前置条件；"
            f"本次确认绑定 {len(context['evidence_refs'])} 项当前证据。"
        )
    elif gate == "G3":
        context = VisualService(ctx.kernel).gate_confirmation_context()
        review_summary = (
            "当前完整视觉合同已满足 G3 用户确认前置条件；"
            f"本次确认绑定 {len(context['evidence_refs'])} 项当前证据。"
        )
    elif gate == "G4":
        context = DeliveryService(ctx.kernel).gate_confirmation_context()
        review_summary = (
            "当前 PPTX 已完成必需目标验证并真实发送；"
            f"本次接受绑定 {len(context['evidence_refs'])} 项当前交付证据。"
        )
    else:
        raise ContractValidationError(
            "Schema 3.0 supports only G0, G3, and G4 confirmation contexts"
        )
    return response(
        ctx,
        confirmation_context={
            **context,
            "gate": gate,
            "review_summary": review_summary,
        },
    )


def add_material(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    artifact_ref, state = ProjectCommandService(ctx.kernel).add_material(
        ctx.command_id,
        int(request["expected_revision"]),
        material_type=str(request.get("material_type") or ""),
        value=str(request.get("value") or ""),
        data_base64=str(request.get("data_base64") or ""),
        label=str(request.get("label") or ""),
        filename=str(request.get("filename") or ""),
        mime_type=str(request.get("mime_type") or ""),
    )
    return result(ctx, state, artifact_ref=artifact_ref)


def save_mission(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    artifact_ref = MissionMaterialService(ctx.kernel).save_mission_draft(
        ctx.command_id,
        int(request["expected_revision"]),
        object_value(request, "payload"),
    )
    return result(ctx, artifact_ref=artifact_ref)


def confirm_mission(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    artifact_ref = MissionMaterialService(ctx.kernel).confirm_mission(
        ctx.command_id,
        int(request["expected_revision"]),
        mission_draft_ref=str(request.get("mission_draft_ref") or ""),
        material_mode=str(request.get("material_mode") or ""),
        material_inventory_ref=str(request.get("material_inventory_ref") or ""),
        user_action_ref=str(request.get("user_action_ref") or ""),
        user_message_ref=str(request.get("user_message_ref") or ""),
    )
    return result(ctx, artifact_ref=artifact_ref)


def request_agent_action(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    artifact_ref, task, state = ProjectCommandService(ctx.kernel).request_agent_action(
        ctx.command_id,
        int(request["expected_revision"]),
        action_type=str(request.get("action_type") or ""),
        target_refs=string_array(request, "target_refs"),
        instructions=str(request.get("instructions") or ""),
    )
    return result(ctx, state, artifact_ref=artifact_ref, task=task)


def submit_human_decision(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    decision_ref, follow_up, state = ProjectCommandService(
        ctx.kernel
    ).submit_human_decision(
        ctx.command_id,
        int(request["expected_revision"]),
        target_ref=str(request.get("target_ref") or ""),
        choice=str(request.get("choice") or ""),
        feedback=str(request.get("feedback") or ""),
    )
    return result(
        ctx, state, decision_ref=decision_ref, follow_up_message=follow_up
    )


def confirm_gate(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    gate = str(request.get("gate") or "")
    revision = int(request["expected_revision"])
    message_ref = str(request.get("user_message_ref") or "")
    if gate == "G0":
        state = PresalesContentService(ctx.kernel).confirm_g0(
            command_id=ctx.command_id,
            expected_revision=revision,
            source_version=str(request.get("source_version") or ""),
            challenge_id=str(request.get("challenge_id") or ""),
            challenge_revision=int(request.get("challenge_revision", -1)),
            host_confirmation_assertion=str(
                request.get("host_confirmation_assertion") or ""
            ),
            user_action_ref=str(request.get("user_action_ref") or ""),
            user_message_ref=message_ref,
        )
    elif gate == "G3":
        state = VisualService(ctx.kernel).confirm_g3(
            ctx.command_id,
            revision,
            source_version=str(request.get("source_version") or ""),
            challenge_id=str(request.get("challenge_id") or ""),
            challenge_revision=int(request.get("challenge_revision", -1)),
            host_confirmation_assertion=str(
                request.get("host_confirmation_assertion") or ""
            ),
            user_action_ref=str(request.get("user_action_ref") or ""),
            user_message_ref=message_ref,
        )
    elif gate == "G4":
        state = DeliveryService(ctx.kernel).confirm_g4(
            ctx.command_id,
            revision,
            source_version=str(request.get("source_version") or ""),
            challenge_id=str(request.get("challenge_id") or ""),
            challenge_revision=int(request.get("challenge_revision", -1)),
            host_confirmation_assertion=str(
                request.get("host_confirmation_assertion") or ""
            ),
            user_action_ref=str(request.get("user_action_ref") or ""),
            user_message_ref=message_ref,
        )
    else:
        raise ContractValidationError(
            "Schema 3.0 supports only the G0, G3, and G4 user checkpoints"
        )
    return result(ctx, state)


def commit_artifact(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    payload = object_value(request, "payload")
    kind = str(request.get("kind") or "")
    task_id = str(request.get("task_id") or "").strip()
    revision = int(request["expected_revision"])
    commands = ProjectCommandService(ctx.kernel)
    if task_id:
        task = commands.resolve_agent_task(task_id)
        commands.validate_noncontent_agent_result_kind(task, kind, payload)
        replay = commands.replay_noncontent_agent_result(
            command_id=ctx.command_id,
            task_id=task_id,
            request_kind=kind,
            payload=payload,
            expected_revision=revision,
        )
        if replay is not None:
            artifact_ref, state = replay
            return result(ctx, state, artifact_ref=artifact_ref)
        artifact_ref, state = commands.commit_noncontent_agent_result(
            command_id=ctx.command_id,
            expected_revision=revision,
            task_id=task_id,
            request_kind=kind,
            raw_request_payload=payload,
        )
    else:
        artifact_ref = VisualService(ctx.kernel).commit_public_artifact(
            ctx.command_id, revision, kind=kind, payload=payload
        )
        state = ctx.kernel.load()
    return result(ctx, state, artifact_ref=artifact_ref)


def close_project(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    state = ProjectCommandService(ctx.kernel).close_project(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        user_message_ref=str(request.get("user_message_ref") or ""),
        completed_at=str(request.get("completed_at") or ""),
    )
    return result(ctx, state)


def abort_project(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    state = ProjectCommandService(ctx.kernel).abort_project(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        user_message_ref=str(request.get("user_message_ref") or ""),
        reason=str(request.get("reason") or ""),
        completed_at=str(request.get("completed_at") or ""),
    )
    return result(ctx, state)


def reopen_scope(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    gate = str(request.get("gate") or "")
    if gate == "G3":
        state = VisualService(ctx.kernel).reopen_g3(
            ctx.command_id,
            int(request["expected_revision"]),
            reason=str(request.get("reason") or ""),
        )
    else:
        state = DeliveryService(ctx.kernel).reopen_public_scope(
            ctx.command_id,
            int(request["expected_revision"]),
            gate=gate,
            reason=str(request.get("reason") or ""),
        )
    return result(ctx, state)


def set_release_target_policy(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    if str(request.get("policy_id") or "") != "v1.6-macos-powerpoint":
        raise ContractValidationError(
            "policy_id must be v1.6-macos-powerpoint"
        )
    artifact_ref, state = ReleaseTargetPolicyService(
        ctx.kernel
    ).bind_current_policy(ctx.command_id, int(request["expected_revision"]))
    return result(ctx, state, artifact_ref=artifact_ref)


HANDLERS = {
    "get-project-user-status": get_user_status,
    "get-project-snapshot": get_snapshot,
    "get-gate-confirmation-context": get_gate_confirmation_context,
    "add-material": add_material,
    "save-mission-draft": save_mission,
    "confirm-mission": confirm_mission,
    "request-agent-action": request_agent_action,
    "submit-human-decision": submit_human_decision,
    "confirm-gate": confirm_gate,
    "commit-artifact": commit_artifact,
    "close-project": close_project,
    "abort-project": abort_project,
    "reopen-scope": reopen_scope,
    "set-release-target-policy": set_release_target_policy,
}


__all__ = ["HANDLERS"]
