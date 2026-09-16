"""Bridge regression tests migrated from the v1.6 experience surface."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_project_retrospective import retrospective_payload
from tests.v22_experience_fixtures import experience_item


class V16ExperienceBridgeMigrationTests(unittest.TestCase):
    def test_generic_commit_accepts_only_the_current_experience_item_contract(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            ProjectKernel.initialize(project, project_id="p1")
            payload = {"artifact_type": "experience-item", **experience_item()}
            committed = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "command_id": "commit-current-experience",
                    "expected_revision": 0,
                    "kind": "experience",
                    "payload": payload,
                }
            )
            self.assertTrue(
                committed["result"]["artifact_ref"].startswith(
                    "artifact://experience-item/"
                )
            )
            before = ProjectKernel(project, project_id="p1").load()
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "commit-artifact",
                        "project_root": str(project),
                        "command_id": "commit-retired-experience",
                        "expected_revision": before.revision,
                        "kind": "experience",
                        "payload": {"artifact_type": "experience-intake"},
                    }
                )
            self.assertEqual(ProjectKernel(project, project_id="p1").load(), before)

    def test_recommend_and_application_bridge_bind_the_exact_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            kernel = ProjectKernel.initialize(project, project_id="p1")
            created = dispatch_v16(
                {
                    "operation": "commit-artifact",
                    "project_root": str(project),
                    "command_id": "absorb",
                    "expected_revision": 0,
                    "kind": "experience",
                    "payload": {
                        "artifact_type": "experience-item",
                        **experience_item(),
                    },
                }
            )
            experience_ref = created["result"]["artifact_ref"]
            recommended = dispatch_v16(
                {
                    "operation": "recommend-experience",
                    "project_root": str(project),
                    "domain": "content",
                    "type_signature": "presales:transport:decision",
                    "applicability": {"conditions": ["阅读优先"]},
                    "top_n": 3,
                }
            )
            self.assertEqual(
                [item["experience_ref"] for item in recommended["recommendations"]],
                [experience_ref],
            )
            request = {
                "operation": "record-experience-application",
                "project_root": str(project),
                "command_id": "apply",
                "expected_revision": kernel.load().revision,
                "experience_ref": experience_ref,
                "target_project_id": "p1",
                "target_type_signature": "presales:transport:decision",
                "context": {"conditions": ["阅读优先"]},
                "evidence_refs": [
                    "artifact://reading-deck-blueprint/" + "e" * 64
                ],
                "applied_at": "2026-08-15T06:00:00+08:00",
                "explicit_validation": False,
            }
            first = dispatch_v16(request)
            self.assertEqual(dispatch_v16(request), first)
            self.assertEqual(
                first["result"]["application"]["experience_ref"], experience_ref
            )
            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {**request, "context": {"conditions": ["不同语义"]}}
                )

    def test_terminal_project_and_retrospective_are_separate_operations(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            ProjectKernel.initialize(project, project_id="p1")
            closed = dispatch_v16(
                {
                    "operation": "close-project",
                    "project_root": str(project),
                    "command_id": "close",
                    "expected_revision": 0,
                    "user_message_ref": "chat://message/close",
                    "completed_at": "2026-08-15T07:00:00+08:00",
                }
            )
            completed = dispatch_v16(
                {
                    "operation": "summarize-project-experience",
                    "project_root": str(project),
                    "command_id": "summarize",
                    "expected_revision": closed["result"]["snapshot"]["revision"],
                    "terminal_status": "closed",
                    "payload": retrospective_payload("closed"),
                    "started_at": "2026-08-15T07:01:00+08:00",
                    "finished_at": "2026-08-15T07:02:00+08:00",
                    "retryable": True,
                }
            )
            self.assertEqual(completed["result"]["job"]["status"], "completed")
            self.assertTrue(completed["result"]["retrospective_ref"])


if __name__ == "__main__":
    unittest.main()
