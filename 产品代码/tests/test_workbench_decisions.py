from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import RevisionConflictError, WorkbenchValidationError
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore
from ai_ppt_studio.workbench_store import WorkbenchStore


class WorkbenchDecisionTests(unittest.TestCase):
    def make_store(self, base: Path) -> WorkbenchStore:
        protected = base / "web"
        protected.mkdir()
        config = RuntimeConfig.create(
            runtime_root=base / "runtime",
            source_repo_root=base / "repo",
            install_root=base / "install",
            upstream_root=protected,
        )
        policy = PathPolicy(config)
        manifest = ProjectStore(config, policy).create("Phase A 验收项目")
        project = Path(manifest.project_root)
        StateStore(project, policy).initialize()
        return WorkbenchStore(project, policy)

    def test_decision_increments_revision_and_persists_after_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(Path(temp))
            before = store.ensure()

            result = store.submit_decision(
                expected_revision=before.revision,
                target_ref="mission://goal",
                choice="revise",
                feedback="先明确给园区管委会领导汇报，并促成一期立项。",
            )

            self.assertEqual(result.snapshot.revision, 1)
            self.assertEqual(result.decision["choice"], "revise")
            self.assertEqual(result.snapshot.last_human_decision_id, result.decision["decision_id"])
            self.assertIn("用户已提交判断", result.follow_up_message)
            self.assertEqual(result.model_context["project_revision"], 1)
            reopened = store.ensure()
            self.assertEqual(reopened.revision, 1)
            self.assertEqual(reopened.last_human_decision_id, result.decision["decision_id"])

            decision_lines = (store.project_root / "cognition" / "decisions.jsonl").read_text("utf-8").splitlines()
            self.assertEqual(len(decision_lines), 1)
            self.assertEqual(json.loads(decision_lines[0])["feedback"], "先明确给园区管委会领导汇报，并促成一期立项。")
            event_lines = (store.project_root / "events" / "events.jsonl").read_text("utf-8").splitlines()
            self.assertEqual(json.loads(event_lines[-1])["event_type"], "workbench.human-decision.submitted")

    def test_stale_revision_does_not_append_partial_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(Path(temp))
            snapshot = store.ensure()
            store.submit_decision(
                expected_revision=snapshot.revision,
                target_ref="mission://goal",
                choice="confirm",
                feedback="确认",
            )
            decisions_path = store.project_root / "cognition" / "decisions.jsonl"
            events_path = store.project_root / "events" / "events.jsonl"
            decisions_before = decisions_path.read_text("utf-8")
            events_before = events_path.read_text("utf-8")

            with self.assertRaises(RevisionConflictError) as caught:
                store.submit_decision(
                    expected_revision=snapshot.revision,
                    target_ref="mission://goal",
                    choice="reject",
                    feedback="过期写入",
                )

            self.assertEqual(caught.exception.actual_revision, 1)
            self.assertEqual(decisions_path.read_text("utf-8"), decisions_before)
            self.assertEqual(events_path.read_text("utf-8"), events_before)

    def test_choice_and_target_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(Path(temp))
            snapshot = store.ensure()
            for target, choice in (("", "confirm"), ("mission://goal", "")):
                with self.assertRaises(WorkbenchValidationError):
                    store.submit_decision(
                        expected_revision=snapshot.revision,
                        target_ref=target,
                        choice=choice,
                        feedback="",
                    )


if __name__ == "__main__":
    unittest.main()
