"""Project, Mission, Agent-task, and user-checkpoint bridge handlers."""

from __future__ import annotations

import json
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
from ai_ppt_studio.kernel.references import ArtifactReference


def get_user_status(ctx: BridgeContext, _request: dict[str, Any]) -> dict[str, Any]:
    return response(ctx, status=ProjectStatusProjectionService(ctx.kernel).project())


def get_snapshot(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    include = request.get("include_image2_preflight", False)
    if type(include) is not bool:
        raise ContractValidationError("include_image2_preflight must be a boolean")
    values = {"snapshot": snapshot(ctx)}
    if include:
        from ai_ppt_studio.adapters.image2_command import image2_preflight
        values["image2_preflight"] = image2_preflight()
    return response(ctx, **values)


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


def get_image_led_confirmation_context(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    """Resolve the target before Node chooses a trusted or ordinary decision path."""
    target_ref = str(request.get("target_ref") or "")
    target = ArtifactReference.parse(target_ref)
    envelope = ctx.kernel.artifacts.resolve(target)
    if not target.kind.startswith("image-led-"):
        return response(ctx, image_led=False, confirmation_context=None)

    from ai_ppt_studio.application.image_led_service import ImageLedService

    choice = str(request.get("choice") or "")
    context = ImageLedService(ctx.kernel).confirmation_context(target_ref, choice)
    # All review text comes from the resolved, hash-bound artifact, never from
    # model-supplied feedback. The signature binds the exact scope/proposal ref.
    payload = envelope["payload"]
    if target.kind == "image-led-authorization-scope":
        review_summary = "\n".join([
            "撤销以下材料使用授权。" if choice == "revoked" else "确认以下材料使用范围；范围内的后续页面可复用。",
            f"接收方：{payload['receiver']}；模型：{payload['model']}",
            "授权与排除项：" + json.dumps(
                {key: payload[key] for key in ("allowed", "excluded")},
                ensure_ascii=False, sort_keys=True,
            ),
        ])
    else:
        review_summary = "确认当前确切图片与逐字文案；此决定不等于 G3。\n" + json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
        )
    return response(ctx, image_led=True, confirmation_context={
        **context, "target_ref": target_ref, "choice": choice,
        "review_summary": review_summary,
    })


def add_material(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    common = {"operation", "project_root", "expected_revision", "material_type", "command_id"}
    fields = {key: value for key, value in request.items() if key not in common}
    artifact_ref, state = ProjectCommandService(ctx.kernel).add_material(
        ctx.command_id, request["expected_revision"],
        material_type=request.get("material_type"), **fields,
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
    action = str(request.get("action_type") or "").strip()
    target_refs = string_array(request, "target_refs")
    instructions = str(request.get("instructions") or "")
    adapter = None
    generation_request_id = ""
    if action == "generate-slide-images":
        from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
        from ai_ppt_studio.application.artifact_guards import require_revision
        from ai_ppt_studio.application.image_led_service import ImageLedService
        service = ImageLedService(ctx.kernel)
        generation_request_id, existing = service.generation_intent(
            target_refs=target_refs, instructions=instructions,
            intent=request.get("generation_intent", ""),
            request_id=request.get("generation_request_id", ""))
        if existing is not None:
            return _image_led_receipt(ctx, existing)
        require_revision(ctx.kernel, int(request["expected_revision"]))
        payload = service.compile_request(target_refs[0])
        adapter = Image2CommandAdapter.from_environment()
        adapter.preflight(payload)
    elif request.get("generation_intent") or request.get("generation_request_id"):
        raise ContractValidationError("Generation intent is only valid for generate-slide-images")
    artifact_ref, task, state = ProjectCommandService(ctx.kernel).request_agent_action(
        ctx.command_id,
        int(request["expected_revision"]),
        action_type=action,
        target_refs=target_refs,
        instructions=instructions,
        generation_request_id=generation_request_id,
    )
    if adapter is not None:
        return _execute_image_led(ctx, task, adapter, artifact_ref=artifact_ref)
    return result(ctx, state, artifact_ref=artifact_ref, task=task)


def _execute_image_led(ctx, task, adapter, **values):
    from ai_ppt_studio.application.image_led_service import ImageLedService
    ImageLedService(ctx.kernel).execute_generation(task["task_id"], transport=adapter)
    return _image_led_receipt(ctx, task, **values)


def _image_led_receipt(ctx, task, **values):
    from ai_ppt_studio.application.image_led_service import ImageLedService
    reference, generation, usability = ImageLedService(ctx.kernel).generation_receipt(task)
    follow_up = (
        "图片已返回。请核对确切图片的逐字文案与材料，再通过当前 taskId 提交 image-led-candidate；本结果不代表选稿或 G3。"
        if usability["candidate_eligible"] else
        "原请求的图片已保全，实际尺寸或比例未达到横屏候选要求，需要修订后再选稿；不会自动缩放或裁切，恢复查询不会再次生成。"
        if usability['status'] == 'needs-revision' else
        "原请求的图片已保全，当前依赖或任务已变化；历史结果不能直接进入候选或选稿。"
        if generation["status"] == "completed" else
        "原请求尚无确定图片，已保留请求记录。恢复查询不会再次生成；明确要求再设计一版时可沿用仍有效的材料授权。"
    )
    return result(ctx, task=task, generation_response_ref=reference,
                  generation_response=generation, generation_usability=usability,
                  follow_up_message=follow_up, **values)


def execute_image_led_generation(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    """Private bridge/CLI resume entry; public input cannot choose its adapter."""
    from ai_ppt_studio.adapters.image2_command import Image2CommandAdapter
    from ai_ppt_studio.application.artifact_guards import require_revision
    from ai_ppt_studio.application.image_led_service import ImageLedService
    require_revision(ctx.kernel, int(request["expected_revision"]))
    task, _, payload = ImageLedService(ctx.kernel).generation_context(str(request.get("task_id") or ""))
    adapter = Image2CommandAdapter.from_environment()
    adapter.preflight(payload)
    return _execute_image_led(ctx, task, adapter)


def submit_human_decision(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    target_ref = str(request.get("target_ref") or "")
    target = ArtifactReference.parse(target_ref)
    confirmation = None
    if target.kind.startswith("image-led-") and request.get("host_confirmation_assertion"):
        # Internal bridge fields are verified cryptographically by the service;
        # the public MCP schema never accepts this assertion from the caller.
        confirmation = {
            "source_version": str(request.get("source_version") or ""),
            "challenge_id": str(request.get("challenge_id") or ""),
            "challenge_revision": int(request.get("challenge_revision", -1)),
            "host_confirmation_assertion": str(request["host_confirmation_assertion"]),
        }
    decision_ref, follow_up, state = ProjectCommandService(
        ctx.kernel
    ).submit_human_decision(
        ctx.command_id,
        int(request["expected_revision"]),
        target_ref=target_ref,
        choice=str(request.get("choice") or ""),
        feedback=str(request.get("feedback") or ""),
        image_led_confirmation=confirmation,
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
    if kind == "native-anchor-set" and not task_id:
        raise ContractValidationError(
            "native-anchor-set requires its build-native-first task_id"
        )
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
    "get-image-led-confirmation-context": get_image_led_confirmation_context,
    "add-material": add_material,
    "save-mission-draft": save_mission,
    "confirm-mission": confirm_mission,
    "request-agent-action": request_agent_action,
    "execute-image-led-generation": execute_image_led_generation,
    "submit-human-decision": submit_human_decision,
    "confirm-gate": confirm_gate,
    "commit-artifact": commit_artifact,
    "close-project": close_project,
    "abort-project": abort_project,
    "reopen-scope": reopen_scope,
    "set-release-target-policy": set_release_target_policy,
}


__all__ = ["HANDLERS"]
