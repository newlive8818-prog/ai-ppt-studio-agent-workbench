from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.kernel.references import ArtifactReference
from tests.v16_visual_fixtures import confirmed_g0, valid_visual_brief


class V22VisualLineageTests(unittest.TestCase):
    def test_visual_brief_binds_current_reading_blueprint_after_v22_g0(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            content, revision, blueprint_ref = confirmed_g0(Path(folder))
            self.assertEqual(
                ArtifactReference.parse(blueprint_ref).kind,
                "reading-deck-blueprint",
            )
            brief_ref = VisualService(content.kernel).register_visual_brief(
                "visual-brief-v22",
                revision,
                valid_visual_brief(blueprint_ref),
            )
            brief = content.kernel.artifacts.resolve(
                ArtifactReference.parse(brief_ref)
            )["payload"]
            self.assertEqual(brief["reading_blueprint_ref"], blueprint_ref)
            self.assertNotIn("content_blueprint_ref", brief)


if __name__ == "__main__":
    unittest.main()
