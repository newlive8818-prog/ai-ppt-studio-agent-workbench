from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.workbench_bridge import dispatch
from tests.host_confirmation_fixtures import gate_confirmation_kwargs
from tests.test_v22_content_review_projection import accepted_review


class V16BridgeTests(unittest.TestCase):
    def test_bridge_exposes_content_review_and_trusted_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            kernel = ProjectKernel.initialize(project, project_id="p1")
            blueprint_ref, _session_ref, session, state = accepted_review(kernel)
            review = dispatch_v16(
                {
                    "operation": "get-content-review-projection",
                    "project_root": str(project),
                    "review_session_id": session["review_session_id"],
                }
            )
            self.assertEqual(review["review"]["reading_blueprint_ref"], blueprint_ref)

            dispatch_v16(
                {
                    "operation": "save-content-page-decision",
                    "project_root": str(project),
                    "command_id": "approve-s01",
                    "expected_revision": state.revision,
                    "review_session_id": session["review_session_id"],
                    "source_version": "content-v1",
                    "slide_id": "S01",
                    "decision": "approved",
                    "comment": "",
                }
            )
            submitted = dispatch_v16(
                {
                    "operation": "submit-content-review-batch",
                    "project_root": str(project),
                    "command_id": "submit-batch",
                    "expected_revision": kernel.load().revision,
                    "review_session_id": session["review_session_id"],
                    "source_version": "content-v1",
                }
            )
            opened = dispatch_v16(
                {
                    "operation": "open-g0-review",
                    "project_root": str(project),
                    "command_id": "open-g0",
                    "expected_revision": submitted["result"]["snapshot"]["revision"],
                }
            )

            revision = opened["result"]["snapshot"]["revision"]
            bridged_context = dispatch_v16(
                {
                    "operation": "get-gate-confirmation-context",
                    "project_root": str(project),
                    "gate": "G0",
                }
            )["confirmation_context"]
            self.assertEqual(bridged_context["gate"], "G0")
            self.assertEqual(bridged_context["scope_kind"], "gate")
            self.assertEqual(bridged_context["scope_id"], "G0")
            self.assertEqual(bridged_context["challenge_revision"], revision)
            self.assertEqual(
                Path(bridged_context["project_root"]).resolve(),
                project.resolve(),
            )
            self.assertTrue(bridged_context["review_summary"])
            with self.assertRaises(GateBlockedError):
                dispatch_v16(
                    {
                        "operation": "confirm-gate",
                        "project_root": str(project),
                        "expected_revision": revision,
                        "gate": "G0",
                        "user_message_ref": "chat://message/fabricated-g0",
                    }
                )
            context = PresalesContentService(kernel).gate_confirmation_context()
            self.assertEqual(
                {
                    key: bridged_context[key]
                    for key in (
                        "project_id",
                        "project_root",
                        "scope_kind",
                        "scope_id",
                        "source_version",
                        "evidence_refs",
                        "challenge_id",
                        "challenge_revision",
                    )
                },
                context,
            )
            confirmed = dispatch_v16({
                "operation": "confirm-gate",
                "project_root": str(project),
                "expected_revision": revision,
                "gate": "G0",
                **gate_confirmation_kwargs(context),
            })
            self.assertEqual(
                confirmed["result"]["snapshot"]["gate_state"]["gates"]["G0"],
                "passed",
            )

    def test_public_bridge_routes_schema3_before_legacy_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source"
            install = base / "install"
            upstream = base / "upstream"
            source.mkdir()
            install.mkdir()
            upstream.mkdir()
            config = RuntimeConfig.create(
                base / "runtime", source, install, upstream
            )
            profile = config.runtime_root / "workspace.json"
            config.save(profile)
            project = config.runtime_root / "projects" / "p1"
            kernel = ProjectKernel.initialize(project, project_id="p1")
            blueprint_ref, _session_ref, session, _state = accepted_review(kernel)
            result = dispatch(
                {
                    "operation": "get-content-review-projection",
                    "workspace_config": str(profile),
                    "project_root": str(project),
                    "review_session_id": session["review_session_id"],
                }
            )
            self.assertEqual(result["review"]["reading_blueprint_ref"], blueprint_ref)

    def test_project_snapshot_uses_schema3_workspace_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            ProjectKernel.initialize(project, project_id="p1")
            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]
            self.assertNotIn("workspace", snapshot)
            self.assertNotIn("space_projections", snapshot)
            self.assertEqual(snapshot["contentMode"], "blocked")
            self.assertIn("status", snapshot)


if __name__ == "__main__":
    unittest.main()
