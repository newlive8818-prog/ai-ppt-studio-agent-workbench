from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V16SupportScriptContractTests(unittest.TestCase):
    def test_mcp_probe_uses_only_data_and_capability_gap_contracts(self) -> None:
        body = (ROOT / "scripts" / "probe-mcp.mjs").read_text(encoding="utf-8")
        for value in (
            "PUBLIC_TOOL_CATALOG",
            "get_ai_ppt_project_snapshot",
            "open_or_resume_review_session",
            "get_content_review_projection",
            "get_visual_review_projection",
            "BROWSER_REVIEW_UNAVAILABLE",
            "host_notification",
            "ai_receipt",
        ):
            self.assertIn(value, body)
        for obsolete in (
            "render_ai_ppt_workbench",
            "render_ai_ppt_review",
            "readResource",
            "ui://ai-ppt-studio",
            "openai/outputTemplate",
            "requestedDisplayMode",
            "AI_PPT_PROBE_WRITE",
            "get_ai_ppt_sidebar_projection",
            "HOST_SIDEBAR_UNAVAILABLE",
        ):
            self.assertNotIn(obsolete, body)

    def test_local_preview_scripts_disclaim_real_host_evidence(self) -> None:
        self.assertFalse((ROOT / "scripts" / "create-widget-preview.mjs").exists())
        body = (ROOT / "scripts" / "create-review-preview.mjs").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("requestedDisplayMode", body)
        self.assertIn('evidenceScope: "local-development-preview"', body)
        self.assertIn("proofEligible: false", body)
        self.assertIn("realHostEvidence: false", body)
        self.assertIn('import { loadProjectionPreviewAssets } from "./review-preview-assets.mjs"', body)
        self.assertIn("loadProjectionPreviewAssets({ review: payload.review, projectRoot })", body)
        self.assertNotIn("function collectAssetRefs", body)
        assets = (ROOT / "scripts" / "review-preview-assets.mjs").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'import { collectProjectionAssetRefs } from "../mcp/review-bridge.mjs"',
            assets,
        )
        self.assertIn("collectProjectionAssetRefs(review)", assets)
        self.assertNotIn("catch", assets)

    def test_ui_acceptance_has_only_current_review_surfaces(self) -> None:
        self.assertFalse((ROOT / "scripts" / "run-v16-ui-acceptance.mjs").exists())
        body = (ROOT / "scripts" / "run-v22-ui-acceptance.mjs").read_text(
            encoding="utf-8"
        )
        for value in (
            "content-review",
            "visual-review",
            "LOCAL_PREVIEW_EVIDENCE",
            "previewEvidence: { ...LOCAL_PREVIEW_EVIDENCE }",
            "rawScreenshot",
            "expandedEvidenceScreenshot",
            "disclaimer: LOCAL_PREVIEW_DISCLAIMER",
            "AI_PPT_PREVIEW_OUTPUT_DIR: runDirectory",
        ):
            self.assertIn(value, body)
        self.assertIn('surfaces: ["content-review", "visual-review"]', body)
        self.assertNotIn("read-only-evidence-layer", body)
        self.assertNotIn("AI_PPT_PREVIEW_OUTPUT_DIR: outputDirectory", body)
        self.assertNotIn("os.homedir()", body)
        evidence = (ROOT / "scripts" / "v22-ui-acceptance-evidence.mjs").read_text(
            encoding="utf-8"
        )
        for value in (
            'evidenceScope: "local-development-preview"',
            "proofEligible: false",
            "realHostEvidence: false",
        ):
            self.assertIn(value, evidence)
        self.assertIn("Not G3 or user acceptance proof", evidence)
        self.assertNotIn("Not G3 or user acceptance proof", body)
        for obsolete in (
            "compact-app-shell",
            "stable-navigation",
            "four desktop targets",
            "create-widget-preview.mjs",
        ):
            self.assertNotIn(obsolete, body)


if __name__ == "__main__":
    unittest.main()
