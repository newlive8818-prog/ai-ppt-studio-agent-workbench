from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ai_ppt_studio"
WIDGET = ROOT / "widget" / "src"


class V22SourceShapeTests(unittest.TestCase):
    def test_retired_python_write_modules_are_absent_and_not_imported(self) -> None:
        retired = (
            SRC / "application" / "workspace_projection.py",
            SRC / "application" / "framework_discussion_service.py",
            SRC / "application" / "content_action_policy.py",
            SRC / "application" / "content_service.py",
            SRC / "application" / "content_review_service.py",
            SRC / "domains" / "content" / "framework.py",
            SRC / "domains" / "content" / "review_contracts.py",
        )
        self.assertEqual([path for path in retired if path.exists()], [])

        formal = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SRC / "application").rglob("*.py")
            if "adapters/legacy" not in path.as_posix()
        )
        for forbidden in (
            "application.content_service",
            "application.content_action_policy",
            "framework_discussion_service",
            "domains.content.framework",
            "content/framework-confirmation",
            "content/full-deck-expansion-authorization",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, formal)
        review_sessions = (
            SRC / "application" / "review_session_service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"content-blueprint"', review_sessions)
        content_contracts = (SRC / "domains" / "content" / "contracts.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "proposal-only",
            "def validate_content_stage(",
            "def validate_content_review(",
            "def aggregate_content_reviews(",
            "contentIdentityMode",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, formal + content_contracts)

    def test_formal_bridge_has_no_sidebar_framework_expansion_or_generic_write(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                ROOT / "mcp" / "tool-catalog.mjs",
                ROOT / "mcp" / "server.mjs",
                ROOT / "mcp" / "tools" / "project-tools.mjs",
                SRC / "application" / "v16_bridge.py",
            )
        )
        for forbidden in (
            "get_ai_ppt_sidebar_projection",
            "framework-confirmation",
            "full-deck-expansion",
            "awaiting-full-deck-authorization",
            "build-presales-strategy",
            "build-claim-evidence-map",
            "build-deck-argument-map",
            "build-slide-draft-set",
            "curate-experience",
            "evaluate-experience",
            '"operation" == "commit-artifact"',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, sources)

    def test_widget_contains_only_on_demand_review_surfaces(self) -> None:
        retired = (
            "App.tsx",
            "ProfessionalReviewApp.tsx",
            "components/CompactWorkspace.tsx",
            "components/StableNavigation.tsx",
            "components/GateStrip.tsx",
            "components/SlideContactSheet.tsx",
            "components/SpaceConclusion.tsx",
            "lib/sidebar-host-client.ts",
            "styles.css",
            "types.ts",
        )
        self.assertEqual(
            [name for name in retired if (WIDGET / name).exists()],
            [],
        )
        main = (WIDGET / "main.tsx").read_text(encoding="utf-8")
        self.assertIn("createBrowserReviewClient", main)
        for forbidden in (
            "createSidebarHostClient",
            "CompactWorkspace",
            "StableNavigation",
            "ProfessionalReviewApp",
            "initialSpace",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, main)


if __name__ == "__main__":
    unittest.main()
