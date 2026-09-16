from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.errors import ContractValidationError, ExperienceValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v22_experience_fixtures import experience_item


class RealtimeExperienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.kernel = ProjectKernel.initialize(Path(self.temp.name), project_id="project-01")
        self.service = ExperienceService(self.kernel)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_one_valid_feedback_is_immediately_recommended_only_in_its_domain_and_type(self) -> None:
        content_ref, content, state = self.service.absorb_same_type(
            command_id="absorb-content",
            expected_revision=0,
            payload=experience_item(),
        )
        visual_payload = experience_item(
            experience_id="exp-visual-grid",
            domain="visual",
            type_signature="presales:transport:visual",
        )
        visual_payload["mechanism"] = "同类方案先统一页面网格，再变化页面构图。"
        visual_ref, _, _ = self.service.absorb_same_type(
            command_id="absorb-visual",
            expected_revision=state.revision,
            payload=visual_payload,
        )

        recommended = self.service.recommend(
            domain="content",
            type_signature="presales:transport:decision",
            applicability={"conditions": ["阅读优先"]},
        )
        self.assertEqual([item["experience_ref"] for item in recommended], [content_ref])
        self.assertEqual(
            self.service.recommend(
                domain="content",
                type_signature="presales:transport:visual",
                applicability={"conditions": ["阅读优先"]},
            ),
            [],
        )
        self.assertNotEqual(content_ref, visual_ref)
        self.assertEqual(content["application_count"], 0)

    def test_application_binds_exact_version_and_records_later_real_outcome(self) -> None:
        experience_ref, _, state = self.service.absorb_same_type(
            command_id="absorb",
            expected_revision=0,
            payload=experience_item(),
        )
        application_ref, application, state = self.service.record_application(
            command_id="apply",
            expected_revision=state.revision,
            experience_ref=experience_ref,
            target_project_id="project-target",
            target_type_signature="presales:transport:decision",
            context={"conditions": ["阅读优先"]},
            evidence_refs=["artifact://reading-deck-blueprint/" + "e" * 64],
            applied_at="2026-08-15T01:00:00+08:00",
        )
        self.assertEqual(application["experience_ref"], experience_ref)
        self.assertEqual(application["experience_version"], 1)

        outcome_ref, outcome, state = self.service.evaluate_application(
            command_id="evaluate",
            expected_revision=state.revision,
            application_ref=application_ref,
            outcome="success",
            user_outcome_ref="host-message://accepted-target",
            hard_gate_refs=["artifact://content-hard-gate-record/" + "f" * 64],
            evidence_refs=["artifact://reading-deck-blueprint/" + "1" * 64],
            evaluated_at="2026-08-15T02:00:00+08:00",
        )
        self.assertTrue(outcome_ref)
        self.assertEqual(outcome["outcome"], "success")
        current = self.service.get_current("content", "same-type", "exp-reading-path")
        self.assertEqual(current[1]["application_count"], 1)
        self.assertEqual(state.revision, 3)

    def test_command_replay_is_semantic_and_cross_type_application_is_explicit(self) -> None:
        experience_ref, _, state = self.service.absorb_same_type(
            command_id="absorb",
            expected_revision=0,
            payload=experience_item(),
        )
        replay_ref, _, replay_state = self.service.absorb_same_type(
            command_id="absorb",
            expected_revision=0,
            payload=experience_item(),
        )
        self.assertEqual(replay_ref, experience_ref)
        self.assertEqual(replay_state.revision, state.revision)

        changed = experience_item()
        changed["mechanism"] = "不同语义不能复用同一 command identity。"
        with self.assertRaises(ContractValidationError):
            self.service.absorb_same_type(
                command_id="absorb",
                expected_revision=state.revision,
                payload=changed,
            )
        with self.assertRaises(ExperienceValidationError):
            self.service.record_application(
                command_id="cross-type",
                expected_revision=state.revision,
                experience_ref=experience_ref,
                target_project_id="project-target",
                target_type_signature="presales:manufacturing:decision",
                context={"conditions": ["阅读优先"]},
                evidence_refs=["artifact://reading-deck-blueprint/" + "9" * 64],
                applied_at="2026-08-15T01:00:00+08:00",
            )
        self.assertEqual(self.kernel.load().revision, state.revision)


if __name__ == "__main__":
    unittest.main()
