from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.kernel.references import ArtifactReference


class ArtifactReferenceTests(unittest.TestCase):
    def test_round_trips_formal_reference(self) -> None:
        value = f"artifact://content-acceptance/{'a' * 64}"
        parsed = ArtifactReference.parse(value)
        self.assertEqual(parsed.kind, "content-acceptance")
        self.assertEqual(parsed.sha256, "a" * 64)
        self.assertEqual(str(parsed), value)

    def test_rejects_role_names_paths_versions_and_uppercase_hashes(self) -> None:
        invalid = (
            "content-review-agent",
            "artifacts/content.json",
            f"artifact://content-acceptance/v0001#{'a' * 64}",
            f"artifact://content-acceptance/{'A' * 64}",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(
                ArtifactReferenceError
            ):
                ArtifactReference.parse(value)


if __name__ == "__main__":
    unittest.main()
