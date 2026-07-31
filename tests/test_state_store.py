from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import InvalidTransitionError
from ai_ppt_studio.models import Gate, GateStatus
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_gates_advance_sequentially_and_reopen_only_affected_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            config = RuntimeConfig.create(
                runtime, base / "repo", base / "install", base / "web"
            )
            policy = PathPolicy(config)
            project = ProjectStore(config, policy).create("状态测试")
            project_root = Path(project.project_root)
            store = StateStore(project_root, policy)
            initial = store.initialize()
            self.assertEqual(initial.gates[Gate.G0.value], GateStatus.OPEN.value)
            self.assertEqual(initial.gates[Gate.G1.value], GateStatus.LOCKED.value)
            with self.assertRaises(InvalidTransitionError):
                store.pass_gate(Gate.G1, ("visual/brief.json",))
            after_g0 = store.pass_gate(Gate.G0, ("blueprint/content.json",))
            self.assertEqual(
                after_g0.gates[Gate.G0.value], GateStatus.PASSED.value
            )
            self.assertEqual(after_g0.gates[Gate.G1.value], GateStatus.OPEN.value)
            reopened = store.reopen_from(Gate.G0, "核心事实变化")
            self.assertEqual(reopened.gates[Gate.G0.value], GateStatus.OPEN.value)
            self.assertEqual(reopened.gates[Gate.G1.value], GateStatus.LOCKED.value)
            self.assertGreater(reopened.revision, after_g0.revision)
            events = [
                json.loads(line)
                for line in (project_root / "events" / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(
                [event["event_type"] for event in events],
                [
                    "project.state.initialized",
                    "project.gate.passed",
                    "project.gate.reopened",
                ],
            )
            self.assertEqual(len({event["event_id"] for event in events}), 3)


if __name__ == "__main__":
    unittest.main()
