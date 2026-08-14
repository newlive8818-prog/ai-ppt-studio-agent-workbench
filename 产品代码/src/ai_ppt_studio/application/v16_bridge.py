"""Thin JSON facade over schema 3.0 application services."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.content_action_policy import (
    CONTENT_RESULT_CONTRACTS,
    FORMAL_AGENT_CONTENT_ARTIFACT_TYPES,
)
from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.application.review_service import ReviewService
from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.application.workspace_projection import (
    WorkspaceProjectionService,
)
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


def is_schema3_project(project_root: Path) -> bool:
    try:
        payload = json.loads(
            (project_root / "kernel" / "state.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False
    return str(payload.get("schema_version")) == "3.0"


def _kernel(project_root: Path) -> ProjectKernel:
    state_path = project_root / "kernel" / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        project_id = str(payload["project_id"])
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise ContractValidationError(
            f"Schema 3.0 project state is invalid: {state_path}"
        ) from exc
    return ProjectKernel(project_root, project_id=project_id)


def _snapshot(state: KernelState, project_root: Path) -> dict[str, Any]:
    kernel = ProjectKernel(project_root, project_id=state.project_id)
    experience = ExperienceService(kernel).experience_projection()
    workspace_service = WorkspaceProjectionService(kernel)
    from ai_ppt_studio.application.mission_readiness import (
        MissionReadinessPolicy,
    )

    identity = MissionReadinessPolicy(kernel).projection()
    return {
        "schema_version": state.schema_version,
        "revision": state.revision,
        "project": {
            "project_id": state.project_id,
            "name": workspace_service.project_name(),
            "project_root": str(project_root),
        },
        "gate_state": {
            "current_gate": next(
                (
                    gate
                    for gate in ("G0", "G1", "G2", "G3", "G4")
                    if state.gate_status.get(gate) not in {"locked", "passed"}
                ),
                "G4",
            ),
            "gates": dict(state.gate_status),
        },
        "artifacts": dict(state.artifact_heads),
        "missionDraftRef": identity["mission_draft_ref"],
        "missionConfirmationRef": identity["mission_confirmation_ref"],
        "materialMode": identity["material_mode"],
        "contentIdentityMode": identity["content_identity_mode"],
        "workspace": workspace_service.project(),
        "experience": experience,
        "allowed_next_actions": [],
    }


def _command_id(operation: str, request: dict[str, Any]) -> str:
    supplied = str(request.get("command_id") or "").strip()
    if supplied:
        return supplied
    encoded = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"bridge:{operation}:{hashlib.sha256(encoded).hexdigest()}"


def dispatch_v16(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch supported public MCP operations without domain logic in Node."""

    operation = str(request.get("operation") or "").strip()
    project_value = str(request.get("project_root") or "").strip()
    if not operation or not project_value:
        raise ContractValidationError("operation and project_root are required")
    project_root = Path(project_value).resolve()
    kernel = _kernel(project_root)
    content = ContentService(kernel)
    delivery = DeliveryService(kernel)
    visual = VisualService(kernel)
    review_service = ReviewService(kernel)
    project_commands = ProjectCommandService(kernel)

    if operation == "get-project-snapshot":
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "snapshot": _snapshot(kernel.load(), project_root),
        }
    if operation == "get-review-projection":
        review_type = str(request.get("review_type") or "")
        if review_type not in {"content", "visual"}:
            raise ContractValidationError("review_type must be content or visual")
        state = kernel.load()
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "review": (
                review_service.content_projection()
                if review_type == "content"
                else review_service.visual_projection()
            ),
            "snapshot_revision": state.revision,
        }
    if operation == "get-delivery-status-projection":
        state = kernel.load()
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "delivery": delivery.delivery_status_projection(),
            "snapshot_revision": state.revision,
        }
    if operation == "add-material":
        artifact_ref, state = project_commands.add_material(
            _command_id(operation, request),
            int(request["expected_revision"]),
            material_type=str(request.get("material_type") or ""),
            value=str(request.get("value") or ""),
            data_base64=str(request.get("data_base64") or ""),
            label=str(request.get("label") or ""),
            filename=str(request.get("filename") or ""),
            mime_type=str(request.get("mime_type") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "artifact_ref": artifact_ref,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "save-mission-draft":
        payload = request.get("payload")
        if not isinstance(payload, dict):
            raise ContractValidationError("payload must be an object")
        artifact_ref = content.save_mission_draft(
            _command_id(operation, request),
            int(request["expected_revision"]),
            payload,
        )
        state = kernel.load()
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "artifact_ref": artifact_ref,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "confirm-mission":
        artifact_ref = content.confirm_mission(
            _command_id(operation, request),
            int(request["expected_revision"]),
            mission_draft_ref=str(request.get("mission_draft_ref") or ""),
            material_mode=str(request.get("material_mode") or ""),
            material_inventory_ref=str(
                request.get("material_inventory_ref") or ""
            ),
            user_action_ref=str(request.get("user_action_ref") or ""),
            user_message_ref=str(request.get("user_message_ref") or ""),
        )
        state = kernel.load()
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "artifact_ref": artifact_ref,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "request-agent-action":
        raw_refs = request.get("target_refs")
        if not isinstance(raw_refs, list) or any(
            not isinstance(value, str) for value in raw_refs
        ):
            raise ContractValidationError("target_refs must be an array")
        artifact_ref, task, state = project_commands.request_agent_action(
            _command_id(operation, request),
            int(request["expected_revision"]),
            action_type=str(request.get("action_type") or ""),
            target_refs=list(raw_refs),
            instructions=str(request.get("instructions") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "artifact_ref": artifact_ref,
                "task": task,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "submit-human-decision":
        decision_ref, follow_up, state = project_commands.submit_human_decision(
            _command_id(operation, request),
            int(request["expected_revision"]),
            target_ref=str(request.get("target_ref") or ""),
            choice=str(request.get("choice") or ""),
            feedback=str(request.get("feedback") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "decision_ref": decision_ref,
                "follow_up_message": follow_up,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "save-review-marks":
        raw_marks = request.get("marks")
        if not isinstance(raw_marks, list):
            raise ContractValidationError("marks must be an array")
        marks = [
            {
                "mark_id": item.get("mark_id"),
                "field_anchor": item.get("field_anchor"),
                "exact_text": item.get("exact_text"),
                "prefix": item.get("prefix", ""),
                "suffix": item.get("suffix", ""),
                "comment": item.get("comment"),
            }
            for item in raw_marks
            if isinstance(item, dict)
        ]
        state = review_service.save_marks(
            command_id=_command_id(operation, request),
            expected_revision=int(request["expected_revision"]),
            source_version=str(request.get("source_version") or ""),
            marks=marks,
            review_type=str(request.get("review_type") or "content"),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {"snapshot": _snapshot(state, project_root)},
        }
    if operation == "confirm-gate":
        gate = str(request.get("gate") or "")
        if gate == "G0":
            state = content.confirm_g0(
                _command_id(operation, request),
                int(request["expected_revision"]),
                user_message_ref=str(request.get("user_message_ref") or ""),
            )
        elif gate == "G3":
            state = visual.confirm_g3(
                _command_id(operation, request),
                int(request["expected_revision"]),
                user_message_ref=str(request.get("user_message_ref") or ""),
            )
        elif gate == "G4":
            state = delivery.confirm_g4(
                _command_id(operation, request),
                int(request["expected_revision"]),
                user_message_ref=str(request.get("user_message_ref") or ""),
            )
        else:
            raise ContractValidationError(
                "Schema 3.0 supports only the G0, G3, and G4 user checkpoints"
            )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {"snapshot": _snapshot(state, project_root)},
        }
    if operation == "commit-artifact":
        payload = request.get("payload")
        if not isinstance(payload, dict):
            raise ContractValidationError("payload must be an object")
        kind = str(request.get("kind") or "")
        task_id = str(request.get("task_id") or "").strip()
        artifact_type = str(payload.get("artifact_type") or "")
        content_task = None
        if task_id:
            content_task, _context = project_commands.preflight_content_agent_result(
                task_id=task_id,
                request_kind=kind,
                payload=payload,
                expected_revision=int(request["expected_revision"]),
            )
        elif artifact_type in FORMAL_AGENT_CONTENT_ARTIFACT_TYPES:
            from ai_ppt_studio.errors import ContentWorkflowError

            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Formal Agent content results require an active task identity",
                {"artifact_type": artifact_type},
            )
        command_id = _command_id(operation, request)
        if content_task is not None:
            action = str(content_task["action_type"])
            result_contract = CONTENT_RESULT_CONTRACTS[action]
            if result_contract.stage:
                slot, artifact_kind, normalized = (
                    content.prepare_content_stage_update(
                        result_contract.stage, payload
                    )
                )
            else:
                slot, artifact_kind, normalized = content.prepare_review_update(
                    payload
                )
            artifact_ref, state = project_commands.commit_content_agent_result(
                command_id=command_id,
                expected_revision=int(request["expected_revision"]),
                task_id=task_id,
                artifact_slot=slot,
                artifact_kind=artifact_kind,
                artifact_payload=normalized,
            )
        elif kind == "mission":
            artifact_ref = content.save_mission_draft(
                command_id,
                int(request["expected_revision"]),
                payload,
            )
        elif kind in {
            "material-findings",
            "content-blueprint",
            "content-acceptance",
            "feedback",
        }:
            artifact_ref = content.commit_public_artifact(
                command_id,
                int(request["expected_revision"]),
                kind=kind,
                payload=payload,
            )
        else:
            artifact_ref = visual.commit_public_artifact(
                command_id,
                int(request["expected_revision"]),
                kind=kind,
                payload=payload,
            )
        if content_task is None:
            state = kernel.load()
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {
                "artifact_ref": artifact_ref,
                "snapshot": _snapshot(state, project_root),
            },
        }
    if operation == "record-internal-gate":
        refs = request.get("acceptance_record_refs")
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ContractValidationError(
                "acceptance_record_refs must be an array of artifact references"
            )
        state = visual.record_internal_gate(
            _command_id(operation, request),
            int(request["expected_revision"]),
            gate=str(request.get("gate") or ""),
            reviewer_role=str(request.get("reviewer_role") or ""),
            acceptance_record_refs=refs,
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {"snapshot": _snapshot(state, project_root)},
        }
    if operation == "record-chat-delivery":
        refs = request.get("artifact_refs")
        if not isinstance(refs, list) or any(
            not isinstance(value, str) for value in refs
        ):
            raise ContractValidationError(
                "artifact_refs must be an array of artifact references"
            )
        state = delivery.record_public_chat_delivery(
            _command_id(operation, request),
            int(request["expected_revision"]),
            delivery_type=str(request.get("delivery_type") or ""),
            artifact_refs=list(refs),
            message_ref=str(request.get("message_ref") or ""),
            send_status=str(request.get("send_status") or ""),
            retry_of=str(request.get("retry_of") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {"snapshot": _snapshot(state, project_root)},
        }
    if operation == "reopen-scope":
        state = delivery.reopen_public_scope(
            _command_id(operation, request),
            int(request["expected_revision"]),
            gate=str(request.get("gate") or ""),
            reason=str(request.get("reason") or ""),
        )
        return {
            "ok": True,
            "operation": operation,
            "selected_project_root": str(project_root),
            "result": {"snapshot": _snapshot(state, project_root)},
        }
    raise ContractValidationError(
        f"Unsupported schema 3.0 operation: {operation}"
    )
