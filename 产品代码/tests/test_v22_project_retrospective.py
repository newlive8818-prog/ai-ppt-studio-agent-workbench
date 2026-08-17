from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.project_service import ProjectCommandService
from ai_ppt_studio.application.project_status_projection import (
    ProjectStatusProjectionService,
)
from ai_ppt_studio.application.retrospective_service import (
    RetrospectiveService,
)
from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v16_delivery_fixtures import (
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)


def retrospective_payload(
    completion_kind: str, *, successful_change: bool = False
) -> dict[str, object]:
    return {
        "project_type_signature": "presales:transport:reading-first",
        "content_findings": ["事实与诊断假设需要分层呈现"],
        "visual_findings": ["锚点页必须先统一网格"],
        "accepted_mechanisms": ["先事实、再假设、后验证动作"],
        "rejected_patterns": ["无来源数字冒充客户事实"],
        "before_after_refs": [],
        "user_outcome_refs": ["host-message://project-completion"],
        "gate_and_render_refs": [],
        "same_type_changes": (
            [{"action": "evaluate", "outcome": "success"}]
            if successful_change
            else []
        ),
        "global_changes": [],
        "next_project_recommendations": ["优先命中同类型内容经验"],
        "completion_kind": completion_kind,
    }


class ProjectRetrospectiveTests(unittest.TestCase):
    def test_g4_pass_queues_then_runs_one_idempotent_delivered_retrospective(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_delivery_ready(
                Path(temp), slide_count=3
            )
            artifacts = package_artifacts(delivery, refs)
            package_ref = delivery.register_delivery_package(
                "package",
                revision,
                valid_package_payload(refs, artifacts),
            )
            sent = delivery.record_chat_delivery(
                "send",
                revision + 1,
                {
                    "delivery_type": "pptx",
                    "build_ref": refs["build"],
                    "package_ref": package_ref,
                    "pptx_ref": refs["final_pptx"],
                    "pptx_sha256": refs["pptx_sha256"],
                    "artifact_refs": [package_ref, refs["final_pptx"]],
                    "message_ref": "chat://message/pptx-sent",
                    "send_status": "sent",
                    "sent_at": "2026-08-15T01:00:00+08:00",
                    "retry_of": "",
                },
            )
            accepted = delivery.confirm_g4(
                "accept-g4-retrospective",
                sent.revision,
                user_message_ref="chat://message/final-accepted",
            )
            service = RetrospectiveService(delivery.kernel)
            _, queued = service.current_job()
            self.assertEqual(accepted.gate_status["G4"], "passed")
            self.assertEqual(queued["status"], "queued")
            self.assertEqual(queued["completion_kind"], "delivered")

            completed = service.run(
                command_id="retrospective",
                expected_revision=accepted.revision,
                builder=lambda job: retrospective_payload(
                    job["completion_kind"], successful_change=True
                ),
                started_at="2026-08-15T02:00:00+08:00",
                finished_at="2026-08-15T02:01:00+08:00",
            )
            retrospective_ref, retrospective = service.current_retrospective()
            self.assertTrue(retrospective_ref)
            self.assertEqual(retrospective["completion_kind"], "delivered")
            self.assertEqual(service.current_job()[1]["status"], "completed")

            replayed = service.queue_project_completion(
                command_id="same-completion-new-command",
                expected_revision=completed.revision,
                completion_kind="delivered",
                completion_identity=queued["completion_identity"],
                completion_ref=queued["completion_ref"],
                completed_at=queued["completed_at"],
            )
            self.assertEqual(replayed.revision, completed.revision)
            self.assertEqual(
                replayed.artifact_heads["experience/project-retrospective"],
                retrospective_ref,
            )

    def test_close_and_abort_use_same_queue_but_abort_cannot_record_success(self) -> None:
        for kind in ("closed", "aborted"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                kernel = ProjectKernel.initialize(
                    Path(temp), project_id=f"project-{kind}"
                )
                commands = ProjectCommandService(kernel)
                if kind == "closed":
                    state = commands.close_project(
                        command_id="close",
                        expected_revision=0,
                        user_message_ref="chat://message/close-project",
                        completed_at="2026-08-15T03:00:00+08:00",
                    )
                else:
                    state = commands.abort_project(
                        command_id="abort",
                        expected_revision=0,
                        user_message_ref="chat://message/abort-project",
                        reason="客户取消本轮方案",
                        completed_at="2026-08-15T03:00:00+08:00",
                    )
                service = RetrospectiveService(kernel)
                self.assertEqual(service.current_job()[1]["status"], "queued")
                self.assertEqual(
                    service.current_job()[1]["completion_kind"], kind
                )
                if kind == "aborted":
                    with self.assertRaises(ExperienceValidationError):
                        service.run(
                            command_id="invalid-abort-retrospective",
                            expected_revision=state.revision,
                            builder=lambda _job: retrospective_payload(
                                "aborted", successful_change=True
                            ),
                            started_at="2026-08-15T03:01:00+08:00",
                            finished_at="2026-08-15T03:02:00+08:00",
                            capture_failure=False,
                        )
                else:
                    state = service.run(
                        command_id="close-retrospective",
                        expected_revision=state.revision,
                        builder=lambda _job: retrospective_payload("closed"),
                        started_at="2026-08-15T03:01:00+08:00",
                        finished_at="2026-08-15T03:02:00+08:00",
                    )
                    self.assertEqual(
                        service.current_job()[1]["status"], "completed"
                    )

    def test_failure_keeps_g4_and_exposes_retry_or_evidence_backed_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kernel = ProjectKernel.initialize(
                Path(temp), project_id="project-failure"
            )
            commands = ProjectCommandService(kernel)
            queued = commands.close_project(
                command_id="close",
                expected_revision=0,
                user_message_ref="chat://message/close",
                completed_at="2026-08-15T04:00:00+08:00",
            )
            service = RetrospectiveService(kernel)

            def fail(_job: dict[str, object]) -> dict[str, object]:
                raise RuntimeError("experience store unavailable")

            pending = service.run(
                command_id="retryable",
                expected_revision=queued.revision,
                builder=fail,
                started_at="2026-08-15T04:01:00+08:00",
                finished_at="2026-08-15T04:02:00+08:00",
            )
            self.assertEqual(
                service.current_job()[1]["status"], "pending-retry"
            )
            status = ProjectStatusProjectionService(kernel).project()
            self.assertEqual(status["status"], "AI 正在处理")
            self.assertIn("自动重试", status["reason"])

            completed = service.run(
                command_id="retry-success",
                expected_revision=pending.revision,
                builder=lambda _job: retrospective_payload("closed"),
                started_at="2026-08-15T04:03:00+08:00",
                finished_at="2026-08-15T04:04:00+08:00",
            )
            self.assertEqual(service.current_job()[1]["status"], "completed")

            second = ProjectCommandService(
                ProjectKernel.initialize(
                    Path(temp) / "second", project_id="project-blocked"
                )
            )
            state = second.abort_project(
                command_id="abort",
                expected_revision=0,
                user_message_ref="chat://message/abort",
                reason="无法取得必要材料",
                completed_at="2026-08-15T05:00:00+08:00",
            )
            blocked_service = RetrospectiveService(second.kernel)
            blocked_service.run(
                command_id="nonretryable",
                expected_revision=state.revision,
                builder=fail,
                started_at="2026-08-15T05:01:00+08:00",
                finished_at="2026-08-15T05:02:00+08:00",
                retryable=False,
            )
            blocked = ProjectStatusProjectionService(second.kernel).project()
            self.assertEqual(blocked["status"], "任务受阻")
            self.assertIn("失败证据", blocked["reason"])


if __name__ == "__main__":
    unittest.main()
