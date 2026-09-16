from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_skill_bundle import build_bundle
from scripts.install_skill import install_bundle


class InstallSkillTests(unittest.TestCase):
    def test_install_replaces_only_exact_skill_and_preserves_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = build_bundle(ROOT, base / "bundle")
            unrelated_runtime = base / "runtime"
            unrelated_runtime.mkdir()
            (unrelated_runtime / "keep.txt").write_text("keep", encoding="utf-8")
            target = base / "skills" / "ai-ppt-studio"
            target.mkdir(parents=True)
            (target / "old.txt").write_text("old", encoding="utf-8")
            installed = install_bundle(bundle, target)
            self.assertEqual(installed, target.resolve())
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "runtime" / "VERSION").is_file())
            self.assertFalse((installed / "old.txt").exists())
            self.assertTrue((unrelated_runtime / "keep.txt").is_file())
            self.assertEqual(
                list(target.parent.glob(".ai-ppt-studio.*")), []
            )


if __name__ == "__main__":
    unittest.main()
