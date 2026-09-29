"""One compact user-facing status derived from authoritative runtime facts."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.domains.review.contracts import validate_review_session
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel

STATUSES = ("AI 正在处理", "成果已可查看", "需要你处理", "任务受阻")
PRIORITY = {status: index for index, status in enumerate(STATUSES)}


def select_user_status(
    candidates: list[dict[str, Any]], *, revision: int
) -> dict[str, Any]:
    """Normalize notify-only semantics and select the highest-priority fact."""

    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        if item.get("status") not in PRIORITY:
            raise ValueError("Unknown project user status")
        if item.get("host_open_status") in {"failed", "unavailable"}:
            item.update(
                {
                    "status": "任务受阻",
                    "reason": "专业审核宿主打开失败或不可用",
                    "next_action": "检查宿主能力并重试",
                }
            )
        elif item.get("host_notification_status") in {"failed", "unavailable"}:
            item.update(
                {
                    "status": "任务受阻",
                    "reason": "专业审核宿主通知失败或不可用",
                    "next_action": "检查通知能力并重试",
                }
            )
        elif item.get("ai_receipt_status") in {"rejected", "unverified"}:
            item.update(
                {
                    "status": "任务受阻",
                    "reason": "AI 回执被拒绝或未验证",
                    "next_action": "检查回执并重试",
                }
            )
        elif item.get("open_policy") == "notify-only" and item["status"] == "需要你处理":
            if item.get("host_notification_status") == "sent":
                item["status"] = "成果已可查看"
                item["next_action"] = "打开审核成果"
            else:
                item["status"] = "AI 正在处理"
                item["reason"] = "审核成果已保存，等待宿主发送可查看通知"
                item["next_action"] = "发送成果可查看通知"
        item["revision"] = revision
        normalized.append(item)
    if not normalized:
        return {
            "status": "AI 正在处理",
            "object_type": "runtime-task",
            "object_ref": "runtime://current-project",
            "reason": "当前没有需要用户处理或可查看的新成果",
            "next_action": "继续当前运行时任务",
            "revision": revision,
        }
    return max(normalized, key=lambda item: PRIORITY[item["status"]])


class ProjectStatusProjectionService:
    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self) -> dict[str, Any]:
        state = self.kernel.load()
        candidates: list[dict[str, Any]] = []
        for review_type in ("content-full-deck", "visual-professional"):
            if (
                review_type == "content-full-deck"
                and state.gate_status.get("G0") == "passed"
            ):
                continue
            if (
                review_type == "visual-professional"
                and state.gate_status.get("G3") == "passed"
            ):
                continue
            ref = state.review_session_ref(review_type)
            if not ref:
                continue
            session = validate_review_session(
                self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"],
                trusted_receipts=True,
            )
            candidates.append(self._review_candidate(ref, session))
        for slot, ref in state.artifact_heads.items():
            if slot.startswith("runtime/task/"):
                candidates.append(self._runtime_candidate(ref))
        retrospective_job = state.artifact_heads.get(
            "experience/retrospective/job", ""
        )
        if retrospective_job:
            candidates.append(
                self._retrospective_candidate(retrospective_job)
            )
        return select_user_status(candidates, revision=state.revision)

    @staticmethod
    def _review_candidate(ref: str, session: dict[str, Any]) -> dict[str, Any]:
        object_type = (
            "content-review"
            if session["review_type"] == "content-full-deck"
            else "visual-review"
        )
        if session["host_open_status"] in {"failed", "unavailable"}:
            status, reason, next_action = (
                "任务受阻",
                "专业审核宿主打开失败或不可用",
                "检查宿主能力并重试",
            )
        elif session["host_notification_status"] in {"failed", "unavailable"}:
            status, reason, next_action = (
                "任务受阻",
                "专业审核宿主通知失败或不可用",
                "检查通知能力并重试",
            )
        elif session["ai_receipt_status"] in {"rejected", "unverified"}:
            status, reason, next_action = (
                "任务受阻",
                "AI 回执被拒绝或未验证",
                "检查回执并重试",
            )
        elif session["status"] == "submitted" and session["ai_receipt_status"] == "pending":
            status, reason, next_action = (
                "AI 正在处理",
                "审核已提交，等待 AI 接收回执",
                "等待 AI 接收回执",
            )
        elif session["open_policy"] == "notify-only":
            if session["host_notification_status"] == "sent":
                status, reason, next_action = (
                    "成果已可查看",
                    "审核成果已保存并已通知",
                    "打开审核成果",
                )
            else:
                status, reason, next_action = (
                    "AI 正在处理",
                    "审核成果已保存，等待宿主通知",
                    "发送成果可查看通知",
                )
        elif session["host_open_status"] == "pending":
            status, reason, next_action = (
                "需要你处理",
                "审核已准备，等待当前用户打开",
                "打开或继续审核",
            )
        elif session["status"] == "submitted":
            status, reason, next_action = (
                "AI 正在处理",
                "审核反馈已保存并提交",
                "等待 AI 接收并执行反馈",
            )
        else:
            status, reason, next_action = (
                "需要你处理",
                "专业审核成果已保存",
                "完成内容审核" if object_type == "content-review" else "完成视觉审核",
            )
        return {
            "status": status,
            "object_type": object_type,
            "object_ref": ref,
            "reason": reason,
            "next_action": next_action,
            "open_policy": session["open_policy"],
            "host_notification_status": session["host_notification_status"],
        }

    def _runtime_candidate(self, ref: str) -> dict[str, Any]:
        payload = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]
        status = {
            "running": "AI 正在处理",
            "ready": "成果已可查看",
            "needs-user": "需要你处理",
            "blocked": "任务受阻",
        }.get(str(payload.get("status")), "AI 正在处理")
        return {
            "status": status,
            "object_type": str(payload.get("object_type") or "runtime-task"),
            "object_ref": ref,
            "reason": str(payload.get("reason") or "运行时任务状态已更新"),
            "next_action": str(payload.get("next_action") or "继续当前任务"),
        }

    def _retrospective_candidate(self, ref: str) -> dict[str, Any]:
        payload = self.kernel.artifacts.resolve(
            ArtifactReference.parse(ref)
        )["payload"]
        status = str(payload.get("status") or "")
        if status == "failed-with-evidence":
            user_status, reason, next_action = (
                "任务受阻",
                "项目经验复盘失败，已保存失败证据",
                "检查失败证据后重试复盘",
            )
        elif status == "pending-retry":
            user_status, reason, next_action = (
                "AI 正在处理",
                "项目经验复盘失败，系统将自动重试",
                "等待自动重试",
            )
        elif status == "completed":
            user_status, reason, next_action = (
                "成果已可查看",
                "项目经验复盘已完成",
                "继续下一个项目",
            )
        else:
            user_status, reason, next_action = (
                "AI 正在处理",
                "系统正在生成项目经验复盘",
                "等待复盘完成",
            )
        return {
            "status": user_status,
            "object_type": "project-experience-retrospective",
            "object_ref": ref,
            "reason": reason,
            "next_action": next_action,
        }
