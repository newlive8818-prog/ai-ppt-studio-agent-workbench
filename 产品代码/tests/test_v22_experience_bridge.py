from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_project_retrospective import retrospective_payload
from tests.v22_experience_fixtures import experience_item


class ExperienceBridgeTests(unittest.TestCase):
    def test_recommend_and_record_application_bind_the_exact_experience_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            kernel = ProjectKernel.initialize(project, project_id="p1")
            experience_ref, _item, state = ExperienceService(kernel).absorb_same_type(
                command_id="absorb",
                expected_revision=0,
                payload=experience_item(),
            )
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
                "expected_revision": state.revision,
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
            replay = dispatch_v16(request)
            self.assertEqual(replay, first)
            self.assertEqual(
                first["result"]["application"]["experience_ref"], experience_ref
            )
            with self.assertRaises(ContractValidationError):
                dispatch_v16({**request, "context": {"conditions": ["不同语义"]}})

    def test_close_and_summarize_are_separate_idempotent_operations(self) -> None:
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
            request = {
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
            completed = dispatch_v16(request)
            self.assertEqual(completed["result"]["job"]["status"], "completed")
            self.assertTrue(completed["result"]["retrospective_ref"])


if __name__ == "__main__":
    unittest.main()
