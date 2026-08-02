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

        self.assertEqual(__version__, "0.2.0")
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
        self.assertIn("Read isolation-policy.md before any file write", body)


if __name__ == "__main__":
    unittest.main()
