"""Project one authoritative, user-readable status from current Runtime facts."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


PRIORITY = {
    "任务受阻": 0,
    "需要你处理": 1,
    "成果已可查看": 2,
    "AI 正在处理": 3,
}

REVIEW_LABELS = {
    "content-full-deck": {
        "object_type": "content-review",
        "foreground_action": "打开或继续内容全稿审核",
        "notify_action": "需要时打开内容全稿审核",
        "label": "内容全稿审核",
    },
    "visual-professional": {
        "object_type": "visual-review",
        "foreground_action": "打开或继续视觉专业审核",
        "notify_action": "需要时打开视觉专业审核",
        "label": "视觉专业审核",
    },
}


class ProjectStatusProjectionService:
    """Select one status without copying Gate or UI-local state."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self) -> dict[str, Any]:
        state = self.kernel.load()
        candidates = self._candidates(state)
        if not candidates:
            return {
                "status": "AI 正在处理",
                "object_type": "runtime-task",
                "object_ref": f"project://{state.project_id}",
                "reason": "当前没有等待用户处理的审核或已确认阻断。",
                "next_action": "继续当前 Codex 任务",
                "revision": state.revision,
            }
        candidates.sort(
            key=lambda item: (
                PRIORITY[item["status"]],
                item["object_ref"],
            )
        )
        return candidates[0]

    def _candidates(self, state: KernelState) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        task = self._active_task(state)
        if task is not None:
            task_ref, payload = task
            status = str(payload.get("status") or "")
            if status in {"failed", "blocked"}:
                error = payload.get("error")
                reason = str(error).strip() if error is not None else ""
                candidates.append(
                    self._projection(
                        state,
                        status="任务受阻",
                        object_type="runtime-task",
                        object_ref=task_ref,
                        reason=reason or "运行任务未能继续。",
                        next_action="处理阻断后重试当前任务",
                    )
                )
            elif status in {"queued", "running"}:
                candidates.append(
                    self._projection(
                        state,
                        status="AI 正在处理",
                        object_type="runtime-task",
                        object_ref=task_ref,
                        reason="当前运行任务仍在处理。",
                        next_action="等待当前任务完成",
                    )
                )

        for review_type in REVIEW_LABELS:
            current_ref = state.artifact_heads.get(
                f"review/session/current/{review_type}",
                "",
            )
            if not current_ref:
                continue
            session = self._review_session(state, current_ref, review_type)
            labels = REVIEW_LABELS[review_type]
            session_status = session["status"]
            if session_status in {"ready", "opened"}:
                if session["open_policy"] == "foreground-if-waiting":
                    candidates.append(
                        self._projection(
                            state,
                            status="需要你处理",
                            object_type=labels["object_type"],
                            object_ref=current_ref,
                            reason=f"{labels['label']}已准备并等待当前用户处理。",
                            next_action=labels["foreground_action"],
                        )
                    )
                else:
                    candidates.append(
                        self._projection(
                            state,
                            status="成果已可查看",
                            object_type=labels["object_type"],
                            object_ref=current_ref,
                            reason=f"{labels['label']}已在后台准备完成。",
                            next_action=labels["notify_action"],
                        )
                    )
            elif (
                session_status == "submitted"
                and session["ai_receipt_status"] == "pending"
            ):
                candidates.append(
                    self._projection(
                        state,
                        status="AI 正在处理",
                        object_type=labels["object_type"],
                        object_ref=current_ref,
                        reason=f"{labels['label']}已提交，正在等待 AI 接收回执。",
                        next_action="等待 AI 接收回执",
                    )
                )
        return candidates

    def _active_task(
        self,
        state: KernelState,
    ) -> tuple[str, dict[str, Any]] | None:
        task_ref = state.artifact_heads.get("agent/task/active", "")
        if not task_ref:
            return None
        reference = ArtifactReference.parse(task_ref)
        if reference.kind != "agent-task":
            raise ContractValidationError("Active AgentTask has the wrong kind")
        payload = self.kernel.artifacts.resolve(reference)["payload"]
        if not isinstance(payload, dict):
            raise ContractValidationError("Active AgentTask payload is invalid")
        return task_ref, payload

    def _review_session(
        self,
        state: KernelState,
        current_ref: str,
        review_type: str,
    ) -> dict[str, Any]:
        reference = ArtifactReference.parse(current_ref)
        if reference.kind != "review-session":
            raise ContractValidationError(
                "Current ReviewSession has the wrong kind"
            )
        session = validate_review_session(
            self.kernel.artifacts.resolve(reference)["payload"],
            current_revision=state.revision,
        )
        if session["review_type"] != review_type:
            raise ContractValidationError(
                "Current ReviewSession type does not match its slot"
            )
        return session

    @staticmethod
    def _projection(
        state: KernelState,
        *,
        status: str,
        object_type: str,
        object_ref: str,
        reason: str,
        next_action: str,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "object_type": object_type,
            "object_ref": object_ref,
            "reason": reason,
            "next_action": next_action,
            "revision": state.revision,
        }
