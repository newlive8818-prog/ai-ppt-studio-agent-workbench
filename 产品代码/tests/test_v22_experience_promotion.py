from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.v22_experience_fixtures import experience_item


class ExperiencePromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.kernel = ProjectKernel.initialize(Path(self.temp.name), project_id="project-01")
        self.service = ExperienceService(self.kernel)
        self.ref, _, self.state = self.service.absorb_same_type(
            command_id="absorb",
            expected_revision=0,
            payload=experience_item(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def evaluate_success(self, suffix: str, type_signature: str) -> None:
        application_ref, _, state = self.service.record_application(
            command_id=f"apply-{suffix}",
            expected_revision=self.kernel.load().revision,
            experience_ref=self.service.get_current(
                "content", "same-type", "exp-reading-path"
            )[0],
            target_project_id=f"project-{suffix}",
            target_type_signature=type_signature,
            context={"conditions": ["阅读优先"]},
            evidence_refs=["artifact://reading-deck-blueprint/" + suffix[0] * 64],
            applied_at="2026-08-15T01:00:00+08:00",
            explicit_validation=True,
        )
        self.service.evaluate_application(
            command_id=f"evaluate-{suffix}",
            expected_revision=state.revision,
            application_ref=application_ref,
            outcome="success",
            user_outcome_ref=f"host-message://accepted-{suffix}",
            hard_gate_refs=["artifact://content-hard-gate-record/" + suffix[-1] * 64],
            evidence_refs=["artifact://reading-deck-blueprint/" + suffix[-1] * 64],
            evaluated_at="2026-08-15T02:00:00+08:00",
        )

    def test_global_requires_user_directive_or_two_different_real_success_types(self) -> None:
        self.evaluate_success("aa", "presales:transport:decision")
        with self.assertRaises(ExperienceValidationError):
            self.service.promote_global(
                command_id="promote-too-early",
                expected_revision=self.kernel.load().revision,
                same_type_ref=self.service.get_current(
                    "content", "same-type", "exp-reading-path"
                )[0],
            )
        self.evaluate_success("bb", "presales:manufacturing:decision")
        global_ref, global_item, _ = self.service.promote_global(
            command_id="promote-global",
            expected_revision=self.kernel.load().revision,
            same_type_ref=self.service.get_current(
                "content", "same-type", "exp-reading-path"
            )[0],
        )
        self.assertEqual(global_item["layer"], "global")
        self.assertEqual(len(global_item["success_type_signatures"]), 2)
        self.assertTrue(global_ref)

    def test_user_directive_promotes_immediately_and_counterexample_narrows_scope(self) -> None:
        global_ref, _, state = self.service.promote_global(
            command_id="user-global",
            expected_revision=self.kernel.load().revision,
            same_type_ref=self.ref,
            user_global_directive_ref="host-message://use-globally",
        )
        application_ref, _, state = self.service.record_application(
            command_id="apply-counterexample",
            expected_revision=state.revision,
            experience_ref=global_ref,
            target_project_id="project-counterexample",
            target_type_signature="presales:finance:decision",
            context={"conditions": ["阅读优先"]},
            evidence_refs=["artifact://reading-deck-blueprint/" + "2" * 64],
            applied_at="2026-08-15T03:00:00+08:00",
        )
        self.service.evaluate_application(
            command_id="reject-counterexample",
            expected_revision=state.revision,
            application_ref=application_ref,
            outcome="failure",
            user_outcome_ref="host-message://rejected-finance",
            hard_gate_refs=["artifact://content-hard-gate-record/" + "3" * 64],
            evidence_refs=["artifact://reading-deck-blueprint/" + "4" * 64],
            evaluated_at="2026-08-15T04:00:00+08:00",
        )
        self.assertEqual(
            self.service.recommend(
                domain="content",
                type_signature="presales:finance:decision",
                applicability={"conditions": ["阅读优先"]},
            ),
            [],
        )
        self.assertTrue(
            self.service.recommend(
                domain="content",
                type_signature="presales:energy:decision",
                applicability={"conditions": ["阅读优先"]},
            )
        )

        current_ref, current = self.service.get_current(
            "content", "global", "exp-reading-path"
        )
        rollback_ref, rolled_back, state = self.service.rollback(
            command_id="rollback-global",
            expected_revision=self.kernel.load().revision,
            experience_ref=current_ref,
            target_version_ref=global_ref,
            reason="金融项目反例不代表原全局指令本身无效，恢复并等待拆分。",
            rolled_back_at="2026-08-15T05:00:00+08:00",
        )
        self.assertNotEqual(rollback_ref, current_ref)
        self.assertEqual(rolled_back["version"], current["version"] + 1)
        self.assertEqual(rolled_back["rollback_from_version"], 1)
        self.assertEqual(rolled_back["previous_version_ref"], current_ref)
        self.assertEqual(state.revision, self.kernel.load().revision)


if __name__ == "__main__":
    unittest.main()
