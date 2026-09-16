from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class PackageShapeTests(unittest.TestCase):
    def test_python_package_and_skill_metadata_exist(self) -> None:
        from ai_ppt_studio import __version__

        self.assertEqual(__version__, "0.4.0")
        self.assertIn(
            'version = "0.4.0"',
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        skill = ROOT / "skills" / "ai-ppt-studio"
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertTrue((skill / "agents" / "openai.yaml").is_file())
        self.assertTrue((skill / "references" / "isolation-policy.md").is_file())
        self.assertTrue((skill / "references" / "runtime-workflow.md").is_file())
        self.assertTrue((skill / "assets" / "project-schema.json").is_file())

    def test_skill_is_thin_and_contains_hard_safety_language(self) -> None:
        body = (ROOT / "skills" / "ai-ppt-studio" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(body.splitlines()), 180)
        self.assertIn("Never write into the current working directory", body)
        self.assertIn("managed runtime root", body)
        self.assertIn("Read `references/isolation-policy.md` before any write", body)

    def test_production_tree_has_no_legacy_runtime_contract(self) -> None:
        forbidden = (
            "WorkbenchStore",
            "space_projections",
            "ReviewSurfaceProjector",
            "seed-v15",
            'schema_version": "2.0"',
            "artifact://<kind>/vNNNN#sha256=<digest>",
            "MissionBrief",
            "render_ai_ppt_workbench",
            "render_ai_ppt_review",
            "AI_PPT_WIDGET_URI",
            "AI_PPT_REVIEW_URI",
            "requestedDisplayMode",
            "requestDisplayMode",
            "fullscreen/independent",
            '"fullscreen"',
            '"inline"',
        )
        roots = (
            ROOT / "src",
            ROOT / "mcp",
            ROOT / "scripts",
            ROOT / "skills",
            ROOT / "widget" / "src",
        )
        hits: list[str] = []
        for source_root in roots:
            for path in source_root.rglob("*"):
                if not path.is_file() or path.suffix not in {
                    ".py", ".mjs", ".js", ".ts", ".tsx", ".md"
                }:
                    continue
                relative = path.relative_to(ROOT).as_posix()
                if relative == "src/ai_ppt_studio/adapters/legacy/importer.py":
                    continue
                if ".test." in path.name:
                    continue
                body = path.read_text(encoding="utf-8")
                for token in forbidden:
                    if token in body:
                        hits.append(f"{relative}: {token}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
