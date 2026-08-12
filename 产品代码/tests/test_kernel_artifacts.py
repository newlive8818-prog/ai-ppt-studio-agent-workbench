from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.errors import ArtifactReferenceError
from ai_ppt_studio.kernel.artifacts import ArtifactRepository


class ArtifactRepositoryTests(unittest.TestCase):
    def test_put_is_immutable_deduplicated_and_project_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = ArtifactRepository(root, project_id="project-1")
            first = repo.put("mission-brief", {"goal": "通过方案"})
            second = repo.put("mission-brief", {"goal": "通过方案"})
            self.assertEqual(first, second)
            self.assertEqual(repo.resolve(first)["payload"]["goal"], "通过方案")
            with self.assertRaises(ArtifactReferenceError):
                ArtifactRepository(root, project_id="project-2").resolve(first)

    def test_resolve_rejects_tampered_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = ArtifactRepository(root, project_id="project-1")
            ref = repo.put("mission-brief", {"goal": "通过方案"})
            path = repo.path_for(ref)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["payload"]["goal"] = "已篡改"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ArtifactReferenceError):
                repo.resolve(ref)


if __name__ == "__main__":
    unittest.main()
