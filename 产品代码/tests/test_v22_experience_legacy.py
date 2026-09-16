from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.adapters.legacy.experience_v16 import (
    LegacyExperienceV16Adapter,
)


class LegacyExperienceV16Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = LegacyExperienceV16Adapter()
        self.legacy = {
            "experience_id": "EXP-abcdef123456",
            "version": 4,
            "level": "personal",
            "experience_type": "visual-mechanism",
            "mechanism": "双主体协同页先统一坐标轴和文字基线。",
            "source_project_ids": ["project-source"],
            "source_refs": ["artifact://visual-contract/" + "a" * 64],
            "scope": {
                "scenes": ["售前解决方案"],
                "audiences": ["客户决策团队"],
                "slide_tasks": ["协同机制"],
                "conditions": ["阅读优先"],
            },
            "before_after_refs": [
                {
                    "before": "artifact://anchor-slide-set/" + "b" * 64,
                    "after": "artifact://anchor-slide-set/" + "c" * 64,
                }
            ],
            "validation_evidence_refs": [
                "artifact://visual-acceptance-record/" + "d" * 64
            ],
            "counterexamples": [],
            "sanitized_for_reuse": True,
            "accepted_success_project_ids": ["project-a", "project-b"],
            "updated_at": "2026-08-14T18:00:00+08:00",
        }

    def test_candidate_and_personal_are_read_as_same_type_migration_drafts(self) -> None:
        draft = self.adapter.convert_record(
            self.legacy,
            legacy_ref="legacy-file://personal-memory/EXP-abcdef123456/v0004.json",
        )
        self.assertEqual(draft["migration_status"], "same-type-draft")
        self.assertEqual(draft["item"]["layer"], "same-type")
        self.assertEqual(draft["item"]["domain"], "visual")
        self.assertEqual(draft["item"]["success_type_signatures"], [])
        self.assertFalse(draft["eligible_for_automatic_global"])

    def test_stable_release_candidate_never_becomes_global(self) -> None:
        stable = {
            "artifact_type": "stable-capability-release-candidate",
            "release_candidate_id": "release-legacy",
            "source_experience_refs": ["artifact://experience-candidate/" + "e" * 64],
        }
        draft = self.adapter.convert_record(
            stable,
            legacy_ref="artifact://stable-capability-release-candidate/" + "f" * 64,
        )
        self.assertEqual(draft["migration_status"], "legacy-only")
        self.assertIsNone(draft["item"])
        self.assertFalse(draft["eligible_for_automatic_global"])


if __name__ == "__main__":
    unittest.main()
