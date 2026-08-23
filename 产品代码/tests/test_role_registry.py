from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.role_registry import (  # noqa: E402
    RoleRegistry,
    RoleContract,
    ProductionRole,
    ReviewRole,
    SupportRole,
)
from ai_ppt_studio.scenario_packs import (  # noqa: E402
    ScenarioPackRegistry,
    PresalesScenarioPack,
)


class RoleRegistryTests(unittest.TestCase):
    def test_all_approved_roles_have_chinese_display_name_and_stable_id(self) -> None:
        """每一个已批准的正式角色都有中文显示名、稳定 roleId 和隔离组。"""
        registry = RoleRegistry.default()
        self.assertGreaterEqual(len(registry.all()), 14)
        for role in registry.all():
            with self.subTest(role_id=role.role_id):
                self.assertTrue(role.role_id, "role_id 不能为空")
                self.assertTrue(role.display_name, f"{role.role_id} 必须有中文显示名")
                # 中文显示名至少含一个中文字符
                self.assertTrue(
                    any("\u4e00" <= ch <= "\u9fff" for ch in role.display_name),
                    f"{role.role_id} 的 display_name 必须包含中文",
                )
                self.assertIn(
                    role.role_group,
                    {"content", "visual", "review", "feedback", "experience", "delivery"},
                    f"{role.role_id} 必须声明隔离组",
                )
                self.assertIn(
                    role.authority,
                    {"producer", "reviewer", "support"},
                    f"{role.role_id} 必须声明权限角色",
                )

    def test_content_producer_roles_are_isolated_from_reviewer_roles(self) -> None:
        """内容生产者不能看到审查者记录；审查者不能看到生产者自评。"""
        registry = RoleRegistry.default()
        content_producers = [
            r for r in registry.all()
            if r.role_group == "content" and r.authority == "producer"
        ]
        content_reviewers = [
            r for r in registry.all()
            if r.role_group == "content" and r.authority == "reviewer"
        ]
        self.assertEqual(
            {role.role_id for role in content_producers},
            {"presales-solution-chief"},
        )
        self.assertEqual(
            {role.role_id for role in content_reviewers},
            {
                "content-evidence-gate-reviewer",
                "content-presales-reading-gate-reviewer",
            },
        )
        # 不同隔离组
        producer_ids = {r.role_id for r in content_producers}
        reviewer_ids = {r.role_id for r in content_reviewers}
        self.assertFalse(producer_ids.intersection(reviewer_ids))
        self.assertTrue(registry.has("presales-risk-specialist/*"))
        specialist = registry.get("presales-risk-specialist/*")
        self.assertEqual(specialist.authority, "support")
        self.assertEqual(specialist.role_group, "content")

    def test_legacy_fixed_content_roles_are_not_formal_roles(self) -> None:
        registry = RoleRegistry.default()
        legacy = {
            "presales-content-strategist",
            "claim-evidence-analyst",
            "deck-narrative-architect",
            "slide-copywriter",
            "presales-content-reviewer",
            "audience-decision-reviewer",
            "content-fact-checker",
            "argument-logic-reviewer",
            "reading-experience-reviewer",
            "deck-coherence-editor",
        }
        self.assertFalse(legacy.intersection({role.role_id for role in registry.all()}))

    def test_formal_visual_roles_enforce_strict_b(self) -> None:
        """正式视觉生产角色必须绑定 strict-B 路线。"""
        registry = RoleRegistry.default()
        visual_producers = [
            r for r in registry.all()
            if r.role_group == "visual" and r.authority == "producer"
        ]
        self.assertGreaterEqual(len(visual_producers), 3)
        for role in visual_producers:
            with self.subTest(role_id=role.role_id):
                self.assertIn(
                    "strict-B",
                    role.tags,
                    f"视觉生产角色 {role.role_id} 必须带 strict-B 标签",
                )

    def test_reviewer_slices_include_anti_patterns_and_producers_mechanisms(self) -> None:
        """审查者切片含反模式；生产者切片含合格机制和偏好。"""
        registry = RoleRegistry.default()
        for role in registry.all():
            with self.subTest(role_id=role.role_id):
                if role.authority == "reviewer":
                    self.assertIn(
                        "anti-patterns",
                        role.experience_access,
                        f"审查者 {role.role_id} 必须能访问反模式",
                    )
                elif role.authority == "producer":
                    self.assertIn(
                        "mechanisms",
                        role.experience_access,
                        f"生产者 {role.role_id} 必须能访问合格机制",
                    )
                    self.assertIn(
                        "preferences",
                        role.experience_access,
                        f"生产者 {role.role_id} 必须能访问偏好信号",
                    )

    def test_get_unknown_role_raises(self) -> None:
        registry = RoleRegistry.default()
        with self.assertRaises(KeyError):
            registry.get("nonexistent-role")


class ScenarioPackTests(unittest.TestCase):
    def test_default_pack_resolves_presales_reading_first(self) -> None:
        """售前阅读优先场景可解析，并返回正确的角色路线。"""
        registry = ScenarioPackRegistry.default()
        pack = registry.resolve(scene="presales", task_type="reading-first")
        self.assertIsInstance(pack, PresalesScenarioPack)
        self.assertEqual(pack.scene, "presales")
        self.assertGreaterEqual(len(pack.production_roles), 5)
        self.assertGreaterEqual(len(pack.review_roles), 5)
        self.assertEqual(
            set(pack.production_roles).intersection(
                {
                    "presales-solution-chief",
                    "presales-content-strategist",
                    "claim-evidence-analyst",
                    "deck-narrative-architect",
                    "slide-copywriter",
                }
            ),
            {"presales-solution-chief"},
        )
        self.assertEqual(
            set(pack.review_roles).intersection(
                {
                    "content-evidence-gate-reviewer",
                    "content-presales-reading-gate-reviewer",
                    "presales-content-reviewer",
                    "content-fact-checker",
                    "argument-logic-reviewer",
                    "audience-decision-reviewer",
                    "reading-experience-reviewer",
                }
            ),
            {
                "content-evidence-gate-reviewer",
                "content-presales-reading-gate-reviewer",
            },
        )
        self.assertEqual(pack.risk_specialist_role_pattern, "presales-risk-specialist/*")

    def test_unknown_scenario_raises(self) -> None:
        registry = ScenarioPackRegistry.default()
        with self.assertRaises(KeyError):
            registry.resolve(scene="unknown", task_type="anything")


if __name__ == "__main__":
    unittest.main()
