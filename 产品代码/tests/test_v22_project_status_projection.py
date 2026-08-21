from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_status_projection import select_user_status


def candidate(status: str, object_type: str) -> dict[str, object]:
    return {
        "status": status,
        "object_type": object_type,
        "object_ref": f"artifact://runtime-task/{object_type:0<64}"[:88],
        "reason": f"{status} 的具体事实",
        "next_action": f"处理 {object_type}",
    }


class ProjectStatusProjectionTests(unittest.TestCase):
    def test_priority_is_blocked_then_user_then_result_then_processing(self) -> None:
        rows = [
            candidate("AI 正在处理", "runtime-task"),
            candidate("成果已可查看", "delivery"),
            candidate("需要你处理", "gate"),
            candidate("任务受阻", "visual-review"),
        ]
        self.assertEqual(select_user_status(rows, revision=17)["status"], "任务受阻")
        self.assertEqual(
            select_user_status(rows[:-1], revision=17)["status"], "需要你处理"
        )
        self.assertEqual(
            select_user_status(rows[:-2], revision=17)["status"], "成果已可查看"
        )
        self.assertEqual(
            select_user_status(rows[:1], revision=17)["status"], "AI 正在处理"
        )

    def test_notify_only_is_not_prematurely_projected_as_user_work(self) -> None:
        row = {
            **candidate("需要你处理", "content-review"),
            "open_policy": "notify-only",
            "host_notification_status": "not-requested",
        }
        projected = select_user_status([row], revision=7)
        self.assertEqual(projected["status"], "AI 正在处理")
        self.assertEqual(projected["revision"], 7)
        row["host_notification_status"] = "sent"
        self.assertEqual(
            select_user_status([row], revision=8)["status"], "成果已可查看"
        )

    def test_empty_candidates_have_one_truthful_runtime_next_action(self) -> None:
        projected = select_user_status([], revision=3)
        self.assertEqual(projected["status"], "AI 正在处理")
        self.assertEqual(projected["object_type"], "runtime-task")
        self.assertTrue(projected["reason"])
        self.assertTrue(projected["next_action"])


if __name__ == "__main__":
    unittest.main()
