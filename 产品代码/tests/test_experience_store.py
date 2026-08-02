from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import ExperienceValidationError
from ai_ppt_studio.experience_models import ExperienceLevel, EvaluationOutcome
from ai_ppt_studio.experience_store import ExperienceStore
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore


def candidate_payload(name: str = "双主体协同页对齐机制") -> dict[str, object]:
    return {
        "name": name,
        "experience_type": "visual-mechanism",
        "mechanism": "双主体协同页先建立共享坐标轴，再统一文字基线、图形中心线和连接点。",
        "model_interpretation": "错位不是单个元素问题，而是页面缺少统一网格与锚点。",
        "source_refs": ["reviews/feedback/v0003.json"],
        "scope": {
            "scenes": ["战略合作方案"],
            "audiences": ["国企决策者"],
            "slide_tasks": ["双方能力协同"],
            "conditions": ["双主体", "流程链"],
        },
        "evidence_refs": ["renders/slide-06-before.png", "renders/slide-06-after.png"],
        "before_after_refs": [
            {
                "before": "renders/slide-06-before.png",
                "after": "renders/slide-06-after.png",
            }
        ],
        "counterexamples": [],
        "privacy_level": "private",
        "portable_scope": "personal-installation",
        "sanitized_for_reuse": True,
    }


def context() -> dict[str, object]:
    return {
        "scene": "战略合作方案",
        "audience": "国企决策者",
        "slide_task": "双方能力协同",
        "conditions": ["双主体", "流程链"],
    }


class ExperienceStoreTests(unittest.TestCase):
    def make_runtime(self, base: Path):
        config = RuntimeConfig.create(
            base / "runtime", base / "repo", base / "install", base / "web"
        )
        policy = PathPolicy(config)
        projects = ProjectStore(config, policy)
        source = projects.create("华西合作方案")
        target_a = projects.create("重庆轨道能力方案")
        target_b = projects.create("环境投资合作方案")
        return config, projects, source, target_a, target_b, ExperienceStore(config, policy)

    def test_create_candidate_persists_immutable_personal_memory_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            config, _, source, _, _, store = self.make_runtime(base)

            created = store.create_candidate(source, candidate_payload())

            self.assertEqual(created.level, ExperienceLevel.CANDIDATE)
            self.assertEqual(created.version, 1)
            self.assertEqual(created.source_project_ids, (source.project_id,))
            self.assertTrue(Path(created.path).is_file())
            self.assertTrue(
                Path(created.path).is_relative_to(config.runtime_root / "personal-memory")
            )
            self.assertFalse(Path(created.path).is_relative_to(Path(source.project_root)))
            latest = store.get(created.experience_id)
            self.assertEqual(latest.mechanism, candidate_payload()["mechanism"])
            index = json.loads(
                (config.runtime_root / "personal-memory" / "experience-index.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(index["experiences"][0]["experience_id"], created.experience_id)

    def test_candidate_requires_a_sanitized_reusable_mechanism(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, _, source, _, _, store = self.make_runtime(Path(temp))
            payload = candidate_payload()
            payload["sanitized_for_reuse"] = False
            with self.assertRaises(ExperienceValidationError):
                store.create_candidate(source, payload)
            with self.assertRaisesRegex(ExperienceValidationError, "Invalid experience id"):
                store.get("EXP-../../evaluation")

    def test_recommend_matches_context_across_projects_and_explains_why(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, _, source, _, _, store = self.make_runtime(Path(temp))
            created = store.create_candidate(source, candidate_payload())

            recommendations = store.recommend(context())

            self.assertEqual(recommendations[0]["experience_id"], created.experience_id)
            self.assertGreater(recommendations[0]["match_score"], 0)
            self.assertIn("scene:战略合作方案", recommendations[0]["match_reasons"])
            self.assertEqual(recommendations[0]["level"], "candidate")
            mismatch = context()
            mismatch["scene"] = "年度财务报表"
            self.assertEqual(store.recommend(mismatch), [])

    def test_two_accepted_successes_in_distinct_projects_promote_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config, _, source, target_a, target_b, store = self.make_runtime(Path(temp))
            created = store.create_candidate(source, candidate_payload())

            first = store.record_application(target_a, created.experience_id, context())
            store.evaluate(
                first.application_id,
                {
                    "outcome": EvaluationOutcome.SUCCESS.value,
                    "user_accepted": True,
                    "notes": "一次通过",
                    "evidence_refs": ["reviews/delivery-review.html"],
                },
            )
            after_first = store.get(created.experience_id)
            self.assertEqual(after_first.level, ExperienceLevel.CANDIDATE)

            second = store.record_application(target_b, created.experience_id, context())
            evaluation = store.evaluate(
                second.application_id,
                {
                    "outcome": EvaluationOutcome.SUCCESS.value,
                    "user_accepted": True,
                    "notes": "减少了对齐返工",
                    "evidence_refs": ["renders/accepted.png"],
                },
            )

            promoted = store.get(created.experience_id)
            self.assertEqual(evaluation.experience_id, created.experience_id)
            self.assertEqual(promoted.level, ExperienceLevel.PERSONAL)
            self.assertEqual(set(promoted.accepted_success_project_ids), {target_a.project_id, target_b.project_id})
            self.assertEqual(promoted.success_count, 2)
            self.assertGreater(promoted.confidence, after_first.confidence)
            decisions = (config.runtime_root / "evaluation" / "promotion-decisions.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertIn('"to_level":"personal"', decisions)

    def test_two_failures_after_promotion_demote_to_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, projects, source, target_a, target_b, store = self.make_runtime(Path(temp))
            created = store.create_candidate(source, candidate_payload())
            for target in (target_a, target_b):
                application = store.record_application(target, created.experience_id, context())
                store.evaluate(
                    application.application_id,
                    {"outcome": "success", "user_accepted": True, "evidence_refs": []},
                )
            self.assertEqual(store.get(created.experience_id).level, ExperienceLevel.PERSONAL)

            for name in ("失败项目一", "失败项目二"):
                target = projects.create(name)
                application = store.record_application(target, created.experience_id, context())
                store.evaluate(
                    application.application_id,
                    {"outcome": "failure", "user_accepted": False, "evidence_refs": []},
                )

            demoted = store.get(created.experience_id)
            self.assertEqual(demoted.level, ExperienceLevel.CANDIDATE)
            self.assertEqual(demoted.failures_since_promotion, 2)

    def test_disable_excludes_recommendation_and_rollback_restores_prior_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            _, _, source, _, _, store = self.make_runtime(Path(temp))
            created = store.create_candidate(source, candidate_payload())
            changed = store.set_level(
                created.experience_id,
                ExperienceLevel.DISABLED,
                "暂时不用于推荐",
            )
            self.assertGreater(changed.version, created.version)
            self.assertEqual(store.recommend(context()), [])

            rolled_back = store.rollback(
                created.experience_id,
                version=1,
                reason="恢复首版机制",
            )
            self.assertGreater(rolled_back.version, changed.version)
            self.assertEqual(rolled_back.level, ExperienceLevel.CANDIDATE)
            self.assertEqual(rolled_back.rollback_from_version, 1)
            self.assertEqual(store.recommend(context())[0]["experience_id"], created.experience_id)


if __name__ == "__main__":
    unittest.main()
