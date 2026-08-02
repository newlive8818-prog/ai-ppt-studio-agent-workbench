from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ai-ppt-studio" / "SKILL.md"


class SkillWorkflowTests(unittest.TestCase):
    def test_skill_routes_pptx_to_codex_presentations(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        self.assertLess(len(body.splitlines()), 220)
        self.assertIn("Codex Presentations", body)
        self.assertIn("Do not build or use a second PPTX editor", body)
        self.assertIn("Image 2", body)
        self.assertIn("G0", body)
        self.assertIn("G4", body)
        self.assertIn("No separate Image 2 privacy gate", body)

    def test_skill_has_focused_workflow_references(self) -> None:
        references = SKILL.parent / "references"
        expected = {
            "content-workflow.md",
            "visual-workflow.md",
            "presentations-handoff.md",
            "review-and-feedback.md",
            "experience-evolution.md",
            "native-workbench.md",
        }
        self.assertTrue(expected.issubset({path.name for path in references.glob("*.md")}))

    def test_skill_governs_native_workbench_agent_loop(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        workbench = (SKILL.parent / "references" / "native-workbench.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("native-workbench.md", body)
        self.assertIn("request_ai_ppt_agent_action", workbench)
        self.assertIn("commit_ai_ppt_artifact", workbench)
        self.assertIn("confirm_ai_ppt_gate", workbench)
        self.assertIn("expectedRevision", workbench)
        self.assertIn("Image 2", workbench)
        self.assertIn("Codex Presentations", workbench)
        self.assertIn("材料空间", workbench)
        self.assertIn("内容蓝图", workbench)
        self.assertIn("视觉设计", workbench)
        self.assertIn("制作与交付", workbench)

    def test_skill_requires_cross_project_experience_recommend_apply_evaluate_loop(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        evolution = (SKILL.parent / "references" / "experience-evolution.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("experience-recommend", body)
        self.assertIn("experience-apply", body)
        self.assertIn("experience-evaluate", body)
        self.assertIn("personal-memory/experience-index.json", evolution)
        self.assertIn("evaluation/applications.jsonl", evolution)
        self.assertIn("candidate -> personal", evolution)
        self.assertIn("personal -> candidate", evolution)
        self.assertIn("experience-rollback", evolution)
        self.assertIn("stable Skill core", evolution)


if __name__ == "__main__":
    unittest.main()
