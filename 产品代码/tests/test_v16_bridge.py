from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.application.project_service import ProjectService
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.workbench_bridge import dispatch
from tests.test_v16_project_service import runtime_config
from tests.test_v16_review_marks import accepted_content
from tests.host_confirmation_fixtures import signed_gate_assertion
from tests.v16_visual_fixtures import apply_all_approved_content_review
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from tests.test_v16_framework_discussion import TEST_SECRET, signed_assertion
from tests.test_v22_content_review_projection import review_ready_kernel


class V16BridgeTests(unittest.TestCase):
    def test_bridge_exposes_v22_full_deck_projection_decision_and_submission(self) -> None:
        kernel, _blueprint_ref, session = review_ready_kernel(slide_count=1)
        self.addCleanup(lambda: __import__("shutil").rmtree(kernel.project_root))
        review_session_id = str(session["review_session_id"])
        review_batch_id = "bridge-v22-review-batch"

        projection = dispatch_v16(
            {
                "operation": "get-content-full-deck-review-projection",
                "project_root": str(kernel.project_root),
                "review_session_id": review_session_id,
            }
        )
        self.assertEqual(projection["review"]["surface"], "content-full-deck")
        self.assertEqual(
            projection["review"]["review_session"]["review_session_id"],
            review_session_id,
        )

        slide_id = str(projection["review"]["slides"][0]["slide_id"])
        saved = dispatch_v16(
            {
                "operation": "save-content-full-deck-page-decision",
                "project_root": str(kernel.project_root),
                "command_id": "bridge-save-v22-page-decision",
                "expected_revision": projection["snapshot_revision"],
                "review_session_id": review_session_id,
                "review_batch_id": review_batch_id,
                "slide_id": slide_id,
                "decision": "approved",
                "comment": "",
            }
        )
        self.assertEqual(saved["result"]["review_progress"]["remaining"], 0)

        context_result = dispatch_v16(
            {
                "operation": "get-content-full-deck-review-batch-submission-context",
                "project_root": str(kernel.project_root),
                "review_session_id": review_session_id,
                "review_batch_id": review_batch_id,
            }
        )
        context = context_result["context"]
        with patch.dict(
            __import__("os").environ,
            {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET},
            clear=False,
        ):
            submitted = dispatch_v16(
                {
                    "operation": "submit-content-full-deck-review-batch",
                    "project_root": str(kernel.project_root),
                    "command_id": "bridge-submit-v22-review-batch",
                    "expected_revision": saved["result"]["revision"],
                    "review_session_id": review_session_id,
                    "review_batch_id": review_batch_id,
                    "challenge_id": context["challenge_id"],
                    "challenge_revision": context["challenge_revision"],
                    "host_confirmation_assertion": signed_assertion(context),
                }
            )
        self.assertTrue(submitted["result"]["artifact_ref"].startswith("artifact://content-review-batch/"))
        self.assertEqual(submitted["result"]["follow_up_message"], "已提交，等待整套修改方案")

    def test_bridge_exposes_authoritative_review_session_and_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            kernel = ProjectKernel.initialize(project, project_id="review-bridge")
            state = kernel.commit(
                command_id="seed-review-target",
                expected_revision=0,
                event_type="test.review-target-created",
                artifact_updates={
                    "content/reading-deck-blueprint": (
                        "reading-deck-blueprint",
                        {"title": "完整内容", "slides": [{"slide_id": "s1"}]},
                    )
                },
            )
            target_ref = state.artifact_heads[
                "content/reading-deck-blueprint"
            ]
            opened = dispatch_v16(
                {
                    "operation": "open-or-resume-review-session",
                    "project_root": str(project),
                    "command_id": "bridge-open-review",
                    "expected_revision": state.revision,
                    "review_type": "content-full-deck",
                    "target_artifact_ref": target_ref,
                    "source_version": "content-v1",
                    "target_revision": state.revision,
                    "open_policy": "foreground-if-waiting",
                }
            )
            session = opened["session"]
            self.assertEqual(session["review_type"], "content-full-deck")
            self.assertEqual(opened["snapshot_revision"], state.revision + 1)

            status = dispatch_v16(
                {
                    "operation": "get-project-user-status",
                    "project_root": str(project),
                }
            )
            self.assertEqual(status["status"]["status"], "需要你处理")

            host_open = dispatch_v16(
                {
                    "operation": "record-review-host-open",
                    "project_root": str(project),
                    "command_id": "bridge-record-host-open",
                    "expected_revision": opened["snapshot_revision"],
                    "review_session_id": session["review_session_id"],
                    "result": "opened",
                    "receipt_ref": "host-receipt://open/001",
                }
            )
            self.assertEqual(host_open["session"]["host_open_status"], "opened")

            notified = dispatch_v16(
                {
                    "operation": "record-review-host-notification",
                    "project_root": str(project),
                    "command_id": "bridge-record-notification",
                    "expected_revision": host_open["snapshot_revision"],
                    "review_session_id": session["review_session_id"],
                    "result": "sent",
                    "receipt_ref": "host-receipt://notification/001",
                }
            )
            self.assertEqual(
                notified["session"]["host_notification_status"], "sent"
            )

            received = dispatch_v16(
                {
                    "operation": "record-review-ai-receipt",
                    "project_root": str(project),
                    "command_id": "bridge-record-ai-receipt",
                    "expected_revision": notified["snapshot_revision"],
                    "review_session_id": session["review_session_id"],
                    "result": "received",
                    "receipt_ref": "ai-receipt://001",
                }
            )
            self.assertEqual(
                received["session"]["ai_receipt_status"], "received"
            )

    def test_bridge_rejects_client_owned_session_status_without_writes(self) -> None:
        for index, (field, value) in enumerate(
            (
                ("status", "opened"),
                ("host_open_status", "opened"),
                ("persistence_status", "saved"),
                ("host_notification_status", "sent"),
                ("ai_receipt_status", "received"),
            )
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                kernel = ProjectKernel.initialize(
                    project,
                    project_id=f"forged-review-{index}",
                )
                state = kernel.commit(
                    command_id="seed-target",
                    expected_revision=0,
                    event_type="test.target-created",
                    artifact_updates={
                        "visual/contract": (
                            "visual-contract",
                            {"title": "视觉合同"},
                        )
                    },
                )
                target_ref = state.artifact_heads["visual/contract"]
                before_objects = tuple(
                    sorted(
                        str(path.relative_to(kernel.artifacts.objects_root))
                        for path in kernel.artifacts.objects_root.rglob("*")
                        if path.is_file()
                    )
                )
                request = {
                    "operation": "open-or-resume-review-session",
                    "project_root": str(project),
                    "command_id": f"forged-{field}",
                    "expected_revision": state.revision,
                    "review_type": "visual-professional",
                    "target_artifact_ref": target_ref,
                    "source_version": "visual-v1",
                    "target_revision": state.revision,
                    "open_policy": "foreground-if-waiting",
                    field: value,
                }
                with self.assertRaisesRegex(
                    ContractValidationError,
                    f"{field} is Runtime-owned",
                ):
                    dispatch_v16(request)
                self.assertEqual(kernel.load(), state)
                after_objects = tuple(
                    sorted(
                        str(path.relative_to(kernel.artifacts.objects_root))
                        for path in kernel.artifacts.objects_root.rglob("*")
                        if path.is_file()
                    )
                )
                self.assertEqual(after_objects, before_objects)

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
