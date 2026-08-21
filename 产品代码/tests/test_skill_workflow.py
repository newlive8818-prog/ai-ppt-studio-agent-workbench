from __future__ import annotations

import unittest
import json
import subprocess
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
        result = subprocess.run(
            ["python3", str(SKILL.parent / "scripts" / "ai_ppt_runtime.py"), "preflight"],
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
            "four-target-acceptance.md",
        }
        self.assertTrue(expected.issubset({path.name for path in references.glob("*.md")}))

    def test_skill_and_references_use_the_policy_driven_release_contract(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "artifact://<kind>/<sha256>",
            "ReleaseTargetPolicy",
            "macos-powerpoint",
            "same PPTX SHA-256",
            "maximum-width sidebar",
            "deferred",
            "preflight-only output cannot replace desktop evidence",
            "G4 requires a new final-PPTX macOS PowerPoint record",
        ):
            self.assertIn(value, body)
        self.assertIn("do not claim wps or windows compatibility", body.lower())
        main = SKILL.read_text(encoding="utf-8")
        self.assertIn("release-target G2", main)
        self.assertIn("release-target G4", main)
        self.assertNotIn("four-target G2", main)
        self.assertNotIn("four-target G4", main)
        self.assertNotIn("artifact://<kind>/vNNNN#sha256=<digest>", body)
        self.assertNotIn("Pass G1 after the main direction is selected", body)
        self.assertNotIn("Engineering samples — G2", body)

    def test_skill_requires_explicit_mission_confirmation_before_content(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "MissionDraft",
            "MissionConfirmation",
            "confirmable",
            "confirm_ai_ppt_mission",
            "no-materials-confirmed",
            "material-backed",
            "mixed-evidence",
            "proposal-led",
            "来源事实",
            "材料推断",
            "证据缺口",
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

    def test_user_gate_confirmation_is_single_use_and_version_bound(self) -> None:
        files = [SKILL, *(SKILL.parent / "references").glob("*.md")]
        body = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for value in (
            "one current checkpoint",
            "`MissionConfirmation` never confirms G0, G3, or G4",
            "sourceVersion",
            "challenge",
            "One Agent turn",
            "host-native confirmation",
        ):
            self.assertIn(value, body)
        self.assertIn("locks G1–G4", body)
        self.assertIn("removes downstream current heads", body)

    def test_current_content_workflow_matches_the_v21_sidebar_review_contract(self) -> None:
        current_files = [
            SKILL,
            SKILL.parent / "references" / "content-workflow.md",
            SKILL.parent / "references" / "native-workbench.md",
            SKILL.parent / "references" / "review-and-feedback.md",
            SKILL.parent / "references" / "runtime-workflow.md",
        ]
        body = "\n".join(
            path.read_text(encoding="utf-8") for path in current_files
        )
        for value in (
            "single `售前方案总师`",
            "`事实与证据硬门`",
            "`售前阅读与客户立场硬门`",
            "neutral titles",
            "maximum-width sidebar",
            "silent page save",
            "save_content_page_decision",
            "submit_content_review_batch",
            "immutable review batch",
            "deck-level revision plan",
            "confirm_content_batch_revision_plan",
            "full re-review of every new source version",
            "current source is confirmed at G0",
            "open_content_evidence_browser",
            "read-only evidence",
            "G3 visual",
            "open_ai_ppt_browser_review",
        ):
            self.assertIn(value, body)
        for obsolete_current_instruction in (
            "desired judgment/action",
            "Run exactly the required five independent roles",
            "Keep both review types in the 64px Header",
            "open_ai_ppt_browser_review` opens content/visual professional review",
            "Content actions require a current `MissionConfirmation` and Python-approved identity first, then build strategy",
        ):
            self.assertNotIn(obsolete_current_instruction, body)

    def test_skill_routes_ui_only_to_sidebar_and_codex_browser(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        workbench = (SKILL.parent / "references" / "native-workbench.md").read_text(
            encoding="utf-8"
        )
        runtime = (SKILL.parent / "references" / "runtime-workflow.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((body, workbench, runtime))
        for value in (
            "get_ai_ppt_sidebar_projection",
            "open_ai_ppt_browser_review",
            "HOST_SIDEBAR_UNAVAILABLE",
            "BROWSER_REVIEW_UNAVAILABLE",
            "BROWSER_REVIEW_SAVE_UNAVAILABLE",
            "Codex built-in Browser",
            "review-session-ready",
            "open-scoped-url",
            "Agent",
        ):
            self.assertIn(value, combined)
        self.assertIn("never renders a Widget in chat", combined)
        self.assertIn("do not claim", combined.lower())
        self.assertIn("stdio", combined)

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
        self.assertIn("项目总览", workbench)
        self.assertIn("材料工作台", workbench)
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
        self.assertIn("`same-type`", evolution)
        self.assertIn("`global`", evolution)
        self.assertIn("Global promotion", evolution)
        self.assertIn("Rollback creates a new latest version", evolution)
        self.assertIn("Legacy candidate/personal records", evolution)


if __name__ == "__main__":
    unittest.main()
