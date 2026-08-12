from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V16SupportScriptContractTests(unittest.TestCase):
    def test_mcp_probe_uses_only_data_and_capability_gap_contracts(self) -> None:
        body = (ROOT / "scripts" / "probe-mcp.mjs").read_text(encoding="utf-8")
        for value in (
            "get_ai_ppt_project_snapshot",
            "get_ai_ppt_sidebar_projection",
            "open_ai_ppt_browser_review",
            "HOST_SIDEBAR_UNAVAILABLE",
            "BROWSER_REVIEW_UNAVAILABLE",
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
        ):
            self.assertNotIn(obsolete, body)

    def test_local_preview_scripts_disclaim_real_host_evidence(self) -> None:
        for name in ("create-widget-preview.mjs", "create-review-preview.mjs"):
            body = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("requestedDisplayMode", body)
            self.assertIn('evidenceScope: "local-development-preview"', body)
            self.assertIn("proofEligible: false", body)
            self.assertIn("realHostEvidence: false", body)


if __name__ == "__main__":
    unittest.main()
