from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_status_projection import (
    ProjectStatusProjectionService,
)
from ai_ppt_studio.application.review_session_service import (
    ReviewSessionService,
)
from ai_ppt_studio.kernel.transactions import ProjectKernel


def kernel_with_review(
    root: Path,
    open_policy: str,
) -> tuple[ProjectKernel, str]:
    kernel = ProjectKernel.initialize(root, project_id="p1")
    state = kernel.commit(
        command_id="seed-target",
        expected_revision=0,
        event_type="test.target-created",
        artifact_updates={
            "content/reading-deck-blueprint": (
                "reading-deck-blueprint",
                {"title": "完整内容", "slides": [{"slide_id": "s1"}]},
            )
        },
    )
    target_ref = state.artifact_heads["content/reading-deck-blueprint"]
    session, _state = ReviewSessionService(
        kernel,
        clock=lambda: "2026-08-23T00:00:00+00:00",
    ).open_or_resume(
        command_id="open-review",
        expected_revision=state.revision,
        review_type="content-full-deck",
        target_artifact_ref=target_ref,
        source_version="content-v1",
        target_revision=state.revision,
        open_policy=open_policy,
    )
    return kernel, str(session["review_session_id"])


def add_active_task(
    kernel: ProjectKernel,
    *,
    status: str,
    error: str | None = None,
) -> str:
    state = kernel.load()
    task = {
        "task_id": f"task-{status}",
        "action_type": "build-reading-deck-blueprint",
        "role_id": "presales-solution-chief",
        "status": status,
        "progress": {"stage": status, "done": 0, "total": 1},
        "error": error,
    }
    committed = kernel.commit(
        command_id=f"add-task-{status}",
        expected_revision=state.revision,
        event_type="test.task-added",
        artifact_updates={
            "agent/task/active": ("agent-task", task),
            f"agent/task/{task['task_id']}": ("agent-task", task),
        },
    )
    return committed.artifact_heads["agent/task/active"]


class ProjectStatusProjectionTests(unittest.TestCase):
    def test_blocked_task_has_highest_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, _session_id = kernel_with_review(
                Path(temp), "foreground-if-waiting"
            )
            blocked_task_ref = add_active_task(
                kernel,
                status="blocked",
                error="缺少当前内容证据",
            )
            projection = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(projection["status"], "任务受阻")
            self.assertEqual(projection["object_type"], "runtime-task")
            self.assertEqual(projection["object_ref"], blocked_task_ref)
            self.assertEqual(projection["reason"], "缺少当前内容证据")

    def test_foreground_ready_review_requires_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, _session_id = kernel_with_review(
                Path(temp), "foreground-if-waiting"
            )
            projection = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(projection["status"], "需要你处理")
            self.assertEqual(projection["object_type"], "content-review")
            self.assertEqual(
                projection["next_action"], "打开或继续内容全稿审核"
            )

    def test_notify_only_review_is_available_without_focus_takeover(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel, _session_id = kernel_with_review(
                Path(temp), "notify-only"
            )
            projection = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(projection["status"], "成果已可查看")
            self.assertEqual(projection["object_type"], "content-review")
            self.assertEqual(
                projection["next_action"], "需要时打开内容全稿审核"
            )

    def test_queued_task_projects_ai_processing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            task_ref = add_active_task(kernel, status="queued")
            projection = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(projection["status"], "AI 正在处理")
            self.assertEqual(projection["object_type"], "runtime-task")
            self.assertEqual(projection["object_ref"], task_ref)


if __name__ == "__main__":
    unittest.main()
