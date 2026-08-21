from __future__ import annotations

import unittest
import json
import subprocess
import tempfile
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

    def test_plugin_skill_entrypoint_can_run_preflight_from_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            install = base / "install"
            upstream = base / "upstream"
            install.mkdir()
            upstream.mkdir()
            result = subprocess.run(
                [
                    "python3",
                    str(SKILL.parent / "scripts" / "ai_ppt_runtime.py"),
                    "--runtime-root",
                    str(base / "runtime"),
                    "--source-repo-root",
                    str(ROOT),
                    "--install-root",
                    str(install),
                    "--upstream-root",
                    str(upstream),
                    "preflight",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])

    def test_skill_has_focused_workflow_references(self) -> None:
        references = SKILL.parent / "references"
        expected = {
            "content-workflow.md",
            "visual-workflow.md",
            "presentations-handoff.md",
            "review-and-feedback.md",
            "experience-evolution.md",
            "native-workbench.md",
            "release-target-policy.md",
        }
        self.assertTrue(expected.issubset({path.name for path in references.glob("*.md")}))

    def test_skill_and_references_use_only_the_approved_v22_contract(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "artifact://<kind>/<sha256>",
            "macos-powerpoint",
            "ReleaseTargetPolicy",
            "macos-wps",
            "windows-powerpoint",
            "windows-wps",
            "deferred",
            "material-backed",
            "mixed-evidence",
            "proposal-led",
            "PresalesEvidenceBook",
            "CustomerDecisionContext",
            "ProblemSolutionFitMap",
            "ReadingDeckBlueprint",
            "same-type",
            "global",
            "760/1000/1440px",
        ):
            self.assertIn(value, body)
        for obsolete in (
            "artifact://<kind>/vNNNN#sha256=<digest>",
            "proposal-only",
            "get_ai_ppt_sidebar_projection",
            "HOST_SIDEBAR_UNAVAILABLE",
            "five-space",
            "项目总览",
            "材料工作台",
            "内容蓝图空间",
            "视觉设计空间",
            "制作与交付页",
            "full-deck authorization",
            "candidate -> personal",
            "personal -> candidate",
            "stable Skill core",
        ):
            self.assertNotIn(obsolete, body)

    def test_skill_requires_explicit_mission_confirmation_before_content(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "MissionDraft",
            "MissionConfirmation",
            "confirmable",
            "confirm_ai_ppt_mission",
            "materials-provided",
            "no-materials-confirmed",
            "material-backed",
            "mixed-evidence",
            "proposal-led",
            "诊断假设",
            "方案建议",
            "待联合验证",
        ):
            self.assertIn(value, body)
        for obsolete in (
            "MissionBrief",
            "render_ai_ppt_workbench",
            "render_ai_ppt_review",
            "fullscreen/independent",
            "smaller host regions request fullscreen",
            "chat://message/...",
        ):
            self.assertNotIn(obsolete, body)

    def test_skill_routes_confirmation_intent_through_host_native_confirmation(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "OK",
            "确认",
            "采纳",
            "继续",
            "confirmation intent",
            "host-native confirmation",
            "HOST_CONFIRMATION_UNAVAILABLE",
            "HOST_CONFIRMATION_DECLINED",
        ):
            self.assertIn(value, body)
        self.assertIn("never persisted as evidence", body)
        self.assertIn("ordinary conversation", body)
        self.assertIn("never ask for more material", body)
        self.assertIn("never bypass AI PPT Studio", body)

    def test_skill_routes_ui_to_current_chat_and_on_demand_reviews(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        workbench = (SKILL.parent / "references" / "native-workbench.md").read_text(
            encoding="utf-8"
        )
        runtime = (SKILL.parent / "references" / "runtime-workflow.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((body, workbench, runtime))
        for value in (
            "Codex current project conversation",
            "open_or_resume_review_session",
            "Review Bridge",
            "BROWSER_REVIEW_UNAVAILABLE",
            "BROWSER_REVIEW_SAVE_UNAVAILABLE",
            "Codex built-in Browser",
            "AI 正在处理",
            "需要你处理",
            "成果已可查看",
            "任务受阻",
        ):
            self.assertIn(value, combined)
        self.assertIn("ContentReviewPageViewModel", combined)
        self.assertNotIn("read-only evidence layer", combined)

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
        self.assertIn("content-full-deck", workbench)
        self.assertIn("visual-professional", workbench)
        self.assertNotIn("sidebar", workbench.lower())

    def test_skill_requires_same_type_global_experience_and_retrospective(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        evolution = (SKILL.parent / "references" / "experience-evolution.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("recommend_experience", body)
        self.assertIn("record_experience_application", body)
        self.assertIn("summarize_project_experience", body)
        self.assertIn("personal-memory/experience-index.json", evolution)
        self.assertIn("personal-memory/same-type", evolution)
        self.assertIn("personal-memory/global", evolution)
        self.assertIn("same-type", evolution)
        self.assertIn("global", evolution)
        self.assertIn("ProjectExperienceRetrospective", evolution)
        self.assertNotIn("candidate experience", evolution)
        self.assertNotIn("personal experience", evolution)


if __name__ == "__main__":
    unittest.main()
