from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.agent_tasks import AgentTaskStore
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.context_compiler import ContextCompiler
from ai_ppt_studio.materials import MaterialIntake
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore


def make_project(base: Path) -> tuple[Path, PathPolicy]:
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    policy = PathPolicy(config)
    manifest = ProjectStore(config, policy).create("Agent 任务测试")
    project = Path(manifest.project_root)
    StateStore(project, policy).initialize()
    return project, policy


class AgentTaskTests(unittest.TestCase):
    def test_request_persists_immutable_task_context_and_active_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = make_project(Path(temp))
            MaterialIntake(policy).add_text(project, "客户希望九月上线", "会议纪要")
            context = ContextCompiler(project, policy).compile(
                action_type="classify-materials",
                project_revision=3,
                target_refs=["project://sources"],
                instructions="识别事实、案例和缺口",
            )
            task = AgentTaskStore(project, policy).request(
                action_type="classify-materials",
                target_refs=["project://sources"],
                instructions="识别事实、案例和缺口",
                project_revision=3,
                context_payload=context,
            )

            task_path = project / "tasks" / f"{task['task_id']}.json"
            context_path = project / "context" / f"{task['task_id']}.json"
            self.assertTrue(task_path.is_file())
            self.assertTrue(context_path.is_file())
            self.assertEqual(task["status"], "requested")
            self.assertEqual(task["project_revision"], 3)
            self.assertNotIn("客户希望九月上线", json.dumps(context, ensure_ascii=False))
            self.assertEqual(context["source_summary"]["count"], 1)

            before = task_path.read_bytes()
            recovered = AgentTaskStore(project, policy).active()
            self.assertEqual(recovered["task_id"], task["task_id"])
            self.assertEqual(recovered["context_ref"], f"context/{task['task_id']}.json")
            self.assertEqual(task_path.read_bytes(), before)

    def test_completion_preserves_request_and_creates_result_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = make_project(Path(temp))
            store = AgentTaskStore(project, policy)
            task = store.request(
                action_type="generate-blueprint",
                target_refs=["artifact://content-blueprint"],
                instructions="生成逐页内容蓝图",
                project_revision=1,
                context_payload={"schema_version": "1.0"},
            )
            request_path = project / "tasks" / f"{task['task_id']}.json"
            before = request_path.read_bytes()

            completed = store.complete(
                task["task_id"],
                artifact_refs=["blueprint/content-blueprint/v0001.json"],
                result_revision=2,
            )

            self.assertEqual(completed["status"], "completed")
            self.assertEqual(request_path.read_bytes(), before)
            self.assertTrue(
                (project / "tasks" / f"{task['task_id']}.result.json").is_file()
            )
            self.assertEqual(store.active()["status"], "completed")


if __name__ == "__main__":
    unittest.main()
