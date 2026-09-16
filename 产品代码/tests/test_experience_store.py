from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.experience_store import ExperienceStore
from ai_ppt_studio.paths import PathPolicy
from tests.v22_experience_fixtures import experience_item


class ExperienceStoreTests(unittest.TestCase):
    def make_store(self, base: Path) -> tuple[RuntimeConfig, ExperienceStore]:
        config = RuntimeConfig.create(
            base / "runtime", base / "repo", base / "install", base / "web"
        )
        return config, ExperienceStore(config, PathPolicy(config))

    def test_writes_only_same_type_global_and_v22_evaluation_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, store = self.make_store(Path(temp))
            created = store.absorb_same_type(experience_item())

            self.assertEqual(created.item["layer"], "same-type")
            self.assertTrue(Path(created.path).is_file())
            self.assertTrue(
                Path(created.path).is_relative_to(
                    config.runtime_root / "personal-memory" / "same-type"
                )
            )
            self.assertFalse(
                (config.runtime_root / "personal-memory" / "experiences").exists()
            )
            status = store.capability_status()
            self.assertEqual(status["schema_version"], "2.2")
            self.assertNotIn("create_candidate", status["operations"])
            self.assertNotIn("set_level", status["operations"])

    def test_recommendation_is_domain_and_exact_type_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, store = self.make_store(Path(temp))
            content = store.absorb_same_type(experience_item())
            visual = experience_item(
                experience_id="exp-visual-grid",
                domain="visual",
                type_signature="presales:transport:visual",
            )
            visual["mechanism"] = "同类视觉先统一网格，再变化构图。"
            store.absorb_same_type(visual)

            recommendations = store.recommend(
                domain="content",
                type_signature="presales:transport:decision",
                applicability={"conditions": ["阅读优先"]},
            )
            self.assertEqual(
                [item["experience_ref"] for item in recommendations],
                [content.experience_ref],
            )
            self.assertEqual(
                store.recommend(
                    domain="content",
                    type_signature="presales:transport:visual",
                    applicability={"conditions": ["阅读优先"]},
                ),
                [],
            )

    def test_real_cross_type_successes_promote_and_counterexample_narrows_global(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, store = self.make_store(Path(temp))
            created = store.absorb_same_type(experience_item())
            current = created
            for suffix, target_type in (
                ("a", "presales:transport:decision"),
                ("b", "presales:manufacturing:decision"),
            ):
                application = store.record_application(
                    experience_ref=current.experience_ref,
                    target_project_id=f"project-{suffix}",
                    target_type_signature=target_type,
                    context={"conditions": ["阅读优先"]},
                    evidence_refs=[
                        "artifact://reading-deck-blueprint/" + suffix * 64
                    ],
                    applied_at=f"2026-08-15T0{1 if suffix == 'a' else 3}:00:00+08:00",
                    explicit_validation=True,
                )
                store.evaluate(
                    application_id=application.application_id,
                    outcome="success",
                    user_outcome_ref=f"host-message://accepted-{suffix}",
                    hard_gate_refs=[
                        "artifact://content-hard-gate-record/" + suffix * 64
                    ],
                    evidence_refs=[
                        "artifact://reading-deck-blueprint/" + suffix * 64
                    ],
                    evaluated_at=f"2026-08-15T0{2 if suffix == 'a' else 4}:00:00+08:00",
                )
                current = store.get_current(
                    "content", "same-type", "exp-reading-path"
                )

            promoted = store.promote_global(
                same_type_ref=current.experience_ref,
                promoted_at="2026-08-15T05:00:00+08:00",
            )
            application = store.record_application(
                experience_ref=promoted.experience_ref,
                target_project_id="project-finance",
                target_type_signature="presales:finance:decision",
                context={"conditions": ["阅读优先"]},
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "c" * 64
                ],
                applied_at="2026-08-15T06:00:00+08:00",
            )
            store.evaluate(
                application_id=application.application_id,
                outcome="failure",
                user_outcome_ref="host-message://rejected-finance",
                hard_gate_refs=[
                    "artifact://content-hard-gate-record/" + "d" * 64
                ],
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "e" * 64
                ],
                evaluated_at="2026-08-15T07:00:00+08:00",
            )
            self.assertEqual(
                store.recommend(
                    domain="content",
                    type_signature="presales:finance:decision",
                    applicability={"conditions": ["阅读优先"]},
                ),
                [],
            )
            self.assertTrue(
                store.recommend(
                    domain="content",
                    type_signature="presales:energy:decision",
                    applicability={"conditions": ["阅读优先"]},
                )
            )
            promotions = (
                config.runtime_root / "evaluation" / "promotions.jsonl"
            ).read_text(encoding="utf-8")
            self.assertIn('"action":"promote-global"', promotions)

    def test_rollback_creates_a_new_version_without_erasing_usage_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, store = self.make_store(Path(temp))
            original = store.absorb_same_type(experience_item())
            application = store.record_application(
                experience_ref=original.experience_ref,
                target_project_id="project-target",
                target_type_signature="presales:transport:decision",
                context={"conditions": ["阅读优先"]},
                evidence_refs=[
                    "artifact://reading-deck-blueprint/" + "f" * 64
                ],
                applied_at="2026-08-15T01:00:00+08:00",
            )
            current = store.get_current(
                "content", "same-type", "exp-reading-path"
            )
            rolled_back = store.rollback(
                experience_ref=current.experience_ref,
                target_version_ref=original.experience_ref,
                reason="恢复首版机制",
                rolled_back_at="2026-08-15T02:00:00+08:00",
            )
            self.assertEqual(rolled_back.item["version"], current.item["version"] + 1)
            self.assertEqual(rolled_back.item["rollback_from_version"], 1)
            self.assertEqual(rolled_back.item["application_count"], 1)
            self.assertEqual(application.experience_ref, original.experience_ref)

            index = json.loads(store.index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["schema_version"], "2.2")
            self.assertTrue(all("level" not in item for item in index["items"]))
            self.assertTrue(
                all(
                    item["layer"] in {"same-type", "global"}
                    for item in index["items"]
                )
            )

    def test_global_requires_directive_or_two_distinct_success_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, store = self.make_store(Path(temp))
            created = store.absorb_same_type(experience_item())
            created.item["success_type_signatures"] = []
            with self.assertRaises(ExperienceValidationError):
                store.promote_global(
                    same_type_ref=created.experience_ref,
                    promoted_at="2026-08-15T01:00:00+08:00",
                )
            promoted = store.promote_global(
                same_type_ref=created.experience_ref,
                user_global_directive_ref="host-message://use-globally",
                promoted_at="2026-08-15T01:00:00+08:00",
            )
            self.assertEqual(promoted.item["layer"], "global")


if __name__ == "__main__":
    unittest.main()
