from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore


class WorkbenchBridgeTests(unittest.TestCase):
    def make_workspace(self, base: Path) -> tuple[Path, Path]:
        protected = base / "web"
        protected.mkdir()
        config = RuntimeConfig.create(
            runtime_root=base / "runtime",
            source_repo_root=base / "repo",
            install_root=base / "install",
            upstream_root=protected,
        )
        config_path = config.runtime_root / "workspace.json"
        config.save(config_path)
        policy = PathPolicy(config)
        manifest = ProjectStore(config, policy).create("Bridge 测试项目")
        project = Path(manifest.project_root)
        StateStore(project, policy).initialize()
        return config_path, project

    def run_bridge(self, request: dict[str, object]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ai_ppt_studio.workbench_bridge"],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
            check=False,
        )

    def test_list_and_snapshot_emit_one_json_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path, project = self.make_workspace(Path(temp))
            listed = self.run_bridge(
                {"operation": "list-projects", "workspace_config": str(config_path)}
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            listed_payload = json.loads(listed.stdout)
            self.assertEqual(listed_payload["ok"], True)
            self.assertEqual(listed_payload["projects"][0]["project_root"], str(project))

            snapshot = self.run_bridge(
                {
                    "operation": "get-project-snapshot",
                    "workspace_config": str(config_path),
                    "project_root": str(project),
                }
            )
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr)
            payload = json.loads(snapshot.stdout)
            self.assertEqual(payload["snapshot"]["project"]["name"], "Bridge 测试项目")
            self.assertEqual(payload["snapshot"]["revision"], 0)

    def test_submit_decision_and_conflict_have_stable_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path, project = self.make_workspace(Path(temp))
            request = {
                "operation": "submit-human-decision",
                "workspace_config": str(config_path),
                "project_root": str(project),
                "expected_revision": 0,
                "target_ref": "mission://goal",
                "choice": "revise",
                "feedback": "补充任务目标",
            }
            accepted = self.run_bridge(request)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(json.loads(accepted.stdout)["result"]["snapshot"]["revision"], 1)

            stale = self.run_bridge(request)
            self.assertEqual(stale.returncode, 2)
            error = json.loads(stale.stdout)
            self.assertEqual(error["error"]["code"], "REVISION_CONFLICT")
            self.assertEqual(error["error"]["details"]["actual_revision"], 1)

    def test_missing_project_returns_project_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path, _ = self.make_workspace(Path(temp))
            result = self.run_bridge(
                {
                    "operation": "get-project-snapshot",
                    "workspace_config": str(config_path),
                    "project_root": str(Path(temp) / "runtime" / "projects" / "missing"),
                }
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "PROJECT_NOT_FOUND")

    def test_invalid_json_is_validation_error(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "ai_ppt_studio.workbench_bridge"],
            input="not-json",
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "VALIDATION_ERROR")

    def test_bcd_operations_use_stable_json_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path, project = self.make_workspace(Path(temp))
            common = {
                "workspace_config": str(config_path),
                "project_root": str(project),
            }
            added = self.run_bridge(
                {
                    **common,
                    "operation": "add-material",
                    "expected_revision": 0,
                    "material_type": "text",
                    "value": "客户需要九月上线",
                    "label": "会议纪要",
                }
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            self.assertEqual(json.loads(added.stdout)["result"]["snapshot"]["revision"], 1)

            requested = self.run_bridge(
                {
                    **common,
                    "operation": "request-agent-action",
                    "expected_revision": 1,
                    "action_type": "classify-materials",
                    "target_refs": ["project://sources"],
                    "instructions": "提炼事实与缺口",
                }
            )
            self.assertEqual(requested.returncode, 0, requested.stderr)
            requested_payload = json.loads(requested.stdout)["result"]
            self.assertEqual(requested_payload["snapshot"]["revision"], 2)
            self.assertTrue(requested_payload["model_context"]["context_ref"].startswith("context/"))

            blocked = self.run_bridge(
                {
                    **common,
                    "operation": "confirm-gate",
                    "expected_revision": 2,
                    "gate": "G0",
                }
            )
            self.assertEqual(blocked.returncode, 2)
            error = json.loads(blocked.stdout)["error"]
            self.assertEqual(error["code"], "GATE_BLOCKED")
            self.assertIn("mission", error["details"]["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
