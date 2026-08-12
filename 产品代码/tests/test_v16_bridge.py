from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.workbench_bridge import dispatch
from tests.test_v16_review_marks import accepted_content


class V16BridgeTests(unittest.TestCase):
    def test_bridge_exposes_content_review_and_chat_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            service = ContentService.initialize(project, project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            review = dispatch_v16(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project),
                    "review_type": "content",
                }
            )
            self.assertEqual(review["review"]["source_version"], blueprint_ref)

            confirmed = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "gate": "G0",
                    "user_message_ref": "chat://message/g0-accepted",
                }
            )
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
            service = ContentService.initialize(project, project_id="p1")
            _revision, blueprint_ref = accepted_content(service)
            result = dispatch(
                {
                    "operation": "get-review-projection",
                    "workspace_config": str(profile),
                    "project_root": str(project),
                    "review_type": "content",
                }
            )
            self.assertEqual(result["review"]["source_version"], blueprint_ref)

    def test_project_snapshot_uses_schema3_workspace_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            service = ContentService.initialize(project, project_id="p1")
            accepted_content(service)
            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]
            self.assertIn("workspace", snapshot)
            self.assertNotIn("space_projections", snapshot)


if __name__ == "__main__":
    unittest.main()
