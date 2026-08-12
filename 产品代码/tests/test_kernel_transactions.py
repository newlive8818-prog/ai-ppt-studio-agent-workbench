from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import (
    GateMutationError,
    ProjectIdentityError,
    RevisionConflictError,
)
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ProjectKernelTests(unittest.TestCase):
    def test_load_rejects_another_project_and_gate_requires_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ProjectKernel.initialize(root, project_id="p1")
            with self.assertRaises(ProjectIdentityError):
                ProjectKernel(root, project_id="p2").load()

            kernel = ProjectKernel(root, project_id="p1")
            with self.assertRaises(GateMutationError):
                kernel.commit(
                    command_id="forged",
                    expected_revision=0,
                    event_type="gate.forged",
                    artifact_updates={},
                    gate_mutation={"G0": "passed"},
                )

    def test_commit_advances_revision_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(Path(temp), project_id="p1")
            first = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={
                    "mission": ("mission-brief", {"goal": "通过方案"})
                },
            )
            repeated = kernel.commit(
                command_id="cmd-1",
                expected_revision=0,
                event_type="mission.committed",
                artifact_updates={
                    "mission": ("mission-brief", {"goal": "通过方案"})
                },
            )
            self.assertEqual(first.revision, 1)
            self.assertEqual(repeated.revision, 1)
            self.assertEqual(first.artifact_heads, repeated.artifact_heads)
            with self.assertRaises(RevisionConflictError):
                kernel.commit(
                    command_id="cmd-2",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={},
                )

    def test_state_is_visibility_boundary_when_state_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = ProjectKernel.initialize(root, project_id="p1")
            real_write = __import__(
                "ai_ppt_studio.kernel.transactions",
                fromlist=["atomic_write_json"],
            ).atomic_write_json

            def fail_state(path: Path, payload: dict[str, object]) -> None:
                if path.name == "state.json":
                    raise OSError("simulated state failure")
                real_write(path, payload)

            with patch(
                "ai_ppt_studio.kernel.transactions.atomic_write_json",
                side_effect=fail_state,
            ), self.assertRaises(OSError):
                kernel.commit(
                    command_id="cmd-1",
                    expected_revision=0,
                    event_type="mission.committed",
                    artifact_updates={
                        "mission": ("mission-brief", {"goal": "通过方案"})
                    },
                )
            self.assertEqual(kernel.load().revision, 0)


if __name__ == "__main__":
    unittest.main()
