from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.workbench_bridge import dispatch
from tests.test_v16_project_service import runtime_config
from tests.test_v16_review_marks import accepted_content
from tests.host_confirmation_fixtures import signed_gate_assertion
from tests.v16_visual_fixtures import apply_all_approved_content_review


class V16BridgeTests(unittest.TestCase):
    def test_bridge_binds_only_the_known_macos_powerpoint_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _profile = runtime_config(Path(temp))
            kernel = ProjectService(config).create_project(
                "Policy bridge", project_id="policy-bridge"
            )
            legacy = kernel.commit(
                command_id="remove-policy-for-migration-test",
                expected_revision=1,
                event_type="test.remove-policy",
                artifact_updates={},
                artifact_removals=("release/target-policy",),
            )

            result = dispatch_v16(
                {
                    "operation": "set-release-target-policy",
                    "project_root": str(kernel.project_root),
                    "expected_revision": legacy.revision,
                    "policy_id": "v1.6-macos-powerpoint",
                }
            )["result"]

            self.assertTrue(
                result["artifact_ref"].startswith(
                    "artifact://release-target-policy/"
                )
            )
            self.assertEqual(result["snapshot"]["revision"], 3)
            from ai_ppt_studio.errors import ContractValidationError

            with self.assertRaises(ContractValidationError):
                dispatch_v16(
                    {
                        "operation": "set-release-target-policy",
                        "project_root": str(kernel.project_root),
                        "expected_revision": 3,
                        "policy_id": "ad-hoc-skip-windows",
                        "required_target_ids": ["macos-powerpoint"],
                    }
                )

    def test_raw_bridge_rejects_fabricated_host_action_uris(self) -> None:
        for index, action_ref in enumerate(
            (
                "agent-forged://accepted",
                "host-elicitation://fabricated",
                "host-verifier://fabricated",
            )
        ):
            with self.subTest(action_ref=action_ref), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                service = ContentService.initialize(project, project_id=f"p{index}")
                revision, _blueprint_ref = accepted_content(service)
                apply_all_approved_content_review(
                    service, _blueprint_ref
                )
                revision = service.kernel.load().revision
                context = service.gate_confirmation_context("G0")

                from ai_ppt_studio.errors import GateBlockedError

                with self.assertRaises(GateBlockedError):
                    dispatch_v16(
                        {
                            "operation": "confirm-gate",
                            "project_root": str(project),
                            "expected_revision": revision,
                            "gate": "G0",
                            "user_action_ref": action_ref,
                            "source_version": context["source_version"],
                            "challenge_id": context["challenge_id"],
                            "challenge_revision": context["challenge_revision"],
                        }
                    )

                self.assertEqual(service.kernel.load().revision, revision)

    def test_bridge_exposes_content_review_and_chat_g0(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            service = ContentService.initialize(project, project_id="p1")
            revision, blueprint_ref = accepted_content(service)
            apply_all_approved_content_review(service, blueprint_ref)
            revision = service.kernel.load().revision
            _policy_ref, policy_state = ReleaseTargetPolicyService(
                service.kernel
            ).bind_current_policy(
                "bind-policy-for-content-bridge-snapshot",
                revision,
            )
            revision = policy_state.revision
            review = dispatch_v16(
                {
                    "operation": "get-review-projection",
                    "project_root": str(project),
                    "review_type": "content",
                }
            )
            self.assertEqual(review["review"]["source_version"], blueprint_ref)
            context = dispatch_v16(
                {
                    "operation": "get-gate-confirmation-context",
                    "project_root": str(project),
                    "gate": "G0",
                }
            )["confirmation_context"]

            confirmed = dispatch_v16(
                {
                    "operation": "confirm-gate",
                    "project_root": str(project),
                    "expected_revision": revision,
                    "gate": "G0",
                    "host_confirmation_assertion": signed_gate_assertion(context),
                    "source_version": context["source_version"],
                    "challenge_id": context["challenge_id"],
                    "challenge_revision": context["challenge_revision"],
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
            ReleaseTargetPolicyService(service.kernel).bind_current_policy(
                "bind-policy-for-project-snapshot",
                service.kernel.load().revision,
            )
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
